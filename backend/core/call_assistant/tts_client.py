import pyttsx3

# NOTE: Linux users must run "sudo apt-get install espeak-ng" for this to work

class TTSClient:
    def __init__(self, rate:int=150, volume:float=0.9) -> None:
        self.rate = rate
        self.volume = volume
        self.engine = pyttsx3.init()

        # Configure voice options
        self.engine.setProperty('rate', self.rate)  # Speech speed (wrds/min)
        self.engine.setProperty('volume', self. volume)

    def text_to_speech(self, text:str) -> None:
        # Say the text
        self.engine.say(text)
        self.engine.runAndWait()

if __name__ == "__main__":
    tts_client = TTSClient()
    tts_client.text_to_speech("Cancellation of job for a...Mr. Roberts at...4 PM on...Sunday...is confirmed. Staff has been notified")