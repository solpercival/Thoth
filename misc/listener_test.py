import soundcard as sc
import numpy as np
import time
import platform
import pyaudio
import sys


THRESHOLD = 0.01  # (1%) The higher, the less sensitive program will be at picking up audio

def get_system_audio_device():
    """
    Get the appropriate system audio device based on OS
    """
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
            return p_patch, default_speakers, "windows"
        
        except ImportError:
            print("For windows, install: pip install pyaudiowpatch")
            p.terminate()
            sys.exit(1)

    elif system == "Linux":
        # Find PulseAudio monitor device
        monitor_device = None

        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)


            if "monitor" in info['name'].lower() and info['maxInputChannels'] > 0:
                monitor_device = info
        
        # Cannot find monitor device
        if monitor_device is None:
            print("No monitor device found")
            p.terminate()
            sys.exit(1)

        return p, monitor_device, "linux"
    
    else:
        print(f"Unsupported platform: {system}")
        p.terminate()
        sys.exit(1)


def detect_desktop_audio():
    # Get default speaker
    p, device_info, os_type = get_system_audio_device()
    print(f"\nMonitoring: {device_info}")
    print("Play some audio to test...\n")

    # Start recording from speaker (audio output)
    try:
        # Open a stream depending on the OS
        stream = p.open(
            format=pyaudio.paInt16,
            channels=int(device_info["maxInputChannels"]),
            rate=int(device_info["defaultSampleRate"]),
            input=True,
            frames_per_buffer=1024,
            input_device_index= device_info["index"]
        )

        while True:
            # Read audio data
            data = stream.read(1024, exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.int16)
            
            # Calculate audio level (RMS)
            audio_float = audio_array.astype(np.float32) / 32768.0
            audio_level = np.sqrt(np.mean(audio_array**2))
            
            # Threshold for detection (adjust as needed)
            if audio_level > THRESHOLD:
                print(f"🔊 AUDIO DETECTED! (Level: {audio_level:.0f})")
            
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("Stopped Monitoring.")
    except Exception as e:
        print(e)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    detect_desktop_audio()
