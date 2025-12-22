import pyttsx3
import pyaudio
import wave
import tempfile
import os
import platform
import subprocess

class TTSClient:
    def __init__(self, rate:int=150, volume:float=0.9, output_device_name:str=None) -> None:
        """
        Initialize TTS Client with pyttsx3 and PyAudio for device control.

        Args:
            rate: Speech rate (words per minute)
            volume: Volume level 0.0-1.0
            output_device_name: Name of audio output device
                              Windows: "CABLE Input"
                              Linux: "virtual_speaker" or None for default
        """
        self.rate = rate
        self.volume = volume
        self.system = platform.system()
        
        # Determine the correct output device based on OS
        if output_device_name:
            if self.system == "Linux":
                # On Linux, look for virtual_speaker or use the provided name
                self.output_device_name = output_device_name if "virtual" in output_device_name.lower() else "virtual_speaker"
            else:
                # Windows uses the provided name as-is
                self.output_device_name = output_device_name
        else:
            self.output_device_name = None

        # Find the device index if device name is specified
        self.device_index = None
        if self.output_device_name:
            self.device_index = self._find_device_index(self.output_device_name)
            if self.device_index is not None:
                print(f"[TTS] Using audio device: {self.output_device_name} (index: {self.device_index})")
            else:
                print(f"[TTS] Warning: Device '{self.output_device_name}' not found, using default")

    def _find_device_index(self, device_name:str) -> int:
        """Find the PyAudio device index by name."""
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if device_name.lower() in info['name'].lower() and info['maxOutputChannels'] > 0:
                    return i
        finally:
            p.terminate()
        return None

    def text_to_speech(self, text:str) -> None:
        """
        Convert text to speech and play it through the specified device.

        Args:
            text: The text to speak
        """
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_filename = temp_file.name

        try:
            if self.system == "Linux":
                # Use espeak directly on Linux to avoid pyttsx3 callback issues
                self._generate_with_espeak(text, temp_filename)
            else:
                # Use pyttsx3 on Windows
                engine = pyttsx3.init()
                engine.setProperty('rate', self.rate)
                engine.setProperty('volume', self.volume)
                engine.save_to_file(text, temp_filename)
                engine.runAndWait()

            # Play the WAV file to the specified device
            self._play_audio_file(temp_filename)

        except Exception as e:
            print(f"[TTS ERROR] {e}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except (PermissionError, OSError):
                    pass  # File might still be in use, will be cleaned up later
    
    def _generate_with_espeak(self, text: str, output_file: str) -> None:
        """Generate speech using espeak directly (Linux)"""
        try:
            # Use espeak to generate WAV file
            # -w writes to file, -s sets speed (words per minute)
            subprocess.run(
                ['espeak', '-w', output_file, '-s', str(self.rate), text],
                check=True,
                capture_output=True,
                timeout=10
            )
        except subprocess.TimeoutExpired:
            print("[TTS] Espeak timeout, using fallback")
            # Fallback to pyttsx3 if espeak times out
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)
            engine.save_to_file(text, output_file)
            engine.runAndWait()
            engine.stop()
        except FileNotFoundError:
            print("[TTS] Espeak not found, using pyttsx3")
            # Fallback if espeak is not installed
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)
            engine.save_to_file(text, output_file)
            engine.runAndWait()
            engine.stop()

    def _play_audio_file(self, filename:str) -> None:
        """Play a WAV file through the specified device."""
        # On Linux, use paplay for better PulseAudio/PipeWire integration
        if self.system == "Linux" and self.output_device_name:
            try:
                subprocess.run(
                    ['paplay', '--device', self.output_device_name, filename],
                    check=True,
                    capture_output=True,
                    timeout=10
                )
                return
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                # Fall back to PyAudio if paplay fails
                print("[TTS] paplay failed, using PyAudio fallback")
        
        # Use PyAudio (Windows or Linux fallback)
        p = pyaudio.PyAudio()

        try:
            # Open the WAV file
            wf = wave.open(filename, 'rb')

            # Open stream with specified device
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=self.device_index
            )

            # Read and play audio in chunks
            chunk_size = 1024
            data = wf.readframes(chunk_size)

            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)

            # Clean up
            stream.stop_stream()
            stream.close()
            wf.close()

        finally:
            p.terminate()

if __name__ == "__main__":
    tts_client = TTSClient()
    tts_client.text_to_speech("Cancellation of job for a...Mr. Roberts at...4 PM on...Sunday...is confirmed. Staff has been notified")