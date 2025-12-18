import pyaudio
import platform
import numpy as np
from gtts import gTTS
from pydub import AudioSegment
import tempfile
import os

class StreamingTTSClient:
    """
    Cross-platform TTS client that streams audio to a virtual microphone using Google TTS (gTTS).

    Works on:
    - Windows: Requires VB-Audio Cable installed
    - Linux: Uses PulseAudio (built-in on most distros)

    Usage:
        tts = StreamingTTSClient()
        tts.text_to_speech("Hello world")
    """

    def __init__(self, rate=16000, channels=1):
        """
        Initialize the streaming TTS client.

        Args:
            rate: Sample rate (default 16000 Hz for voice)
            channels: Number of audio channels (1=mono, 2=stereo)
        """
        self.rate = rate
        self.channels = channels

        self.system = platform.system()
        self.pyaudio = None
        self.virtual_device = None
        self.stream = None

        # Initialize virtual audio device
        self._setup_virtual_device()

    def _setup_virtual_device(self) -> None:
        """Setup virtual audio device based on OS"""

        if self.system == "Windows":
            self._setup_windows_virtual_device()
        elif self.system == "Linux":
            self._setup_linux_virtual_device()
        else:
            raise OSError(f"Unsupported platform: {self.system}")

    def _setup_windows_virtual_device(self) -> None:
        """Setup Windows virtual audio device (VB-Cable)"""
        try:
            import pyaudiowpatch as paw
            self.pyaudio = paw.PyAudio()

            # Find VB-Audio Virtual Cable
            cable_device = None
            for i in range(self.pyaudio.get_device_count()):
                info = self.pyaudio.get_device_info_by_index(i)
                # Look for CABLE Input (this appears as a microphone to other apps)
                if 'cable input' in info['name'].lower() and info['maxOutputChannels'] > 0:
                    cable_device = info
                    break

            if cable_device is None:
                print("\n⚠️  WARNING: VB-Audio Cable not found!")
                print("Please install VB-Audio Virtual Cable:")
                print("https://vb-audio.com/Cable/")
                print("\nFalling back to default output device...\n")

                # Fallback to default output
                default_device = self.pyaudio.get_default_output_device_info()
                self.virtual_device = default_device
            else:
                self.virtual_device = cable_device
                print(f"✓ Using virtual device: {cable_device['name']}")

        except ImportError:
            print("PyAudioWPatch not found, using regular PyAudio")
            self.pyaudio = pyaudio.PyAudio()
            self.virtual_device = self.pyaudio.get_default_output_device_info()

    def _setup_linux_virtual_device(self) -> None:
        """Setup Linux virtual audio device (PulseAudio)"""
        self.pyaudio = pyaudio.PyAudio()

        # Look for virtual sink monitor or create instructions
        virtual_device = None

        for i in range(self.pyaudio.get_device_count()):
            info = self.pyaudio.get_device_info_by_index(i)
            # Look for virtual sink or monitor device
            if ('virtual' in info['name'].lower() or
                'monitor' in info['name'].lower()) and info['maxOutputChannels'] > 0:
                virtual_device = info
                break

        if virtual_device is None:
            print("\n⚠️  WARNING: No virtual audio sink found!")
            print("To create a virtual microphone on Linux, run:")
            print("  pactl load-module module-null-sink sink_name=virtual_mic sink_properties=device.description=Virtual_Microphone")
            print("  pactl load-module module-remap-source source_name=virtual_mic_source master=virtual_mic.monitor source_properties=device.description=Virtual_Microphone_Source")
            print("\nFalling back to default output device...\n")

            # Fallback to default
            virtual_device = self.pyaudio.get_default_output_device_info()
        else:
            print(f"✓ Using virtual device: {virtual_device['name']}")

        self.virtual_device = virtual_device

    def _generate_audio_gtts(self, text:str) -> None:
        """Generate audio using Google TTS"""
        # Create TTS
        tts = gTTS(text=text, lang='en', slow=False)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            temp_file = fp.name
            tts.save(temp_file)

        # Load with pydub and convert to desired format
        audio = AudioSegment.from_mp3(temp_file)
        audio = audio.set_frame_rate(self.rate)
        audio = audio.set_channels(self.channels)

        # Clean up temp file
        os.unlink(temp_file)

        # Convert to raw bytes
        return audio.raw_data

    def text_to_speech(self, text:str):
        """
        Convert text to speech and stream to virtual microphone.

        Args:
            text: Text to convert to speech
        """
        if not text or text.strip() == "":
            return

        print(f"🔊 Speaking: {text}")

        # Generate audio using gTTS
        audio_data = self._generate_audio_gtts(text)

        # Stream to virtual device
        self._stream_audio(audio_data)

    def _stream_audio(self, audio_data):
        """Stream audio data to virtual device"""
        try:
            # Open stream
            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                output=True,
                output_device_index=self.virtual_device['index'],
                frames_per_buffer=1024
            )

            # Write audio data in chunks
            chunk_size = 1024 * 2  # 2 bytes per sample for paInt16
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                stream.write(chunk)

            # Close stream
            stream.stop_stream()
            stream.close()

        except Exception as e:
            print(f"Error streaming audio: {e}")
            import traceback
            traceback.print_exc()

    def __del__(self):
        """Cleanup PyAudio"""
        if self.pyaudio:
            self.pyaudio.terminate()


if __name__ == "__main__":
    # Test the streaming TTS
    print("Testing Streaming TTS Client")
    print("=" * 50)

    # Test with gTTS
    print("\nTesting with Google TTS (gTTS)")
    tts = StreamingTTSClient()
    tts.text_to_speech("Hello, this is a test of the streaming text to speech system.")
