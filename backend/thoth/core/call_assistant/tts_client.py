import pyaudio
import wave
import tempfile
import os
import platform
import subprocess
import asyncio

import edge_tts
from pydub import AudioSegment


# Speaker Models:
# en-US-AriaNeural (female US)
# en-US-GuyNeural (male US)
# en-AU-NatashaNeural (female AUS)
# en-AU-WilliamNeural (male AUS)
# en-GB-SoniaNeural (female UK)



class TTSClient:
    def __init__(self, rate:int=150, volume:float=0.9, output_device_name:str=None, voice:str="en-AU-NatashaNeural") -> None:
        """
        Initialize TTS Client with edge-tts and PyAudio for device control.

        Args:
            rate: Speech rate (words per minute) - affects playback speed
            volume: Volume level 0.0-1.0
            output_device_name: Name of audio output device
                              Windows: "CABLE Input"
                              Linux: "virtual_speaker" or None for default
            voice: Edge TTS voice name (default 'en-US-AriaNeural')
        """
        self.rate = rate
        self.volume = volume
        self.voice = voice
        self.system = platform.system()
        
        # Determine the correct output device based on OS
        if output_device_name:
            if self.system == "Linux":
                self.output_device_name = output_device_name if "virtual" in output_device_name.lower() else "virtual_speaker"
            else:
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
        Convert text to speech using edge-tts and play through specified device.

        Args:
            text: The text to speak
        """
        temp_mp3 = None
        temp_wav = None
        try:
            # Create temp file for MP3
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                temp_mp3 = f.name
            
            # Generate speech with edge-tts
            # Convert rate to edge-tts format: +0%, -20%, +50%, etc.
            rate_percent = int(((self.rate / 150.0) - 1) * 100)
            rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
            
            asyncio.run(self._generate_speech(text, temp_mp3, rate_str))
            
            # Convert MP3 to WAV using pydub
            audio = AudioSegment.from_mp3(temp_mp3)
            
            # Adjust volume
            if self.volume != 1.0:
                db_change = 20 * (self.volume - 1.0)
                audio = audio + db_change
            
            # Export to temporary WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                temp_wav = f.name
            audio.export(temp_wav, format='wav')
            
            # Play the WAV file
            self._play_audio_file(temp_wav)

        except Exception as e:
            print(f"[TTS ERROR] {e}")
        finally:
            for f in [temp_mp3, temp_wav]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except (PermissionError, OSError):
                        pass

    async def _generate_speech(self, text: str, output_file: str, rate: str) -> None:
        """Generate speech using edge-tts"""
        communicate = edge_tts.Communicate(text, self.voice, rate=rate)
        await communicate.save(output_file)

    def _play_audio_file(self, filename:str) -> None:
        """Play a WAV file through the specified device."""
        # On Linux, use paplay for better PulseAudio/PipeWire integration
        if self.system == "Linux" and self.output_device_name:
            try:
                subprocess.run(
                    ['paplay', '--device', self.output_device_name, filename],
                    check=True,
                    capture_output=True,
                    timeout=30
                )
                return
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                print("[TTS] paplay failed, using PyAudio fallback")
        
        # Use PyAudio (Windows or Linux fallback)
        p = pyaudio.PyAudio()

        try:
            wf = wave.open(filename, 'rb')

            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=self.device_index
            )

            chunk_size = 1024
            data = wf.readframes(chunk_size)

            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)

            stream.stop_stream()
            stream.close()
            wf.close()

        finally:
            p.terminate()


if __name__ == "__main__":
    tts_client = TTSClient()

    while True:
        text = input(">> ")
        if text.lower() == "quit":
            break
    
        tts_client.text_to_speech(text)