# Thoth Voice Assistant - Linux Setup Guide

This guide will help you run the Thoth Voice Assistant on Linux systems. The main differences from Windows are related to audio device handling and system dependencies.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Audio Configuration](#audio-configuration)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)

---

## System Requirements

- **OS**: Ubuntu 20.04+ (or equivalent Debian-based distribution)
- **Python**: 3.8+
- **Audio System**: PulseAudio (default on most Linux distributions)
- **Hardware**: Microphone and speakers/headphones

### Supported Distributions
- Ubuntu 20.04, 22.04, 24.04
- Debian 11, 12
- Linux Mint 20+
- Pop!_OS 20.04+
- Other PulseAudio-based distributions

---

## Quick Start

For experienced users who want to get started quickly:

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y portaudio19-dev pulseaudio pulseaudio-utils espeak ffmpeg

# 2. Clone and navigate to project
cd /path/to/Thoth

# 3. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install Python dependencies
pip install -r thoth/backend/requirements-linux.txt

# 5. Setup PulseAudio virtual audio
bash scripts/setup_pulseaudio.sh

# 6. Configure environment
cp .env.linux .env
# Edit .env with your credentials

# 7. Run the voice assistant
python thoth/backend/core/call_assistant/app_v3.py
```

---

## Detailed Setup

### 1. Install System Dependencies

#### Required Packages

```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    pulseaudio \
    pulseaudio-utils \
    espeak \
    ffmpeg \
    git \
    python3-dev \
    build-essential
```

**What each package does:**
- `portaudio19-dev`: Audio I/O library for PyAudio
- `pulseaudio`: Audio server (usually pre-installed)
- `pulseaudio-utils`: PulseAudio command-line tools (pactl)
- `espeak`: Text-to-speech engine for pyttsx3
- `ffmpeg`: Audio/video processing (required by Whisper)
- `python3-dev`: Python development headers
- `build-essential`: C/C++ compilers for building Python packages

#### Verify PulseAudio

```bash
# Check if PulseAudio is running
pulseaudio --check && echo "PulseAudio is running" || echo "PulseAudio is not running"

# Start PulseAudio if needed
pulseaudio --start

# List audio devices
pactl list sinks short
pactl list sources short
```

### 2. Python Environment Setup

```bash
# Navigate to project directory
cd /path/to/Thoth

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Linux-specific requirements
pip install -r thoth/backend/requirements-linux.txt
```

**Note**: The `requirements-linux.txt` file excludes Windows-specific packages like:
- `pywin32` - Windows API bindings
- `pypiwin32` - Windows installer for pywin32
- `comtypes` - Windows COM interface
- `PyAudioWPatch` - Windows WASAPI support

### 3. Environment Configuration

```bash
# Copy Linux environment template
cp .env.linux .env

# Edit with your favorite editor
nano .env  # or vim, gedit, etc.
```

**Important settings for Linux:**

```bash
# Audio device - MUST be set for Linux
TTS_OUTPUT_DEVICE=virtual_speaker

# Your credentials (same as Windows)
ADMIN_USERNAME_HAHS_VIC3495=your_email@example.com
ADMIN_PASSWORD_HAHS_VIC3495=your_password
# ... etc
```

---

## Audio Configuration

Linux uses **PulseAudio** instead of VB-Audio Virtual Cable (Windows). We need to create virtual audio devices for routing TTS output to your voice calls.

### Understanding the Audio Flow

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│ TTS Output  │─────>│ Virtual Speaker  │─────>│ Call Device │
│ (pyttsx3)   │      │ (PulseAudio sink)│      │ (Phone/VoIP)│
└─────────────┘      └──────────────────┘      └─────────────┘
```

### Automated Setup (Recommended)

```bash
# Run the setup script
bash scripts/setup_pulseaudio.sh
```

**The script will:**
1. Check if PulseAudio is running
2. Create a virtual speaker (`virtual_speaker`)
3. Ask which device to route audio to (your call device)
4. Create a loopback connection
5. Optionally make the setup persistent across reboots

### Manual Setup

If you prefer to set it up manually:

```bash
# 1. Create virtual speaker
pactl load-module module-null-sink \
    sink_name=virtual_speaker \
    sink_properties=device.description="Thoth_Virtual_Speaker"

# 2. List available output devices
pactl list sinks short

# 3. Create loopback to your call device
# Replace <your_call_sink> with the actual sink name from step 2
pactl load-module module-loopback \
    source=virtual_speaker.monitor \
    sink=<your_call_sink> \
    latency_msec=1
```

### Making Setup Persistent

To automatically load virtual audio devices on system startup:

```bash
# Edit PulseAudio config
nano ~/.config/pulse/default.pa

# Add these lines at the end:
.include /etc/pulse/default.pa

# Thoth Voice Assistant - Virtual Audio Devices
load-module module-null-sink sink_name=virtual_speaker sink_properties=device.description=Thoth_Virtual_Speaker
load-module module-loopback source=virtual_speaker.monitor sink=<your_call_sink> latency_msec=1
```

**Restart PulseAudio:**
```bash
pulseaudio -k
pulseaudio --start
```

---

## Testing

### Test Audio Setup

```bash
# Run the audio test script
bash scripts/test_audio_setup.sh
```

This will:
- Verify virtual speaker exists
- Play a test tone through the virtual speaker
- Show current audio routing

### Test TTS Client

```bash
# Activate virtual environment
source .venv/bin/activate

# Test TTS output
cd thoth/backend/core/call_assistant
python -c "
from tts_client import TTSClient
import os
os.environ['TTS_OUTPUT_DEVICE'] = 'virtual_speaker'
tts = TTSClient(output_device_name='virtual_speaker')
tts.text_to_speech('Testing text to speech on Linux')
"
```

### Test Voice Assistant

```bash
# Start the Flask app
python thoth/backend/core/call_assistant/app_v3.py
```

**Expected output:**
```
============================================================
Starting Flask app with CallAssistantV3
LLM-driven conversation flow - no state machine!
============================================================

Endpoints:
  POST /webhook/call-started - Start a call session
  POST /webhook/call-ended - End a call session
  GET /status - View active sessions

Server running on http://localhost:5000

============================================================
```

### Test API Endpoints

```bash
# In another terminal, test the call-started webhook
curl -X POST http://localhost:5000/webhook/call-started \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-123",
    "from": "+1234567890"
  }'

# Check status
curl http://localhost:5000/status

# End the call
curl -X POST http://localhost:5000/webhook/call-ended \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-123"
  }'
```

---

## Troubleshooting

### Common Issues

#### 1. PyAudio Installation Fails

**Error:**
```
ERROR: Failed building wheel for pyaudio
```

**Solution:**
```bash
# Install portaudio development files
sudo apt-get install portaudio19-dev

# Then reinstall PyAudio
pip install --force-reinstall pyaudio
```

#### 2. PulseAudio Not Found

**Error:**
```
No PulseAudio device found in PyAudio
```

**Solution:**
```bash
# Check if PulseAudio is running
pgrep pulseaudio

# If not running, start it
pulseaudio --start

# Verify devices are available
pactl list sinks short
```

#### 3. Virtual Speaker Not Found

**Error:**
```
[TTS ERROR] Device 'virtual_speaker' not found
```

**Solution:**
```bash
# Run the setup script again
bash scripts/setup_pulseaudio.sh

# Or create manually
pactl load-module module-null-sink sink_name=virtual_speaker
```

#### 4. No Audio Output

**Possible causes:**
- Virtual speaker not created
- Loopback not configured
- Wrong sink selected
- Volume muted

**Solution:**
```bash
# Check if virtual speaker exists
pactl list sinks short | grep virtual_speaker

# Check loopbacks
pactl list modules short | grep loopback

# Unmute and set volume
pactl set-sink-mute virtual_speaker 0
pactl set-sink-volume virtual_speaker 100%

# Check PulseAudio volume mixer
pavucontrol  # Install with: sudo apt-get install pavucontrol
```

#### 5. Whisper Model Download Issues

**Error:**
```
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
```

**Solution:**
```bash
# Check internet connection
ping -c 3 github.com

# Download model manually
python -c "import whisper; whisper.load_model('base')"

# If behind proxy, set environment variables
export http_proxy=http://your-proxy:port
export https_proxy=http://your-proxy:port
```

#### 6. espeak Not Found

**Error:**
```
RuntimeError: espeak not found
```

**Solution:**
```bash
# Install espeak
sudo apt-get install espeak

# Test espeak
espeak "Testing espeak installation"
```

#### 7. Permission Denied on Scripts

**Error:**
```
bash: ./scripts/setup_pulseaudio.sh: Permission denied
```

**Solution:**
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Then run
bash scripts/setup_pulseaudio.sh
```

### Debug Mode

Enable detailed logging:

```bash
# Set debug environment variable
export DEBUG=1

# Run with verbose output
python -v thoth/backend/core/call_assistant/app_v3.py
```

### Get Help

If you encounter issues not covered here:

1. **Check logs**: Look for error messages in console output
2. **Verify dependencies**: Run `pip list` and compare with requirements
3. **Test components individually**: TTS, Whisper, audio devices
4. **Check system resources**: CPU, memory, disk space
5. **Review PulseAudio logs**: `journalctl --user -u pulseaudio`

---

## Performance Tips

### Optimize Whisper Model

The default model is `base`. You can adjust for performance vs. accuracy:

```python
# In call_assistant_v3.py, line 439
# Options: tiny, base, small, medium, large
self.whisper_client = SystemAudioWhisperClient(
    model="tiny",  # Faster, less accurate
    # model="small",  # Balanced
    # model="base",  # Default
    phrase_timeout=5,
    on_phrase_complete=self.on_phrase_complete
)
```

**Model comparison:**
- `tiny`: ~1GB RAM, fastest, 70-80% accuracy
- `base`: ~1.5GB RAM, fast, 80-85% accuracy (default)
- `small`: ~2GB RAM, slower, 85-90% accuracy
- `medium`: ~5GB RAM, slow, 90-95% accuracy
- `large`: ~10GB RAM, very slow, 95%+ accuracy

### Reduce Latency

```bash
# Lower PulseAudio latency
pactl unload-module <loopback_module_id>
pactl load-module module-loopback \
    source=virtual_speaker.monitor \
    sink=<your_sink> \
    latency_msec=1  # Minimum latency
```

### GPU Acceleration (Optional)

If you have an NVIDIA GPU:

```bash
# Install CUDA PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Whisper will automatically use GPU if available
```

---

## Differences from Windows

| Feature | Windows | Linux |
|---------|---------|-------|
| **Audio System** | WASAPI (PyAudioWPatch) | PulseAudio (PyAudio) |
| **Virtual Audio** | VB-Audio Virtual Cable | PulseAudio null sink |
| **TTS Engine** | SAPI5 (Windows Speech) | espeak |
| **Device Name** | `CABLE Input` | `virtual_speaker` |
| **Setup** | Install VB-Cable driver | Run bash script |
| **Persistence** | Automatic (driver) | Config file |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Voice Assistant V3                    │
│                                                           │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────┐ │
│  │ System Audio   │  │ Whisper Client │  │ LLM Client │ │
│  │ (PulseAudio)   │─>│ (Speech-to-Text│─>│ (Ollama)   │ │
│  └────────────────┘  └────────────────┘  └────────────┘ │
│         ↑                                        │        │
│         │                                        ↓        │
│  ┌────────────────┐                    ┌────────────────┐│
│  │  TTS Client    │<───────────────────│  Call Logic    ││
│  │  (espeak)      │                    │  (Flask API)   ││
│  └────────────────┘                    └────────────────┘│
│         ↓                                                 │
│  ┌────────────────┐                                      │
│  │ Virtual Speaker│───> Call Device                      │
│  └────────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Configure webhooks**: Set up your phone/VoIP system to call the Flask webhooks
2. **Test end-to-end**: Make a real call and verify the assistant responds
3. **Customize prompts**: Edit system prompts in `call_assistant_v3.py`
4. **Monitor logs**: Check for errors and performance issues
5. **Production deployment**: Consider using gunicorn/nginx for production

---

## Additional Resources

- [PulseAudio Documentation](https://www.freedesktop.org/wiki/Software/PulseAudio/Documentation/)
- [OpenAI Whisper GitHub](https://github.com/openai/whisper)
- [pyttsx3 Documentation](https://pyttsx3.readthedocs.io/)
- [Flask Documentation](https://flask.palletsprojects.com/)

---

**Questions or issues?** Create an issue in the project repository or check the main README for contact information.
