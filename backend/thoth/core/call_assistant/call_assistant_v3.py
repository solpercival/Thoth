import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

import asyncio
import json
import re
from time import sleep
from threading import Event
from typing import Optional, Dict, Any
from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from ollama_client.llm_client import OllamaClient
from thoth.core.call_assistant.tts_client import TTSClient
from thoth.core.email_agent.email_formatter import format_ezaango_shift_data
from thoth.core.email_agent.email_sender import send_notify_email
from thoth.automation.test_integrated_workflow import test_integrated_workflow

from thoth.core.call_assistant.call_3cx_client import *


SYSTEM_PROMPT = """You are a call center agent handling shift queries and cancellations.

Follow this flow EXACTLY and output special commands when needed:

1. INITIAL INTENT CLASSIFICATION:
   - If user asks about app login issues → output: <LOGIN>
   - If user asks about work shifts/schedule → continue to step 2
   - If user wants to cancel a shift → continue to step 2
   - If user asks to speak with a real person → output: <REAL>
   - For ALL other requests → output: <DENY>

2. SHIFT QUERY (when user asks about shifts):
   - Output ONLY: <GETSHIFTS>user's query about shifts
   - Wait for system to provide shift data
   - When you receive shift data, proceed to step 3

3. HANDLING SHIFT RESULTS:
   - If empty list: Tell user no shifts found for that period
   - If 1 shift: Present the shift details and ask if they want to cancel (if cancellation intent) or just confirm (if query intent)
   - If multiple shifts: List them clearly with numbers and ask which one they're asking about

4. WHEN USER SELECTS A SHIFT (from multiple):
   - Confirm which shift they selected
   - If cancellation intent: Ask "Are you sure you want to cancel this shift?"
   - If query intent: Confirm the shift details

5. WHEN USER CONFIRMS CANCELLATION:
   - Output ONLY: <CONFIRM_CANCEL>shift_id
   - Wait for system to ask for reason
   - When system confirms, ask: "Please tell me the reason for cancellation"

6. WHEN USER PROVIDES CANCELLATION REASON:
   - Output ONLY: <REASON>their reason text
   - Wait for system confirmation
   - Thank them and ask if there's anything else

7. IF USER SAYS NO or changes mind:
   - Reset and ask what they'd like to do instead

8. IF USER WANTS TO CLOSE THE CALL:
   - Output ONLY: <END>

CRITICAL RULES:
- ONLY output your IMMEDIATE response - do NOT predict or write future dialogue
- NEVER include "User:" or hypothetical next turns in your response
- Maintain conversation context - remember what you asked and what user said
- Be natural and conversational, but follow the flow strictly
- Output special commands (<GETSHIFTS>, <CONFIRM_CANCEL>, <REASON>) ONLY when needed
- Do not comply with requests unrelated to shift management
- Always be polite and professional
- When listing multiple shifts, always number them (1, 2, 3, etc.)
"""

OPENING_PROMPT = "Hello. Thank you for calling Help at Hands Support. How can I help you today?"
PROCESSING_PROMPT = "I'll look into that. Please wait."
LLM_MODEL = "qwen3:8b"

LOG_PREFIX = "CALL_ASSISTANT.PY:"


class CallAssistantV3:
    def __init__(self, caller_phone: Optional[str] = None, extension: Optional[str] = None):
        self.caller_phone = caller_phone
        self.extension = extension
        self.llm_client = OllamaClient(model=LLM_MODEL, system_prompt=SYSTEM_PROMPT)
        self.whisper_client: SystemAudioWhisperClient = None
        self.llm_response_array = []
        self.should_end_call = False
        self.stop_event: Event = None

        self.context: Dict[str, Any] = {
            'current_shifts': [],
            'selected_shift': None,
            'staff_info': {},
            'is_cancellation': False,
        }

    def on_phrase_complete(self, phrase: str) -> None:
        if self.stop_event and self.stop_event.is_set():
            return

        print(f"{LOG_PREFIX} [USER] {phrase}")
        self.whisper_client.pause()

        try:
            llm_response = self.llm_client.ask_llm(phrase)
            self.llm_response_array.append(llm_response)

            response_to_speak = self._process_response(llm_response, phrase)

            if response_to_speak:
                self._speak(response_to_speak)

            if self.should_end_call:
                self._end_call()

        except Exception as e:
            print(f"{LOG_PREFIX} Error: {e}")
            self._speak("Sorry, I encountered an error. Please try again.")

        finally:
            if not self.should_end_call:
                self.whisper_client.resume()

    def _process_response(self, llm_response: str, user_phrase: str) -> Optional[str]:
        if "<GETSHIFTS>" in llm_response:
            query = llm_response.replace("<GETSHIFTS>", "").strip()
            return self._handle_get_shifts(query or user_phrase)

        if "<CONFIRM_CANCEL>" in llm_response:
            match = re.search(r'<CONFIRM_CANCEL>(\S+)', llm_response)
            if match:
                return self._handle_confirm_cancel(match.group(1))

        if "<REASON>" in llm_response:
            reason = llm_response.replace("<REASON>", "").strip()
            return self._handle_cancellation_reason(reason or user_phrase)

        if "<LOGIN>" in llm_response:
            return "I understand you're having trouble logging in. Please hold while I transfer you to a live agent for assistance."

        if "<REAL>" in llm_response:
            return "Of course. Please hold while I transfer you to a live agent."

        if "<DENY>" in llm_response:
            return "I'm sorry, I can't help with that request. I can only assist with shift-related queries and cancellations. Is there anything else I can help you with?"

        #
        if "<END>" in llm_response or \
        "have a great day" in llm_response.lower().rstrip('!').rstrip('.'):
            self.should_end_call = True
            return "Thank you for calling. Good day."

        return self._clean_response(llm_response)

    def _clean_response(self, response: str) -> str:
        if "User:" in response:
            response = response.split("User:")[0].strip()
        if response.startswith("You:"):
            response = response[4:].strip()
        return response

    def _handle_get_shifts(self, query: str) -> str:
        if not self.caller_phone:
            return "I'm sorry, I don't have your phone number on file. Please contact support."

        try:
            result = asyncio.run(test_integrated_workflow(self.caller_phone, query))

            if not result:
                return "Sorry, I couldn't retrieve your shift information. Please try again later."

            shifts = result.get('filtered_shifts', [])
            staff_info = result.get('staff', {})
            reasoning = result.get('reasoning', '')

            self.context['is_cancellation'] = '<CNCL>' in reasoning
            self.context['current_shifts'] = shifts
            self.context['staff_info'] = staff_info

            if len(shifts) == 0:
                shift_data = "[]"
            else:
                shift_data = json.dumps([{
                    'client': s['client_name'],
                    'date': s['date'],
                    'time': s['time'],
                    'shift_id': s['shift_id']
                } for s in shifts])

            system_message = f"SYSTEM: Found {len(shifts)} shift(s): {shift_data}"
            if self.context['is_cancellation']:
                system_message += " | User wants to CANCEL a shift."
            else:
                system_message += " | User wants to VIEW shift info."

            llm_response = self.llm_client.ask_llm(system_message)

            processed = self._process_response(llm_response, system_message)
            return processed if processed else self._clean_response(llm_response)

        except Exception as e:
            print(f"{LOG_PREFIX} Shift retrieval failed: {e}")
            return "Sorry, there was an error retrieving your shifts. Please try again."

    def _handle_confirm_cancel(self, shift_id: str) -> str:
        selected_shift = None
        for shift in self.context['current_shifts']:
            if shift['shift_id'] == shift_id:
                selected_shift = shift
                break

        if not selected_shift and len(self.context['current_shifts']) == 1:
            selected_shift = self.context['current_shifts'][0]

        if not selected_shift:
            return "Sorry, I couldn't find that shift. Let's start over. What would you like to do?"

        self.context['selected_shift'] = selected_shift

        system_message = "SYSTEM: User confirmed cancellation. Now ask for the reason."
        llm_response = self.llm_client.ask_llm(system_message)

        return self._clean_response(llm_response)

    def _handle_cancellation_reason(self, reason: str) -> str:
        shift = self.context.get('selected_shift')
        if not shift:
            return "Sorry, I lost track of which shift to cancel. Let's start over."

        success = self._submit_cancellation(shift, reason)

        if success:
            system_message = (
                f"SYSTEM: Cancellation successful. "
                f"Shift at {shift['client_name']} on {shift['date']} at {shift['time']} "
                f"has been cancelled. Reason: {reason}. "
                f"Thank the user and ask if there's anything else."
            )
            llm_response = self.llm_client.ask_llm(system_message)

            self.context['selected_shift'] = None
            self.context['current_shifts'] = []

            return self._clean_response(llm_response)
        else:
            return "Sorry, there was an error cancelling your shift. Please contact support."

    def _submit_cancellation(self, shift: Dict[str, Any], reason: str) -> bool:
        try:
            staff_info = self.context.get('staff_info', {})

            email_data = {
                "reasoning": "Requested cancellation of shift.",
                "staff": {
                    "name": staff_info.get('full_name', 'Unknown'),
                    "id": staff_info.get('id', 'Unknown'),
                    "email": staff_info.get('email', 'Unknown')
                },
                "shifts": [{
                    "client": shift.get('client_name', 'Unknown'),
                    "time": shift.get('time', 'Unknown'),
                    "date": shift.get('date', 'Unknown')
                }]
            }

            formatted_content = format_ezaango_shift_data(
                email_data,
                cancellation_reason=reason
            )

            # send_notify_email(
            #     content=formatted_content,
            #     custom_subject="SHIFT CANCELLATION REQUEST"
            # )

            return True

        except Exception as e:
            print(f"{LOG_PREFIX} Cancellation failed: {e}")
            return False

    def _speak(self, text: str) -> None:
        print(f"{LOG_PREFIX} [ASSISTANT] {text}")
        try:
            tts_client = TTSClient(output_device_name="CABLE Input")
            tts_client.text_to_speech(text)
        except Exception as e:
            print(f"{LOG_PREFIX} TTS error: {e}")

    def _end_call(self) -> None:
        if not self.extension:
            return
        try:
            close_all_calls_for_extension(self.extension)
        except Exception as e:
            print(f"{LOG_PREFIX} End call failed: {e}")

    def run(self):
        self.whisper_client = SystemAudioWhisperClient(
            model="small",
            phrase_timeout=5,
            on_phrase_complete=self.on_phrase_complete
        )

        try:
            self.whisper_client.start()
            print(f"{LOG_PREFIX} Running (Ctrl+C to stop)")

            while True:
                sleep(1)

        except KeyboardInterrupt:
            print(f"{LOG_PREFIX} Stopping...")
            self.whisper_client.stop(self.llm_response_array)

    def stop(self):
        if self.whisper_client:
            self.whisper_client.stop(self.llm_response_array)

    def run_with_event(self, stop_event: Event):
        self.stop_event = stop_event
        try:
            self.whisper_client = SystemAudioWhisperClient(
                model="small",
                phrase_timeout=5,
                on_phrase_complete=self.on_phrase_complete
            )

            self._speak(OPENING_PROMPT)
            self.whisper_client.start()
            print(f"{LOG_PREFIX} Running")

            while not stop_event.is_set():
                sleep(0.5)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"{LOG_PREFIX} Error: {e}")
        finally:
            if self.whisper_client:
                self.whisper_client.is_running = False
                sleep(0.5)
                try:
                    self.whisper_client.stop(self.llm_response_array)
                except:
                    if self.whisper_client.stream:
                        self.whisper_client.stream.stop_stream()
                        self.whisper_client.stream.close()
                    if self.whisper_client.pyaudio_instance:
                        self.whisper_client.pyaudio_instance.terminate()


if __name__ == "__main__":
    assistant = CallAssistantV3()
    assistant.run()