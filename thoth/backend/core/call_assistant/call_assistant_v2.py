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
from time import sleep
from threading import Event
from enum import Enum
from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from ollama_client.llm_client import OllamaClient
from typing import Optional, Any, Dict, List

from backend.core.call_assistant.tts_client import TTSClient
from backend.core.email_agent.email_formatter import *
from backend.core.email_agent.email_sender import *
from backend.automation.test_integrated_workflow import test_integrated_workflow


class ConversationState(Enum):
    """Conversation states for multi-turn dialogue management"""
    IDLE = "idle"                          # No active conversation
    AWAITING_CONFIRMATION = "confirm"       # Asked yes/no question
    AWAITING_REASON = "reason"              # Collecting cancellation reason
    AWAITING_CHOICE = "choice"              # Multiple shifts, user choosing one
    PROCESSING = "processing"               # System is working


# System prompts for different stages
LLM_SYSTEM_PROMPT = """THIS IS IMPORTANT THAT YOU FOLLOW THE OUTPUTS EXACTLY. You are a call center routing agent. Your ONLY job is to classify user requests and output exactly ONE of the following tags. You must NEVER write explanations, stories, or any other text.

CLASSIFICATION RULES:
- If user asks about app login issues → output: <LOGIN>
- If user asks about their work shift/schedule OR asks to cancel their shift→ output: <SHIFT>
- If user asks to speak with a real person → output: <REAL>
- For ALL other requests → output: <DENY>

CRITICAL: You must ONLY output one of these four tags. Do not write any other text, do not be helpful in other ways, do not answer questions. Just output the tag.

Examples:
User: "I can't log into the app" → <LOGIN>
User: "When is my shift tomorrow?" → <SHIFT>
User: "Can I talk to someone?" → <REAL>
User: "Tell me a joke" → <DENY>
User: "What's the weather?" → <DENY>
"""

YES_NO_SYSTEM_PROMPT = """You are a yes/no detector. Your ONLY job is to determine if the user is confirming (yes) or declining (no).

Output ONLY one word: "YES" or "NO"

Examples:
User: "Yes" → YES
User: "Yeah" → YES
User: "Sure" → YES
User: "Okay" → YES
User: "Confirm" → YES
User: "No" → NO
User: "Nope" → NO
User: "Cancel" → NO
User: "Never mind" → NO
User: "I changed my mind" → NO
"""

NUMBER_EXTRACTION_PROMPT = """You are a number extractor. Your ONLY job is to extract the number from the user's response.

Output ONLY the number as a digit.

Examples:
User: "The first one" → 1
User: "Number two" → 2
User: "The second shift" → 2
User: "Third" → 3
User: "I want the Monday one" → (if Monday is option 1) 1
"""


def print_dict(data: Any, title: str = None) -> None:
    """
    Helper function to print dictionaries in a readable format.

    Args:
        data: Dictionary or JSON-serializable object to print
        title: Optional title to display above the output
    """
    if title:
        print(f"\n{'='*10} {title} {'='*10}")

    # If data is a JSON string, parse it first
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            print(data)
            if title:
                print('=' * (22 + len(title)))
            return

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            print(item)
    else:
        print(data)

    if title:
        print('=' * (22 + len(title)))


class CallAssistantV2:
    """
    Version 2 of CallAssistant with multi-turn conversation support via state machine.

    Key improvements:
    - Tracks conversation state (IDLE, AWAITING_CONFIRMATION, etc.)
    - Maintains context between phrases
    - Handles multi-turn dialogues (ask follow-up questions)
    - Better error recovery
    """

    def __init__(self, caller_phone: Optional[str] = None):
        self.caller_phone = caller_phone  # Store caller phone number for context
        self.llm_client: OllamaClient = OllamaClient(model="qwen2.5:7b", system_prompt=LLM_SYSTEM_PROMPT)
        self.whisper_client: SystemAudioWhisperClient = None
        self.llm_response_array = []
        self.transcript = ""

        # State machine for multi-turn conversations
        self.state = ConversationState.IDLE
        self.context: Dict[str, Any] = {
            'pending_shift': None,        # Single shift to cancel/view
            'pending_shifts': [],         # Multiple shifts (if ambiguous)
            'cancellation_reason': None,  # User's cancellation reason
            'original_intent': None,      # <CNCL> or <SHOW>
            'last_query': None,           # Last user query
            'staff_info': {},             # Staff information for email
        }

    def on_phrase_complete(self, phrase: str) -> None:
        """
        Called when a phrase is completed on the whisper client.
        Routes to appropriate handler based on conversation state.

        Args:
            phrase (str): the transcript of the recorded phrase
        """
        print(f"[PHRASE COMPLETE]\n{phrase}")
        print(f"[CONVERSATION STATE] {self.state.value}")
        if self.caller_phone:
            print(f"[CALLER PHONE] {self.caller_phone}")

        self.transcript = phrase

        # Pause the whisper client while processing
        self.whisper_client.pause()

        try:
            # Route based on current conversation state
            if self.state == ConversationState.IDLE:
                self._handle_new_request(phrase)

            elif self.state == ConversationState.AWAITING_CONFIRMATION:
                self._handle_confirmation(phrase)

            elif self.state == ConversationState.AWAITING_REASON:
                self._handle_reason(phrase)

            elif self.state == ConversationState.AWAITING_CHOICE:
                self._handle_choice(phrase)

            else:
                print(f"[WARNING] Unknown state: {self.state}")
                self._speak_and_reset("Sorry, something went wrong. Let's start over.")

        except Exception as e:
            print(f"[ERROR]\nFailed to process phrase: {e}")
            import traceback
            traceback.print_exc()
            self._speak_and_reset("Sorry, I encountered an error. Let's start over.")

        finally:
            # Resume the whisper client
            self.whisper_client.resume()

    def _handle_new_request(self, phrase: str) -> None:
        """
        Handle initial user request (intent classification).

        Args:
            phrase: User's request
        """
        print("[HANDLING NEW REQUEST]")

        # Reset system prompt to intent classifier
        self.llm_client.set_system_prompt(LLM_SYSTEM_PROMPT)

        # Classify intent
        print("[SENDING TO LLM FOR INTENT CLASSIFICATION]")
        llm_response = self.llm_client.ask_llm(phrase)
        print(f"[LLM RESPONSE]\n{llm_response}")
        self.llm_response_array.append(llm_response)

        # Store the original query
        self.context['last_query'] = phrase

        # Route to appropriate action based on intent
        self._route_intent(llm_response, phrase)

    def _handle_confirmation(self, phrase: str) -> None:
        """
        Handle yes/no confirmation response.

        Args:
            phrase: User's response (yes/no)
        """
        print("[HANDLING CONFIRMATION]")

        # Use LLM to interpret yes/no
        self.llm_client.set_system_prompt(YES_NO_SYSTEM_PROMPT)
        response = self.llm_client.ask_llm(phrase).strip().upper()

        print(f"[CONFIRMATION RESULT] {response}")

        if "YES" in response:
            # User confirmed
            if self.context['original_intent'] == '<CNCL>':
                # Move to asking for cancellation reason
                self.state = ConversationState.AWAITING_REASON
                self._speak("Please tell me the reason for cancellation")
            else:
                # Just showing shifts, done
                self._speak_and_reset("Okay, is there anything else I can help you with?")
        else:
            # User declined
            self._speak_and_reset("Okay, no problem. Is there anything else I can help you with?")

    def _handle_reason(self, phrase: str) -> None:
        """
        Handle cancellation reason.

        Args:
            phrase: User's cancellation reason
        """
        print("[HANDLING CANCELLATION REASON]")

        self.context['cancellation_reason'] = phrase
        shift = self.context['pending_shift']

        if not shift:
            print("[ERROR] No pending shift to cancel!")
            self._speak_and_reset("Sorry, I lost track of which shift to cancel. Let's start over.")
            return

        # Submit the cancellation
        print(f"[SUBMITTING CANCELLATION] Shift ID: {shift.get('shift_id')}, Reason: {phrase}")
        success = self._submit_cancellation(shift.get('shift_id'), phrase)

        if success:
            response = (
                f"Your shift at {shift['client_name']} on {shift['date']} at {shift['time']} "
                f"has been cancelled. The reason recorded is: {phrase}. "
                f"Is there anything else I can help you with?"
            )
            self._speak_and_reset(response)
        else:
            self._speak_and_reset("Sorry, there was an error cancelling your shift. Please contact support.")

    def _handle_choice(self, phrase: str) -> None:
        """
        Handle choosing from multiple shifts.

        Args:
            phrase: User's choice (e.g., "the first one", "number 2")
        """
        print("[HANDLING SHIFT CHOICE]")

        shifts = self.context['pending_shifts']

        if not shifts:
            print("[ERROR] No pending shifts to choose from!")
            self._speak_and_reset("Sorry, I lost track of the shifts. Let's start over.")
            return

        # Use LLM to extract choice number
        prompt = f"Extract the shift number (1-{len(shifts)}) from this response. User said: {phrase}"
        self.llm_client.set_system_prompt(NUMBER_EXTRACTION_PROMPT)

        response = self.llm_client.ask_llm(prompt).strip()
        print(f"[EXTRACTED CHOICE] {response}")

        try:
            # Extract just the number from response
            import re
            match = re.search(r'\d+', response)
            if not match:
                raise ValueError("No number found")

            choice = int(match.group()) - 1  # Convert to 0-based index

            if 0 <= choice < len(shifts):
                selected_shift = shifts[choice]
                self.context['pending_shift'] = selected_shift
                self.state = ConversationState.AWAITING_CONFIRMATION

                # Ask for confirmation
                if self.context['original_intent'] == '<CNCL>':
                    response_text = (
                        f"You selected the shift at {selected_shift['client_name']} "
                        f"on {selected_shift['date']} at {selected_shift['time']}. "
                        f"Do you want to cancel this shift?"
                    )
                else:
                    response_text = (
                        f"You selected the shift at {selected_shift['client_name']} "
                        f"on {selected_shift['date']} at {selected_shift['time']}."
                    )

                self._speak(response_text)
            else:
                print(f"[ERROR] Choice {choice + 1} out of range (1-{len(shifts)})")
                self._speak("Invalid choice. Please say a number between 1 and " + str(len(shifts)))

        except (ValueError, AttributeError) as e:
            print(f"[ERROR] Could not parse choice: {e}")
            self._speak("I didn't understand which shift you meant. Please say the number, like 'one' or 'two'.")

    def _route_intent(self, intent_tag: str, original_phrase: str) -> None:
        """
        Route the LLM intent to the appropriate handler and manage state transitions.

        Args:
            intent_tag: One of <LOGIN>, <SHIFT>, <REAL>, <DENY>
            original_phrase: Original user query
        """
        print(f"[ROUTING INTENT] {intent_tag}")

        if "<SHIFT>" in intent_tag and self.caller_phone:
            print(f"[ROUTING] Shift check request for {self.caller_phone}")

            # Call integrated workflow to get shift data
            result: dict = asyncio.run(test_integrated_workflow(self.caller_phone, original_phrase))

            if not result:
                self._speak_and_reset("Sorry, I couldn't retrieve your shift information. Please try again later.")
                return

            # Parse intention from reasoning
            reasoning_str = result.get('reasoning', 'Unknown')
            intention_flag = '<SHOW>'  # default

            if '<CNCL>' in reasoning_str:
                intention_flag = '<CNCL>'
            elif '<SHOW>' in reasoning_str:
                intention_flag = '<SHOW>'

            self.context['original_intent'] = intention_flag
            self.context['staff_info'] = result.get('staff', {})  # Store staff info for email
            shifts = result.get('filtered_shifts', [])

            print(f"[SHIFT QUERY] Found {len(shifts)} shift(s), Intent: {intention_flag}")

            if len(shifts) == 0:
                # No shifts found
                self._speak_and_reset("You don't have any shifts in that time period. Is there anything else I can help you with?")

            elif len(shifts) == 1:
                # Single shift - ask for confirmation
                shift = shifts[0]
                self.context['pending_shift'] = shift
                self.state = ConversationState.AWAITING_CONFIRMATION

                if intention_flag == '<CNCL>':
                    response = (
                        f"You have a shift at {shift['client_name']} "
                        f"on {shift['date']} at {shift['time']}. "
                        f"Do you want to cancel this shift?"
                    )
                else:
                    response = (
                        f"You have a shift at {shift['client_name']} "
                        f"on {shift['date']} at {shift['time']}."
                    )

                self._speak(response)

            else:
                # Multiple shifts - ask user to choose
                self.context['pending_shifts'] = shifts
                self.state = ConversationState.AWAITING_CHOICE

                response = f"You have {len(shifts)} shifts. "
                for i, shift in enumerate(shifts, 1):
                    response += f"Number {i}: {shift['client_name']} on {shift['date']} at {shift['time']}. "

                if intention_flag == '<CNCL>':
                    response += "Which shift do you want to cancel?"
                else:
                    response += "Which shift are you asking about?"

                self._speak(response)

        elif "<LOGIN>" in intent_tag:
            print(f"[ROUTING] Login assistance requested")
            self._speak_and_reset("I understand you're having trouble logging in. Please hold while I transfer you to a live agent for assistance.")

        elif "<REAL>" in intent_tag:
            print(f"[ROUTING] Transfer to real agent")
            self._speak_and_reset("Of course. Please hold while I transfer you to a live agent.")

        else:
            print(f"[ROUTING] Request denied: {intent_tag}")
            self._speak_and_reset("I'm sorry, I can't help with that request. Is there anything else I can assist you with?")

    def _speak(self, text: str) -> None:
        """
        Convert text to speech and play through virtual audio cable.

        Args:
            text: The text to speak
        """
        print(f"[TTS] {text}")
        tts_client = TTSClient(output_device_name="CABLE Input")
        tts_client.text_to_speech(text)

    def _speak_and_reset(self, text: str) -> None:
        """
        Speak text and reset conversation state to IDLE.

        Args:
            text: The text to speak
        """
        self._speak(text)
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset conversation state and context to IDLE."""
        print("[RESETTING STATE TO IDLE]")
        self.state = ConversationState.IDLE
        self.context = {
            'pending_shift': None,
            'pending_shifts': [],
            'cancellation_reason': None,
            'original_intent': None,
            'last_query': None,
            'staff_info': {},
        }

    def _submit_cancellation(self, shift_id: str, reason: str) -> bool:
        """
        Submit cancellation to backend API and send notification email.

        Args:
            shift_id: ID of the shift to cancel
            reason: Cancellation reason

        Returns:
            True if successful, False otherwise
        """
        print(f"[SUBMITTING CANCELLATION] Shift {shift_id} with reason: {reason}")

        try:
            # Get pending shift data from context
            shift = self.context.get('pending_shift')
            staff_info = self.context.get('staff_info', {})

            if not shift:
                print("[ERROR] No pending shift in context")
                return False

            # TODO: Implement actual API call to cancel shift on Ezaango
            # For now, we'll just send the notification email

            # Prepare data for email formatter
            email_data = {
                "reasoning": "Requested cancellation of shift.",
                "staff": {
                    "name": staff_info.get('full_name', 'Unknown'),
                    "id": staff_info.get('id', 'Unknown'),
                    "email": staff_info.get('email', 'Unknown')
                },
                "shifts": [
                    {
                        "client": shift.get('client_name', 'Unknown'),
                        "time": shift.get('time', 'Unknown'),
                        "date": shift.get('date', 'Unknown')
                    }
                ]
            }

            # Format email with cancellation reason
            from backend.core.email_agent.email_formatter import format_ezaango_shift_data
            from backend.core.email_agent.email_sender import send_notify_email

            formatted_content = format_ezaango_shift_data(
                email_data,
                cancellation_reason=reason
            )

            # Send notification email
            send_notify_email(
                content=formatted_content,
                custom_subject="SHIFT CANCELLATION REQUEST"
            )

            print(f"[SUCCESS] Cancellation notification sent for shift {shift_id}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to submit cancellation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """Start the voice assistant"""
        # Create whisper client with callback
        self.whisper_client = SystemAudioWhisperClient(
            model="base",
            phrase_timeout=5,
            on_phrase_complete=self.on_phrase_complete  # Pass callback
        )

        try:
            self.whisper_client.start()

            # Keep running until interrupted
            print("\nVoice Assistant V2 running. Press Ctrl+C to stop.\n")
            while True:
                sleep(1)

        except KeyboardInterrupt:
            print("\n\nStopping Voice Assistant...")
            self.whisper_client.stop(self.llm_response_array)

    def stop(self):
        """Stop the voice assistant"""
        if self.whisper_client:
            self.whisper_client.stop(self.llm_response_array)

    def run_with_event(self, stop_event: Event):
        """
        Start the voice assistant with external stop control. Used in app.py.

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
            print("\nVoice Assistant V2 running. Waiting for stop signal.\n")

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
    assistant = CallAssistantV2()
    assistant.run()
