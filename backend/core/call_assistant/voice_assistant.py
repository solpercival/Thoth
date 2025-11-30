from time import sleep
from system_audio_whisper_client import SystemAudioWhisperClient
from llm_client import OllamaClient


class VoiceAssistant:
    """
    The main class that combines the transcript service/client and the sending to the LLM using the Ollama client
    """
    def __init__(self):
        self.llm_client: OllamaClient = OllamaClient(model="gemma3:1b")
        self.whisper_client: SystemAudioWhisperClient = None
        self.llm_response_array = []


    def on_phrase_complete(self, phrase:str) -> None:
        """
        Called when a phrase is completed on the whisper client

        Args:
            phrase (str): the transcript of the recorded phrase
        """

        print(f"[PHRASE COMPLETE]\n{phrase}")

        # Pause the whisper client, send phrase to LLM, and print response
        print("[SENDING TO LLM]")
        self.whisper_client.pause()
        try:
            llm_response = self.llm_client.ask_llm(phrase)
            print(f"[LLM RESPONSE]\n{llm_response}")
            self.llm_response_array.append(llm_response)
        except Exception as e:
            print(f"[ERROR]\nLLM failed: {e}")

        # Resume the whisper client again once we the response was recieved
        self.whisper_client.resume()


    def run(self):
        """Start the voice assistant"""
        # Create whisper client with callback
        self.whisper_client = SystemAudioWhisperClient(
            model="base",
            phrase_timeout=3,
            on_phrase_complete=self.on_phrase_complete  # Pass callback
        )
        
        try:
            self.whisper_client.start()
            
            # Keep running until interrupted
            print("\nVoice Assistant running. Press Ctrl+C to stop.\n")
            while True:
                sleep(1)
                
        except KeyboardInterrupt:
            print("\n\nStopping Voice Assistant...")
            self.whisper_client.stop(self.llm_response_array)


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()       

