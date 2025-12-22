import sys
from pathlib import Path

# Add project root to Python path
# Files are at: Thoth/thoth/backend/core/call_assistant/
# Need to add both Thoth/ (for whisper/, ollama/) and Thoth/thoth/ (for backend/)
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
thoth_root = project_root / "thoth"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(thoth_root))

import asyncio
import json
import re
from time import sleep
from threading import Event
from typing import Optional, Dict, Any
from whisper.system_audio_whisper_client import SystemAudioWhisperClient
from ollama.llm_client import OllamaClient
from backend.core.call_assistant.tts_client import TTSClient
from backend.core.email_agent.email_formatter import format_ezaango_shift_data
from backend.core.email_agent.email_sender import send_notify_email
from backend.automation.test_integrated_workflow import test_integrated_workflow


# Comprehensive system prompt that defines the entire conversation flow
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

CRITICAL RULES:
- ONLY output your IMMEDIATE response - do NOT predict or write future dialogue
- NEVER include "User:" or hypothetical next turns in your response
- Maintain conversation context - remember what you asked and what user said
- Be natural and conversational, but follow the flow strictly
- Output special commands (<GETSHIFTS>, <CONFIRM_CANCEL>, <REASON>) ONLY when needed
- Do not comply with requests unrelated to shift management
- Always be polite and professional
- When listing multiple shifts, always number them (1, 2, 3, etc.)

Example Interactions (each is a separate turn):

Scenario 1:
User: "I want to cancel my shift tomorrow"
Your response: <GETSHIFTS>cancel shift tomorrow

Scenario 2:
User: "What shifts do I have this week?"
Your response: <GETSHIFTS>shifts this week

Scenario 3:
User: "The second one"
Your response: You selected the shift at [client] on [date] at [time]. Are you sure you want to cancel this shift?

Scenario 4:
User: "Yes"
Your response: <CONFIRM_CANCEL>shift_123

Scenario 5:
User: "I'm feeling sick"
Your response: <REASON>I'm feeling sick
"""

LLM_MODEL = "llama3.1:8b"

class CallAssistantV3:
    """
    Version 3 of CallAssistant - Simplified LLM-driven conversation flow.

    Key improvements over V2:
    - No explicit state machine - LLM manages conversation flow
    - Single comprehensive system prompt
    - Message history maintains context
    - Action tags trigger system operations
    - Much simpler codebase (~250 lines vs V2's ~600)
    """

    def __init__(self, caller_phone: Optional[str] = None):
        self.caller_phone = caller_phone
        self.llm_client = OllamaClient(model=LLM_MODEL, system_prompt=SYSTEM_PROMPT)
        self.whisper_client: SystemAudioWhisperClient = None
        self.llm_response_array = []

        # Context for tracking current operation
        self.context: Dict[str, Any] = {
            'current_shifts': [],      # Shifts from last query
            'selected_shift': None,    # Currently selected shift
            'staff_info': {},          # Staff information
            'is_cancellation': False,  # Whether current intent is cancellation
        }

    def on_phrase_complete(self, phrase: str) -> None:
        """
        Called when a phrase is completed by Whisper.

        Args:
            phrase: Transcribed user speech
        """
        #TODO: Play TTS saying "Just a minute", "Let me work on that for abit", "Hold on a sec", etc


        print(f"\n{'='*50}")
        print(f"[USER SAID] {phrase}")
        print(f"{'='*50}")

        if self.caller_phone:
            print(f"[CALLER] {self.caller_phone}")

        # Pause audio processing while we handle the response
        self.whisper_client.pause()

        try:
            # Get LLM response
            llm_response = self.llm_client.ask_llm(phrase)
            print(f"\n[LLM RESPONSE]\n{llm_response}\n")
            self.llm_response_array.append(llm_response)

            # Check for action tags and execute them
            response_to_speak = self._process_response(llm_response, phrase)

            # Speak the response (if any)
            if response_to_speak:
                self._speak(response_to_speak)

        except Exception as e:
            print(f"[ERROR] Failed to process phrase: {e}")
            import traceback
            traceback.print_exc()
            self._speak("Sorry, I encountered an error. Please try again.")

        finally:
            # Resume audio processing
            self.whisper_client.resume()

    def _process_response(self, llm_response: str, user_phrase: str) -> Optional[str]:
        """
        Process LLM response, execute action tags, and return text to speak.

        Args:
            llm_response: Response from LLM (may contain action tags)
            user_phrase: Original user input

        Returns:
            Text to speak to user (or None if action tag was processed)
        """
        # Check for action tags

        # 1. <GETSHIFTS> - Query shifts from backend
        if "<GETSHIFTS>" in llm_response:
            query = llm_response.replace("<GETSHIFTS>", "").strip()
            return self._handle_get_shifts(query or user_phrase)

        # 2. <CONFIRM_CANCEL> - User confirmed they want to cancel
        if "<CONFIRM_CANCEL>" in llm_response:
            match = re.search(r'<CONFIRM_CANCEL>(\S+)', llm_response)
            if match:
                shift_id = match.group(1)
                return self._handle_confirm_cancel(shift_id)

        # 3. <REASON> - User provided cancellation reason
        if "<REASON>" in llm_response:
            reason = llm_response.replace("<REASON>", "").strip()
            return self._handle_cancellation_reason(reason or user_phrase)

        # 4. <LOGIN> - Transfer to support
        if "<LOGIN>" in llm_response:
            return "I understand you're having trouble logging in. Please hold while I transfer you to a live agent for assistance."

        # 5. <REAL> - Transfer to real agent
        if "<REAL>" in llm_response:
            return "Of course. Please hold while I transfer you to a live agent."

        # 6. <DENY> - Cannot help with request
        if "<DENY>" in llm_response:
            return "I'm sorry, I can't help with that request. I can only assist with shift-related queries and cancellations. Is there anything else I can help you with?"

        # No action tag - clean and return the response for TTS
        return self._clean_response(llm_response)

    def _clean_response(self, response: str) -> str:
        """
        Clean LLM response by removing any hypothetical future dialogue.

        Args:
            response: Raw LLM response

        Returns:
            Cleaned response with only immediate dialogue
        """
        # Split on "User:" to remove any predicted future turns
        if "User:" in response:
            response = response.split("User:")[0].strip()

        # Also check for variations like "You:" at the start (shouldn't be there)
        if response.startswith("You:"):
            response = response[4:].strip()

        return response

    def _handle_get_shifts(self, query: str) -> str:
        """
        Get shifts from backend and inject into conversation.

        Args:
            query: User's shift query

        Returns:
            Text to speak to user
        """
        print(f"[ACTION] Getting shifts for query: {query}")

        if not self.caller_phone:
            return "I'm sorry, I don't have your phone number on file. Please contact support."

        # Call integrated workflow
        try:
            result = asyncio.run(test_integrated_workflow(self.caller_phone, query))

            if not result:
                return "Sorry, I couldn't retrieve your shift information. Please try again later."

            # Extract data
            shifts = result.get('filtered_shifts', [])
            staff_info = result.get('staff', {})
            reasoning = result.get('reasoning', '')

            # Determine if this is a cancellation intent
            self.context['is_cancellation'] = '<CNCL>' in reasoning
            self.context['current_shifts'] = shifts
            self.context['staff_info'] = staff_info

            print(f"[SHIFTS FOUND] {len(shifts)} shift(s)")
            print(f"[INTENT] {'Cancellation' if self.context['is_cancellation'] else 'Query'}")

            # Format shift data for LLM
            if len(shifts) == 0:
                shift_data = "[]"
            else:
                shift_data = json.dumps([{
                    'client': s['client_name'],
                    'date': s['date'],
                    'time': s['time'],
                    'shift_id': s['shift_id']
                } for s in shifts])

            # Inject shift data into conversation
            system_message = f"SYSTEM: Found {len(shifts)} shift(s): {shift_data}"
            if self.context['is_cancellation']:
                system_message += " | User wants to CANCEL a shift."
            else:
                system_message += " | User wants to VIEW shift info."

            # Send to LLM to process and generate natural response
            llm_response = self.llm_client.ask_llm(system_message)
            print(f"\n[LLM PROCESSED SHIFTS]\n{llm_response}\n")

            # Check if LLM response has more action tags
            processed = self._process_response(llm_response, system_message)
            return processed if processed else self._clean_response(llm_response)

        except Exception as e:
            print(f"[ERROR] Failed to get shifts: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, there was an error retrieving your shifts. Please try again."

    def _handle_confirm_cancel(self, shift_id: str) -> str:
        """
        User confirmed cancellation. Find the shift and prepare for reason collection.

        Args:
            shift_id: ID of shift to cancel

        Returns:
            Text to speak to user
        """
        print(f"[ACTION] Confirmed cancellation for shift: {shift_id}")

        # Find the shift in current context
        selected_shift = None
        for shift in self.context['current_shifts']:
            if shift['shift_id'] == shift_id:
                selected_shift = shift
                break

        if not selected_shift:
            # Try finding by matching shift details in conversation
            # For simplicity, just use the first/only shift if available
            if len(self.context['current_shifts']) == 1:
                selected_shift = self.context['current_shifts'][0]

        if not selected_shift:
            return "Sorry, I couldn't find that shift. Let's start over. What would you like to do?"

        self.context['selected_shift'] = selected_shift

        # Inject system message to ask for reason
        system_message = "SYSTEM: User confirmed cancellation. Now ask for the reason."
        llm_response = self.llm_client.ask_llm(system_message)

        return self._clean_response(llm_response)

    def _handle_cancellation_reason(self, reason: str) -> str:
        """
        User provided cancellation reason. Submit the cancellation.

        Args:
            reason: Cancellation reason

        Returns:
            Text to speak to user
        """
        print(f"[ACTION] Cancellation reason: {reason}")

        shift = self.context.get('selected_shift')
        if not shift:
            return "Sorry, I lost track of which shift to cancel. Let's start over."

        # Submit cancellation
        success = self._submit_cancellation(shift, reason)

        if success:
            # Inject confirmation into conversation
            system_message = (
                f"SYSTEM: Cancellation successful. "
                f"Shift at {shift['client_name']} on {shift['date']} at {shift['time']} "
                f"has been cancelled. Reason: {reason}. "
                f"Thank the user and ask if there's anything else."
            )
            llm_response = self.llm_client.ask_llm(system_message)

            # Clear context
            self.context['selected_shift'] = None
            self.context['current_shifts'] = []

            return self._clean_response(llm_response)
        else:
            return "Sorry, there was an error cancelling your shift. Please contact support."

    def _submit_cancellation(self, shift: Dict[str, Any], reason: str) -> bool:
        """
        Submit cancellation to backend and send notification email.

        Args:
            shift: Shift data
            reason: Cancellation reason

        Returns:
            True if successful, False otherwise
        """
        print(f"[SUBMITTING] Cancelling shift {shift.get('shift_id')}")

        try:
            staff_info = self.context.get('staff_info', {})

            # Prepare email data
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

            # Format and send email
            formatted_content = format_ezaango_shift_data(
                email_data,
                cancellation_reason=reason
            )

            #send_notify_email(
                #content=formatted_content,
                #custom_subject="SHIFT CANCELLATION REQUEST"
            #)

            print(f"[SUCCESS] Cancellation notification sent")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to submit cancellation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _speak(self, text: str) -> None:
        """
        Convert text to speech and play through virtual audio cable.

        Args:
            text: Text to speak
        """
        print(f"\n[SPEAKING] {text}\n")
        try:
            tts_client = TTSClient(output_device_name="CABLE Input")
            tts_client.text_to_speech(text)
        except Exception as e:
            print(f"[TTS ERROR] {e}")

    def run(self):
        """Start the voice assistant"""
        self.whisper_client = SystemAudioWhisperClient(
            model="base",
            phrase_timeout=5,
            on_phrase_complete=self.on_phrase_complete
        )

        try:
            self.whisper_client.start()
            print("\n" + "="*50)
            print("Voice Assistant V3 running")
            print("Simplified LLM-driven conversation flow")
            print("Press Ctrl+C to stop")
            print("="*50 + "\n")

            while True:
                sleep(1)

        except KeyboardInterrupt:
            print("\n\nStopping Voice Assistant V3...")
            self.whisper_client.stop(self.llm_response_array)

    def stop(self):
        """Stop the voice assistant"""
        if self.whisper_client:
            self.whisper_client.stop(self.llm_response_array)

    def run_with_event(self, stop_event: Event):
        """
        Start the voice assistant with external stop control.

        Args:
            stop_event: Threading Event to signal when to stop
        """
        try:
            self.whisper_client = SystemAudioWhisperClient(
                model="base",
                phrase_timeout=5,
                on_phrase_complete=self.on_phrase_complete
            )

            self.whisper_client.start()
            print("\nVoice Assistant V3 running. Waiting for stop signal.\n")

            while not stop_event.is_set():
                sleep(0.5)

            print("\n\nStop signal received, shutting down...")

        except KeyboardInterrupt:
            print("\n\nKeyboard interrupt received...")
        except Exception as e:
            print(f"\nError in voice assistant: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("Cleaning up audio resources...")
            if self.whisper_client:
                try:
                    self.whisper_client.is_running = False
                    sleep(0.5)
                except Exception as e:
                    print(f"Error stopping whisper client loops (non-fatal): {e}")

                try:
                    self.whisper_client.stop(self.llm_response_array)
                except Exception as e:
                    print(f"Error during whisper client stop (non-fatal): {e}")
                    # Try manual cleanup if stop() failed
                    try:
                        if self.whisper_client.stream:
                            self.whisper_client.stream.stop_stream()
                            self.whisper_client.stream.close()
                    except Exception as stream_err:
                        print(f"Error closing stream (non-fatal): {stream_err}")

                    try:
                        if self.whisper_client.pyaudio_instance:
                            self.whisper_client.pyaudio_instance.terminate()
                    except Exception as pyaudio_err:
                        print(f"Error terminating pyaudio (non-fatal): {pyaudio_err}")

            print("Cleanup complete.")


if __name__ == "__main__":
    assistant = CallAssistantV3()
    assistant.run()
