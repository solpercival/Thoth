"""
Screening Agent V2 - LLM-Driven with 2-State State Machine

Design principles:
1. Only 2 states - LLM handles conversation flow within each state
2. LLM outputs tags to signal state transitions and actions
3. Chat history maintained - LLM has full context of conversation
4. LLM decides when answers are adequate (not hardcoded)

States:
    AVAILABILITY -> Check if user is free for questions
    INTERVIEW    -> Ask questions and evaluate answer adequacy

Tags:
    <INTER>           -> User is available, transition to INTERVIEW state
    <NO> date/time    -> User not available, record when they're free, end call
    <NEXT> answer     -> Answer is adequate, store it and move to next question
    <END>             -> User wants to end the call
"""

import sys
from pathlib import Path

# Add backend root to path for imports
backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))

from dotenv import load_dotenv
load_dotenv()

from enum import Enum, auto
from typing import Optional, Dict, Any, List
from datetime import date
import threading
import os
import re

from whisper_client.system_audio_whisper_fast_client import SystemAudioWhisperFastClient
from tts_client.tts_client import TTSClient
from ollama_client.llm_client import OllamaClient


# =============================================================================
# STATES
# =============================================================================

class State(Enum):
    """
    Conversation states for screening interview.

    Flow:
        AVAILABILITY ──[<INTER>]──> INTERVIEW ──[<NEXT>]──> (next question)
             │                           │                        │
             │                           └────[loop for clarity]──┘
             │
             └──[<NO> date]──> END CALL
    """
    AVAILABILITY = auto()  # Check if user can talk now
    INTERVIEW = auto()     # Conduct the interview questions


# =============================================================================
# TAGS - LLM outputs these to signal actions
# =============================================================================

class Tags:
    """Constants for LLM output tags."""
    INTER = "<INTER>"      # Transition to interview (user is available)
    NO = "<NO>"            # User not available (followed by date/time)
    NEXT = "<NEXT>"        # Answer adequate (followed by the answer)
    END = "<END>"          # End the call


# =============================================================================
# TTS SCRIPTS - Pre-written messages spoken by the agent
# =============================================================================

class Scripts:
    """Pre-written TTS scripts. Edit these to change what the agent says."""

    # Opening message - asks about availability
    INTRO = "Hello this is Help at Hands Calling! Do you have a moment for a few quick questions?"

    # Closing message - when all questions are answered
    OUTRO = "That concludes all the questions. Thank you for your time. I've recorded all your questions. Good day."

    # When no questions are loaded
    NO_QUESTIONS = "I don't have any questions to ask. Thank you for your time."

    # Error recovery message
    ERROR = "Sorry, I encountered an error. Let me try again."


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

AVAILABILITY_PROMPT = """You are conducting a screening interview availability check.

The user has just been asked: "Do you have a moment for a few quick questions?"

RULES:
1. If the user clearly indicates YES (they are available):
   - Output: <INTER>
   - Example: "Great, let's get started. <INTER>"

2. If the user indicates NO (not available now):
   - Ask them when they would be available
   - Keep asking until they provide a specific date and time
   - Once they provide a time, output: <NO> [date and time]
   - Example: "No problem. When would be a good time? ... <NO> Tomorrow at 2pm"

3. If the user wants to end the call entirely:
   - Output: <END>
   - Example: "I understand. Have a good day. <END>"

4. If the response is unclear, ask for clarification.

5. VOICEMAIL DETECTION: If the user's response sounds like a voicemail greeting or automated message (e.g. "please leave a message after the beep", "is not available right now", "the person you are calling", "voicemail", "record your message"), output <END> immediately. Do NOT leave a message or continue speaking.

CONVERSATION HISTORY:
{chat_history}

CRITICAL:
- Be conversational and polite
- Only output ONE tag per response
- Do NOT predict the user's next response
"""

INTERVIEW_PROMPT = """You are conducting a screening interview.

CURRENT QUESTION: {current_question}

YOUR GOAL:
- Evaluate if the user's answer adequately addresses the question
- If adequate: Output <NEXT> followed by their answer
- If inadequate: Ask clarifying questions to get more information

RULES:
1. When the answer is ADEQUATE (has enough information):
   - Output: <NEXT> [summary of their answer]
   - Example: "Thank you for that detail. <NEXT> User has 5 years of experience in nursing"

2. When the answer is INADEQUATE or unclear:
   - Ask a follow-up question to get more detail
   - Do NOT output any tag
   - Example: "Could you tell me more about your specific experience with that?"

3. If the user wants to end the call:
   - Output: <END>

WHAT MAKES AN ANSWER ADEQUATE:
- It directly addresses the question
- It provides specific information (not vague)
- It gives enough detail to be useful

CONVERSATION HISTORY:
{chat_history}

CRITICAL:
- Be conversational and encouraging
- Only output a tag when you have what you need
- Do NOT predict the user's next response
"""


# =============================================================================
# MAIN CLASS
# =============================================================================

class ScreeningAgentV2:
    """
    LLM-driven screening agent with 2-state machine.

    State 1 (AVAILABILITY): Check if user can talk
    State 2 (INTERVIEW): Ask questions, LLM evaluates answer adequacy
    """

    # Get the directory where this script is located
    _SCRIPT_DIR = Path(__file__).resolve().parent

    # File Paths
    QUESTION_FILE_PATH = _SCRIPT_DIR / "questions.txt"
    LOGS_FILE_PATH = _SCRIPT_DIR / "logs"

    def __init__(self, caller_id: str, caller_number: str):
        """
        Initialize the ScreeningAgentV2.

        :param caller_id: Unique identifier for this call
        :param caller_number: Phone number of the caller
        """
        # Caller information
        self.caller_id: str = caller_id
        self.caller_number: str = caller_number

        # Load questions
        self.questions: List[str] = self._load_questions(self.QUESTION_FILE_PATH)
        self.current_question_index: int = 0

        # Store answers (question -> answer)
        self.answers: Dict[int, str] = {}

        # If user not available, store when they're free
        self.callback_time: Optional[str] = None

        # Track how the call ended
        self.call_status: str = "In Progress"

        # Store last user utterance (for logging if interrupted)
        self.last_user_input: Optional[str] = None

        # State machine
        self.state: State = State.AVAILABILITY

        # Chat history for LLM context
        self.chat_history: List[Dict[str, str]] = []

        # Threading controls
        self._stop_requested = threading.Event()
        self._agent_thread: Optional[threading.Thread] = None

        # Clients (to be initialized in _run)
        self.tts_client = None
        self.whisper_client = None
        self.llm_client = None

    # =========================================================================
    # QUESTION LOADING
    # =========================================================================

    def _load_questions(self, filepath: Path) -> List[str]:
        """Load questions from file into a list."""
        questions = []

        if not filepath.exists():
            print(f"Warning: Questions file not found at {filepath}")
            return questions

        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse "1. Question text" format
                parts = line.split('. ', 1)
                if len(parts) == 2 and parts[0].isdigit():
                    questions.append(parts[1])

        return questions

    # =========================================================================
    # CHAT HISTORY
    # =========================================================================

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to chat history."""
        self.chat_history.append({"role": role, "content": content})

    def _format_chat_history(self) -> str:
        """Format chat history for the system prompt."""
        if not self.chat_history:
            return "No conversation yet."

        return "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in self.chat_history[-10:]  # Last 10 messages
        ])

    # =========================================================================
    # LLM RESPONSE PARSING
    # =========================================================================

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response for tags and extract data.

        Returns dict with:
        - 'tag': The tag found (INTER, NO, NEXT, END, or None)
        - 'data': Associated data (date for NO, answer for NEXT)
        - 'text': Text to speak (with tags removed)
        """
        result = {
            'tag': None,
            'data': None,
            'text': response
        }

        # Check for <END>
        if Tags.END in response:
            result['tag'] = 'END'
            result['text'] = response.replace(Tags.END, '').strip()
            return result

        # Check for <INTER>
        if Tags.INTER in response:
            result['tag'] = 'INTER'
            result['text'] = response.replace(Tags.INTER, '').strip()
            return result

        # Check for <NO> date/time
        no_match = re.search(r'<NO>\s*(.+?)(?:$|<)', response)
        if no_match:
            result['tag'] = 'NO'
            result['data'] = no_match.group(1).strip()
            result['text'] = re.sub(r'<NO>\s*.+?(?:$|<)', '', response).strip()
            return result

        # Check for <NEXT> answer
        next_match = re.search(r'<NEXT>\s*(.+?)(?:$|<)', response)
        if next_match:
            result['tag'] = 'NEXT'
            result['data'] = next_match.group(1).strip()
            result['text'] = re.sub(r'<NEXT>\s*.+?(?:$|<)', '', response).strip()
            return result

        return result

    # =========================================================================
    # LLM HELPERS
    # =========================================================================

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on current state."""
        chat_history = self._format_chat_history()

        if self.state == State.AVAILABILITY:
            return AVAILABILITY_PROMPT.format(chat_history=chat_history)
        else:  # INTERVIEW
            current_question = self.questions[self.current_question_index] if self.questions else "No questions loaded"
            return INTERVIEW_PROMPT.format(
                current_question=current_question,
                chat_history=chat_history
            )

    def _ask_llm(self, user_input: str) -> str:
        """Ask the LLM and get response."""
        system_prompt = self._build_system_prompt()
        self.llm_client.set_system_prompt(system_prompt)
        response = self.llm_client.ask_llm(user_input)
        return response.strip()

    # =========================================================================
    # I/O HELPERS
    # =========================================================================

    def _speak(self, text: str) -> None:
        """Convert text to speech."""
        self._log(f"ASSISTANT: {text}")
        if self.tts_client and text:
            self.tts_client.text_to_speech(text)

    def _log(self, message: str) -> None:
        """Log a message."""
        print(f"[SCREENING_V2] {message}")

    # =========================================================================
    # STATE HANDLERS
    # =========================================================================

    def _handle_availability(self, user_input: str) -> bool:
        """
        Handle user input in AVAILABILITY state.

        Returns True if conversation should continue, False if it should end.
        """
        # Add user input to history
        self._add_to_history("user", user_input)

        # Get LLM response
        llm_response = self._ask_llm(user_input)
        self._log(f"LLM: {llm_response}")

        # Parse the response
        parsed = self._parse_llm_response(llm_response)

        # Speak the text part (without tags)
        if parsed['text']:
            self._add_to_history("assistant", parsed['text'])
            self._speak(parsed['text'])

        # Handle tags
        if parsed['tag'] == 'END':
            self._log("User wants to end call")
            self.call_status = "Not Completed - User requested to stop"
            return False

        elif parsed['tag'] == 'NO':
            # User not available, store callback time
            self.callback_time = parsed['data']
            if self.callback_time:
                self.call_status = f"Unavailable - Callback: {self.callback_time}"
            else:
                self.call_status = "Unavailable - No callback provided"
            self._log(f"User not available. Callback time: {self.callback_time}")
            return False

        elif parsed['tag'] == 'INTER':
            # User is available, transition to INTERVIEW
            self._log("User is available. Transitioning to INTERVIEW state")
            self.state = State.INTERVIEW

            # Ask the first question
            if self.questions:
                first_question = self.questions[self.current_question_index]
                self._add_to_history("assistant", first_question)
                self._speak(first_question)
            else:
                self._speak(Scripts.NO_QUESTIONS)
                return False

        # No tag = continue conversation in same state
        return True

    def _handle_interview(self, user_input: str) -> bool:
        """
        Handle user input in INTERVIEW state.

        Returns True if conversation should continue, False if it should end.
        """
        # Add user input to history
        self._add_to_history("user", user_input)

        # Get LLM response
        llm_response = self._ask_llm(user_input)
        self._log(f"LLM: {llm_response}")

        # Parse the response
        parsed = self._parse_llm_response(llm_response)

        # Speak the text part (without tags)
        if parsed['text']:
            self._add_to_history("assistant", parsed['text'])
            self._speak(parsed['text'])

        # Handle tags
        if parsed['tag'] == 'END':
            self._log("User wants to end call")
            self.call_status = "Not Completed - User requested to stop"
            return False

        elif parsed['tag'] == 'NEXT':
            # Answer is adequate, store it and move to next question
            answer = parsed['data']
            self.answers[self.current_question_index] = answer
            self._log(f"Q{self.current_question_index + 1} answered: {answer}")

            # Move to next question
            self.current_question_index += 1

            # Check if there are more questions
            if self.current_question_index < len(self.questions):
                # Clear history for new question context (keep last few for continuity)
                self.chat_history = self.chat_history[-4:]

                # Ask the next question
                next_question = self.questions[self.current_question_index]
                self._add_to_history("assistant", next_question)
                self._speak(next_question)
            else:
                # All questions answered
                self._log("All questions answered")
                self.call_status = "Completed - All questions answered"
                self._speak(Scripts.OUTRO)
                return False

        # No tag = LLM is asking clarifying questions, continue in same state
        return True

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def _on_phrase_complete(self, phrase: str) -> None:
        """Callback when whisper detects a complete phrase."""
        # Stop if user wants to stop or call is dropped
        if self._stop_requested.is_set():
            return

        # Store last user input (for logging if interrupted)
        self.last_user_input = phrase

        self._log(f"USER: {phrase}")
        self._log(f"STATE: {self.state.name}")

        # Pause whisper while processing
        self.whisper_client.pause()

        try:
            # Route to appropriate state handler, state handlers return true if user wants to end the call,
            # False otherwise
            if self.state == State.AVAILABILITY:
                should_continue = self._handle_availability(phrase)
            else:  # INTERVIEW
                should_continue = self._handle_interview(phrase)

            # If there are any indication that we should stop the call, stop it
            if not should_continue:
                self._stop_requested.set()
                return

        except Exception as e:
            self._log(f"ERROR: {e}")
            self._speak(Scripts.ERROR)

        finally:
            # Resume whisper if still running
            if not self._stop_requested.is_set():
                self.whisper_client.resume()

    def _run(self) -> None:
        """Internal method that runs the screening flow."""
        # Initialize clients
        self.tts_client = TTSClient(output_device_name="CABLE Input")
        self.llm_client = OllamaClient(
            model=os.getenv("LLM_MODEL", "qwen3:8b"),
            system_prompt=""  # Will be set dynamically
        )
        self.whisper_client = SystemAudioWhisperFastClient(
            on_phrase_complete=self._on_phrase_complete
        )

        try:
            # Initial greeting - ask about availability
            self._add_to_history("assistant", Scripts.INTRO)
            self._speak(Scripts.INTRO)

            # Start whisper client
            self.whisper_client.start()

            # Wait until stop is requested
            while not self._stop_requested.is_set():
                self._stop_requested.wait(timeout=0.5)

        except KeyboardInterrupt:
            self._log("Interrupted by user")

        except Exception as e:
            self._log(f"Error in main loop: {e}")

        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up resources and generate log."""
        self._log("Cleaning up...")

        # Stop whisper client
        if self.whisper_client:
            try:
                self.whisper_client.stop([])
            except Exception as e:
                self._log(f"Error stopping whisper: {e}")

        # If status is still "In Progress", the call was interrupted
        if self.call_status == "In Progress":
            self.call_status = "Dropped - Unexpected interruption"

        # Always generate a log
        self._generate_log()

    def _generate_log(self) -> None:
        """Generate a log file with questions and answers."""
        # Ensure logs directory exists
        self.LOGS_FILE_PATH.mkdir(parents=True, exist_ok=True)

        filename = f"{self.caller_number}-{date.today()}.txt"
        filepath = self.LOGS_FILE_PATH / filename

        output = f"CALLER PHONE NO. = {self.caller_number}\n"
        output += f"CALLER ID = {self.caller_id}\n\n"

        # Write status
        output += f"STATUS: {self.call_status}\n"

        # If interrupted, show last thing the user said
        if self.call_status == "Dropped - Unexpected interruption" and self.last_user_input:
            output += f"LAST HEARD: {self.last_user_input}\n"

        output += "\n"

        # Write answers if any
        if self.answers:
            output += "ANSWERS:\n"
            output += "-" * 40 + "\n"
            for idx, answer in self.answers.items():
                question = self.questions[idx] if idx < len(self.questions) else "Unknown question"
                output += f"{idx + 1}. {question}\n"
                output += f"   Answer: {answer}\n\n"
        else:
            output += "ANSWERS: None recorded\n"

        # Write full chat history
        if self.chat_history:
            output += "\n"
            output += "FULL CHAT HISTORY:\n"
            output += "=" * 40 + "\n"
            for msg in self.chat_history:
                output += f"{msg['role'].upper()}: {msg['content']}\n"
            output += "=" * 40 + "\n"

        with open(filepath, "w") as f:
            f.write(output)

        self._log(f"Log saved to {filepath}")

    def start(self) -> None:
        """Start the screening agent in a background thread."""
        if self._agent_thread is not None and self._agent_thread.is_alive():
            raise RuntimeError("Agent is already running")

        self._agent_thread = threading.Thread(target=self._run)
        self._agent_thread.start()

    def stop(self) -> None:
        """Stop the screening agent gracefully."""
        self._log("Stop requested")
        self._stop_requested.set()

        if self._agent_thread is not None and self._agent_thread.is_alive():
            self._agent_thread.join(timeout=5.0)

        self._log("Agent stopped")

    # =========================================================================
    # GETTERS
    # =========================================================================

    def get_questions(self) -> List[str]:
        """Get the list of questions."""
        return self.questions

    def get_answers(self) -> Dict[int, str]:
        """Get the recorded answers."""
        return self.answers

    def get_callback_time(self) -> Optional[str]:
        """Get the callback time if user was not available."""
        return self.callback_time


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import signal

    agent = ScreeningAgentV2("test_call_id", "555-1234")

    # Signal handler for clean shutdown
    def signal_handler(_sig, _frame):
        print("\nStopping agent...")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"Loaded {len(agent.questions)} questions:")
    for i, q in enumerate(agent.questions, 1):
        print(f"  {i}. {q}")
    print(f"\nStarting agent... (Ctrl+C to stop)")

    agent.start()

    # Keep the main thread alive with periodic timeout to allow Ctrl+C
    try:
        while agent._agent_thread and agent._agent_thread.is_alive():
            agent._agent_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\nStopping agent...")
        agent.stop()
