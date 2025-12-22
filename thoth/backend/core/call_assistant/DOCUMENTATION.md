# Call Assistant - Complete Documentation

AI-powered voice assistant for handling phone calls through 3CX with shift management capabilities.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Version Comparison (V2 vs V3)](#version-comparison)
4. [Audio Configuration](#audio-configuration)
5. [LLM-Driven Flow (V3)](#llm-driven-flow-v3)
6. [State Machine Design (V2)](#state-machine-design-v2)
7. [API Reference](#api-reference)
8. [Deployment](#deployment)

---

## Quick Start

### Prerequisites

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install -y pulseaudio pulseaudio-utils ffmpeg portaudio19-dev espeak
```

**Python Dependencies:**
```bash
pip install -r requirements.txt
```

### Setup Ollama

```bash
ollama serve
ollama pull qwen2.5:7b
```

### Create Virtual Audio Device (Linux)

```bash
# Create virtual speaker for TTS output
pactl load-module module-null-sink sink_name=virtual_speaker media.class=Audio/Sink

# The monitor (virtual_speaker.monitor) is automatically created for input capture
```

### Run the Assistant

**V3 (Recommended - LLM-driven):**
```bash
cd thoth/backend/core/call_assistant
python app_v3.py
```

**V2 (State machine-based):**
```bash
python app_v2.py
```

Server starts on `http://localhost:5000`

### Test with Webhooks

```bash
# Start a call
curl -X POST http://localhost:5000/webhook/call-started \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test123", "from": "+1234567890"}'

# End the call
curl -X POST http://localhost:5000/webhook/call-ended \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test123"}'

# Check status
curl http://localhost:5000/status
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    3CX Phone System                      │
│                  (Triggers Webhooks)                     │
└────────────────┬──────────────────┬─────────────────────┘
                 │                  │
          [Call Started]      [Call Ended]
                 │                  │
                 ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                  Flask App (app_v3.py)                   │
│            Webhook Endpoints & Session Manager          │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Creates & Manages
                 ▼
┌─────────────────────────────────────────────────────────┐
│               CallAssistantV3 (Main Logic)              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Audio Capture → Transcription → LLM → TTS        │  │
│  └───────────────────────────────────────────────────┘  │
└─┬────────────┬────────────┬────────────┬──────────────┘
  │            │            │            │
  ▼            ▼            ▼            ▼
┌──────┐  ┌─────────┐  ┌───────┐  ┌──────────┐
│Whisper│  │ Ollama  │  │Backend│  │   TTS    │
│ STT   │  │   LLM   │  │  API  │  │(espeak)  │
└──────┘  └─────────┘  └───────┘  └──────────┘
```

### Component Overview

1. **Audio Capture** (`system_audio_whisper_client.py`)
   - Captures system audio from 3CX calls
   - Real-time Whisper transcription
   - Platform: Linux (PipeWire/PulseAudio), Windows (WASAPI)

2. **LLM Processing** (`llm_client.py`)
   - Ollama interface for qwen2.5:7b
   - Conversation context management
   - Action tag generation

3. **TTS Output** (`tts_client.py`)
   - Text-to-speech using espeak (Linux) or pyttsx3 (Windows)
   - Routes audio to virtual_speaker (Linux) or CABLE Input (Windows)

4. **Backend Integration**
   - Shift queries, cancellations, email notifications
   - Staff lookup and management

---

## Version Comparison

### V3 vs V2

| Feature | V2 (State Machine) | V3 (LLM-Driven) |
|---------|-------------------|-----------------|
| **Lines of code** | 606 | 493 (-19%) |
| **Architecture** | Explicit state enum | LLM context-driven |
| **System prompts** | 3 separate prompts | 1 unified prompt |
| **Conversation flow** | Hard-coded transitions | Defined in prompt text |
| **Adding features** | Modify state machine code | Update prompt + add tag handler |
| **Natural language** | Limited by state definitions | Fully flexible |
| **Maintainability** | Complex, requires understanding states | Simple, edit one prompt |
| **Debugging** | Check state transitions | Check LLM action tags |

### When to Use Each

**Use V3 if:**
- You want natural, flexible conversations
- You plan to frequently update conversation logic
- You prefer prompt engineering over code changes
- Your LLM is reliable (qwen2.5:7b or better)

**Use V2 if:**
- You need deterministic, predictable behavior
- You want explicit control over every transition
- Your LLM is inconsistent with instructions
- You need to audit conversation paths

---

## Audio Configuration

### Linux Audio Routing

#### Testing Mode
```
Audio Source: virtual_speaker.monitor
Use case: Development/testing
Flow: Test apps → virtual_speaker → Whisper
```

#### Production Mode
```
Audio Source: Jabra Evolve2 monitor
Use case: Real phone calls via 3CX
Flow: 3CX → Jabra headset → Whisper
```

### Usage in Code

```python
from audio_config import get_audio_source
from system_audio_whisper_client import SystemAudioWhisperClient

# For testing
audio_source = get_audio_source(is_testing=True)  # Returns virtual_speaker.monitor

# For production
audio_source = get_audio_source(is_testing=False)  # Returns Jabra monitor

client = SystemAudioWhisperClient(
    model="base",
    audio_source=audio_source
)
```

### TTS Output Configuration

**Linux:**
- TTS outputs to `virtual_speaker` sink via `paplay` command
- Falls back to PyAudio if paplay unavailable

**Windows:**
- TTS outputs to `CABLE Input` device via PyAudio

The platform is auto-detected and appropriate device names are used.

---

## LLM-Driven Flow (V3)

### Core Concept

V3 uses a **single comprehensive system prompt** that defines the entire conversation flow. The LLM maintains context through message history and outputs **action tags** when system operations are needed.

### Action Tags

| Tag | Purpose | Handler |
|-----|---------|---------|
| `<GETSHIFTS>` | Query backend for shifts | Fetches shifts matching date/criteria |
| `<CONFIRM_CANCEL>` | User confirmed cancellation | Prepares for reason collection |
| `<REASON>` | User provided cancellation reason | Submits cancellation + sends email |
| `<LOGIN>` | User has app login issues | Transfers to live agent |
| `<REAL>` | User wants to speak with person | Transfers to live agent |
| `<DENY>` | Request cannot be processed | Politely denies request |

### Example Conversation Flow

```
User: "I want to cancel my shift tomorrow"
↓
LLM: <GETSHIFTS>cancel shift tomorrow
↓
System: [Queries backend API]
Backend returns: Shift at ABC Corp, 2024-01-15, 9:00 AM
↓
LLM: "You have a shift at ABC Corp on January 15th at 9:00 AM. 
      Would you like to cancel this shift?"
↓
User: "Yes"
↓
LLM: <CONFIRM_CANCEL>shift_123
↓
System: [Prepares cancellation workflow]
↓
LLM: "Please tell me the reason for canceling this shift"
↓
User: "I'm feeling sick"
↓
LLM: <REASON>I'm feeling sick
↓
System: [Submits cancellation, sends email notification]
↓
LLM: "Your shift at ABC Corp on January 15th at 9:00 AM has been 
      cancelled and the staff has been notified. Is there anything 
      else I can help you with?"
```

### Customizing the System Prompt

All conversation logic is defined in `SYSTEM_PROMPT` in `call_assistant_v3.py`:

```python
SYSTEM_PROMPT = """You are a professional call center agent...

Follow this flow EXACTLY:

1. INITIAL GREETING:
   - Greet caller warmly
   - Ask how you can help

2. SHIFT QUERIES (when user asks about shifts):
   - Output: <GETSHIFTS>user's query
   - Wait for system to provide shift data
   - Present shift information clearly
   ...

8. ALWAYS be polite, professional, and helpful.
"""
```

To modify behavior, simply edit this prompt - no code changes needed!

### Adding New Features

**Example: Add shift rescheduling**

1. Update system prompt:
```python
7. RESCHEDULING (when user wants to reschedule):
   - Ask for the new date/time
   - Output: <RESCHEDULE>shift_id|new_date|new_time
```

2. Add tag handler in `_process_response()`:
```python
if "<RESCHEDULE>" in llm_response:
    match = re.search(r'<RESCHEDULE>(\S+)\|(\S+)\|(\S+)', llm_response)
    if match:
        shift_id, new_date, new_time = match.groups()
        return self._handle_reschedule(shift_id, new_date, new_time)
```

3. Implement handler method:
```python
def _handle_reschedule(self, shift_id, new_date, new_time):
    # Call backend API
    # Return confirmation message
```

---

## State Machine Design (V2)

V2 uses explicit conversation states with deterministic transitions.

### States

```python
class ConversationState(Enum):
    IDLE = "idle"                      # No active conversation
    AWAITING_CONFIRMATION = "confirm"   # Asked yes/no question
    AWAITING_REASON = "reason"          # Collecting cancellation reason
    AWAITING_CHOICE = "choice"          # User choosing from multiple shifts
    PROCESSING = "processing"           # System working
```

### State Transitions

```
IDLE
  ├─ User: "Cancel my shift tomorrow"
  ├─ Intent: <SHIFT>
  ├─ Find shift(s)
  │
  ├─ If 1 shift found:
  │   └─→ AWAITING_CONFIRMATION
  │       └─ System: "Confirm cancellation?"
  │           ├─ User: "Yes" → AWAITING_REASON
  │           └─ User: "No" → IDLE
  │
  └─ If multiple shifts:
      └─→ AWAITING_CHOICE
          └─ System: "Which shift? 1) ABC 2pm, 2) DEF 4pm..."
              └─ User: "The first one" → AWAITING_CONFIRMATION

AWAITING_CONFIRMATION
  ├─ User: "Yes" → AWAITING_REASON
  └─ User: "No" → IDLE

AWAITING_REASON
  └─ User provides reason
      └─ Submit cancellation
      └─→ IDLE
```

### Implementation

```python
def on_phrase_complete(self, phrase: str):
    """Route based on conversation state"""
    
    if self.state == ConversationState.IDLE:
        self._handle_new_request(phrase)
    
    elif self.state == ConversationState.AWAITING_CONFIRMATION:
        self._handle_confirmation(phrase)
    
    elif self.state == ConversationState.AWAITING_REASON:
        self._handle_reason(phrase)
    
    elif self.state == ConversationState.AWAITING_CHOICE:
        self._handle_choice(phrase)
```

---

## API Reference

### Webhook Endpoints

#### POST `/webhook/call-started`
Start a new call session.

**Request:**
```json
{
  "call_id": "unique_call_id",
  "from": "+1234567890"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Call session started",
  "call_id": "unique_call_id"
}
```

#### POST `/webhook/call-ended`
End an active call session.

**Request:**
```json
{
  "call_id": "unique_call_id"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Call session ended"
}
```

#### GET `/status`
Get system status and active sessions.

**Response:**
```json
{
  "status": "running",
  "active_calls": 2,
  "sessions": {
    "call_123": {
      "from": "+1234567890",
      "start_time": "2024-01-15T10:30:00"
    }
  }
}
```

### Configuration

**Environment Variables:**
```bash
FLASK_PORT=5000              # Flask server port
OLLAMA_HOST=localhost:11434  # Ollama server
WHISPER_MODEL=base           # Whisper model size
BACKEND_API_URL=http://...   # Shift backend API
```

---

## Deployment

### Development

```bash
# Start Ollama
ollama serve

# Run Flask app with auto-reload
python app_v3.py
```

### Production

**Using systemd (Linux):**

Create `/etc/systemd/system/call-assistant.service`:

```ini
[Unit]
Description=Call Assistant V3
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/thoth/backend/core/call_assistant
ExecStart=/path/to/venv/bin/python app_v3.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable call-assistant
sudo systemctl start call-assistant
sudo systemctl status call-assistant
```

### Docker

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    pulseaudio \
    ffmpeg \
    portaudio19-dev \
    espeak \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app_v3.py"]
```

---

## Troubleshooting

### Audio Issues

**Problem:** No audio captured from 3CX
- Verify audio device: `pactl list sources short`
- Check Jabra is connected and selected
- Test with: `parec --device=<device> | aplay`

**Problem:** TTS not playing
- Check virtual_speaker exists: `pactl list sinks short | grep virtual`
- Test espeak: `espeak "test"`
- Check paplay: `paplay /usr/share/sounds/alsa/Front_Center.wav`

### LLM Issues

**Problem:** LLM not outputting action tags
- Verify model supports instructions: Use qwen2.5:7b or better
- Check system prompt is loaded correctly
- Add more examples to the prompt

**Problem:** LLM responses too slow
- Use smaller model for faster responses (trade-off: less accuracy)
- Increase Ollama GPU allocation
- Consider streaming responses

### Backend Integration

**Problem:** Shifts not loading
- Check backend API is accessible
- Verify authentication tokens
- Check logs for API errors

---

## Example Conversations

### Shift Cancellation

```
System: Hello! How can I help you today?
User: I need to cancel my shift on Friday
System: <GETSHIFTS>cancel shift Friday
System: You have a shift at ABC Hospital on Friday, January 19th at 2:00 PM. 
        Would you like to cancel this shift?
User: Yes please
System: <CONFIRM_CANCEL>shift_456
System: Could you please tell me the reason for canceling this shift?
User: I have a family emergency
System: <REASON>family emergency
System: Your shift at ABC Hospital on Friday, January 19th at 2:00 PM has been 
        cancelled. The staff has been notified via email. Is there anything else?
User: No, that's all
System: Thank you for calling. Have a great day!
```

### Multiple Shifts

```
System: Hello! How can I help you today?
User: Cancel my shift tomorrow
System: <GETSHIFTS>cancel shift tomorrow
System: You have 2 shifts tomorrow. Which one would you like to cancel?
        1. ABC Hospital at 9:00 AM
        2. DEF Clinic at 3:00 PM
User: The morning one
System: You want to cancel the shift at ABC Hospital at 9:00 AM. Is that correct?
User: Yes
System: <CONFIRM_CANCEL>shift_789
System: Please tell me the reason for canceling this shift.
...
```

### Transfer to Agent

```
System: Hello! How can I help you today?
User: I'm having trouble logging into the app
System: <LOGIN>
System: I understand you're having login issues. Let me transfer you to 
        a technical support agent who can help you with that.
[Call transfers to live agent]
```

---

## License

[Add your license information here]

## Support

For issues or questions, contact [your contact information]
