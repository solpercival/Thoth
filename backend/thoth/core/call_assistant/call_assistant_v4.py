"""
Call Assistant V4 - Explicit State Machine with Flexible Intent Handling

Design principles:
1. Explicit state machine - code controls flow, not the LLM
2. Focused LLM prompts - each prompt does ONE job
3. Escape hatches - user can change their mind at any point
4. Clear transitions - easy to follow and debug
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
from typing import Optional, Dict, Any

from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from ollama_client.llm_client import OllamaClient
from thoth.core.call_assistant.tts_client import TTSClient
from thoth.core.email_agent.email_formatter import format_ezaango_shift_data
from thoth.core.email_agent.email_sender import send_notify_email
from thoth.automation.test_integrated_workflow import test_integrated_workflow
from thoth.core.call_assistant.call_3cx_client import close_all_calls_for_extension


# =============================================================================
# STATES - The conversation can only be in ONE of these states at a time
# =============================================================================

class State(Enum):
    """
    Conversation states. The current state determines how we interpret user input.

    Flow diagram:

                                    ┌─────────────────────────────┐
                                    │                             │
                                    ▼                             │
    GREETING → LISTENING → AWAITING_DATE_CLARIFICATION ──────────┘
                  │                 │
                  │ (has date)      │ (user provides date)
                  ▼                 ▼
             FETCHING_SHIFTS ◄──────┘
                  │
                  ▼
          PRESENTING_SHIFTS → AWAITING_CONFIRMATION → AWAITING_REASON → CLOSING
                  │                    │                    │
                  └────────────────────┴────────────────────┘
                        (user can escape back to LISTENING at any point)
    """
    GREETING = auto()                    # Initial greeting, then immediately to LISTENING
    LISTENING = auto()                   # Waiting for user to state their intent
    AWAITING_DATE_CLARIFICATION = auto() # Asked "which day is this shift on?"
    FETCHING_SHIFTS = auto()             # Retrieving shifts from backend (brief processing state)
    PRESENTING_SHIFTS = auto()           # Showed shifts, waiting for user to pick one (if multiple)
    AWAITING_CONFIRMATION = auto()       # Asked "do you want to cancel this shift?"
    AWAITING_REASON = auto()             # Asked "what is your reason for cancellation?"
    CLOSING = auto()                     # Ending the call


# =============================================================================
# LLM PROMPTS - Each prompt does exactly ONE job
# =============================================================================
# NOTE: We break up the prompts and change them so that we dont confuse the LLM with long system prompts
PROMPT_CLASSIFY_INTENT = """Classify this customer request into exactly ONE category.

Categories:
- CANCEL_SHIFT: User wants to cancel a work shift
- QUERY_SHIFT: User wants to know about their shifts/schedule
- LOGIN_HELP: User has trouble logging into the app
- REAL_PERSON: User wants to speak with a human/real person
- END_CALL: User wants to end the call (goodbye, thanks, etc.)
- OTHER: Anything else

Output ONLY the category name, nothing else.

Examples:
"I need to cancel my shift tomorrow" → CANCEL_SHIFT
"When do I work next week?" → QUERY_SHIFT
"I can't log in" → LOGIN_HELP
"Can I talk to someone?" → REAL_PERSON
"That's all, thank you" → END_CALL
"What's the weather?" → OTHER
"""

PROMPT_DETECT_ESCAPE = """Is the user changing their mind, abandoning the current task, or asking for something different?

Current task: {current_task}
User said: "{user_input}"

Answer only YES or NO.

Examples (if current task is "cancelling a shift"):
- "Actually never mind" → YES
- "I changed my mind" → YES
- "Can I talk to a real person instead?" → YES
- "Wait, I want to cancel a different shift" → YES
- "Yes, cancel it" → NO
- "Because I'm sick" → NO
- "The first one" → NO
"""

PROMPT_CONFIRM_YES_NO = """Did the user confirm (yes) or decline (no)?

User said: "{user_input}"

Answer only YES, NO, or UNCLEAR.

Examples:
"Yes" → YES
"Yeah go ahead" → YES
"Sure" → YES
"Confirm" → YES
"No" → NO
"Nope" → NO
"I changed my mind" → NO
"Hmm let me think" → UNCLEAR
"""

PROMPT_EXTRACT_SHIFT_NUMBER = """The user is selecting from {count} shifts. Which number did they pick?

User said: "{user_input}"

Answer with ONLY the number (1, 2, 3, etc.) or UNCLEAR if you can't tell.

Examples:
"The first one" → 1
"Number two" → 2
"The second shift" → 2
"I want the last one" → {count}
"The Monday shift" → UNCLEAR
"""

PROMPT_HAS_DATE_INFO = """Does this request contain specific date or time information?

Look for:
- Specific dates (tomorrow, Monday, next week, January 15th, etc.)
- Relative time references (tonight, this weekend, in 2 days, etc.)
- Time periods (this week, next month, etc.)

User said: "{user_input}"

Answer only YES or NO.

Examples:
"I want to cancel my shift tomorrow" → YES
"Cancel my Monday shift" → YES
"What shifts do I have next week?" → YES
"I need to cancel my shift" → NO
"Cancel a shift" → NO
"What are my upcoming shifts?" → NO
"""

PROMPT_EXTRACT_DATE_INFO = """Extract the date/time information from what the user said.

User said: "{user_input}"

Output a brief, natural phrase describing when (e.g., "tomorrow", "next Monday", "this weekend").
If no date info, output NONE.

Examples:
"I want to cancel tomorrow" → tomorrow
"The one on Monday" → Monday
"Next week's shift" → next week
"Yes" → NONE
"""


# =============================================================================
# MAIN CLASS
# =============================================================================

LOG_PREFIX = "[CALL_ASSISTANT_V4]"


class CallAssistantV4:
    """
    Voice assistant with explicit state machine and flexible intent handling.

    Key features:
    - State is always explicit (self.state)
    - Each state has ONE handler function
    - User can "escape" at any point by changing their mind
    - LLM is used only for understanding language, not controlling flow
    """

    def __init__(self, caller_phone: Optional[str] = None, extension: Optional[str] = None):
        self.caller_phone = caller_phone
        self.extension = extension

        # LLM client - we'll swap prompts as needed
        self.llm = OllamaClient(model=os.getenv("LLM_MODEL", "qwen3:8b"))

        # Audio clients
        self.whisper_client: SystemAudioWhisperClient = None
        self.stop_event: Event = None

        # State machine
        self.state = State.GREETING

        # Context - stores data needed across states
        self.context: Dict[str, Any] = {
            'shifts': [],           # List of shifts from backend
            'selected_shift': None, # The shift user selected
            'staff_info': {},       # Staff info for email
            'is_cancellation': False, # True if user wants to cancel, False if just querying
            'original_query': '',   # Original user query (before date clarification)
        }

        # For logging/debugging
        self.transcript_log = []

    # =========================================================================
    # MAIN ENTRY POINT - Called when user finishes speaking
    # =========================================================================

    def on_phrase_complete(self, phrase: str) -> None:
        """
        Main entry point, called everytime whisper determines an end of phrase.
        Routes to the appropriate handler based on current state.

        This is the ONLY place where state routing happens.
        """
        if self.stop_event and self.stop_event.is_set():
            return

        self._log(f"USER: {phrase}")
        self._log(f"STATE: {self.state.name}")

        self.whisper_client.pause()
        self.transcript_log.append({"role": "user", "content": phrase})

        try:
            # Call the right function based on what state we are in.
            # Each function here does different things based on what they need to do in their current state.
            match self.state:
                case State.LISTENING:
                    self._handle_listening(phrase)

                case State.AWAITING_DATE_CLARIFICATION:
                    self._handle_awaiting_date_clarification(phrase)

                case State.PRESENTING_SHIFTS:
                    self._handle_presenting_shifts(phrase)

                case State.AWAITING_CONFIRMATION:
                    self._handle_awaiting_confirmation(phrase)

                case State.AWAITING_REASON:
                    self._handle_awaiting_reason(phrase)

                case State.CLOSING:
                    self._handle_closing(phrase)

                case _:
                    self._log(f"Unexpected state: {self.state}")
                    self._transition_to(State.LISTENING)
                    self._speak("Sorry, something went wrong. How can I help you?")

        except Exception as e:
            self._log(f"ERROR: {e}")
            self._speak("Sorry, I encountered an error. Let me start over. How can I help you?")
            self._transition_to(State.LISTENING)

        finally:
            if self.state != State.CLOSING:
                self.whisper_client.resume()

    # =========================================================================
    # STATE HANDLERS - Each state has exactly one handler (one function)
    # =========================================================================

    def _handle_listening(self, phrase: str) -> None:
        """
        State: LISTENING
        THE STARTING POINT IN THE STATE MACHINE.
        User just said something. Classify their intent and route and change their state accordingly.
        """
        intent = self._classify_intent(phrase)
        self._log(f"INTENT: {intent}")

        match intent:
            case "CANCEL_SHIFT":
                self.context['is_cancellation'] = True
                self._handle_shift_request(phrase)

            case "QUERY_SHIFT":
                self.context['is_cancellation'] = False
                self._handle_shift_request(phrase)

            case "LOGIN_HELP":
                self._speak("I understand you're having trouble logging in. Let me transfer you to someone who can help.")
                self._transition_to(State.CLOSING)

            case "REAL_PERSON":
                self._speak("Of course. Let me transfer you to a live agent.")
                self._transition_to(State.CLOSING)

            case "END_CALL":
                self._speak("Thank you for calling. Goodbye!")
                self._transition_to(State.CLOSING)
                self._end_call()

            case _:  # OTHER
                self._speak("I can only help with shift-related questions for now, or I can transfer you to a live assistant. Would you like to check your shifts or cancel one? Or need live assistance?")

    def _handle_awaiting_date_clarification(self, phrase: str) -> None:
        """
        State: AWAITING_DATE_CLARIFICATION
        We asked the user which day their shift is on. Waiting for date info.
        """
        # Check if user wants to escape
        if self._wants_to_escape(phrase, "providing date information"):
            return

        # Try to extract date info from their response
        date_info = self._extract_date_info(phrase)
        self._log(f"DATE INFO: {date_info}")

        if date_info == "NONE" or not date_info:
            # Still no date - ask again or be more helpful
            self._speak("I didn't catch the date. Could you tell me which day? For example, tomorrow, Monday, or a specific date?")
            return

        # Build a new query combining original intent with date info
        original_query = self.context.get('original_query', '')
        combined_query = f"{original_query} {date_info}".strip()
        self._log(f"COMBINED QUERY: {combined_query}")

        # Generate natural acknowledgment before fetching
        action = "cancel" if self.context['is_cancellation'] else "check"
        response = self._generate_natural_response(
            situation=f"User provided the date ({date_info}) for the shift they want to {action}",
            user_input=phrase,
            required_info="You will look up their shifts now",
            fallback="Let me look up your shifts."
        )
        self._speak(response)

        # Now fetch shifts with the date-enhanced query
        self._fetch_and_present_shifts(combined_query)

    def _handle_presenting_shifts(self, phrase: str) -> None:
        """
        State: PRESENTING_SHIFTS
        Present the user with their shifts. Now waiting for them to select one (if multiple).
        """
        # Check if user wants to escape
        if self._wants_to_escape(phrase, "selecting a shift"):
            return

        shifts = self.context['shifts']

        # Only one shift, user is probably confirming. Skip asking them which shift they want.
        if len(shifts) == 1:
            # Only one shift, user is probably confirming
            if self.context['is_cancellation']:
                self._transition_to(State.AWAITING_CONFIRMATION)
                self._handle_awaiting_confirmation(phrase)
            # If user just wants to query what shift they have, present and reset to the beginning.
            else:
                # Just querying, we already showed it
                self._speak("Is there anything else I can help you with?")
                self._reset_and_listen()
        else:
            # Multiple shifts, need to extract selection
            selection = self._extract_shift_selection(phrase, len(shifts))

            if selection is None:
                self._speak(f"I didn't catch which shift. Please say a number between 1 and {len(shifts)}.")
                return

            self.context['selected_shift'] = shifts[selection - 1]
            shift = self.context['selected_shift']

            if self.context['is_cancellation']:
                self._speak(f"You selected the shift for {shift['client_name']} on {shift['date']} at {shift['time']}. Do you want to cancel this shift?")
                self._transition_to(State.AWAITING_CONFIRMATION)
            else:
                self._speak(f"That's the shift for {shift['client_name']} on {shift['date']} at {shift['time']}. Is there anything else?")
                self._reset_and_listen()

    def _handle_awaiting_confirmation(self, phrase: str) -> None:
        """
        State: AWAITING_CONFIRMATION
        We asked "Do you want to cancel this shift?" - waiting for yes/no.
        """
        # Check if user wants to escape
        if self._wants_to_escape(phrase, "confirming shift cancellation"):
            return

        answer = self._detect_yes_no(phrase)
        self._log(f"CONFIRMATION: {answer}")

        match answer:
            case "YES":
                self._speak("Okay. What is your reason for cancellation?")
                self._transition_to(State.AWAITING_REASON)

            case "NO":
                self._speak("No problem. Is there anything else I can help you with?")
                self._reset_and_listen()

            case _:  # UNCLEAR
                self._speak("Sorry, I didn't catch that. Do you want to cancel this shift? Please say yes or no.")

    def _handle_awaiting_reason(self, phrase: str) -> None:
        """
        State: AWAITING_REASON
        We asked for the cancellation reason. User's response IS the reason.
        """
        # Check if user wants to escape
        if self._wants_to_escape(phrase, "providing cancellation reason"):
            return

        # User's phrase is the reason
        reason = phrase
        shift = self.context['selected_shift']

        if not shift:
            self._speak("Sorry, I lost track of which shift. Let's start over. How can I help you?")
            self._reset_and_listen()
            return

        # Submit cancellation
        success = self._submit_cancellation(shift, reason)

        if success:
            self._speak(
                f"Okay. Your shift for {shift['client_name']} on {shift['date']} "
                f"has been cancelled. Is there anything else I can help you with?"
            )
        else:
            self._speak("Sorry, there was an error cancelling your shift. Please contact support.")

        self._reset_and_listen()

    def _handle_closing(self, phrase: str) -> None:
        """
        State: CLOSING
        Call is ending. If user says something, acknowledge and close.
        """
        self._speak("Goodbye!")
        self._end_call()

    # =========================================================================
    # ESCAPE HATCH - Allows user to change their mind at any point
    # =========================================================================

    def _wants_to_escape(self, phrase: str, current_task: str) -> bool:
        """
        Check if user wants to abandon the current task.
        If yes, re-route them appropriately.

        Returns True if we handled the escape, False if we should continue normally.
        """
        prompt = PROMPT_DETECT_ESCAPE.format(current_task=current_task, user_input=phrase)
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip().upper()

        if "YES" in response:
            self._log(f"ESCAPE detected: user wants to change course")
            # Re-classify their new intent
            self._reset_and_listen()
            self._handle_listening(phrase)
            return True

        return False

    # =========================================================================
    # LLM NATURAL RESPONSE GENERATION
    # =========================================================================

    def _generate_natural_response(
        self,
        situation: str,
        user_input: str,
        required_info: str = "",
        fallback: str = ""
    ) -> str:
        """
        Generate a natural, empathetic response using the LLM.

        Args:
            situation: What's happening (e.g., "user wants to cancel shift")
            user_input: What the user said
            required_info: Information that MUST be included in the response
            fallback: Fallback message if LLM fails

        Returns:
            Generated natural response, or fallback if generation fails
        """
        prompt = f"""You are a friendly phone support agent for a staffing company. Generate a brief, natural response.

Situation: {situation}
User said: "{user_input}"
{f'You MUST include this information naturally: {required_info}' if required_info else ''}

Rules:
- Be empathetic and conversational (not robotic)
- Keep it SHORT (1-2 sentences max, under 30 words)
- Don't be overly formal or use corporate speak
- If the user mentions feeling unwell or has a problem, briefly acknowledge it
- End with the action you're taking or a question if needed

Response (just the text, nothing else):"""

        try:
            self.llm.set_system_prompt(prompt)
            response = self.llm.ask_llm(user_input).strip()

            # Remove quotes if the LLM wrapped the response in them
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]

            # Basic validation - if response is too long or empty, use fallback
            if not response or len(response) > 200:
                self._log(f"Natural response invalid, using fallback")
                return fallback if fallback else response[:200]

            return response

        except Exception as e:
            self._log(f"Natural response generation failed: {e}")
            return fallback

    # =========================================================================
    # LLM CLASSIFIER HELPER FUNCTIONS
    # =========================================================================

    def _classify_intent(self, phrase: str) -> str:
        """Classify user's intent into one of the predefined categories."""
        self.llm.set_system_prompt(PROMPT_CLASSIFY_INTENT)
        response = self.llm.ask_llm(phrase).strip().upper()

        # Extract just the category
        for category in ["CANCEL_SHIFT", "QUERY_SHIFT", "LOGIN_HELP", "REAL_PERSON", "END_CALL", "OTHER"]:
            if category in response:
                return category
        return "OTHER"

    def _detect_yes_no(self, phrase: str) -> str:
        """Detect if user said yes, no, or something unclear."""
        prompt = PROMPT_CONFIRM_YES_NO.format(user_input=phrase)
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip().upper()

        if "YES" in response:
            return "YES"
        elif "NO" in response:
            return "NO"
        return "UNCLEAR"

    def _extract_shift_selection(self, phrase: str, count: int) -> Optional[int]:
        """Extract which shift number the user selected (1-indexed)."""
        prompt = PROMPT_EXTRACT_SHIFT_NUMBER.format(count=count, user_input=phrase)
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip()

        # Try to extract a number
        match = re.search(r'\d+', response)
        if match:
            num = int(match.group())
            if 1 <= num <= count:
                return num
        return None

    def _has_date_info(self, phrase: str) -> bool:
        """Check if the user's phrase contains date/time information."""
        prompt = PROMPT_HAS_DATE_INFO.format(user_input=phrase)
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip().upper()
        return "YES" in response

    def _extract_date_info(self, phrase: str) -> str:
        """Extract date/time information from user's phrase."""
        prompt = PROMPT_EXTRACT_DATE_INFO.format(user_input=phrase)
        self.llm.set_system_prompt(prompt)
        response = self.llm.ask_llm(phrase).strip()
        return response

    # =========================================================================
    # BUSINESS LOGIC HELPER FUNCTIONS
    # =========================================================================

    def _handle_shift_request(self, phrase: str) -> None:
        """
        Handle a shift-related request (cancel or query).
        Checks if date info is present; if not, asks for clarification.
        """
        # Store the original query in case we need to combine it with date info later
        self.context['original_query'] = phrase

        # Check if the user provided date/time info
        has_date = self._has_date_info(phrase)
        self._log(f"HAS DATE INFO: {has_date}")

        if has_date:
            # Date info present - generate natural acknowledgment and fetch shifts
            action = "cancel" if self.context['is_cancellation'] else "check"
            response = self._generate_natural_response(
                situation=f"User wants to {action} a shift and provided a date/time",
                user_input=phrase,
                required_info="You will look up their shifts now",
                fallback="Let me look up your shifts."
            )
            self._speak(response)
            self._fetch_and_present_shifts(phrase)
        else:
            # No date info - generate natural response asking for date
            action = "cancel" if self.context['is_cancellation'] else "check"
            response = self._generate_natural_response(
                situation=f"User wants to {action} a shift but didn't specify which day",
                user_input=phrase,
                required_info="Ask which day they are referring to",
                fallback="Which day are you asking about?"
            )
            self._speak(response)
            self._transition_to(State.AWAITING_DATE_CLARIFICATION)


    def _fetch_and_present_shifts(self, query: str) -> None:
        """Fetch shifts from backend and present them to the user."""
        if not self.caller_phone:
            self._speak("I don't have your phone number on file. Please contact support.")
            self._reset_and_listen()
            return

        self._transition_to(State.FETCHING_SHIFTS)

        try:
            result = asyncio.run(test_integrated_workflow(self.caller_phone, query))

            if not result:
                self._speak("Sorry, I couldn't retrieve your shifts. Please try again later.")
                self._reset_and_listen()
                return

            shifts = result.get('filtered_shifts', [])
            self.context['shifts'] = shifts
            self.context['staff_info'] = result.get('staff', {})

            # Check if the backend detected cancellation intent
            reasoning = result.get('reasoning', '')
            if '<CNCL>' in reasoning:
                self.context['is_cancellation'] = True
            
            # No shift are found
            if len(shifts) == 0:
                self._speak("You don't have any shifts in that time period.")
                self._reset_and_listen()

            # Only one shift is found so we can skip the asking user for which shift they want 
            elif len(shifts) == 1:
                shift = shifts[0]
                self.context['selected_shift'] = shift

                if self.context['is_cancellation']:
                    self._speak(
                        f"You have one shift at {shift['client_name']} on {shift['date']} at {shift['time']}. "
                        f"Do you want to cancel this shift?"
                    )
                    self._transition_to(State.AWAITING_CONFIRMATION)
                else:
                    self._speak(f"You have a shift at {shift['client_name']} on {shift['date']} at {shift['time']}.")
                    self._transition_to(State.PRESENTING_SHIFTS)

            else:
                # Multiple shifts - list them
                response = f"You have {len(shifts)} shifts. "
                for i, shift in enumerate(shifts, 1):
                    response += f"Number {i}: {shift['client_name']} on {shift['date']} at {shift['time']}. "

                if self.context['is_cancellation']:
                    response += "Which one do you want to cancel?"
                else:
                    response += "Which one are you asking about?"

                self._speak(response)
                self._transition_to(State.PRESENTING_SHIFTS)

        except Exception as e:
            self._log(f"Shift fetch error: {e}")
            self._speak("Sorry, there was an error retrieving your shifts. Please try again.")
            self._reset_and_listen()


    def _submit_cancellation(self, shift: Dict[str, Any], reason: str) -> bool:
        """Submit the cancellation request (sends notification email)."""
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

            formatted_content = format_ezaango_shift_data(email_data, cancellation_reason=reason)

            # Uncomment to actually send email:
            # send_notify_email(content=formatted_content, custom_subject="SHIFT CANCELLATION REQUEST")

            self._log(f"Cancellation submitted for shift {shift.get('shift_id')}")
            return True

        except Exception as e:
            self._log(f"Cancellation error: {e}")
            return False

    # =========================================================================
    # STATE MANAGEMENT FUNCTIONS
    # =========================================================================

    def _transition_to(self, new_state: State) -> None:
        """Transition to a new state. Logs the transition for debugging."""
        self._log(f"TRANSITION: {self.state.name} → {new_state.name}")
        self.state = new_state

    def _reset_and_listen(self) -> None:
        """Reset context and go back to LISTENING state."""
        self.context = {
            'shifts': [],
            'selected_shift': None,
            'staff_info': {},
            'is_cancellation': False,
            'original_query': '',
        }
        self._transition_to(State.LISTENING)
        self._speak("Is there anything else I can help you with today?")

    # =========================================================================
    # I/O HELPER FUNCTIONS
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
        self.whisper_client = SystemAudioWhisperClient(
            model="base",
            phrase_timeout=5,
            on_phrase_complete=self.on_phrase_complete
        )

        try:
            self._speak("Hello. Thank you for calling Help at Hands Support. How can I help you today?")
            self._transition_to(State.LISTENING)
            self.whisper_client.start()

            self._log("Running (Ctrl+C to stop)")
            while True:
                sleep(1)

        except KeyboardInterrupt:
            self._log("Stopping...")
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

            self._speak("Hello. Thank you for calling Help at Hands Support. How can I help you today?")
            self._transition_to(State.LISTENING)
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
    assistant = CallAssistantV4()
    assistant.run()
