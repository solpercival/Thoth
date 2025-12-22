# Call Assistant

AI-powered voice assistant for handling phone calls through 3CX with shift management capabilities.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Ollama
```bash
ollama serve
ollama pull qwen2.5:7b
ollama pull gemma3:1b
```

### 3. Run the Assistant (V2 Recommended)
```bash
cd backend/core/call_assistant
python app_v2.py
```

Server will start on `http://localhost:5000`

### 4. Test with Webhooks
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

## Documentation

### Core Documentation
- **[WORKFLOW.md](WORKFLOW.md)** - Complete system architecture and workflow
- **[MULTI_TURN_DESIGN.md](MULTI_TURN_DESIGN.md)** - State machine design for V2
- **[CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md)** - Example conversations
- **[MIGRATION_V1_TO_V2.md](MIGRATION_V1_TO_V2.md)** - Migration guide

### Setup Guides
- **[VIRTUAL_MIC_SETUP.md](VIRTUAL_MIC_SETUP.md)** - Audio device setup
- **[TEST_GUIDE.md](TEST_GUIDE.md)** - Testing instructions

## File Overview

### Main Applications
| File | Description | Status |
|------|-------------|--------|
| [app_v2.py](app_v2.py) | Flask webhook server (V2) | ✅ Recommended |
| [app.py](app.py) | Flask webhook server (V1) | ⚠️ Legacy |
| [call_assistant_v2.py](call_assistant_v2.py) | Multi-turn conversation engine | ✅ Recommended |
| [call_assistant.py](call_assistant.py) | Single-turn conversation engine | ⚠️ Legacy |

### Components
| File | Purpose |
|------|---------|
| [system_audio_whisper_client.py](system_audio_whisper_client.py) | Audio capture & transcription |
| [llm_client.py](llm_client.py) | Ollama LLM interface |
| [shift_date_reasoner.py](shift_date_reasoner.py) | Date interpretation with LLM |
| [tts_client.py](tts_client.py) | Text-to-speech |
| [tts_client_streaming.py](tts_client_streaming.py) | Streaming TTS (experimental) |

### Testing
| File | Purpose |
|------|---------|
| [test_date_reasoner.py](test_date_reasoner.py) | Test date interpretation |
| [test_virtual_cable.py](test_virtual_cable.py) | Test audio routing |

### Agents (Future)
| File | Purpose |
|------|---------|
| [agents/agent.py](agents/agent.py) | Base agent class |
| [agents/agent_chooser.py](agents/agent_chooser.py) | Agent selection logic |

## Versions

### V1: Single-Turn (Legacy)
- Files: `call_assistant.py`, `app.py`
- Limitation: Cannot handle follow-up questions
- Status: ⚠️ Not recommended for new deployments

### V2: Multi-Turn (Recommended)
- Files: `call_assistant_v2.py`, `app_v2.py`
- Features:
  - State machine for conversation flow
  - Follow-up questions and confirmations
  - Better error recovery
  - Context preservation
- Status: ✅ Production ready

See [MIGRATION_V1_TO_V2.md](MIGRATION_V1_TO_V2.md) for migration details.

## Architecture

```
3CX Phone System
      ↓
Flask Webhooks (app_v2.py)
      ↓
CallAssistantV2 (call_assistant_v2.py)
      ↓
├─ SystemAudioWhisperClient (transcription)
├─ OllamaClient (LLM for intent & reasoning)
├─ ShiftDateReasoner (date interpretation)
└─ TTSClient (text-to-speech)
```

## Workflow Example

### Multi-Turn Conversation (V2)
```
1. User: "Cancel my shift tomorrow"
   State: IDLE → AWAITING_CONFIRMATION
   System: "You have a shift at ABC Hospital at 2pm. Confirm?"

2. User: "Yes"
   State: AWAITING_CONFIRMATION → AWAITING_REASON
   System: "Please tell me the reason"

3. User: "I'm sick"
   State: AWAITING_REASON → IDLE
   System: "Cancelled. Reason recorded: I'm sick"
```

See [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md) for more scenarios.

## Configuration

### Environment Variables
```bash
# Override today's date for testing
export SHIFT_REASONER_TODAY="2025-12-25"
```

### Audio Settings
- **Input**: System audio loopback (WASAPI/PulseAudio)
- **Output**: Virtual audio cable (e.g., "CABLE Input")

See [VIRTUAL_MIC_SETUP.md](VIRTUAL_MIC_SETUP.md) for setup.

### LLM Models
- **Intent classification**: `qwen2.5:7b`
- **Date reasoning**: `gemma3:1b` or `llama2:latest`
- **Yes/No detection**: Uses same model as intent

Change models in the code:
```python
# In call_assistant_v2.py
self.llm_client = OllamaClient(model="qwen2.5:7b", ...)

# In shift_date_reasoner.py
reasoner = ShiftDateReasoner(model="gemma3:1b")
```

## API Endpoints

### POST /webhook/call-started
Start a new call session
```json
{
  "call_id": "unique-call-id",
  "from": "+1234567890"
}
```

### POST /webhook/call-ended
End an active call session
```json
{
  "call_id": "unique-call-id"
}
```

### GET /status
View active sessions
```json
{
  "active_sessions": 2,
  "sessions": [
    {
      "call_id": "test123",
      "version": "v2",
      "uptime": 45.2,
      "started_at": "Tue Dec 17 14:30:00 2025"
    }
  ]
}
```

## Troubleshooting

### Audio Issues
```bash
# Test virtual cable
python test_virtual_cable.py

# Check audio devices
python -c "import pyaudio; p=pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

### LLM Issues
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test date reasoning
python test_date_reasoner.py
```

### State Machine Issues
- Check logs for `[CONVERSATION STATE]` messages
- Verify state transitions match expected flow
- Review [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md)

## Performance

### Latency Breakdown
- **Transcription**: 1-3 seconds (depends on Whisper model)
- **LLM inference**: 0.5-2 seconds (depends on model)
- **TTS generation**: 0.5-1 second
- **Total (first turn)**: ~5 seconds
- **Total (follow-up)**: ~3.5 seconds (30-40% faster)

### Optimization Tips
- Use smaller Whisper models (`base` or `small`)
- Use lighter LLM models (`gemma3:1b`)
- Adjust `phrase_timeout` for faster detection
- Consider streaming TTS for lower latency

## Security

- Caller phone numbers are logged
- Session data stored in memory only
- No persistent storage of call audio
- Webhook endpoints should be secured in production
- Virtual audio cable prevents audio leakage

## Development

### Running Tests
```bash
# Test date reasoner
python test_date_reasoner.py

# Test virtual cable
python test_virtual_cable.py

# Test call assistant directly (without Flask)
python call_assistant_v2.py
```

### Adding New States
See [MIGRATION_V1_TO_V2.md](MIGRATION_V1_TO_V2.md) FAQ section.

### Contributing
1. Read [WORKFLOW.md](WORKFLOW.md) to understand the architecture
2. Review [MULTI_TURN_DESIGN.md](MULTI_TURN_DESIGN.md) for state machine design
3. Test with examples from [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md)
4. Ensure backward compatibility with V1 API

## License

[Your license here]

## Support

For issues or questions:
1. Check documentation in this folder
2. Review logs for error messages
3. Test individual components
4. Create an issue in the repository
