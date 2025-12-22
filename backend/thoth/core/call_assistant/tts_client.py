import pyttsx3
import pyaudio
import wave
import tempfile
import os

class TTSClient:
    def __init__(self, rate:int=150, volume:float=0.9, output_device_name:str=None) -> None:
        """
        Initialize TTS Client with pyttsx3 and PyAudio for device control.

        Args:
            rate: Speech rate (words per minute)
            volume: Volume level 0.0-1.0
            output_device_name: Name of audio output device (e.g., "CABLE Input")
                              If None, uses system default
        """
        self.rate = rate
        self.volume = volume
        self.output_device_name = output_device_name

        # Find the device index if device name is specified
        self.device_index = None
        if output_device_name:
            self.device_index = self._find_device_index(output_device_name)
            if self.device_index is not None:
                print(f"[TTS] Using audio device: {output_device_name} (index: {self.device_index})")
            else:
                print(f"[TTS] Warning: Device '{output_device_name}' not found, using default")

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
            # Initialize pyttsx3 engine
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)

            # Save to WAV file
            engine.save_to_file(text, temp_filename)
            engine.runAndWait()

            # Play the WAV file to the specified device
            self._play_audio_file(temp_filename)

        finally:
            # Clean up temp file
            if os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except PermissionError:
                    pass  # File might still be in use, will be cleaned up later

    def _play_audio_file(self, filename:str) -> None:
        """Play a WAV file through the specified device."""
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