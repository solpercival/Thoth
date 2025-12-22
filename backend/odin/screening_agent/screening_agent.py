from backend.whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from backend.thoth.core.call_assistant.tts_client import TTSClient
import threading

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


questions_dict: dict = {
    1 : "How are you today?",
    2 : "What is your full name?",
    3 : "Do you identify as a Aboriginal or Torres Strait Islanders?",
    4 : "What is your nationality?"
}

answers_dict: dict = {}

question_number: int = 1

# Use an event to control whiser pause and resume
answer_recieved = threading.Event()


# NOTE: SHOULD ONLY BE CALLED ONCE
def run() -> None:
    """
    Called to initate the screening flow
    """
    # Setup the clients
    global question_number
    tts_client: TTSClient = TTSClient()
    whisper_client: SystemAudioWhisperClient = SystemAudioWhisperClient(on_phrase_complete=_record_answer)

    # Read intro ductions
    tts_client.text_to_speech(INTRO)

    # Start the whisper client and pause it to standby
    whisper_client.start()
    whisper_client.pause() 

    while True:
        # 1. TTS question
        tts_client.text_to_speech(questions_dict[question_number])

        # 2. Whisper Client activate
        answer_recieved.clear()
        whisper_client.resume()

        # 3. Wait until phrase recorded
        answer_recieved.wait()

        # 4. Notify answer recorded
        whisper_client.pause()
        tts_client.text_to_speech(ANS_RECORDED)

        # 5. Increment the counter
        question_number += 1
        if question_number > len(questions_dict):
            break
        
        tts_client.text_to_speech(NEXT_QUESTION)
    

     # Read outro
    tts_client.text_to_speech(OUTRO)


    print(answers_dict)

    whisper_client.stop([])



def get_questions() -> dict:
    return questions_dict

def get_answers() -> dict:
    return answers_dict

def _record_answer(text: str) -> None:
    answers_dict[question_number] = text
    answer_recieved.set()


if __name__ == "__main__":
    run()