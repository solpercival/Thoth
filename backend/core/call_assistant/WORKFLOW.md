# Call Assistant Workflow Documentation

## Overview
The Call Assistant is an AI-powered voice assistant for handling phone calls through 3CX. It listens to system audio, transcribes speech, classifies user intent, and responds with appropriate actions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         3CX Phone System                         │
│                    (Triggers Webhooks)                           │
└────────────────┬──────────────────────────┬─────────────────────┘
                 │                          │
          [Call Started]              [Call Ended]
                 │                          │
                 ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         app.py (Flask)                           │
│              Webhook Endpoints & Session Manager                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Creates & Manages
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    call_assistant.py                             │
│                  Main Orchestrator Class                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  1. Audio Capture → 2. Transcription → 3. Intent → 4. TTS │  │
│  └───────────────────────────────────────────────────────────┘  │
└─┬───────┬──────────┬────────────┬────────────┬─────────────────┘
  │       │          │            │            │
  │       │          │            │            │
  ▼       ▼          ▼            ▼            ▼
┌────┐ ┌────┐   ┌────────┐   ┌──────┐   ┌──────────┐
│ 1  │ │ 2  │   │   3    │   │  3.1 │   │    4     │
└────┘ └────┘   └────────┘   └──────┘   └──────────┘
```

## Component Details

### 1. Audio Capture - [system_audio_whisper_client.py](system_audio_whisper_client.py)
**Purpose**: Captures system audio (from 3CX call) and transcribes it in real-time

**Key Features**:
- Cross-platform audio capture (Windows WASAPI, Linux PulseAudio)
- Real-time Whisper transcription
- Phrase detection with configurable timeout
- Pause/Resume capability
- Silence detection

**Flow**:
```
System Audio → PyAudio → Audio Chunks → Whisper Model → Text Transcription
     ↓
Phrase Complete Event → Callback to CallAssistant
```

**Configuration**:
- `model`: Whisper model size (tiny, base, small, medium, large)
- `phrase_timeout`: Seconds of silence before phrase is complete (default: 5s)
- `silence_threshold`: Audio level to detect speech vs silence (default: 0.01)
- `max_phrase_duration`: Force phrase completion after N seconds (default: 15s)

### 2. LLM Client - [llm_client.py](llm_client.py)
**Purpose**: Interface to Ollama for LLM processing

**Key Features**:
- Manages conversation history
- Configurable system prompts
- Model selection

**Models Used**:
- Intent classification: `qwen2.5:7b`
- Response formatting: (same model, different system prompt)

**Methods**:
- `ask_llm(prompt)`: Send query and get response
- `set_system_prompt(prompt)`: Update system instructions
- `clear_history()`: Reset conversation

### 3. Intent Classification & Routing - [call_assistant.py](call_assistant.py:166-234)
**Purpose**: Classify user requests and route to appropriate handlers

**Intent Tags**:
- `<LOGIN>`: User has app login issues → Transfer to live agent
- `<SHIFT>`: User asking about work shifts → Process shift request
- `<REAL>`: User wants to speak with real person → Transfer to live agent
- `<DENY>`: Request cannot be processed → Deny politely

**System Prompt**:
```python
LLM_SYSTEM_PROMPT = """
You are a call center routing agent. Your ONLY job is to classify
user requests and output exactly ONE of the following tags:
<LOGIN>, <SHIFT>, <REAL>, <DENY>
"""
```

### 3.1 Date Reasoning - [shift_date_reasoner.py](shift_date_reasoner.py)
**Purpose**: Interpret temporal expressions in shift queries using LLM

**Input Examples**:
- "Cancel my shift tomorrow"
- "What shifts do I have next week?"
- "When is my shift on the 25th?"

**Output Format**:
```json
{
  "is_shift_query": true,
  "date_range_type": "tomorrow",
  "start_date": "17-12-2025",
  "end_date": "17-12-2025",
  "reasoning": "<CNCL> User wants to cancel shift tomorrow"
}
```

**Date Interpretation Rules**:
- "tomorrow" → Today + 1 day
- "next week" → 7 days from today
- "this week" → Today until Sunday
- "next month" → Entire next calendar month
- No date mentioned → Today + 7 days (default)

**Reasoning Tags**:
- `<CNCL>`: User wants to cancel a shift
- `<SHOW>`: User wants to view shifts

### 4. Text-to-Speech - [tts_client.py](tts_client.py)
**Purpose**: Convert AI responses to speech and play through virtual audio cable

**Technology**: pyttsx3 + PyAudio

**Configuration**:
- `rate`: Speech rate in words per minute (default: 150)
- `volume`: Volume level 0.0-1.0 (default: 0.9)
- `output_device_name`: Target audio device (e.g., "CABLE Input")

**Process**:
1. Generate speech with pyttsx3
2. Save to temporary WAV file
3. Play through specified audio device
4. Clean up temporary file

## Complete Workflow

### Call Lifecycle

#### 1. Call Starts
```
3CX → POST /webhook/call-started
      {
        "call_id": "abc123",
        "from": "+1234567890"
      }
      ↓
Flask creates CallAssistant instance
      ↓
Start SystemAudioWhisperClient
      ↓
Begin listening to system audio
```

#### 2. User Speaks
```
User: "I want to cancel my shift tomorrow"
      ↓
System Audio Captured
      ↓
Whisper Transcription
      ↓
Phrase Complete Event
      ↓
on_phrase_complete() callback
```

#### 3. Intent Processing
```
Transcript → LLM (qwen2.5:7b)
      ↓
LLM Response: "<SHIFT>"
      ↓
_route_intent("<SHIFT>")
      ↓
Call test_integrated_workflow()
  ├─ Login to system (Playwright)
  ├─ Lookup staff by phone
  ├─ Reason dates with ShiftDateReasoner
  │   Input: "cancel my shift tomorrow"
  │   Output: {start_date: "17-12-2025", end_date: "17-12-2025", reasoning: "<CNCL>..."}
  ├─ Search shifts in date range
  └─ Filter and format results
      ↓
Return JSON response
```

#### 4. Response Generation
```
JSON Response → LLM (formatting)
      ↓
Natural language response:
"You have a shift with ABC Hospital at 2pm on Tuesday, December 17th"
      ↓
TTSClient.text_to_speech()
      ↓
Play through CABLE Input → 3CX
```

#### 5. Call Ends
```
3CX → POST /webhook/call-ended
      {"call_id": "abc123"}
      ↓
Set stop_event
      ↓
Cleanup audio resources
      ↓
Remove session from active_sessions
```

## File Structure

```
call_assistant/
├── app.py                          # Flask webhook server
├── call_assistant.py               # Main orchestrator
├── system_audio_whisper_client.py  # Audio capture & transcription
├── llm_client.py                   # Ollama LLM interface
├── shift_date_reasoner.py          # Date interpretation
├── tts_client.py                   # Text-to-speech
├── tts_client_streaming.py         # Streaming TTS (alternative)
├── agents/
│   ├── agent.py                    # Base agent class
│   └── agent_chooser.py            # Agent selection logic
├── test_date_reasoner.py           # Date reasoner tests
├── test_virtual_cable.py           # Audio device tests
├── VIRTUAL_MIC_SETUP.md            # Audio setup guide
└── TEST_GUIDE.md                   # Testing instructions
```

## Dependencies

### Python Packages
- `flask`: Webhook server
- `whisper`: Speech-to-text
- `ollama`: LLM interface
- `pyttsx3`: Text-to-speech
- `pyaudio`: Audio I/O
- `pyaudiowpatch`: Windows WASAPI support (Windows only)
- `playwright`: Browser automation for shift lookup
- `torch`: PyTorch (for Whisper)

### External Services
- **Ollama**: Local LLM server (`http://127.0.0.1:11434`)
  - Models: `qwen2.5:7b`, `gemma3:1b`, `llama2:latest`
- **3CX**: Phone system for call handling
- **Virtual Audio Cable**: Route audio between 3CX and Python

## Configuration

### Environment Variables
- `SHIFT_REASONER_TODAY`: Override today's date for testing (YYYY-MM-DD)

### Audio Devices
- **Input**: System audio loopback (Windows: WASAPI, Linux: PulseAudio)
- **Output**: Virtual audio cable (e.g., "CABLE Input")

## Testing

### Manual Testing
```bash
# Test date reasoner
python test_date_reasoner.py

# Test virtual audio cable
python test_virtual_cable.py

# Test call assistant directly
python call_assistant.py
```

### Running the Server
```bash
# Start Ollama
ollama serve

# Start Flask app
python app.py

# Server runs on http://localhost:5000
```

## Error Handling

### Audio Issues
- **No audio device found**: Check virtual cable installation
- **Transcription fails**: Verify Whisper model is loaded
- **Silence not detected**: Adjust `silence_threshold` parameter

### LLM Issues
- **No response**: Check Ollama is running (`ollama serve`)
- **Wrong intent**: Review and update `LLM_SYSTEM_PROMPT`
- **Date parsing errors**: Check `ShiftDateReasoner.SYSTEM_PROMPT_TEMPLATE`

### Session Management
- Sessions are tracked by `call_id`
- Auto-cleanup on call end
- Daemon threads prevent blocking Flask shutdown
- Graceful shutdown with timeout (5 seconds)

## Performance Considerations

### Latency Points
1. **Whisper transcription**: 1-3 seconds (depends on model size)
2. **LLM inference**: 0.5-2 seconds (depends on model and hardware)
3. **TTS generation**: 0.5-1 second
4. **Total response time**: ~3-6 seconds

### Optimization Tips
- Use smaller Whisper models (base/small) for faster transcription
- Use lighter LLM models (gemma3:1b) for faster inference
- Adjust `phrase_timeout` to balance accuracy vs speed
- Pre-load models on server startup

## Security Considerations

- Caller phone numbers are logged
- Session data stored in memory only
- No persistent storage of call audio
- Webhook endpoints should be secured (add authentication in production)
- Virtual audio cable prevents audio leakage to system speakers

## Version Comparison

### V1: call_assistant.py (Single-Turn)

⚠️ **Limitation**: The V1 implementation treats each phrase independently and cannot handle multi-turn conversations.

**Problem**: When the whisper client resumes after responding, the next phrase goes through the same intent classification flow.

**Example of what doesn't work in V1**:
```
User: "Cancel my shift tomorrow"
System: "You have a shift at ABC at 2pm. Do you want to cancel?"
User: "Yes"  ← This gets sent to intent classifier (wrong!)
System: "Please tell me the reason"
User: "I'm sick"  ← This also gets sent to intent classifier (wrong!)
```

### V2: call_assistant_v2.py (Multi-Turn) ✅

**Solution**: V2 implements a state machine that tracks conversation context and enables multi-turn dialogues.

**Features**:
- State tracking (`IDLE`, `AWAITING_CONFIRMATION`, `AWAITING_REASON`, `AWAITING_CHOICE`)
- Context preservation between phrases
- Follow-up questions and confirmations
- Better error recovery

**Files**:
- [call_assistant_v2.py](call_assistant_v2.py) - V2 implementation with state machine
- [app_v2.py](app_v2.py) - Flask app using V2
- [MULTI_TURN_DESIGN.md](MULTI_TURN_DESIGN.md) - Design document
- [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md) - Example conversations
- [MIGRATION_V1_TO_V2.md](MIGRATION_V1_TO_V2.md) - Migration guide

**Recommended**: Use V2 for production deployments.

## Future Enhancements

- [x] **Multi-turn conversation support** - Implemented in [call_assistant_v2.py](call_assistant_v2.py)
- [ ] Multi-language support
- [ ] Voice activity detection (VAD) for faster phrase detection
- [ ] Streaming TTS for lower latency
- [ ] Agent specialization (see [agents/](agents/))
- [ ] Call recording and transcription export
- [ ] Real-time dashboard for active calls
- [ ] Analytics and reporting
