# Testing Guide: Virtual Microphone TTS

This guide will help you test if your TTS is properly streaming to the virtual microphone.

---

## Windows Testing

### Step 1: Install VB-Audio Cable

1. Download **VB-Audio Virtual Cable**: https://vb-audio.com/Cable/
2. Run installer as Administrator
3. **Restart your computer** (important!)
4. Verify installation:
   - Right-click speaker icon in taskbar → **Sound Settings**
   - Under **Output**, you should see **CABLE Input (VB-Audio Virtual Cable)**
   - Under **Input**, you should see **CABLE Output (VB-Audio Virtual Cable)**

### Step 2: Install FFmpeg

**Option A: Using Chocolatey (Recommended)**
```powershell
# Open PowerShell as Administrator
choco install ffmpeg
```

**Option B: Manual Installation**
1. Download FFmpeg: https://www.gyan.dev/ffmpeg/builds/
2. Choose "ffmpeg-release-essentials.zip"
3. Extract to `C:\ffmpeg`
4. Add to PATH:
   - Press Win + Search "Environment Variables"
   - Click "Environment Variables"
   - Under "System variables", select "Path" → Click "Edit"
   - Click "New" → Add `C:\ffmpeg\bin`
   - Click OK on all windows
   - **Restart your terminal/IDE**

Verify FFmpeg installation:
```powershell
ffmpeg -version
```

### Step 3: Test Basic TTS

Open a terminal in your project directory and run:

```bash
python backend/core/call_assistant/tts_client_streaming.py
```

**Expected output:**
```
✓ Using virtual device: CABLE Input
Testing Streaming TTS Client
==================================================

Testing with Google TTS (gTTS)
🔊 Speaking: Hello, this is a test of the streaming text to speech system.
```

**If you see errors:**
- `VB-Audio Cable not found` → Install VB-Cable and restart
- `FFmpeg not found` → Install FFmpeg and restart terminal
- `No module named 'gtts'` → Run `pip install gTTS pydub`

### Step 4: Test That Virtual Mic is Working

1. **Open Sound Settings** (right-click speaker icon)
2. Scroll down to **Advanced** → Click **More sound settings**
3. Go to **Recording** tab
4. Find **CABLE Output (VB-Audio Virtual Cable)**
5. Right-click → **Properties** → **Listen** tab
6. Check "Listen to this device"
7. Click **Apply** (don't close yet)
8. Run the test again:
   ```bash
   python backend/core/call_assistant/tts_client_streaming.py
   ```
9. **You should hear the voice through your speakers!**
10. Uncheck "Listen to this device" when done testing

### Step 5: Configure 3CX

1. Open 3CX client/app
2. Go to **Settings** → **Audio Settings**
3. Set **Microphone** to: **CABLE Output (VB-Audio Virtual Cable)**
4. Make a test call
5. When your Python app runs `tts.text_to_speech()`, the caller should hear it!

---

## Linux Testing

### Step 1: Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y pulseaudio pulseaudio-utils ffmpeg portaudio19-dev python3-pyaudio
```

**Fedora/RHEL:**
```bash
sudo dnf install -y pulseaudio pulseaudio-utils ffmpeg portaudio-devel python3-pyaudio
```

**Arch:**
```bash
sudo pacman -S pulseaudio ffmpeg portaudio python-pyaudio
```

### Step 2: Create Virtual Audio Device

Run these commands:

```bash
# Create virtual sink (acts as speakers)
pactl load-module module-null-sink sink_name=virtual_mic sink_properties=device.description=Virtual_Microphone

# Create virtual source (acts as microphone)
pactl load-module module-remap-source source_name=virtual_mic_source master=virtual_mic.monitor source_properties=device.description=Virtual_Microphone_Source
```

**Verify it was created:**
```bash
pactl list sinks short | grep virtual
pactl list sources short | grep virtual
```

You should see `virtual_mic` and `virtual_mic_source`.

**To make it permanent** (survives reboot):
```bash
sudo nano /etc/pulse/default.pa
```

Add these lines at the end:
```
load-module module-null-sink sink_name=virtual_mic sink_properties=device.description=Virtual_Microphone
load-module module-remap-source source_name=virtual_mic_source master=virtual_mic.monitor source_properties=device.description=Virtual_Microphone_Source
```

Save and restart PulseAudio:
```bash
pulseaudio -k
pulseaudio --start
```

### Step 3: Test Basic TTS

```bash
python backend/core/call_assistant/tts_client_streaming.py
```

**Expected output:**
```
✓ Using virtual device: virtual_mic.monitor
Testing Streaming TTS Client
==================================================

Testing with Google TTS (gTTS)
🔊 Speaking: Hello, this is a test of the streaming text to speech system.
```

### Step 4: Test That Virtual Mic is Working

**Option A: Using parecord/paplay**
1. In one terminal, record from virtual mic:
   ```bash
   parecord --device=virtual_mic_source test.wav
   ```

2. In another terminal, run TTS:
   ```bash
   python backend/core/call_assistant/tts_client_streaming.py
   ```

3. Press Ctrl+C on the first terminal to stop recording
4. Play back the recording:
   ```bash
   paplay test.wav
   ```
   You should hear the TTS!

**Option B: Using pavucontrol (GUI)**
```bash
sudo apt-get install pavucontrol
pavucontrol
```

1. Open pavucontrol
2. Go to **Recording** tab
3. Run your TTS test
4. You should see audio levels moving for `virtual_mic_source`

### Step 5: Configure 3CX

1. Open 3CX client/app
2. Go to **Settings** → **Audio Settings**
3. Set **Microphone** to: **Virtual_Microphone_Source**
4. Make a test call
5. When your Python app runs `tts.text_to_speech()`, the caller should hear it!

---

## Quick Integration Test

Create a simple test script to verify everything works:

**File: `test_tts_integration.py`**
```python
from backend.core.call_assistant.tts_client_streaming import StreamingTTSClient
import time

print("Testing TTS Integration...")
print("=" * 50)

tts = StreamingTTSClient()

# Test multiple phrases
phrases = [
    "Hello, welcome to our automated system.",
    "Your call is important to us.",
    "Please hold while we check your information.",
    "Thank you for calling. Goodbye."
]

for i, phrase in enumerate(phrases, 1):
    print(f"\n[Test {i}/{len(phrases)}]")
    tts.text_to_speech(phrase)
    time.sleep(2)  # Wait between phrases

print("\n" + "=" * 50)
print("✓ All tests completed!")
print("\nIf you heard all 4 phrases through your virtual mic setup, it's working!")
```

Run it:
```bash
python test_tts_integration.py
```

---

## Troubleshooting

### Windows Issues

**"VB-Audio Cable not found"**
- Install VB-Audio Cable from https://vb-audio.com/Cable/
- Restart computer
- Verify in Sound Settings

**"FFmpeg not found" or "RuntimeError: Couldn't find ffmpeg or avconv"**
- Install FFmpeg (see Step 2)
- Make sure it's in your PATH
- Restart terminal/IDE after adding to PATH
- Test: `ffmpeg -version`

**"No sound in virtual mic"**
- Make sure VB-Cable is installed
- Try the "Listen to this device" test (Step 4)
- Check Windows Sound Settings that CABLE devices are not muted

### Linux Issues

**"No virtual audio sink found"**
- Run the `pactl load-module` commands from Step 2
- Check: `pactl list sinks short`
- Make sure PulseAudio is running: `pulseaudio --check`

**"Connection refused" or "PulseAudio not running"**
```bash
pulseaudio --kill
pulseaudio --start
```

**"No module named 'pyaudio'"**
```bash
pip install pyaudio
# If that fails:
sudo apt-get install portaudio19-dev python3-pyaudio
```

### General Issues

**"gTTS requires internet connection"**
- Make sure you have internet access
- gTTS connects to Google's servers to generate audio
- If offline, you'll need to use a different TTS solution

**"Audio is choppy or delayed"**
- This is normal for gTTS (~500ms latency)
- Consider pre-generating common phrases and caching them

**"No sound in 3CX during call"**
- Verify 3CX microphone is set to virtual device
- Test virtual mic with recording tools first
- Make sure virtual device is not muted
- Check 3CX audio permissions

---

## Success Checklist

- [ ] Virtual audio device installed (VB-Cable on Windows or PulseAudio on Linux)
- [ ] FFmpeg installed and in PATH
- [ ] Python dependencies installed (`gTTS`, `pydub`, `pyaudio`)
- [ ] Basic TTS test runs without errors
- [ ] Virtual microphone receives audio (verified with recording test)
- [ ] 3CX configured to use virtual microphone
- [ ] Test call successful - caller can hear TTS

Once all checkboxes are complete, you're ready to integrate with your call assistant! ✅
