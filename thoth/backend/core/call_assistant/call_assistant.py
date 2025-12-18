import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from time import sleep
from threading import Event
from backend.core.call_assistant.system_audio_whisper_client import SystemAudioWhisperClient
from backend.core.call_assistant.llm_client import OllamaClient
from typing import Optional, Any

from backend.core.call_assistant.tts_client import TTSClient
from backend.core.email_agent.email_formatter import *
from backend.core.email_agent.email_sender import *
from backend.automation.test_integrated_workflow import test_integrated_workflow


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

# Own dependencies
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

FORMAT_SYSTEM_PROMPT = """
    You are a shift agent tasked with converting shift information in the form of dictionary to a normal sentence.
    Make sure there are no special characters like emojis.
    Example:
    "You have a shift with [client name] at [date]"
"""


class CallAssistant:
    """
    The main class that combines the transcript service/client and the sending to the LLM using the Ollama client
    """
    def __init__(self, caller_phone: Optional[str] = None):
        self.caller_phone = caller_phone  # Store caller phone number for context
        self.llm_client: OllamaClient = OllamaClient(model="qwen2.5:7b", system_prompt=LLM_SYSTEM_PROMPT)
        self.whisper_client: SystemAudioWhisperClient = None
        self.llm_response_array = []
        self.transcript = ""


    def on_phrase_complete(self, phrase:str) -> None:
        """
        Called when a phrase is completed on the whisper client

        Args:
            phrase (str): the transcript of the recorded phrase
        """

        print(f"[PHRASE COMPLETE]\n{phrase}")
        if self.caller_phone:
            print(f"[CALLER PHONE] {self.caller_phone}")
        
        self.transcript = phrase

        # Pause the whisper client, send phrase to LLM, and print response
        print("[SENDING TO LLM]")
        route_response = ""
        self.whisper_client.pause()
        try:
            llm_response = self.llm_client.ask_llm(phrase)
            print(f"[LLM RESPONSE]\n{llm_response}")
            self.llm_response_array.append(llm_response)
            
            # Route to appropriate action based on intent
            route_response = self._route_intent(llm_response)
        except Exception as e:
            print(f"[ERROR]\nLLM failed: {e}")


        # Send the results to the llm
        print("[SENDING AGENT DATA TO LLM]")
        #print_dict(route_response, "Results")
        print(route_response)
        self.llm_client.set_system_prompt(FORMAT_SYSTEM_PROMPT)
        llm_response = self.llm_client.ask_llm(route_response)

        print("[LLM PROCESSED RESPONSE]")
        print(llm_response)

        # Convert it to TTS and pipe it through 3CX
        print("[PLAYING LLM RESPONSE]")
        tts_client:TTSClient = TTSClient(output_device_name="CABLE Input")
        tts_client.text_to_speech("Thank you for waiting " + llm_response)

        # 

        # Resume the whisper client again
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


    def _route_intent(self, intent_tag: str) -> str:
        """
        Route the LLM intent to the appropriate handler.

        Args:
            intent_tag: One of <LOGIN>, <SHIFT>, <REAL>, <DENY>
        Return:
            script to be passed into tts
        """
        
        if "<SHIFT>" in intent_tag and self.caller_phone:
            print(f"[ROUTING] Shift check request for {self.caller_phone}")
            
            result:dict = asyncio.run(test_integrated_workflow(self.caller_phone, self.transcript))
            
            if result:
                # Extract the reasoning flag and separate it from the explanation
                reasoning_str = result.get('reasoning', 'Unknown')
                intention_flag = '<SHOW>'  # default
                reasoning_explanation = reasoning_str
                
                # Parse the reasoning string to extract flag
                if '<CNCL>' in reasoning_str:
                    intention_flag = '<CNCL>'
                    # Remove the flag from the explanation
                    reasoning_explanation = reasoning_str.replace('<CNCL>', '').strip()
                elif '<SHOW>' in reasoning_str:
                    intention_flag = '<SHOW>'
                    reasoning_explanation = reasoning_str.replace('<SHOW>', '').strip()
                
                # Format response as JSON with separate intention field
                formatted_response = {
                    'intention': intention_flag,
                    'reasoning': reasoning_explanation,
                    'staff': {
                        'name': result['staff']['full_name'],
                        'id': result['staff']['id'],
                        'email': result['staff']['email']
                    },
                    'date_range': {
                        'start_date': result['dates']['start_date'],
                        'end_date': result['dates']['end_date'],
                        'type': result['dates']['date_range_type']
                    },
                    'shifts_found': len(result['filtered_shifts']),
                    'shifts': [
                        {
                            'client': shift['client_name'],
                            'date': shift['date'],
                            'time': shift['time'],
                            'shift_id': shift['shift_id']
                        } for shift in result['filtered_shifts']
                    ]
                }
                
                #print(json.dumps(formatted_response, indent=2))
                return json.dumps(formatted_response)
            else:
                return json.dumps({'error': 'Failed to process shift request'})
        
        elif "<LOGIN>" in intent_tag:
            print(f"[ROUTING] Login assistance requested")
            return json.dumps({'intention': '<LOGIN>', 'message': "Please hold, You will be redirected for live assistance"})
        elif "<REAL>" in intent_tag:
            print(f"[ROUTING] Transfer to real agent")
            return json.dumps({'intention': '<REAL>', 'message': "Please hold, You will be redirected for live assistance"})
        else:
            print(f"[ROUTING] Request denied: {intent_tag}")
            return json.dumps({'intention': '<DENY>', 'message': 'Request cannot be processed'})

    def stop(self):
        """Stop the voice assistant"""
        self.is_running = False
        if self.whisper_client:
            self.whisper_client.stop(self.llm_response_array)


    def run_with_event(self, stop_event: Event):
        """
        Start the voice assistant with external stop control. Used in app.py.
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

