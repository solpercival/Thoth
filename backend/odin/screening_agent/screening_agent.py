from pathlib import Path
from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from thoth.core.call_assistant.tts_client import TTSClient
import threading
from datetime import date
import os

SYSTEM_PROMPT = """
You are an agent conducting a screening interview availability check. The question 
"Are you free to do a quick interview right now?" has already been asked. The first 
input you receive is the user's answer to that question.

RULES:
1. If the user clearly indicates YES (they are available now), output ONLY: <YES>
   
2. If the user indicates NO (not available now):
   - Ask them when they would be available for the interview
   - Keep asking until they provide a specific date and time
   - Once they provide a time, output: <NO> [date and time they are free]
   
3. If the response is unclear, ask for clarification.

OUTPUT FORMAT:
- For yes: <YES>
- For no with time: <NO> [their available date/time]

DO NOT output <YES> or <NO> until you have the required information.
"""

class ScreeningAgent:
    """
    A screening agent that conducts automated interviews by asking questions
    and recording answers using text-to-speech and speech recognition.
    """
    # Get the directory where this script is located
    _SCRIPT_DIR = Path(__file__).resolve().parent
    
    # File Paths
    QUESTION_FILE_PATH = _SCRIPT_DIR / "questions.txt"
    LOGS_FILE_PATH = _SCRIPT_DIR / "logs"

    # Class constants
    INTRO = """
Hello. We are going to ask you a few questions. Please only speak once the question has been fully read to you.
"""

    OUTRO = """
That concludes all the question we wanted to ask you.
Thank you for answering our questions. You're answers have been recorded and is awaiting review.
Good day.
"""

    ANS_RECORDED = """
Your answer has been recorded.
"""

    NEXT_QUESTION = """
 Next question.
"""


    def __init__(self, caller_id:str, caller_number:str):
        """
        Initialize the ScreeningAgent with a set of questions.

        :param questions: Dictionary of questions to ask (key: question number, value: question text)
        :type questions: dict, optional
        """


        # Register the questions
        self.questions_dict = self._question_dict_builder(self.QUESTION_FILE_PATH)
        print(self.questions_dict)

        self.answers_dict:dict = {}
        self.question_number:int = 1

        # Use an event to control whisper pause and resume
        self.answer_recieved = threading.Event()

        # Use an event to signal when stop is requested
        self._stop_requested = threading.Event()

        # Thread for running the agent
        self._agent_thread = None

        # Clients
        self.tts_client: TTSClient = None
        self.whisper_client: SystemAudioWhisperClient = None

        # Caller information
        self.caller_id:str = caller_id
        self.caller_number:str = caller_number

    def _run(self) -> None:
        """
        Internal method that runs the screening flow.
        Don't call this directly - use start() instead.
        """
        # Setup the clients
        self.tts_client = TTSClient()
        self.whisper_client = SystemAudioWhisperClient(on_phrase_complete=self._record_answer)

        # Read intro ductions
        self.tts_client.text_to_speech(self.INTRO)

        # Start the whisper client and pause it to standby
        self.whisper_client.start()
        self.whisper_client.pause()

        while True:
            # Check if stop was requested
            if self._stop_requested.is_set():
                break

            # 1. TTS question
            self.tts_client.text_to_speech(self.questions_dict[self.question_number])

            # 2. Whisper Client activate
            self.answer_recieved.clear()
            self.whisper_client.resume()

            # 3. Wait until phrase recorded (with timeout to allow checking stop)
            while not self.answer_recieved.wait(timeout=0.5):
                if self._stop_requested.is_set():
                    break

            # Check again if stop was requested during waiting
            if self._stop_requested.is_set():
                break

            # 4. Notify answer recorded
            self.whisper_client.pause()
            self.tts_client.text_to_speech(self.ANS_RECORDED)

            # 5. Increment the counter
            self.question_number += 1
            if self.question_number > len(self.questions_dict):
                break

            self.tts_client.text_to_speech(self.NEXT_QUESTION)

        # Only read outro and generate log if not stopped prematurely
        if not self._stop_requested.is_set():
            # Read outro
            self.tts_client.text_to_speech(self.OUTRO)

            # Generate log
            self._generate_log()

            print(self.answers_dict)

        # Clean up whisper client
        if self.whisper_client:
            self.whisper_client.stop([])

    def start(self) -> None:
        """
        Start the screening agent in a background thread.
        This allows you to call stop() later without blocking.
        """
        if self._agent_thread is not None and self._agent_thread.is_alive():
            raise RuntimeError("Agent is already running")

        self._agent_thread = threading.Thread(target=self._run)
        self._agent_thread.start()

    def stop(self) -> None:
        """
        Stop the screening agent gracefully.
        This will wait for the agent to finish cleanup before returning.
        """
        self._stop_requested.set()
        # Unblock the answer waiting loop
        self.answer_recieved.set()

        # Wait for the thread to finish if it exists
        if self._agent_thread is not None and self._agent_thread.is_alive():
            self._agent_thread.join(timeout=5.0)  # Wait up to 5 seconds

    def get_questions(self) -> dict:
        """
        Get the current questions dictionary.

        :return: Dictionary of questions
        :rtype: dict
        """
        return self.questions_dict

    def get_answers(self) -> dict:
        """
        Get the recorded answers dictionary.

        :return: Dictionary of answers
        :rtype: dict
        """
        return self.answers_dict

    def _record_answer(self, text: str) -> None:
        """
        To be passed into the whisper client as a callback function

        :param text: The phrase recorded by the whisper client
        :type text: str
        """
        self.answers_dict[self.question_number] = text
        self.answer_recieved.set()

    def _generate_log(self) -> None:
        """
        Generates a readable transcript of the conversation into the logs folder
        """

        # User caller phone number
        filename = self.caller_number + "-" + str(date.today()) + ".txt"

        output = "CALLER PHONE NO. = " + self.caller_number + "\n\n"

        for question_number in self.questions_dict:
            # The question
            output += str(question_number) + ". " + self.questions_dict[question_number] + "\n"

            # The answer
            output += "- " + self.answers_dict[question_number] + "\n\n"

        # Finally write to the file
        with open(self.LOGS_FILE_PATH + "/" + filename, "w") as file:
            file.write(output)


    def _question_dict_builder(self, filepath:str) -> dict:
        questions_dict:dict = {}

        # Open and read the file
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts: list[str] = line.split('. ', 1)

                if len(parts) == 2 and parts[0].isdigit():
                    questions_dict[int(parts[0])] = parts[1]
        
        return questions_dict
                    

if __name__ == "__main__":
    agent = ScreeningAgent("test_call_id", "555-1234")
    agent.start()

    # Keep the main thread alive
    try:
        agent._agent_thread.join()  # Wait for the agent to finish
    except KeyboardInterrupt:
        print("\nStopping agent...")
        agent.stop()
