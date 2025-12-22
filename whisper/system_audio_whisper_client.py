import argparse
import os
import numpy as np
import speech_recognition as sr
import whisper
import torch
import threading
import platform

# Suppress ALSA warnings on Linux
from ctypes import *
from contextlib import contextmanager

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    try:
        asound = cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
    except:
        yield
    finally:
        try:
            asound.snd_lib_error_set_handler(None)
        except:
            pass

# Import pyaudio with ALSA errors suppressed
with noalsaerr():
    import pyaudio

from datetime import datetime, timedelta
from queue import Queue
from time import sleep
from sys import platform as sys_platform


class SystemAudioWhisperClient:
    """
    WhisperClient modified to transcribe system audio instead of microphone.
    
    Usage: 
    client = SystemAudioWhisperClient(on_phrase_complete=callback_function)
    client.start() - start the transcription 
    client.pause() - pause transcription
    client.resume() - resume transcription
    client.stop() - stop transcribing
    """
    def __init__(self, model="medium", non_english=False, energy_threshold=1000,
                 record_timeout=0.5, phrase_timeout=5, on_phrase_complete=None,
                 silence_threshold=0.01, max_phrase_duration=15, audio_source=None):
        """
        Initialize the transcription service.
        
        Args:
            model: Whisper model to use (tiny, base, small, medium, large)
            non_english: Whether to use non-English model
            energy_threshold: Energy level to detect audio (not used for system audio, kept for compatibility)
            record_timeout: How real time the recording is in seconds
            phrase_timeout: Empty space between recordings before new line
            on_phrase_complete: Callback function(text) called when a phrase is complete
            silence_threshold: Audio level below this is considered silence (0-1 range), increase if ends to early, vice versa
            max_phrase_duration: Maximum duration in seconds before forcing phrase completion (default: 30)
            audio_source: Specific audio source name to use (Linux only). If None, uses auto-detection.
                         Examples: 'virtual_speaker.monitor', 'alsa_output.usb-GN_Audio_A_S_Jabra_Evolve2_30*.monitor'
        """
        self.model_name = model
        self.non_english = non_english
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.phrase_timeout = phrase_timeout
        self.max_phrase_duration = max_phrase_duration
        self.on_phrase_complete = on_phrase_complete
        self.silence_threshold = silence_threshold
        self.audio_source = audio_source  # Fixed audio source (no dynamic switching)
        
        # State variables
        self.last_speech_time = None
        self.phrase_start_time = None  # NEW: track when current phrase started
        self.data_queue = Queue()
        self.phrase_bytes = bytes()
        self.transcription = ['']
        self.last_transcription = ''
        self.is_running = False
        self.is_paused = False
        self.transcription_thread = None
        self.audio_capture_thread = None
        
        # Audio components
        self.pyaudio_instance = None
        self.stream = None
        self.audio_model = None
        self.device_info = None
        self.current_source = None
        self.source_channels = 2  # Default to stereo
        self.source_sample_rate = 44100  # Default sample rate
        self.source_check_thread = None
        self.last_source_check = 0
        
    def _get_system_audio_device(self):
        """Get the appropriate system audio device based on OS"""
        with noalsaerr():
            p = pyaudio.PyAudio()
        
        system = platform.system()
        
        if system == "Windows":
            try:
                import pyaudiowpatch as pyaudio_patch
                p_patch = pyaudio_patch.PyAudio()
                
                # Get default WASAPI loopback device
                wasapi_info = p_patch.get_host_api_info_by_type(pyaudio_patch.paWASAPI)
                default_speakers = p_patch.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                
                if not default_speakers["isLoopbackDevice"]:
                    for loopback in p_patch.get_loopback_device_info_generator():
                        if default_speakers["name"] in loopback["name"]:
                            default_speakers = loopback
                            break
                
                p.terminate()
                return p_patch, default_speakers
            except ImportError:
                print("For Windows, install: pip install pyaudiowpatch")
                p.terminate()
                raise
        
        elif system == "Linux":
            # Fixed source strategy - use specified source or Jabra as default for production
            import subprocess
            
            selected_source = None
            
            # If audio_source is specified, use it directly
            if self.audio_source:
                print(f"Using specified audio source: {self.audio_source}")
                selected_source = self.audio_source
            else:
                # Default strategy: Look for Jabra Evolve2 monitor for production calls
                result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                                    capture_output=True, text=True)
                
                jabra_source = None
                
                for line in result.stdout.strip().split('\n'):
                    if not line or line.startswith('#'):
                        continue
                        
                    parts = line.split()
                    if len(parts) >= 2:
                        source_name = parts[1]
                        
                        # Look for Jabra Evolve2 monitor (production audio)
                        if 'jabra' in source_name.lower() and 'evolve2' in source_name.lower() and 'monitor' in source_name.lower():
                            jabra_source = source_name
                            print(f"Found Jabra Evolve2 audio source: {source_name}")
                            break
                
                selected_source = jabra_source
                
                if not selected_source:
                    print("⚠️  Jabra Evolve2 not found, using system default")
            
            if selected_source:
                print(f"Setting audio source: {selected_source}")
                subprocess.run(['pactl', 'set-default-source', selected_source])
                os.environ['PULSE_SOURCE'] = selected_source
                self.current_source = selected_source
                
                # Get actual channel count and sample rate from the source
                self._update_source_info(selected_source)
            else:
                print("Using system default audio source")
                self.current_source = None
            
            # Find the 'pulse' device in PyAudio
            pulse_device = None
            
            with noalsaerr():
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info['name'] == 'pulse' and info['maxInputChannels'] > 0:
                        pulse_device = info
                        break
            
            if pulse_device is None:
                print("No PulseAudio device found in PyAudio")
                p.terminate()
                raise ValueError("No pulse device found")
            
            return p, pulse_device
        
        else:
            print(f"Unsupported platform: {system}")
            p.terminate()
            raise ValueError(f"Unsupported platform: {system}")
    
    def _initialize_audio(self):
        """Initialize audio components."""
        # Get system audio device
        self.pyaudio_instance, self.device_info = self._get_system_audio_device()
        
        print(f"Using audio device: {self.device_info['name']}")
        
        # Load Whisper model
        model = self.model_name
        if self.model_name != "large" and not self.non_english:
            model = model + ".en"
        print(f"Loading Whisper model: {model}")
        self.audio_model = whisper.load_model(model)
        print("Model loaded.")
    
    def _update_source_info(self, source_name):
        """Get channel count and sample rate from PulseAudio source"""
        import subprocess
        try:
            # Parse from pactl list sources short output (format: s16le 2ch 48000Hz)
            result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                                capture_output=True, text=True, timeout=1)
            
            for line in result.stdout.strip().split('\n'):
                if source_name in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        # Extract channel count (e.g., "2ch" -> 2)
                        channels_str = parts[3]
                        if 'ch' in channels_str:
                            self.source_channels = int(channels_str.replace('ch', ''))
                        
                        # Extract sample rate (e.g., "48000Hz" -> 48000)
                        rate_str = parts[4] if len(parts) > 4 else '44100Hz'
                        if 'Hz' in rate_str:
                            self.source_sample_rate = int(rate_str.replace('Hz', ''))
                        
                        print(f"Source info: {self.source_channels}ch @ {self.source_sample_rate}Hz")
                        break
        except Exception as e:
            print(f"Could not get source info, using defaults: {e}")
            self.source_channels = 2
            self.source_sample_rate = 44100
    
    def _open_audio_stream(self):
        """Open the audio stream with current device settings"""
        # On Linux with pulse device, use actual source channels
        if platform.system() == "Linux" and self.device_info["name"] == "pulse":
            channels = self.source_channels
            rate = self.source_sample_rate
        else:
            channels = int(self.device_info["maxInputChannels"])
            rate = int(self.device_info["defaultSampleRate"])

        self.stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=1024,
            input_device_index=self.device_info["index"]
        )
        
        print(f"Audio capture started (rate: {rate}Hz, channels: {channels})")
    
    def _audio_capture_loop(self):
        """Capture audio from active audio source and put into queue."""
        try:
            # Open initial stream
            target_rate = 16000
            
            self._open_audio_stream()
            
            while self.is_running:
                # Get current stream settings (use actual source channels)
                if platform.system() == "Linux" and self.device_info["name"] == "pulse":
                    channels = self.source_channels
                    source_rate = self.source_sample_rate
                else:
                    channels = int(self.device_info["maxInputChannels"])
                    source_rate = int(self.device_info["defaultSampleRate"])
                    
                # Only capture audio if not paused
                if not self.is_paused:
                    # Read audio data
                    data = self.stream.read(1024, exception_on_overflow=False)
                    
                    # Convert to numpy array
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    
                    # If stereo, convert to mono by averaging channels
                    if channels > 1:
                        audio_array = audio_array.reshape(-1, channels)
                        audio_array = audio_array.mean(axis=1).astype(np.int16)
                    
                    # Resample to 16kHz if needed
                    if source_rate != target_rate:
                        # Simple resampling (you might want to use a library like resampy for better quality)
                        num_samples = int(len(audio_array) * target_rate / source_rate)
                        audio_array = np.interp(
                            np.linspace(0, len(audio_array), num_samples),
                            np.arange(len(audio_array)),
                            audio_array
                        ).astype(np.int16)
                    
                    # Check audio level to detect speech vs silence
                    audio_float = audio_array.astype(np.float32) / 32768.0
                    audio_level = np.sqrt(np.mean(audio_float**2))
                    
                    # Convert back to bytes and add to queue with level info
                    self.data_queue.put({
                        'data': audio_array.tobytes(),
                        'level': audio_level,
                        'timestamp': datetime.utcnow()
                    })
                else:
                    # When paused, just sleep a bit
                    sleep(0.1)
                
        except Exception as e:
            if self.is_running:
                print(f"Error in audio capture loop: {e}")
                import traceback
                traceback.print_exc()
    
    def _transcription_loop(self):
        """Main transcription loop that runs in a separate thread."""
        while self.is_running:
            try:
                # Skip processing if paused
                if self.is_paused:
                    sleep(0.25)
                    continue
                
                now = datetime.utcnow()
                
                if not self.data_queue.empty():
                    # Get all audio chunks from queue
                    chunks = []
                    has_speech = False
                    latest_timestamp = None
                    
                    while not self.data_queue.empty():
                        chunk = self.data_queue.get()
                        
                        # Check if this chunk contains speech (above silence threshold)
                        if chunk['level'] > self.silence_threshold:
                            has_speech = True
                            self.last_speech_time = chunk['timestamp']
                            chunks.append(chunk['data'])  # Only add if above threshold
                        
                        latest_timestamp = chunk['timestamp']
                    
                    # Only process if we actually have speech chunks
                    if chunks:
                        # Combine all audio data
                        audio_data = b''.join(chunks)
                        
                        # Track when phrase started
                        if not self.phrase_bytes:
                            self.phrase_start_time = now
                        
                        # Add to accumulated phrase data
                        self.phrase_bytes += audio_data
                    
                    # Convert to numpy array
                    if self.phrase_bytes:
                        audio_np = np.frombuffer(self.phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                        
                        # Only transcribe if we have enough audio (at least 0.5 seconds)
                        if len(audio_np) > 8000:  # 0.5 seconds at 16kHz
                            # Transcribe
                            result = self.audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                            text = result['text'].strip()
                            
                            # Only update display if text actually changed
                            if text != self.last_transcription:
                                self.transcription[-1] = text
                                self.last_transcription = text
                                self._display_transcription()
                            
                            # Check if phrase has exceeded maximum duration
                            if self.phrase_start_time:
                                phrase_duration = (now - self.phrase_start_time).total_seconds()
                                if phrase_duration >= self.max_phrase_duration:
                                    text = self.transcription[-1]
                                    print(f"\n[Max duration {self.max_phrase_duration}s reached - sending phrase]")
                                    self.transcription.append('')
                                    
                                    if text and self.on_phrase_complete:
                                        self.on_phrase_complete(text)
                                    
                                    # Reset for next phrase
                                    self.phrase_bytes = bytes()
                                    self.last_speech_time = None
                                    self.phrase_start_time = None
                                    self.last_transcription = ''
                                    continue  # Skip the silence check below
                            
                            # Check immediately after transcription if we should finalize
                            if self.last_speech_time and not has_speech:
                                silence_duration = (now - self.last_speech_time).total_seconds()
                                if silence_duration >= self.phrase_timeout:
                                    # Use the existing transcription without re-transcribing
                                    text = self.transcription[-1]
                                    
                                    print(f"\n[Detected complete phrase after {silence_duration:.1f}s silence]")
                                    self.transcription.append('')
                                    
                                    if text and self.on_phrase_complete:
                                        self.on_phrase_complete(text)
                                    
                                    # Reset for next phrase
                                    self.phrase_bytes = bytes()
                                    self.last_speech_time = None
                                    self.phrase_start_time = None
                                    self.last_transcription = ''
                else:
                    # Queue is empty - check if we need to finalize
                    if self.last_speech_time and self.phrase_bytes:
                        silence_duration = (now - self.last_speech_time).total_seconds()
                        if silence_duration >= self.phrase_timeout:
                            # Use existing transcription
                            text = self.transcription[-1]
                            
                            print(f"\n[Detected complete phrase after {silence_duration:.1f}s silence]")
                            self.transcription.append('')
                            
                            if text and self.on_phrase_complete:
                                self.on_phrase_complete(text)
                            
                            # Reset for next phrase
                            self.phrase_bytes = bytes()
                            self.last_speech_time = None
                            self.phrase_start_time = None
                            self.last_transcription = ''
                    
                    sleep(0.1)
                        
            except Exception as e:
                if self.is_running:
                    print(f"Error in transcription loop: {e}")
                    import traceback
                    traceback.print_exc()
                break
    
    def _display_transcription(self):
        """Clear console and display current transcription."""
        os.system('cls' if os.name == 'nt' else 'clear')
        for line in self.transcription:
            print(line)
        print('', end='', flush=True)
    
    def pause(self):
        """Pause transcription (stops capturing/processing audio)"""
        self.is_paused = True
        # Clear any accumulated audio data
        while not self.data_queue.empty():
            self.data_queue.get()
        self.phrase_bytes = bytes()
        self.last_speech_time = None
        self.phrase_start_time = None
        print("Transcription service is paused")
    
    def resume(self):
        """Resume transcription"""
        self.is_paused = False
        self.last_transcription = ''
        self.phrase_bytes = bytes()
        self.last_speech_time = None
        self.phrase_start_time = None
        # Clear the queue
        while not self.data_queue.empty():
            self.data_queue.get()
        print("Transcription service is resumed")
    
    def start(self):
        """Start the transcription service."""
        if self.is_running:
            print("Transcription service is already running!")
            return
        
        print("Starting system audio transcription service...")
        
        # Initialize audio components
        self._initialize_audio()
        
        # Reset state
        self.last_speech_time = None
        self.phrase_start_time = None
        self.data_queue = Queue()
        self.phrase_bytes = bytes()
        self.transcription = ['']
        self.last_transcription = ''
        self.is_running = True
        self.is_paused = False
        
        # Start audio capture thread
        self.audio_capture_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_capture_thread.start()
        
        # Start transcription thread
        self.transcription_thread = threading.Thread(target=self._transcription_loop, daemon=True)
        self.transcription_thread.start()
        
        print("Transcription service started. Listening to system audio...")
    
    def stop(self, llm_response_array):
        """Stop the transcription service."""
        if not self.is_running:
            print("Transcription service is not running!")
            return
        
        print("\nStopping transcription service...")
        self.is_running = False
        
        # Wait for threads to finish
        if self.audio_capture_thread:
            self.audio_capture_thread.join(timeout=2)
        if self.transcription_thread:
            self.transcription_thread.join(timeout=2)
        
        # Close audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            
        
        print("\nFinal Transcription:")
        llm_res_len = len(llm_response_array)
        for line in range(len(self.transcription)):
            print(f"[USER]\n{self.transcription[line]}")
            if line < llm_res_len:
                print(f"[LLM]\n{llm_response_array[line]}")
        
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