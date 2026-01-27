"""
Call Assistant V5 - Simplified LLM-Driven Conversation

Design principles:
1. Only 2 states - LLM handles the conversation flow within each state
2. Tag-based transitions - LLM signals state changes via special tags
3. Chat history maintained - enables natural, contextual conversations
4. LLM decides when enough information is gathered
"""

import sys
import os
from dotenv import load_dotenv
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

load_dotenv()

import asyncio
import re
from time import sleep
from threading import Event
from enum import Enum, auto
from typing import Optional, Dict, Any, List

from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from ollama_client.llm_client import OllamaClient
from thoth.core.call_assistant.tts_client import TTSClient
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
# SYSTEM PROMPTS
# =============================================================================

PROMPT_GATHERING_INFO = """You are a friendly phone support agent for a healthcare staffing company called "Helping Hands".
Your job is to help staff members cancel their upcoming shifts.

CURRENT TASK:
- Understand what the user wants (they likely want to cancel a shift)
- Get the DATE or TIME PERIOD for the shift they want to cancel
- Be empathetic and conversational

CONVERSATION SO FAR:
{chat_history}

RULES:
1. Keep responses SHORT (1-2 sentences, under 30 words)
2. Be warm and empathetic - if they mention being unwell, acknowledge it briefly
3. Don't be robotic or overly formal
4. If user wants something other than cancelling a shift, politely explain you can only help with shift cancellations or transfer them

WHEN YOU HAVE THE DATE/TIME INFO:
Once the user has clearly specified WHEN their shift is (e.g., "tomorrow", "Monday", "next week", "January 15th"), output:
<FETCH>the date or time description here</FETCH>

Examples of when to output <FETCH>:
- User: "I need to cancel my shift tomorrow" → Got it, let me look that up for you. <FETCH>tomorrow</FETCH>
- User: "Cancel my Monday shift" → Sure thing, let me look at your monday shifts. <FETCH>Monday</FETCH>
- User: "I can't make it to work next week" → I'll take a look at which shifts you have then<FETCH>next week</FETCH>

DO NOT output <FETCH> if the user hasn't mentioned when. Instead, ask them which day.

USER JUST SAID: "{user_input}"

Your response:"""


PROMPT_CONFIRMING_DETAILS = """You are a friendly phone support agent helping a staff member cancel a shift.

SHIFTS FOUND FOR THIS USER:
{shifts_info}

CONVERSATION SO FAR:
{chat_history}

CURRENT TASK:
1. If there are MULTIPLE shifts: Ask which one they want to cancel (refer to them by number or details)
2. Once a shift is identified: Confirm it's the correct one
3. Ask for their REASON for cancellation
4. Once you have confirmation AND reason: Output the completion tag

RULES:
1. Keep responses SHORT (1-2 sentences)
2. Be conversational and empathetic
3. Don't ask for the reason until they've confirmed which shift

WHEN YOU HAVE EVERYTHING:
Once the user has:
- Confirmed which shift (if multiple)
- Said YES to cancelling it
- Provided a reason

Output: <DONE>shift_number|their reason</DONE>

Examples:
- User confirmed shift 1, reason is "I'm sick" → I'm sorry to hear that. <DONE>1|I'm sick</DONE>
- User confirmed shift 2, reason is "family emergency" → Understood, I hope its not too bad. <DONE>2|family emergency</DONE>
- Only 1 shift and user said "yes, cancel it because I have a doctor's appointment" → Got it.<DONE>1|doctor's appointment</DONE>

DO NOT output <DONE> until you have BOTH confirmation AND reason.

USER JUST SAID: "{user_input}"

Your response:"""


# =============================================================================
# MAIN CLASS
# =============================================================================

LOG_PREFIX = "[CALL_ASSISTANT_V5]"


class CallAssistantV5:
    """
    Simplified voice assistant with LLM-driven conversation flow.

    Key differences from V4:
    - Only 2 states instead of 7
    - LLM decides when to transition (via tags)
    - Chat history maintained for natural conversation
    - LLM handles all the "is this enough info?" decisions
    """

    def __init__(self, caller_phone: Optional[str] = None, extension: Optional[str] = None):
        self.caller_phone = caller_phone
        self.extension = extension

        # LLM client
        self.llm = OllamaClient(model=os.getenv("LLM_MODEL", "qwen3:8b"))

        # Audio clients
        self.whisper_client: SystemAudioWhisperClient = None
        self.stop_event: Event = None

        # State machine - only 2 states!
        self.state = State.GATHERING_INFO

        # Chat history - maintained across the conversation
        self.chat_history: List[Dict[str, str]] = []

        # Context - stores extracted data
        self.context: Dict[str, Any] = {
            'date_query': None,       # Date/time the user mentioned
            'shifts': [],             # Shifts retrieved from backend
            'selected_shift': None,   # The shift user confirmed
            'reason': None,           # Cancellation reason
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

        LLM converses with user to understand their intent and gather date info.
        When LLM determines enough info is gathered, it outputs <FETCH>date_query</FETCH>
        """
        # Add user message to chat history
        self._add_to_history("user", phrase)

        # Build the prompt with chat history
        prompt = PROMPT_GATHERING_INFO.format(
            chat_history=self._format_chat_history(),
            user_input=phrase
        )

        # Get LLM response
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip()
        self._log(f"LLM RAW RESPONSE: {response}")

        # Check for <FETCH> tag, returns None if LLM thinks user did not provide date
        date_query = self._parse_tag(response, "FETCH")

        if date_query:
            # LLM determined we have enough info - fetch shifts
            self._log(f"FETCH tag found with date: {date_query}")
            self.context['date_query'] = date_query

            # Get the spoken part (without the tag)
            spoken_response = self._remove_tags(response)
            if spoken_response:
                self._add_to_history("assistant", spoken_response)
                self._speak(spoken_response)

            # Fetch shifts from backend
            success = self._fetch_shifts(date_query)

            if success and self.context['shifts']:
                # Transition to confirming details
                self._transition_to(State.CONFIRMING_DETAILS)

                # Let the LLM present the shifts naturally
                self._present_shifts_naturally()

            elif success and not self.context['shifts']:
                # No shifts found for that date
                no_shifts_msg = "I couldn't find any shifts for that time period. Is there another date you'd like me to check?"
                self._add_to_history("assistant", no_shifts_msg)
                self._speak(no_shifts_msg)
                # Stay in GATHERING_INFO to try again

            else:
                # Error fetching shifts
                error_msg = "Sorry, I had trouble looking up your shifts. Could you tell me the date again?"
                self._add_to_history("assistant", error_msg)
                self._speak(error_msg)
                # Stay in GATHERING_INFO

        else:
            # No <FETCH> tag - LLM is still gathering info
            # Speak the response and stay in current state
            self._add_to_history("assistant", response)
            self._speak(response)

    def _present_shifts_naturally(self) -> None:
        """
        After fetching shifts, let the LLM present them naturally.
        This is the first message in CONFIRMING_DETAILS state.
        """
        shifts = self.context.get('shifts', [])
        if not shifts:
            return

        # Build a simple prompt to present the shifts
        if len(shifts) == 1:
            shift = shifts[0]
            presentation = f"I found your shift at {shift.get('client_name')} on {shift.get('date')} at {shift.get('time')}. Would you like to cancel this one?"
        else:
            presentation = f"I found {len(shifts)} shifts. "
            for i, shift in enumerate(shifts, 1):
                presentation += f"{i}: {shift.get('client_name')} on {shift.get('date')} at {shift.get('time')}. "
            presentation += "Which one would you like to cancel?"

        self._add_to_history("assistant", presentation)
        self._speak(presentation)

    def _handle_confirming_details(self, phrase: str) -> None:
        """
        State: CONFIRMING_DETAILS

        LLM presents shifts and confirms which one to cancel + reason.
        When confirmed, outputs <DONE>shift_index|reason</DONE>
        """
        # Add user message to chat history
        self._add_to_history("user", phrase)

        # Build the prompt with shifts info and chat history
        prompt = PROMPT_CONFIRMING_DETAILS.format(
            shifts_info=self._format_shifts_for_prompt(),
            chat_history=self._format_chat_history(),
            user_input=phrase
        )

        # Get LLM response
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip()
        self._log(f"LLM RAW RESPONSE: {response}")

        # Check for <DONE> tag
        done_content = self._parse_tag(response, "DONE")

        if done_content:
            # LLM determined we have everything - process cancellation
            self._log(f"DONE tag found: {done_content}")

            # Parse the content: shift_number|reason
            parts = done_content.split("|", 1)
            if len(parts) == 2:
                try:
                    shift_index = int(parts[0].strip()) - 1  # Convert to 0-indexed
                    reason = parts[1].strip()

                    shifts = self.context.get('shifts', [])
                    if 0 <= shift_index < len(shifts):
                        self.context['selected_shift'] = shifts[shift_index]
                        self.context['reason'] = reason

                        # Get the spoken part (without the tag)
                        spoken_response = self._remove_tags(response)
                        if spoken_response:
                            self._add_to_history("assistant", spoken_response)
                            self._speak(spoken_response)

                        # Submit the cancellation
                        success = self._submit_cancellation()

                        if success:
                            # Cancellation successful
                            shift = self.context['selected_shift']
                            success_msg = f"Done. Your shift at {shift.get('client_name')} on {shift.get('date')} has been cancelled. Is there anything else I can help with?"
                            self._add_to_history("assistant", success_msg)
                            self._speak(success_msg)
                        else:
                            # Cancellation failed
                            error_msg = "Sorry, there was an error processing your cancellation. Please try again or contact support."
                            self._add_to_history("assistant", error_msg)
                            self._speak(error_msg)

                        # Reset and go back to beginning
                        self._reset_conversation()
                        return

                    else:
                        self._log(f"Invalid shift index: {shift_index}")

                except ValueError:
                    self._log(f"Could not parse shift number from: {parts[0]}")

            # If we got here, parsing failed - ask LLM to try again
            error_msg = "Sorry, I got confused. Could you confirm which shift and your reason again?"
            self._add_to_history("assistant", error_msg)
            self._speak(error_msg)

        else:
            # No <DONE> tag - LLM is still confirming details
            # Speak the response and stay in current state
            self._add_to_history("assistant", response)
            self._speak(response)

    def _submit_cancellation(self) -> bool:
        """
        Submit the cancellation request (sends notification email).
        Returns True if successful, False otherwise.
        """
        try:
            shift = self.context.get('selected_shift')
            reason = self.context.get('reason')
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
    # HELPER FUNCTIONS
    # =========================================================================

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to chat history."""
        self.chat_history.append({"role": role, "content": content})

    def _reset_conversation(self) -> None:
        """Reset to initial state."""
        self.state = State.GATHERING_INFO
        self.chat_history = []
        self.context = {
            'date_query': None,
            'shifts': [],
            'selected_shift': None,
            'reason': None,
            'staff_info': {},
        }

    def _transition_to(self, new_state: State) -> None:
        """Transition to a new state."""
        self._log(f"TRANSITION: {self.state.name} -> {new_state.name}")
        self.state = new_state

    def _format_chat_history(self) -> str:
        """Format chat history as a readable string for the LLM prompt."""
        if not self.chat_history:
            return "(No previous messages)"

        formatted = []
        for msg in self.chat_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted.append(f"{role}: {msg['content']}")
        return "\n".join(formatted)

    def _parse_tag(self, text: str, tag_name: str) -> Optional[str]:
        """
        Extract content from a tag like <TAG>content</TAG>.
        Returns None if tag not found.
        """
        pattern = f"<{tag_name}>(.*?)</{tag_name}>"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _remove_tags(self, text: str) -> str:
        """Remove all XML-style tags from text, keeping only the spoken content."""
        # Remove <TAG>...</TAG> patterns
        cleaned = re.sub(r'<[^>]+>.*?</[^>]+>', '', text, flags=re.DOTALL)
        # Remove any standalone tags like <TAG> without closing
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()

    def _format_shifts_for_prompt(self) -> str:
        """Format shifts list for the LLM prompt."""
        shifts = self.context.get('shifts', [])
        if not shifts:
            return "No shifts found."

        formatted = []
        for i, shift in enumerate(shifts, 1):
            formatted.append(
                f"{i}. {shift.get('client_name', 'Unknown')} on {shift.get('date', 'Unknown')} at {shift.get('time', 'Unknown')}"
            )
        return "\n".join(formatted)

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
            self._speak("Hello, thank you for Help at hands support. How can I help you today?")
            self._add_to_history("assistant", "Hello, thank you for calling. How can I help you today?")

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
            self._speak("Hello, thank you for calling. How can I help you today?")
            self._add_to_history("assistant", "Hello, thank you for calling. How can I help you today?")

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
