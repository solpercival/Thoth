import argparse
import os
import numpy as np
import speech_recognition as sr
import whisper_client
import torch
import threading

from datetime import datetime, timedelta
from queue import Queue
from time import sleep
from sys import platform



class WhisperClient:
    """
    Usage: 
    WhisperClient.start() - start the transcription 
    WhisperClient.get_transcript() - get the words already transcripted
    WhisperClient.stop() - stop transcribing
    NOTE:
    By default we are listening from microphone, but it can be set to listen to system audio by setting the 
    use_system_audio flag to True in constructor
    """
    def __init__(self, model="medium", non_english=False, energy_threshold=1000,
                 record_timeout=2, phrase_timeout=3, default_microphone='pulse'):
        """
        Initialize the transcription service.
        
        Args:
            model: Whisper model to use (tiny, base, small, medium, large)
            non_english: Whether to use non-English model
            energy_threshold: Energy level for mic to detect
            record_timeout: How real time the recording is in seconds
            phrase_timeout: Empty space between recordings before new line
            default_microphone: Default microphone name (for Linux)
        """
        self.model_name = model
        self.non_english = non_english
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.phrase_timeout = phrase_timeout
        self.default_microphone = default_microphone
        
        # State variables
        self.phrase_time = None
        self.data_queue = Queue()
        self.phrase_bytes = bytes()
        self.transcription = ['']
        self.is_running = False
        self.transcription_thread = None
        
        # Audio components (initialized in start())
        self.recorder = None
        self.source = None
        self.audio_model = None
        
    def _initialize_audio(self):
        """Initialize audio components."""
        # Setup speech recognizer
        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = self.energy_threshold
        self.recorder.dynamic_energy_threshold = False
        
        # Setup microphone
        if 'linux' in platform:
            mic_name = self.default_microphone
            if not mic_name or mic_name == 'list':
                print("Available microphone devices are: ")
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    print(f"Microphone with name \"{name}\" found")
                raise ValueError("Please specify a valid microphone name")
            else:
                found = False
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    if mic_name in name:
                        self.source = sr.Microphone(sample_rate=16000, device_index=index)
                        found = True
                        break
                if not found:
                    raise ValueError(f"Microphone '{mic_name}' not found")
        else:
            self.source = sr.Microphone(sample_rate=16000)
        
        # Load Whisper model
        model = self.model_name
        if self.model_name != "large" and not self.non_english:
            model = model + ".en"
        print(f"Loading Whisper model: {model}")
        self.audio_model = whisper_client.load_model(model)
        print("Model loaded.")
        
        # Adjust for ambient noise
        with self.source:
            self.recorder.adjust_for_ambient_noise(self.source)
    
    def _record_callback(self, _, audio: sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.
        """
        data = audio.get_raw_data()
        self.data_queue.put(data)
    
    def _transcription_loop(self):
        """Main transcription loop that runs in a separate thread."""
        while self.is_running:
            try:
                now = datetime.utcnow()
                
                if not self.data_queue.empty():
                    phrase_complete = False
                    
                    # Check if phrase is complete
                    if self.phrase_time and now - self.phrase_time > timedelta(seconds=self.phrase_timeout):
                        self.phrase_bytes = bytes()
                        phrase_complete = True
                    
                    self.phrase_time = now
                    
                    # Combine audio data from queue
                    audio_data = b''.join(self.data_queue.queue)
                    self.data_queue.queue.clear()
                    
                    # Add to accumulated phrase data
                    self.phrase_bytes += audio_data
                    
                    # Convert to numpy array
                    audio_np = np.frombuffer(self.phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    # Transcribe
                    result = self.audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                    text = result['text'].strip()
                    
                    # Update transcription
                    if phrase_complete:
                        self.transcription.append(text)
                    else:
                        self.transcription[-1] = text
                    
                    # Display transcription
                    self._display_transcription()
                else:
                    sleep(0.25)
                    
            except Exception as e:
                if self.is_running:  # Only print error if we're supposed to be running
                    print(f"Error in transcription loop: {e}")
                break
    
    def _display_transcription(self):
        """Clear console and display current transcription."""
        os.system('cls' if os.name == 'nt' else 'clear')
        for line in self.transcription:
            print(line)
        print('', end='', flush=True)
    
    def start(self):
        """Start the transcription service."""
        if self.is_running:
            print("Transcription service is already running!")
            return
        
        print("Starting transcription service...")
        
        # Initialize audio components
        self._initialize_audio()
        
        # Reset state
        self.phrase_time = None
        self.data_queue = Queue()
        self.phrase_bytes = bytes()
        self.transcription = ['']
        self.is_running = True
        
        # Start background recording
        self.recorder.listen_in_background(
            self.source,
            self._record_callback,
            phrase_time_limit=self.record_timeout
        )
        
        # Start transcription thread
        self.transcription_thread = threading.Thread(target=self._transcription_loop, daemon=True)
        self.transcription_thread.start()
        
        print("Transcription service started. Listening...")
    
    def stop(self):
        """Stop the transcription service."""
        if not self.is_running:
            print("Transcription service is not running!")
            return
        
        print("\nStopping transcription service...")
        self.is_running = False
        
        # Wait for transcription thread to finish
        if self.transcription_thread:
            self.transcription_thread.join(timeout=2)
        
        print("\nFinal Transcription:")
        for line in self.transcription:
            print(line)
        
        print("Transcription service stopped.")
    
    def get_transcription(self):
        """Get the current transcription as a list of strings."""
        return self.transcription.copy()
    
    def get_transcription_text(self):
        """Get the current transcription as a single string."""
        return '\n'.join(self.transcription)
    
    def clear_transcription(self):
        """Clear the current transcription."""
        self.transcription = ['']
        self._display_transcription()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="medium", help="Model to use",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
    parser.add_argument("--energy_threshold", default=1000,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=2,
                        help="How real time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=3,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    if 'linux' in platform:
        parser.add_argument("--default_microphone", default='pulse',
                            help="Default microphone name for SpeechRecognition. "
                                 "Run this with 'list' to view available Microphones.", type=str)
    args = parser.parse_args()
    
    # Create service
    service = WhisperClient(
        model=args.model,
        non_english=args.non_english,
        energy_threshold=args.energy_threshold,
        record_timeout=args.record_timeout,
        phrase_timeout=args.phrase_timeout,
        default_microphone=args.default_microphone if 'linux' in platform else None
    )
    
    # Start service
    service.start()
    
    try:
        # Keep main thread alive
        while True:
            sleep(1)
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
