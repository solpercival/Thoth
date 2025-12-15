# Virtual Microphone Setup Guide

This guide will help you set up virtual audio devices for streaming TTS to 3CX on both Windows and Linux.

## Installation Steps

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Windows Setup

### Step 1: Install VB-Audio Virtual Cable

1. Download **VB-Audio Virtual Cable** from: https://vb-audio.com/Cable/
2. Run the installer as Administrator
3. Restart your computer after installation
4. Verify installation:
   - Open **Sound Settings** (right-click speaker icon in taskbar)
   - You should see **CABLE Input** and **CABLE Output** devices

### Step 2: Configure 3CX to Use Virtual Cable

1. Open **3CX** settings
2. Go to **Audio Settings** or **Microphone Settings**
3. Select **CABLE Output (VB-Audio Virtual Cable)** as your microphone
4. This makes 3CX "listen" to what your TTS outputs

### Step 3: Install FFmpeg (Required for pydub)

**Option A: Using Chocolatey (Recommended)**
```powershell
# Install Chocolatey if not installed
# Then run:
choco install ffmpeg
```

**Option B: Manual Installation**
1. Download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH:
   - Search "Environment Variables" in Windows
   - Edit "Path" under System Variables
   - Add `C:\ffmpeg\bin`
   - Restart terminal

### Verify Setup
```python
python backend/core/call_assistant/tts_client_streaming.py
```

You should see: `✓ Using virtual device: CABLE Input`

---

## Linux Setup

### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y pulseaudio pulseaudio-utils ffmpeg portaudio19-dev
```

**Fedora/RHEL:**
```bash
sudo dnf install -y pulseaudio pulseaudio-utils ffmpeg portaudio-devel
```

**Arch:**
```bash
sudo pacman -S pulseaudio ffmpeg portaudio
```

### Step 2: Create Virtual Audio Device

Run these commands to create a virtual microphone:

```bash
# Create a virtual sink (acts as a speaker)
pactl load-module module-null-sink sink_name=virtual_mic sink_properties=device.description=Virtual_Microphone

# Create a virtual source (acts as a microphone) that monitors the sink
pactl load-module module-remap-source source_name=virtual_mic_source master=virtual_mic.monitor source_properties=device.description=Virtual_Microphone_Source
```

**To make it permanent** (survives reboot), add to `/etc/pulse/default.pa`:
```bash
# Add these lines at the end of /etc/pulse/default.pa
load-module module-null-sink sink_name=virtual_mic sink_properties=device.description=Virtual_Microphone
load-module module-remap-source source_name=virtual_mic_source master=virtual_mic.monitor source_properties=device.description=Virtual_Microphone_Source
```

Then restart PulseAudio:
```bash
pulseaudio -k
pulseaudio --start
```

### Step 3: Configure 3CX to Use Virtual Microphone

1. Open **3CX** settings
2. Go to **Audio Settings** or **Microphone Settings**
3. Select **Virtual_Microphone_Source** as your microphone
4. This makes 3CX "listen" to your TTS output

### Verify Setup

List audio devices:
```bash
pactl list sources short
```

You should see `Virtual_Microphone_Source` in the list.

Test the TTS client:
```python
python backend/core/call_assistant/tts_client_streaming.py
```

You should see: `✓ Using virtual device: virtual_mic.monitor` or similar

---

## Usage in Your Code

### Simple Usage (Streams to Virtual Mic)

```python
from backend.core.call_assistant.tts_client_streaming import TTSClient

# Initialize
tts = TTSClient(use_virtual_mic=True)

# Speak (will stream to virtual mic)
tts.text_to_speech("Hello, this is a test!")
```

### Advanced Usage (Direct StreamingTTSClient)

```python
from backend.core.call_assistant.tts_client_streaming import StreamingTTSClient

# Initialize
tts = StreamingTTSClient(rate=16000, channels=1)

# Speak
tts.text_to_speech("This streams to the virtual microphone")
```

### Backward Compatibility (Use Speaker Output)

If you want to keep using the old pyttsx3 behavior (output to speakers):

```python
from backend.core.call_assistant.tts_client_streaming import TTSClient

# Use speaker output (old behavior)
tts = TTSClient(use_virtual_mic=False)
tts.text_to_speech("This goes to speakers")
```

---

## Troubleshooting

### Windows

**"VB-Audio Cable not found"**
- Make sure you installed VB-Audio Cable
- Restart your computer
- Check Sound Settings to verify CABLE devices exist

**"No sound in 3CX"**
- Verify 3CX is using "CABLE Output" as microphone
- Test the virtual cable by playing music and selecting CABLE Input as recording device in Windows Sound Settings

**"FFmpeg not found"**
- Install FFmpeg using instructions above
- Restart your terminal/IDE after adding to PATH

### Linux

**"No virtual audio sink found"**
- Run the `pactl load-module` commands from Step 2
- Check with: `pactl list sinks short`

**"PulseAudio not running"**
```bash
pulseaudio --check
pulseaudio --start
```

**"No sound in 3CX"**
- Verify 3CX is using "Virtual_Microphone_Source" as microphone
- Test with: `parecord --device=virtual_mic_source test.wav` (speak into virtual mic, Ctrl+C to stop, then `paplay test.wav`)

---

## How It Works

```
┌─────────────────────┐
│   Your Python App   │
│    (TTS Client)     │
└──────────┬──────────┘
           │
           │ Audio Stream
           ▼
┌─────────────────────┐
│  Virtual Audio      │
│  Cable/Sink         │
│  (Acts as Mic)      │
└──────────┬──────────┘
           │
           │ 3CX Reads From This
           ▼
┌─────────────────────┐
│       3CX           │
│  (Phone System)     │
└─────────────────────┘
```

Your TTS → Virtual Mic → 3CX → Phone Call

---

## Performance Notes

- **gTTS (Google TTS)**: Free, requires internet, ~500ms latency, good voice quality
- **pyttsx3**: Free, offline, fast but can't stream to virtual mic easily

For production, consider:
1. Pre-generating common phrases and caching them to reduce latency
2. Implementing a queue system for multiple simultaneous calls
3. Adding error handling for internet connectivity issues (gTTS requires internet)
