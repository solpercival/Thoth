"""
Test script to verify TTS audio routing to virtual cable.
This will list all audio devices and test playing to CABLE Input.
"""
import sys
from pathlib import Path

# Add backend root to Python path
# test_virtual_cable.py is at: backend/thoth/core/call_assistant/test_virtual_cable.py
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

import pyaudio
from thoth.core.call_assistant.tts_client import TTSClient


def list_audio_devices():
    """List all available audio output devices."""
    print("\n" + "="*60)
    print("AVAILABLE AUDIO OUTPUT DEVICES")
    print("="*60)

    p = pyaudio.PyAudio()

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxOutputChannels'] > 0:
            print(f"\n[{i}] {info['name']}")
            print(f"    Channels: {info['maxOutputChannels']}")
            print(f"    Sample Rate: {int(info['defaultSampleRate'])} Hz")

            # Highlight virtual cable
            if 'CABLE' in info['name'].upper():
                print("    >>> VIRTUAL CABLE DEVICE <<<")

    p.terminate()
    print("\n" + "="*60 + "\n")


def test_default_output():
    """Test TTS with default audio output."""
    print("\n[TEST 1] Testing TTS with DEFAULT audio output...")
    print("You should hear this through your normal speakers/headphones.\n")

    try:
        tts = TTSClient()
        tts.text_to_speech("Testing default audio output. This should play through your regular speakers.")
        print("✓ Default output test completed\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")


def test_cable_output():
    """Test TTS with CABLE Input (virtual cable)."""
    print("\n[TEST 2] Testing TTS with CABLE Input (virtual cable)...")
    print("This should play through the virtual cable.")
    print("You won't hear it unless you have CABLE Output monitoring enabled,")
    print("or if 3CX is using CABLE Output as its microphone input.\n")

    try:
        tts = TTSClient(output_device_name="CABLE Input")
        tts.text_to_speech("Testing virtual cable output. This should route to CABLE Input device.")
        print("✓ Virtual cable test completed\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")


def main():
    print("\n" + "="*60)
    print("VIRTUAL CABLE TEST SCRIPT")
    print("="*60)

    # List all devices
    list_audio_devices()

    # Test default output
    test_default_output()

    # Wait for user
    input("Press Enter to test virtual cable output...")

    # Test cable output
    test_cable_output()

    print("\n" + "="*60)
    print("SETUP VERIFICATION")
    print("="*60)
    print("\nFor proper 3CX integration, verify:")
    print("1. ✓ CABLE Input device is listed above")
    print("2. ✓ Test 2 completed without errors")
    print("3. ✓ 3CX microphone is set to 'CABLE Output'")
    print("4. ✓ Windows default playback is your regular speakers (NOT CABLE Input)")
    print("\nIf all checks pass, your setup is ready!\n")


if __name__ == "__main__":
    main()
