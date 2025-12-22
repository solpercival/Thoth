# CallAssistant V3 - Quick Start Guide

## What is V3?

CallAssistant V3 is a **simplified, LLM-driven voice assistant** that eliminates the complex state machine from V2. Instead of managing conversation states manually, it lets the LLM handle the entire conversation flow naturally.

## Key Features

✅ **19% less code** (493 lines vs 606 in V2)
✅ **Single system prompt** defines entire conversation flow
✅ **No state machine** - LLM manages context via message history
✅ **Action tags** for deterministic system operations
✅ **More natural conversations** - handles variations better
✅ **Easier to maintain** - one place to update conversation logic

## How It Works

### 1. LLM-Driven Flow

The LLM maintains conversation context and outputs **action tags** when system operations are needed:

- `<GETSHIFTS>` - Trigger backend shift query
- `<CONFIRM_CANCEL>` - User confirmed cancellation
- `<REASON>` - User provided cancellation reason
- `<LOGIN>`, `<REAL>`, `<DENY>` - Route to appropriate handler

### 2. Example Conversation

```
User: "I want to cancel my shift tomorrow"
LLM: <GETSHIFTS>cancel shift tomorrow
System: [Fetches shifts from backend]
LLM: "You have a shift at ABC Corp on 2024-01-15 at 9:00 AM. Do you want to cancel this shift?"

User: "Yes"
LLM: <CONFIRM_CANCEL>shift_123
System: [Prepares for reason collection]
LLM: "Please tell me the reason for cancellation"

User: "I'm feeling sick"
LLM: <REASON>I'm feeling sick
System: [Submits cancellation and sends email]
LLM: "Your shift at ABC Corp on 2024-01-15 at 9:00 AM has been cancelled. Is there anything else I can help you with?"
```

The LLM naturally handles the conversation while action tags trigger system operations.

## Running V3

### Option 1: Standalone
```bash
python backend/core/call_assistant/call_assistant_v3.py
```

### Option 2: Flask App (Production)
```bash
python backend/core/call_assistant/app_v3.py
```

Then trigger calls via webhooks:
```bash
# Start call
curl -X POST http://localhost:5000/webhook/call-started \
  -H "Content-Type: application/json" \
  -d '{"call_id": "123", "from": "+1234567890"}'

# End call
curl -X POST http://localhost:5000/webhook/call-ended \
  -H "Content-Type: application/json" \
  -d '{"call_id": "123"}'

# Check status
curl http://localhost:5000/status
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CallAssistantV3                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────┐         │
│  │        Whisper (Speech-to-Text)            │         │
│  └────────────┬───────────────────────────────┘         │
│               │                                          │
│               ▼                                          │
│  ┌────────────────────────────────────────────┐         │
│  │  LLM (Ollama - qwen2.5:7b)                 │         │
│  │  - Single comprehensive system prompt      │         │
│  │  - Maintains conversation via history      │         │
│  │  - Outputs action tags when needed         │         │
│  └────────────┬───────────────────────────────┘         │
│               │                                          │
│               ▼                                          │
│  ┌────────────────────────────────────────────┐         │
│  │    Action Tag Processor                    │         │
│  │    - Detects tags in LLM response          │         │
│  │    - Triggers system operations            │         │
│  │    - Returns text for TTS                  │         │
│  └────────────┬───────────────────────────────┘         │
│               │                                          │
│               ├──→ <GETSHIFTS> → Backend API             │
│               ├──→ <CONFIRM_CANCEL> → Prep cancellation  │
│               ├──→ <REASON> → Submit & Email             │
│               └──→ Text → TTS                            │
│                                                          │
│  ┌────────────────────────────────────────────┐         │
│  │        TTS (Text-to-Speech)                │         │
│  │        → CABLE Input (VoIP)                │         │
│  └────────────────────────────────────────────┘         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Customizing the Conversation Flow

To modify how V3 behaves, edit the `SYSTEM_PROMPT` in [call_assistant_v3.py](call_assistant_v3.py:23-85):

```python
SYSTEM_PROMPT = """You are a call center agent handling shift queries and cancellations.

Follow this flow EXACTLY and output special commands when needed:

1. INITIAL INTENT CLASSIFICATION:
   - If user asks about app login issues → output: <LOGIN>
   ...
```

All conversation logic is in this one prompt - no need to touch the code!

## Adding New Features

### Example: Add Shift Rescheduling

1. **Add to system prompt:**
```python
8. RESCHEDULING (when user wants to reschedule):
   - Ask for the new date/time
   - Output: <RESCHEDULE>shift_id|new_date|new_time
```

2. **Add tag handler in `_process_response()`:**
```python
if "<RESCHEDULE>" in llm_response:
    match = re.search(r'<RESCHEDULE>(\S+)\|(\S+)\|(\S+)', llm_response)
    if match:
        shift_id, new_date, new_time = match.groups()
        return self._handle_reschedule(shift_id, new_date, new_time)
```

3. **Implement handler:**
```python
def _handle_reschedule(self, shift_id: str, new_date: str, new_time: str) -> str:
    # Call backend API to reschedule
    # Return confirmation message
```

That's it! No state machine changes needed.

## Advantages Over V2

| Feature | V2 | V3 |
|---------|----|----|
| Lines of code | 606 | 493 |
| System prompts | 3 separate | 1 unified |
| State management | Manual enum | LLM-driven |
| Conversation flow | Hard-coded transitions | Defined in prompt |
| Adding features | Modify state machine | Update prompt + handler |
| Natural language | Limited by states | Fully flexible |
| Maintainability | Complex | Simple |

## Troubleshooting

### LLM not outputting tags correctly
- Check that your model supports instruction following well
- Try a larger model (e.g., qwen2.5:14b)
- Add more examples to the system prompt

### Conversation getting stuck
- Check logs for action tag detection
- Verify backend API is responding
- LLM message history might need clearing (add reset mechanism)

### TTS errors
- Verify CABLE Input device exists
- Check audio device permissions
- Test TTS independently

## Testing

### Manual Testing
Run standalone and speak:
```bash
python backend/core/call_assistant/call_assistant_v3.py
```

### Test with Mock Data
Modify `test_integrated_workflow` to return mock shifts for testing conversation flow without real backend.

## Next Steps

1. **Test thoroughly** with various conversation patterns
2. **Monitor LLM outputs** to ensure tag generation is reliable
3. **Iterate on system prompt** based on real usage
4. **Add more action tags** as needed for new features
5. **Consider prompt engineering** to improve natural responses

## Questions?

Check the [V2 vs V3 Comparison](V2_VS_V3_COMPARISON.md) for detailed differences.

---

**V3 is the future. Simpler. Smarter. More maintainable.** 🚀

CallAssistant V3 - Architecture Overview
Core Concept
V3 uses a LLM-driven conversation flow instead of a state machine. The LLM maintains conversation context through message history and outputs action tags when system operations are needed.
Flow Diagram

┌─────────────────────────────────────────────────────────────┐
│                     User speaks                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Whisper (Speech-to-Text)                                    │
│  → Transcribes audio to text                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM (Ollama - qwen2.5:7b)                                   │
│  → Single comprehensive system prompt                        │
│  → Maintains context via message history                     │
│  → Decides what to say OR what action to trigger             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Action Tag Processor (_process_response)                    │
│  → Checks LLM output for special tags                        │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┬───────────────┐
        │                         │               │
        ▼                         ▼               ▼
┌──────────────┐    ┌────────────────────┐   ┌──────────────┐
│ Action Tags  │    │  System Operations  │   │  Plain Text  │
│              │    │                     │   │              │
│ <GETSHIFTS>  │───►│ Query Backend API   │   │ "Which shift │
│ <CONFIRM>    │───►│ Prepare Cancel      │   │  do you want │
│ <REASON>     │───►│ Submit & Email      │   │  to cancel?" │
│ <LOGIN>      │───►│ Transfer to Agent   │   │              │
│ <REAL>       │───►│ Transfer to Agent   │   │              │
│ <DENY>       │───►│ Reject Request      │   │              │
└──────────────┘    └────────────┬───────┘   └──────┬───────┘
                                 │                   │
                                 └─────────┬─────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │  _clean_response()    │
                               │  → Strip "User:" etc  │
                               └───────────┬───────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │  TTS (Text-to-Speech) │
                               │  → CABLE Input (VoIP) │
                               └───────────────────────┘
Key Components
1. Single System Prompt (Lines 23-93)
Defines the ENTIRE conversation flow in one place:
Intent classification
Multi-turn dialogue handling
When to output action tags
Conversation rules

SYSTEM_PROMPT = """You are a call center agent handling shift queries and cancellations.

Follow this flow EXACTLY and output special commands when needed:
1. INITIAL INTENT CLASSIFICATION...
2. SHIFT QUERY...
3. HANDLING SHIFT RESULTS...
...
"""
2. Action Tags
Special commands the LLM outputs to trigger system operations:
Tag	Purpose	Example
<GETSHIFTS>	Query backend for shifts	<GETSHIFTS>cancel shift tomorrow
<CONFIRM_CANCEL>	User confirmed cancellation	<CONFIRM_CANCEL>shift_123
<REASON>	User provided cancellation reason	<REASON>I'm feeling sick
<LOGIN>	Login assistance needed	Routes to support
<REAL>	User wants real agent	Routes to human
<DENY>	Request can't be handled	Polite rejection
3. Message History
The LLM maintains conversation context automatically through OllamaClient:
Each user phrase is added to history
Each LLM response is added to history
LLM "remembers" what was said before
No manual state tracking needed!
Example Conversation Flow

# Turn 1
User: "I want to cancel my shift tomorrow"
  ↓
LLM: <GETSHIFTS>cancel shift tomorrow
  ↓
_process_response() detects <GETSHIFTS>
  ↓
_handle_get_shifts() calls backend API
  ↓
Backend returns: [shift at ABC Corp, 10AM, Dec 19]
  ↓
Inject into LLM: "SYSTEM: Found 1 shift: {...} | User wants to CANCEL"
  ↓
LLM: "You have a shift at ABC Corp on Dec 19 at 10 AM. Do you want to cancel?"
  ↓
TTS speaks this to user

# Turn 2
User: "Yes"
  ↓
LLM: <CONFIRM_CANCEL>shift_123
  ↓
_process_response() detects <CONFIRM_CANCEL>
  ↓
_handle_confirm_cancel() stores shift_id
  ↓
Inject into LLM: "SYSTEM: User confirmed cancellation. Now ask for reason."
  ↓
LLM: "Please tell me the reason for cancellation"
  ↓
TTS speaks this to user

# Turn 3
User: "I'm feeling sick"
  ↓
LLM: <REASON>I'm feeling sick
  ↓
_process_response() detects <REASON>
  ↓
_handle_cancellation_reason() calls _submit_cancellation()
  ↓
Formats email and sends notification
  ↓
Inject into LLM: "SYSTEM: Cancellation successful. Thank user."
  ↓
LLM: "Your shift at ABC Corp on Dec 19 at 10 AM has been cancelled. Anything else?"
  ↓
TTS speaks this to user
Key Methods
on_phrase_complete(phrase) (Line 122)
Entry point when Whisper completes transcription
Pauses audio processing
Sends phrase to LLM
Processes response and speaks it
Resumes audio processing
_process_response(llm_response, user_phrase) (Line 162)
Checks for action tags in LLM response
Routes to appropriate handler
Falls back to cleaning and returning text
_clean_response(response) (Line 199)
Strips out hypothetical future dialogue
Removes "User:" and "You:" prefixes
Ensures only immediate response is spoken
_handle_get_shifts(query) (Line 219)
Calls test_integrated_workflow() with phone + query
Uses same date reasoner as V1/V2 ✅
Validates shifts against backend ✅
Injects shift data into LLM conversation
Returns natural language response
_handle_confirm_cancel(shift_id) (Line 266)
Finds shift by ID in context
Stores selected shift
Asks LLM to request cancellation reason
_handle_cancellation_reason(reason) (Line 302)
Submits cancellation
Sends email notification
Confirms with user
Why V3 is Simpler
No State Machine:
V2 had 5 explicit states (IDLE, AWAITING_CONFIRMATION, etc.)
V3 lets LLM manage state implicitly through context
Single Prompt:
V2 had 3 separate system prompts
V3 has ONE comprehensive prompt
Fewer Lines:
V2: 606 lines
V3: 493 lines (19% reduction)
Easier to Modify:
Want to add feature? Update prompt + add tag handler
No state machine transitions to manage
Context Storage

self.context = {
    'current_shifts': [],      # Shifts from last backend query
    'selected_shift': None,    # Currently selected shift
    'staff_info': {},          # Staff info for email
    'is_cancellation': False,  # Whether user wants to cancel
}
Minimal context - just what's needed for current operation.
Integration Points
Same as V1/V2:
✅ test_integrated_workflow() - Date reasoning + backend API
✅ format_ezaango_shift_data() - Email formatting
✅ send_notify_email() - Email sending (currently commented out)
✅ SystemAudioWhisperClient - Speech-to-text
✅ TTSClient - Text-to-speech
The only difference is the conversation management layer!
TL;DR: V3 uses a smart LLM to manage the conversation naturally, outputting action tags when system operations are needed. It's simpler, more flexible, and easier to maintain than the state machine approach in V2.