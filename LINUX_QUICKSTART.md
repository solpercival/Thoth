# Linux Quick Start Checklist

Use this checklist to get Thoth Voice Assistant running on Linux quickly.

## Pre-flight Checklist

- [ ] Linux distribution with PulseAudio (Ubuntu 20.04+ recommended)
- [ ] Python 3.8 or higher installed
- [ ] Internet connection for downloading dependencies
- [ ] Microphone and speakers/headphones connected

## Installation Steps

### 1. System Dependencies
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev pulseaudio pulseaudio-utils espeak ffmpeg
```
- [ ] All packages installed successfully

### 2. Python Environment
```bash
cd /path/to/Thoth
python3 -m venv .venv
source .venv/bin/activate
pip install -r thoth/backend/requirements-linux.txt
```
- [ ] Virtual environment created
- [ ] Dependencies installed without errors

### 3. Audio Setup
```bash
bash scripts/setup_pulseaudio.sh
```
- [ ] Virtual speaker created
- [ ] Loopback configured to call device
- [ ] (Optional) Made persistent

### 4. Environment Configuration
```bash
cp .env.linux .env
nano .env  # Edit with your credentials
```
- [ ] `.env` file created from template
- [ ] Credentials filled in
- [ ] `TTS_OUTPUT_DEVICE=virtual_speaker` confirmed

### 5. Test Setup
```bash
# Test audio
bash scripts/test_audio_setup.sh

# Test voice assistant
python thoth/backend/core/call_assistant/app_v3.py
```
- [ ] Audio test passes
- [ ] Flask app starts without errors
- [ ] Endpoints accessible at http://localhost:5000

## Verification

### Quick Test Commands
```bash
# Check virtual speaker exists
pactl list sinks short | grep virtual_speaker

# Check environment variable
grep TTS_OUTPUT_DEVICE .env

# Test API
curl http://localhost:5000/status
```

## Common Issues

| Issue | Quick Fix |
|-------|-----------|
| PyAudio won't install | `sudo apt-get install portaudio19-dev` |
| Virtual speaker not found | `bash scripts/setup_pulseaudio.sh` |
| espeak not found | `sudo apt-get install espeak` |
| Permission denied on scripts | `chmod +x scripts/*.sh` |

## Next Steps

- [ ] Configure webhook endpoints in your phone/VoIP system
- [ ] Test with a real call
- [ ] Review logs for any issues
- [ ] Customize system prompts if needed

## Need Help?

See [LINUX_SETUP.md](LINUX_SETUP.md) for detailed documentation and troubleshooting.

---

**Status**: Ready to run on Linux! 🐧
