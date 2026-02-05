import argparse
import os
import numpy as np
import torch
import threading
import platform

from faster_whisper import WhisperModel

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


LOG_PREFIX = "[WHISPER_FAST_CLIENT]"


def _log(message: str) -> None:
    """Log a message with prefix."""
    print(f"{LOG_PREFIX} {message}")


class SystemAudioWhisperFastClient:
    """
    WhisperClient using Faster Whisper for improved performance.

    Faster Whisper is 4-5x faster than standard OpenAI Whisper while
    maintaining the same accuracy. It uses CTranslate2 backend with
    INT8/FP16 quantization support.

    Usage:
    client = SystemAudioWhisperFastClient(on_phrase_complete=callback_function)
    client.start() - start the transcription
    client.pause() - pause transcription
    client.resume() - resume transcription
    client.stop() - stop transcribing
    """
    def __init__(self, model="small", non_english=False, energy_threshold=1000,
                 record_timeout=0.1, phrase_timeout=2, on_phrase_complete=None,
                 silence_threshold=0.01, max_phrase_duration=15,
                 # Whisper accuracy parameters
                 language="en", temperature=0.0, initial_prompt=None,
                 condition_on_previous_text=True, no_speech_threshold=0.6,
                 log_prob_threshold=-1.0, compression_ratio_threshold=2.4,
                 min_audio_length=0.3,
                 # Faster Whisper specific parameters
                 compute_type="float16", device="auto", cpu_threads=4,
                 num_workers=1):
        """
        Initialize the transcription service.

        Args:
            model: Whisper model to use (tiny, base, small, medium, large-v2, large-v3)
            non_english: Whether to use non-English model
            energy_threshold: Energy level to detect audio (not used for system audio, kept for compatibility)
            record_timeout: How real time the recording is in seconds
            phrase_timeout: Empty space between recordings before new line
            on_phrase_complete: Callback function(text) called when a phrase is complete
            silence_threshold: Audio level below this is considered silence (0-1 range)
            max_phrase_duration: Maximum duration in seconds before forcing phrase completion

            # Whisper Accuracy Parameters:
            language: Language code (e.g., "en", "es", "fr"). Explicitly setting improves accuracy
            temperature: Sampling temperature (0.0 = greedy/deterministic)
            initial_prompt: Optional text to provide context/vocabulary to the model
            condition_on_previous_text: Use context from previous segments for better continuity
            no_speech_threshold: Threshold to filter out non-speech/hallucinations (0.0-1.0)
            log_prob_threshold: Filter segments with low average log probability
            compression_ratio_threshold: Detect repetitive/bad transcriptions
            min_audio_length: Minimum audio length in seconds before transcribing

            # Faster Whisper Specific Parameters:
            compute_type: Quantization type ("float16", "int8_float16", "int8", "float32")
                         - float16: Good balance of speed and accuracy (requires GPU)
                         - int8_float16: Faster, slightly lower accuracy (requires GPU)
                         - int8: Fastest, works on CPU
                         - float32: Most accurate, slowest
            device: Device to use ("auto", "cuda", "cpu")
            cpu_threads: Number of threads for CPU inference
            num_workers: Number of workers for parallel processing
        """
        self.model_name = model
        self.non_english = non_english
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.phrase_timeout = phrase_timeout
        self.max_phrase_duration = max_phrase_duration
        self.on_phrase_complete = on_phrase_complete
        self.silence_threshold = silence_threshold

        # Whisper accuracy parameters
        self.language = language if not non_english else None
        self.temperature = temperature
        self.initial_prompt = initial_prompt
        self.condition_on_previous_text = condition_on_previous_text
        self.no_speech_threshold = no_speech_threshold
        self.log_prob_threshold = log_prob_threshold
        self.compression_ratio_threshold = compression_ratio_threshold
        self.min_audio_length = min_audio_length

        # Faster Whisper specific parameters
        self.compute_type = compute_type
        self.device = device
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers

        # State variables
        self.last_speech_time = None
        self.phrase_start_time = None
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
        self.source_channels = 2
        self.source_sample_rate = 44100
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
            except ImportError as e:
                _log("ERROR: pyaudiowpatch not installed. Install with: pip install pyaudiowpatch")
                p.terminate()
                raise ImportError("pyaudiowpatch is required for Windows. Install with: pip install pyaudiowpatch") from e
            except Exception as e:
                _log(f"ERROR: Failed to initialize Windows audio: {e}")
                p.terminate()
                raise

        elif system == "Linux":
            import subprocess

            result = subprocess.run(['pactl', 'list', 'sources', 'short'],
                                capture_output=True, text=True)

            active_source = None
            idle_source = None

            for line in result.stdout.strip().split('\n'):
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if len(parts) >= 5:
                    source_name = parts[1]
                    status = parts[4] if len(parts) > 4 else ''

                    if 'RUNNING' in status:
                        active_source = source_name
                        break
                    elif 'IDLE' in status and idle_source is None:
                        idle_source = source_name

            selected_source = active_source or idle_source

            if selected_source:
                _log(f"Using audio source: {selected_source}")
                subprocess.run(['pactl', 'set-default-source', selected_source])
                os.environ['PULSE_SOURCE'] = selected_source
                self.current_source = selected_source
                self._update_source_info(selected_source)
            else:
                _log("No active audio source found, using system default")
                self.current_source = None

            pulse_device = None

            with noalsaerr():
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info['name'] == 'pulse' and info['maxInputChannels'] > 0:
                        pulse_device = info
                        break

            if pulse_device is None:
                _log("ERROR: No PulseAudio device found")
                p.terminate()
                raise ValueError("No pulse device found")

            return p, pulse_device

        else:
            _log(f"ERROR: Unsupported platform: {system}")
            p.terminate()
            raise ValueError(f"Unsupported platform: {system}")

    def _initialize_audio(self):
        """Initialize audio components."""
        self.pyaudio_instance, self.device_info = self._get_system_audio_device()
        _log(f"Using audio device: {self.device_info['name']}")

        # Determine model name
        model = self.model_name
        if self.model_name != "large" and self.model_name != "large-v2" and self.model_name != "large-v3" and not self.non_english:
            model = model + ".en"

        # Determine device
        if self.device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = self.device

        # Adjust compute type for CPU
        compute_type = self.compute_type
        if device == "cpu" and compute_type in ["float16", "int8_float16"]:
            _log(f"Switching compute_type from {compute_type} to int8 for CPU")
            compute_type = "int8"

        _log(f"Loading Faster Whisper model '{model}' on {device} with {compute_type}...")

        self.audio_model = WhisperModel(
            model,
            device=device,
            compute_type=compute_type,
            cpu_threads=self.cpu_threads,
            num_workers=self.num_workers
        )

        _log("Faster Whisper model loaded")

    def _update_source_info(self, source_name):
        """Get channel count and sample rate from PulseAudio source"""
        import subprocess
        try:
            result = subprocess.run(['pactl', 'list', 'sources', 'short'],
                                capture_output=True, text=True, timeout=1)

            for line in result.stdout.strip().split('\n'):
                if source_name in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        channels_str = parts[3]
                        if 'ch' in channels_str:
                            self.source_channels = int(channels_str.replace('ch', ''))

                        rate_str = parts[4] if len(parts) > 4 else '44100Hz'
                        if 'Hz' in rate_str:
                            self.source_sample_rate = int(rate_str.replace('Hz', ''))
                        break
        except Exception as e:
            _log(f"Could not get source info, using defaults: {e}")
            self.source_channels = 2
            self.source_sample_rate = 44100

    def _check_and_switch_source(self):
        """Check for RUNNING audio sources and switch if needed (Linux only)"""
        if platform.system() != "Linux":
            return False

        import subprocess
        import time

        current_time = time.time()
        if current_time - self.last_source_check < 3:
            return False

        self.last_source_check = current_time

        try:
            result = subprocess.run(['pactl', 'list', 'sources', 'short'],
                                capture_output=True, text=True, timeout=1)

            for line in result.stdout.strip().split('\n'):
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if len(parts) >= 5:
                    source_name = parts[1]
                    status = parts[4] if len(parts) > 4 else ''

                    if 'RUNNING' in status and source_name != self.current_source:
                        _log(f"Switching to active audio source: {source_name}")
                        subprocess.run(['pactl', 'set-default-source', source_name])
                        os.environ['PULSE_SOURCE'] = source_name
                        self.current_source = source_name

                        self._update_source_info(source_name)

                        if self.stream:
                            self.stream.stop_stream()
                            self.stream.close()

                        self._open_audio_stream()
                        return True
        except Exception as e:
            _log(f"Error checking audio sources: {e}")

        return False

    def _open_audio_stream(self):
        """Open the audio stream with current device settings"""
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

    def _audio_capture_loop(self):
        """Capture audio from active audio source and put into queue."""
        try:
            target_rate = 16000

            self._open_audio_stream()

            while self.is_running:
                self._check_and_switch_source()

                if platform.system() == "Linux" and self.device_info["name"] == "pulse":
                    channels = self.source_channels
                    source_rate = self.source_sample_rate
                else:
                    channels = int(self.device_info["maxInputChannels"])
                    source_rate = int(self.device_info["defaultSampleRate"])

                if not self.is_paused:
                    data = self.stream.read(1024, exception_on_overflow=False)

                    audio_array = np.frombuffer(data, dtype=np.int16)

                    if channels > 1:
                        audio_array = audio_array.reshape(-1, channels)
                        audio_array = audio_array.mean(axis=1).astype(np.int16)

                    if source_rate != target_rate:
                        num_samples = int(len(audio_array) * target_rate / source_rate)
                        audio_array = np.interp(
                            np.linspace(0, len(audio_array), num_samples),
                            np.arange(len(audio_array)),
                            audio_array
                        ).astype(np.int16)

                    audio_float = audio_array.astype(np.float32) / 32768.0
                    audio_level = np.sqrt(np.mean(audio_float**2))

                    self.data_queue.put({
                        'data': audio_array.tobytes(),
                        'level': audio_level,
                        'timestamp': datetime.utcnow()
                    })
                else:
                    sleep(0.1)

        except Exception as e:
            if self.is_running:
                _log(f"Error in audio capture loop: {e}")

    def _transcription_loop(self):
        """Main transcription loop that runs in a separate thread."""
        while self.is_running:
            try:
                if self.is_paused:
                    sleep(0.25)
                    continue

                now = datetime.utcnow()

                if not self.data_queue.empty():
                    chunks = []
                    has_speech = False
                    latest_timestamp = None

                    while not self.data_queue.empty():
                        chunk = self.data_queue.get()

                        if chunk['level'] > self.silence_threshold:
                            has_speech = True
                            self.last_speech_time = chunk['timestamp']
                            chunks.append(chunk['data'])

                        latest_timestamp = chunk['timestamp']

                    if chunks:
                        audio_data = b''.join(chunks)

                        if not self.phrase_bytes:
                            self.phrase_start_time = now

                        self.phrase_bytes += audio_data

                    if self.phrase_bytes:
                        audio_np = np.frombuffer(self.phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                        min_samples = int(self.min_audio_length * 16000)
                        if len(audio_np) > min_samples:
                            # Faster Whisper transcription - returns segments iterator
                            segments, info = self.audio_model.transcribe(
                                audio_np,
                                language=self.language,
                                temperature=self.temperature,
                                initial_prompt=self.initial_prompt,
                                condition_on_previous_text=self.condition_on_previous_text,
                                no_speech_threshold=self.no_speech_threshold,
                                log_prob_threshold=self.log_prob_threshold,
                                compression_ratio_threshold=self.compression_ratio_threshold,
                                vad_filter=True,  # Enable VAD for better accuracy
                                vad_parameters=dict(
                                    min_silence_duration_ms=500,
                                    speech_pad_ms=400
                                )
                            )

                            # Collect all segment texts
                            text_parts = []
                            for segment in segments:
                                text_parts.append(segment.text)

                            text = ''.join(text_parts).strip()

                            if text != self.last_transcription:
                                self.transcription[-1] = text
                                self.last_transcription = text
                                self._display_transcription()

                            if self.phrase_start_time:
                                phrase_duration = (now - self.phrase_start_time).total_seconds()
                                if phrase_duration >= self.max_phrase_duration:
                                    text = self.transcription[-1]
                                    self.transcription.append('')

                                    if text and self.on_phrase_complete:
                                        self.on_phrase_complete(text)

                                    self.phrase_bytes = bytes()
                                    self.last_speech_time = None
                                    self.phrase_start_time = None
                                    self.last_transcription = ''
                                    continue

                            if self.last_speech_time and not has_speech:
                                silence_duration = (now - self.last_speech_time).total_seconds()
                                if silence_duration >= self.phrase_timeout:
                                    text = self.transcription[-1]
                                    self.transcription.append('')

                                    if text and self.on_phrase_complete:
                                        self.on_phrase_complete(text)

                                    self.phrase_bytes = bytes()
                                    self.last_speech_time = None
                                    self.phrase_start_time = None
                                    self.last_transcription = ''
                else:
                    if self.last_speech_time and self.phrase_bytes:
                        silence_duration = (now - self.last_speech_time).total_seconds()
                        if silence_duration >= self.phrase_timeout:
                            text = self.transcription[-1]
                            self.transcription.append('')

                            if text and self.on_phrase_complete:
                                self.on_phrase_complete(text)

                            self.phrase_bytes = bytes()
                            self.last_speech_time = None
                            self.phrase_start_time = None
                            self.last_transcription = ''

                    sleep(0.1)

            except Exception as e:
                if self.is_running:
                    _log(f"Error in transcription loop: {e}")
                break

    def _display_transcription(self):
        """Display current transcription (no-op to avoid console clearing)."""
        pass

    def pause(self):
        """Pause transcription (stops capturing/processing audio)"""
        self.is_paused = True
        while not self.data_queue.empty():
            self.data_queue.get()
        self.phrase_bytes = bytes()
        self.last_speech_time = None
        self.phrase_start_time = None
        _log("Transcription paused")

    def resume(self):
        """Resume transcription"""
        self.is_paused = False
        self.last_transcription = ''
        self.phrase_bytes = bytes()
        self.last_speech_time = None
        self.phrase_start_time = None
        while not self.data_queue.empty():
            self.data_queue.get()
        _log("Transcription resumed")

    def start(self):
        """Start the transcription service."""
        if self.is_running:
            _log("Transcription service is already running")
            return

        _log("Starting transcription service...")

        self._initialize_audio()

        self.last_speech_time = None
        self.phrase_start_time = None
        self.data_queue = Queue()
        self.phrase_bytes = bytes()
        self.transcription = ['']
        self.last_transcription = ''
        self.is_running = True
        self.is_paused = False

        self.audio_capture_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_capture_thread.start()

        self.transcription_thread = threading.Thread(target=self._transcription_loop, daemon=True)
        self.transcription_thread.start()

        _log("Transcription service started")

    def stop(self, _llm_response_array=None):
        """Stop the transcription service."""
        if not self.is_running:
            _log("Transcription service is not running")
            return

        _log("Stopping transcription service...")
        self.is_running = False

        if self.audio_capture_thread:
            self.audio_capture_thread.join(timeout=2)
        if self.transcription_thread:
            self.transcription_thread.join(timeout=2)

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

        _log("Transcription service stopped")

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
