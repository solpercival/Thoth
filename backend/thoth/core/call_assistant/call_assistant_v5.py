"""
Call Assistant V5 - LLM-Driven with Simplified State Machine

Design principles:
1. Only 2 states - LLM handles conversation flow within each state
2. LLM outputs tags to signal state transitions (<FETCH>, <SUBMIT>, <DONE>, <END>)
3. Chat history maintained - LLM has full context of conversation
4. Single tweakable system prompt controls all behavior
"""

import sys
from dotenv import load_dotenv
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

load_dotenv()

import asyncio
import os
from time import sleep
from threading import Event
from enum import Enum, auto
from typing import Optional, Dict, Any, List

from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from ollama_client.llm_client import OllamaClient
from tts_client.tts_client import TTSClient
from thoth.core.email_agent.email_formatter import format_ezaango_shift_data
from thoth.core.email_agent.email_sender import send_notify_email
from thoth.automation.test_integrated_workflow import test_integrated_workflow
from thoth.core.call_assistant.call_3cx_client import close_all_calls_for_extension


# =============================================================================
# STATES - Only 2 states, LLM handles everything within each state
# =============================================================================

class State(Enum):
    """
    Simplified conversation states.

    Flow:
        GATHERING_INFO ──[<FETCH> tag]──> (fetch shifts) ──> CONFIRMING_DETAILS
              ▲                                                      │
              └──────────────[<DONE> tag]────────────────────────────┘
    """
    GATHERING_INFO = auto()       # Collect intent and date from user
    CONFIRMING_DETAILS = auto()   # Confirm shift selection and get reason


# =============================================================================
# SYSTEM PROMPT - Controls all LLM behavior
# =============================================================================

SYSTEM_PROMPT = """You are a professional call center agent handling shift cancellation requests.

CURRENT STATE: {state}

{state_instructions}

SPECIAL COMMANDS (output these when appropriate):
- <FETCH>date_query - When you have enough info to fetch the user's shifts
- <SUBMIT>shift_id|reason> - When you have shift selection AND cancellation reason (MUST close with >)
- <DONE> - When the current task is complete and you should reset
- <END> - When the user wants to end the call

CONVERSATION HISTORY:
{chat_history}

{context_info}

CRITICAL RULES:
- Be natural, conversational, and empathetic
- Show empathy if user mentions being sick/unwell
- ONLY output your IMMEDIATE response - NEVER predict user's next response
- NEVER include "User:" or hypothetical dialogue in your output
- Maintain context - remember what you've asked and what the user said
- When you output a special command, include it naturally in your response

EXAMPLES:
User: "I need to cancel my shift tomorrow"
You: "I understand. Let me look up your shift for tomorrow. <FETCH>tomorrow"

User: "The first one" (after being shown multiple shifts)
You: "Okay, the shift at McDonald's on January 30th. What's your reason for cancellation?"

User: "I'm feeling sick"
You: "I'm sorry to hear that. I'll let the rostering team know about your cancellation. <SUBMIT>123456|I'm feeling sick> Is there anything else I can help you with?"

User: "No, that's all"
You: "Thank you for calling. Have a great day! <END>"
"""

GATHERING_INFO_INSTRUCTIONS = """STATE: GATHERING_INFO

Your goal: Collect enough information to fetch the user's shifts.

What you need:
- Understand if they want to cancel a shift or just query their schedule
- Get date/time information (tomorrow, Monday, next week, specific date, etc.)

When you have the date/time information:
- Output: <FETCH>date_query (e.g., "<FETCH>tomorrow" or "<FETCH>next Monday")

If the user wants to end the call at any point:
- Output: <END>
"""

CONFIRMING_DETAILS_INSTRUCTIONS = """STATE: CONFIRMING_DETAILS

AVAILABLE SHIFTS:
{shifts_formatted}

Make sure you Omit the ID and just tell them about  the client name and the date and time.

Your goal: Confirm which shift to cancel and get the cancellation reason.

What you need:
1. Which shift they want to cancel (if multiple shifts)
2. The reason for cancellation

When you have BOTH the shift selection AND reason:
- Output: <SUBMIT>shift_id|reason> (IMPORTANT: Use the numeric ID only, no "shift_" prefix. Close with >)
- Example: "<SUBMIT>207414|I'm sick> Is there anything else?"

After successful cancellation:
- Tell the user that the rostering team has been notified and that they might get in touch
- Ask if there's anything else
- If they say no or are done: Output <DONE>
- Do not assume that the user wants to end the call just because the shift cancellation has been confirmed.

If the user wants to end the call:
- Output: <END>
"""


# =============================================================================
# CONFIGURATION
# =============================================================================

LOG_PREFIX = "[CALL_ASSISTANT_V5]"

# Test mode configuration
TEST_MODE = True
TEST_NUMBER = "0411 305 401"  # Replace with your test number


# =============================================================================
# TEST MODE CONFIGURATION
# =============================================================================

TEST_MODE = True  # Set to True to use test phone number instead of real caller
TEST_NUMBER = "0433622442"  # Phone number to use when TEST_MODE is True


# =============================================================================
# MAIN CLASS
# =============================================================================


class CallAssistantV5:
    """
    LLM-driven voice assistant with simplified 2-state machine.

    Key differences from V4:
    - Only 2 states instead of 7
    - LLM decides when to transition via output tags
    - Chat history maintained - LLM has full conversation context
    - Single system prompt controls all behavior
    """

    def __init__(self, caller_phone: Optional[str] = None, extension: Optional[str] = None):

        if TEST_MODE:
            self.caller_phone = TEST_NUMBER
        else:
            self.caller_phone = caller_phone

        self.extension = extension

        # LLM client - will use dynamic system prompts based on state
        self.llm_client = OllamaClient(
            model=os.getenv("LLM_MODEL", "qwen3:8b"),
            system_prompt=""  # Will be set dynamically
        )

        # Audio clients
        self.whisper_client: SystemAudioWhisperClient = None
        self.stop_event: Event = None

        # State machine - only 2 states!
        self.state = State.GATHERING_INFO

        # Chat history - maintained across the conversation
        self.chat_history: List[Dict[str, str]] = []

        # Context - stores extracted data
        self.context: Dict[str, Any] = {
            'shifts': [],             # Shifts retrieved from backend
            'selected_shift': None,   # The shift user confirmed
            'staff_info': {},         # Staff info for email
        }

        # For logging/debugging
        self.transcript_log = []

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================

    def on_phrase_complete(self, phrase: str) -> None:
        """
        Called when user finishes speaking.
        Routes to appropriate state handler.
        """
        # Check if user drops the call
        if self.stop_event and self.stop_event.is_set():
            return

        self._log(f"[CALL ASSISTANT V5] USER: {phrase}")
        self._log(f"[CALL ASSISTANT V5] STATE: {self.state.name}")

        # Pause the whisper client
        self.whisper_client.pause()
        self.transcript_log.append({"role": "user", "content": phrase})

        # Handle the phrase based on the current state
        try:
            match self.state:
                case State.GATHERING_INFO:
                    self._handle_gathering_info(phrase)

                case State.CONFIRMING_DETAILS:
                    self._handle_confirming_details(phrase)

                case _:
                    self._log(f"Unexpected state: {self.state}")
                    self._reset_conversation()

        except Exception as e:
            self._log(f"ERROR: {e}")
            self._speak("Sorry, I encountered an error. Let me start over. How can I help you?")
            self._reset_conversation()

        finally:
            if self.state != State.GATHERING_INFO or not self.stop_event.is_set():
                self.whisper_client.resume()

    # =========================================================================
    # STATE HANDLERS (to be implemented)
    # =========================================================================

    def _handle_gathering_info(self, phrase: str) -> None:
        """
        State: GATHERING_INFO

        LLM determines when enough info is collected and outputs <FETCH>query tag.
        """
        # Add user message to chat history
        self._add_to_history("user", phrase)

        # Ask LLM to process the user input
        llm_response = self._ask_llm(phrase)
        self._log(f"LLM Response: {llm_response}")

        # Parse the response for commands
        parsed = self._parse_llm_response(llm_response)

        # Speak the text part (if any)
        if parsed['text']:
            self._add_to_history("assistant", parsed['text'])
            self._speak(parsed['text'])

        # Handle commands
        if parsed['command'] == 'END':
            self._end_call()
            return

        elif parsed['command'] == 'FETCH':
            # LLM decided it has enough info to fetch shifts
            date_query = parsed['data']
            self._log(f"Fetching shifts for: {date_query}")

            # Build full context query for the date reasoner
            # If the current phrase has the date info, use it directly
            # Otherwise combine the original query with the date
            if date_query.lower() in phrase.lower():
                # Current phrase contains the date - likely a complete sentence
                full_query = phrase
            else:
                # Date was provided separately - combine with original intent
                full_query = f"{self.context.get('original_query', '')} {phrase}".strip()

            self._log(f"FULL QUERY FOR DATE REASONER: {full_query}")

            # Fetch shifts from backend with full context
            success = self._fetch_shifts(full_query)

            if success and self.context['shifts']:
                # Transition to confirming details
                self._transition_to(State.CONFIRMING_DETAILS)

                # Let LLM present the shifts in the next interaction
                # by asking it to respond to a system message
                system_msg = f"SYSTEM: Found {len(self.context['shifts'])} shift(s). Present them to the user."
                self._add_to_history("system", system_msg)

                # Ask LLM to present the shifts
                presentation = self._ask_llm(system_msg)
                parsed_presentation = self._parse_llm_response(presentation)

                if parsed_presentation['text']:
                    self._add_to_history("assistant", parsed_presentation['text'])
                    self._speak(parsed_presentation['text'])

            elif success and not self.context['shifts']:
                # No shifts found
                system_msg = "SYSTEM: No shifts found for that time period. Tell the user and ask if they want to check another date."
                self._add_to_history("system", system_msg)

                no_shifts_response = self._ask_llm(system_msg)
                parsed_no_shifts = self._parse_llm_response(no_shifts_response)

                if parsed_no_shifts['text']:
                    self._add_to_history("assistant", parsed_no_shifts['text'])
                    self._speak(parsed_no_shifts['text'])

            else:
                # Error fetching shifts
                error_msg = "Sorry, I had trouble looking up your shifts. Could you tell me the date again?"
                self._add_to_history("assistant", error_msg)
                self._speak(error_msg)


    def _handle_confirming_details(self, phrase: str) -> None:
        """
        State: CONFIRMING_DETAILS

        LLM determines when it has shift selection and reason, then outputs <SUBMIT>shift_id|reason tag.
        """
        # Add user message to chat history
        self._add_to_history("user", phrase)

        # Ask LLM to process the user input
        llm_response = self._ask_llm(phrase)
        self._log(f"LLM Response: {llm_response}")

        # Parse the response for commands
        parsed = self._parse_llm_response(llm_response)

        # For SUBMIT command, don't speak yet - wait until after submission
        # For other commands or no command, speak the text immediately
        if parsed['command'] != 'SUBMIT':
            if parsed['text']:
                self._add_to_history("assistant", parsed['text'])
                self._speak(parsed['text'])

        # Handle commands
        if parsed['command'] == 'END':
            self._end_call()
            return

        elif parsed['command'] == 'DONE':
            # User is done with current task, reset to beginning
            self._reset_conversation()
            return

        elif parsed['command'] == 'SUBMIT':
            # LLM has shift selection and reason
            shift_id = parsed['data']['shift_id']
            reason = parsed['data']['reason']

            self._log(f"Submitting cancellation: shift={shift_id}, reason={reason}")

            # Find the shift by ID
            selected_shift = None
            for shift in self.context['shifts']:
                if shift.get('shift_id') == shift_id:
                    selected_shift = shift
                    break

            if not selected_shift:
                # Couldn't find shift - ask LLM to clarify
                error_msg = "Sorry, I couldn't identify that shift. Could you tell me which one again?"
                self._add_to_history("assistant", error_msg)
                self._speak(error_msg)
                return

            self.context['selected_shift'] = selected_shift

            # Submit the cancellation
            success = self._submit_cancellation(selected_shift, reason)

            if success:
                # Tell LLM cancellation was successful
                system_msg = f"SYSTEM: Cancellation successful. Shift at {selected_shift.get('client_name')} on {selected_shift.get('date')} has been cancelled. Tell the user and ask if there's anything else."
                self._add_to_history("system", system_msg)

                success_response = self._ask_llm(system_msg)
                parsed_success = self._parse_llm_response(success_response)

                if parsed_success['text']:
                    self._add_to_history("assistant", parsed_success['text'])
                    self._speak(parsed_success['text'])

                # Handle DONE command if LLM outputs it
                if parsed_success['command'] == 'DONE':
                    self._reset_conversation()

            else:
                error_msg = "Sorry, there was an error cancelling your shift. Please try again or contact support."
                self._add_to_history("assistant", error_msg)
                self._speak(error_msg)
                self._reset_conversation()

    def _submit_cancellation(self, shift: Dict[str, Any], reason: str) -> bool:
        """
        Submit the cancellation request (sends notification email).
        Returns True if successful, False otherwise.
        """
        try:
            staff_info = self.context.get('staff_info', {})

            if not shift or not reason:
                self._log("Missing shift or reason for cancellation")
                return False

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

            formatted_content = format_ezaango_shift_data(email_data, cancellation_reason=reason)

            # Uncomment to actually send email:
            # send_notify_email(content=formatted_content, custom_subject="SHIFT CANCELLATION REQUEST")

            self._log(f"Cancellation submitted for shift at {shift.get('client_name')} - Reason: {reason}")
            return True

        except Exception as e:
            self._log(f"Cancellation error: {e}")
            return False

    # =========================================================================
    # LLM HELPER FUNCTIONS
    # =========================================================================

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on current state and context."""
        # Format chat history
        chat_history = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in self.chat_history[-10:]  # Last 10 messages for context
        ]) or "No conversation yet."

        # Get state-specific instructions
        if self.state == State.GATHERING_INFO:
            state_instructions = GATHERING_INFO_INSTRUCTIONS
            context_info = ""
        else:  # CONFIRMING_DETAILS
            # Format shifts for the LLM
            shifts_formatted = self._format_shifts_for_llm()
            state_instructions = CONFIRMING_DETAILS_INSTRUCTIONS.format(
                shifts_formatted=shifts_formatted
            )
            context_info = ""

        # Build complete prompt
        return SYSTEM_PROMPT.format(
            state=self.state.name,
            state_instructions=state_instructions,
            chat_history=chat_history,
            context_info=context_info
        )

    def _format_shifts_for_llm(self) -> str:
        """Format shifts list for the LLM to understand."""
        shifts = self.context.get('shifts', [])
        if not shifts:
            return "No shifts available."

        formatted = []
        for i, shift in enumerate(shifts, 1):
            formatted.append(
                f"{i}. shift_id={shift.get('shift_id')} - "
                f"{shift.get('client_name')} on {shift.get('date')} at {shift.get('time')}"
            )
        return "\n".join(formatted)

    def _ask_llm(self, user_phrase: str) -> str:
        """
        Ask the LLM and get response.
        Sets the system prompt based on current state before asking.
        """
        system_prompt = self._build_system_prompt()
        self.llm_client.set_system_prompt(system_prompt)
        response = self.llm_client.ask_llm(user_phrase)
        return response.strip()

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response for special commands and text to speak.

        Handles multiple tags in the same response (e.g., <SUBMIT>...<END>).
        Removes ALL tags from text, then determines primary command.

        Returns dict with:
        - 'command': The command tag found (FETCH, SUBMIT, DONE, END, or None)
        - 'data': Associated data with the command
        - 'text': Text to speak (with ALL commands removed)
        """
        import re

        result = {
            'command': None,
            'data': None,
            'text': llm_response
        }

        # First, extract command data (before removing tags)
        submit_match = re.search(r'<SUBMIT>(.+?)\|(.+?)(?:>|<|$)', llm_response)
        fetch_match = re.search(r'<FETCH>(.+?)(?:>|<|$)', llm_response)
        has_done = '<DONE>' in llm_response
        has_end = '<END>' in llm_response

        # Remove ALL tags from text (do this first, before determining command priority)
        clean_text = llm_response
        clean_text = re.sub(r'<SUBMIT>.+?(?:>|<|$)', '', clean_text)
        clean_text = re.sub(r'<FETCH>.+?(?:>|<|$)', '', clean_text)
        clean_text = clean_text.replace('<DONE>', '')
        clean_text = clean_text.replace('<END>', '')
        result['text'] = clean_text.strip()

        # Determine primary command (priority order: END > SUBMIT > FETCH > DONE)
        if has_end:
            result['command'] = 'END'
            return result

        if submit_match:
            result['command'] = 'SUBMIT'
            # Strip "shift_" prefix if LLM added it
            shift_id = submit_match.group(1).strip()
            if shift_id.lower().startswith('shift_'):
                shift_id = shift_id[6:]  # Remove "shift_" prefix

            result['data'] = {
                'shift_id': shift_id,
                'reason': submit_match.group(2).strip()
            }
            return result

        if fetch_match:
            result['command'] = 'FETCH'
            result['data'] = fetch_match.group(1).strip()
            return result

        if has_done:
            result['command'] = 'DONE'
            return result

        # No command found - just regular text
        return result

    # =========================================================================
    # UTILITY FUNCTIONS
    # =========================================================================

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to chat history."""
        self.chat_history.append({"role": role, "content": content})

    def _reset_conversation(self) -> None:
        """Reset to initial state."""
        self.state = State.GATHERING_INFO
        self.chat_history = []
        self.context = {
            'shifts': [],
            'selected_shift': None,
            'staff_info': {},
        }

    def _transition_to(self, new_state: State) -> None:
        """Transition to a new state."""
        self._log(f"TRANSITION: {self.state.name} -> {new_state.name}")
        self.state = new_state


    def _fetch_shifts(self, date_query: str) -> bool:
        """
        Fetch shifts from the backend.
        Returns True if successful, False otherwise.
        """
        if not self.caller_phone:
            self._log("No caller phone number available")
            return False

        try:
            result = asyncio.run(test_integrated_workflow(self.caller_phone, date_query))

            if not result:
                self._log("No result from backend")
                return False

            self.context['shifts'] = result.get('filtered_shifts', [])
            self.context['staff_info'] = result.get('staff', {})

            self._log(f"Fetched {len(self.context['shifts'])} shifts")
            return True

        except Exception as e:
            self._log(f"Error fetching shifts: {e}")
            return False

    # =========================================================================
    # I/O FUNCTIONS
    # =========================================================================

    def _speak(self, text: str) -> None:
        """Convert text to speech."""
        self._log(f"ASSISTANT: {text}")
        self.transcript_log.append({"role": "assistant", "content": text})
        try:
            tts_client = TTSClient(output_device_name="CABLE Input")
            tts_client.text_to_speech(text)
        except Exception as e:
            self._log(f"TTS error: {e}")

    def _log(self, message: str) -> None:
        """Log a message with prefix."""
        print(f"{LOG_PREFIX} {message}")

    def _end_call(self) -> None:
        """End the phone call."""
        if self.extension:
            try:
                close_all_calls_for_extension(self.extension)
            except Exception as e:
                self._log(f"End call error: {e}")

    # =========================================================================
    # RUN METHODS
    # =========================================================================

    def run(self) -> None:
        """Start the assistant (standalone mode)."""
        self.stop_event = Event()

        self.whisper_client = SystemAudioWhisperClient(
            model="base",
            phrase_timeout=5,
            on_phrase_complete=self.on_phrase_complete
        )

        try:
            # Initial greeting
            greeting = "Hello, thank you for calling Help at Hand Support. How can I help you today?"
            self._speak(greeting)
            self._add_to_history("assistant", greeting)

            self.whisper_client.start()

            self._log("Running (Ctrl+C to stop)")
            while not self.stop_event.is_set():
                sleep(1)

        except KeyboardInterrupt:
            self._log("Stopping...")
        finally:
            if self.whisper_client:
                self.whisper_client.stop(self.transcript_log)

    def run_with_event(self, stop_event: Event) -> None:
        """Start the assistant with external stop control (for app.py integration)."""
        self.stop_event = stop_event

        try:
            self.whisper_client = SystemAudioWhisperClient(
                model="base",
                phrase_timeout=5,
                on_phrase_complete=self.on_phrase_complete
            )

            # Initial greeting
            greeting = "Hello, thank you for calling. How can I help you today?"
            self._speak(greeting)
            self._add_to_history("assistant", greeting)

            self.whisper_client.start()

            self._log("Running")
            while not stop_event.is_set():
                sleep(0.5)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            self._log(f"Error: {e}")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up audio resources."""
        if self.whisper_client:
            self.whisper_client.is_running = False
            sleep(0.5)
            try:
                self.whisper_client.stop(self.transcript_log)
            except:
                if self.whisper_client.stream:
                    self.whisper_client.stream.stop_stream()
                    self.whisper_client.stream.close()
                if self.whisper_client.pyaudio_instance:
                    self.whisper_client.pyaudio_instance.terminate()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    assistant = CallAssistantV5()
    assistant.run()
