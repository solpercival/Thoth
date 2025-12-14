from time import sleep
from threading import Event
from system_audio_whisper_client import SystemAudioWhisperClient
from llm_client import OllamaClient
from typing import Optional

LLM_SYSTEM_PROMPT = """THIS IS IMPORTANT THAT YOU FOLLOW THE OUTPUTS EXACTLY. You are a call center routing agent. Your ONLY job is to classify user requests and output exactly ONE of the following tags. You must NEVER write explanations, stories, or any other text.

CLASSIFICATION RULES:
- If user asks about app login issues → output: <LOGIN>
- If user asks about their work shift/schedule → output: <SHIFT>
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


class CallAssistant:
    """
    The main class that combines the transcript service/client and the sending to the LLM using the Ollama client
    """
    def __init__(self, caller_phone: Optional[str] = None):
        self.caller_phone = caller_phone  # Store caller phone number for context
        self.llm_client: OllamaClient = OllamaClient(model="gemma3:1b", system_prompt=LLM_SYSTEM_PROMPT)
        self.whisper_client: SystemAudioWhisperClient = None
        self.llm_response_array = []


    def on_phrase_complete(self, phrase:str) -> None:
        """
        Called when a phrase is completed on the whisper client

        Args:
            phrase (str): the transcript of the recorded phrase
        """

        print(f"[PHRASE COMPLETE]\n{phrase}")
        if self.caller_phone:
            print(f"[CALLER PHONE] {self.caller_phone}")

        # Pause the whisper client, send phrase to LLM, and print response
        print("[SENDING TO LLM]")
        self.whisper_client.pause()
        try:
            llm_response = self.llm_client.ask_llm(phrase)
            print(f"[LLM RESPONSE]\n{llm_response}")
            self.llm_response_array.append(llm_response)
            
            # Route to appropriate action based on intent
            self._route_intent(llm_response)
        except Exception as e:
            print(f"[ERROR]\nLLM failed: {e}")

        # Resume the whisper client again once we the response was recieved
        self.whisper_client.resume()


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
            print("\nVoice Assistant running. Press Ctrl+C to stop.\n")
            while True:
                sleep(1)
                
        except KeyboardInterrupt:
            print("\n\nStopping Voice Assistant...")
            self.whisper_client.stop(self.llm_response_array)


    def _route_intent(self, intent_tag: str) -> None:
        """
        Route the LLM intent to the appropriate handler.
        
        Args:
            intent_tag: One of <LOGIN>, <SHIFT>, <REAL>, <DENY>
        """
        if "<SHIFT>" in intent_tag and self.caller_phone:
            print(f"[ROUTING] Shift check request for {self.caller_phone}")
            # Would trigger shift checking here (async integration)
            # await check_shifts_for_caller(service_name="hahs_vic3495", caller_phone=self.caller_phone)
        elif "<LOGIN>" in intent_tag:
            print(f"[ROUTING] Login assistance requested")
            # Would trigger login flow here
        elif "<REAL>" in intent_tag:
            print(f"[ROUTING] Transfer to real agent")
            # Would trigger agent transfer here
        else:
            print(f"[ROUTING] Request denied: {intent_tag}")

    def stop(self):
        """Stop the voice assistant"""
        self.is_running = False
        if self.whisper_client:
            self.whisper_client.stop(self.llm_response_array)


    def run_with_event(self, stop_event: Event):
        """
        Start the voice assistant with external stop control.
        """
        try:
            self.whisper_client = SystemAudioWhisperClient(
                model="base",
                phrase_timeout=5,
                on_phrase_complete=self.on_phrase_complete
            )
            
            self.whisper_client.start()
            print("\nVoice Assistant running. Waiting for stop signal.\n")
            
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
    assistant = CallAssistant()
    assistant.run()       

