# Migration Guide: V1 to V2

This guide explains how to migrate from `call_assistant.py` (V1) to `call_assistant_v2.py` (V2) with multi-turn conversation support.

## What's New in V2

### State Machine
- **ConversationState enum**: Tracks where you are in the conversation
  - `IDLE`: No active conversation
  - `AWAITING_CONFIRMATION`: Asked yes/no question
  - `AWAITING_REASON`: Collecting cancellation reason
  - `AWAITING_CHOICE`: User selecting from multiple shifts

### Context Management
- **context dict**: Preserves data between phrases
  - `pending_shift`: Single shift to cancel/view
  - `pending_shifts`: Multiple shifts (if ambiguous)
  - `cancellation_reason`: User's cancellation reason
  - `original_intent`: `<CNCL>` or `<SHOW>`
  - `last_query`: Last user query

### New Handlers
- `_handle_confirmation()`: Process yes/no responses
- `_handle_reason()`: Collect cancellation reason
- `_handle_choice()`: Select from multiple shifts
- `_speak_and_reset()`: Respond and reset to IDLE
- `_reset_state()`: Clear context and return to IDLE

### Better LLM Prompts
- `YES_NO_SYSTEM_PROMPT`: Detect yes/no responses
- `NUMBER_EXTRACTION_PROMPT`: Extract choice numbers from natural language

---

## Breaking Changes

### API Changes

#### V1
```python
class CallAssistant:
    def __init__(self, caller_phone: Optional[str] = None):
        # Only tracks basic state
        self.llm_response_array = []
        self.transcript = ""
```

#### V2
```python
class CallAssistantV2:
    def __init__(self, caller_phone: Optional[str] = None):
        # Adds state machine
        self.state = ConversationState.IDLE
        self.context = {
            'pending_shift': None,
            'pending_shifts': [],
            'cancellation_reason': None,
            'original_intent': None,
            'last_query': None,
        }
```

### Behavior Changes

#### V1: Single Turn
```
User: "Cancel my shift tomorrow"
System: [Finds shift] "You have a shift at ABC Hospital at 2pm..."
[Conversation ends, whisper resumes]

User: "Yes"  ← Gets sent to intent classifier (BROKEN)
```

#### V2: Multi-Turn
```
User: "Cancel my shift tomorrow"
State: IDLE → AWAITING_CONFIRMATION
System: "You have a shift at ABC Hospital at 2pm. Do you want to cancel?"

User: "Yes"  ← Handled by _handle_confirmation() (CORRECT)
State: AWAITING_CONFIRMATION → AWAITING_REASON
System: "Please tell me the reason"

User: "I'm sick"  ← Handled by _handle_reason() (CORRECT)
State: AWAITING_REASON → IDLE
System: "Cancelled. Reason: I'm sick"
```

---

## Migration Steps

### Step 1: Update Imports in app.py

#### Before (V1)
```python
from backend.core.call_assistant.call_assistant import CallAssistant

assistant = CallAssistant(caller_phone=caller_phone)
```

#### After (V2)
```python
from backend.core.call_assistant.call_assistant_v2 import CallAssistantV2

assistant = CallAssistantV2(caller_phone=caller_phone)
```

**OR** use the new `app_v2.py`:
```bash
# Instead of
python app.py

# Use
python app_v2.py
```

### Step 2: No Code Changes Required

The V2 API is **fully backward compatible**. The only change is the import statement.

All existing methods work the same:
- `run()`: Start standalone
- `run_with_event(stop_event)`: Start with stop control
- `stop()`: Stop the assistant

### Step 3: Test Multi-Turn Conversations

See [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md) for test scenarios.

---

## Side-by-Side Comparison

### V1 Flow
```python
def on_phrase_complete(self, phrase: str) -> None:
    # Always does the same thing:
    self.whisper_client.pause()

    # 1. Send to intent classifier
    llm_response = self.llm_client.ask_llm(phrase)

    # 2. Route based on intent
    route_response = self._route_intent(llm_response)

    # 3. Format response
    self.llm_client.set_system_prompt(FORMAT_SYSTEM_PROMPT)
    llm_response = self.llm_client.ask_llm(route_response)

    # 4. Speak and resume
    tts_client.text_to_speech(llm_response)
    self.whisper_client.resume()
```

**Problem**: Every phrase goes through the same flow, no context between calls.

### V2 Flow
```python
def on_phrase_complete(self, phrase: str) -> None:
    self.whisper_client.pause()

    # Route based on STATE
    if self.state == ConversationState.IDLE:
        self._handle_new_request(phrase)  # Intent classifier

    elif self.state == ConversationState.AWAITING_CONFIRMATION:
        self._handle_confirmation(phrase)  # Yes/No detector

    elif self.state == ConversationState.AWAITING_REASON:
        self._handle_reason(phrase)  # Store reason, submit

    elif self.state == ConversationState.AWAITING_CHOICE:
        self._handle_choice(phrase)  # Extract number, select shift

    self.whisper_client.resume()
```

**Solution**: Each phrase is routed to the appropriate handler based on conversation state.

---

## Rollback Plan

If you need to rollback to V1:

### Option 1: Switch Apps
```bash
# Stop V2
pkill -f app_v2.py

# Start V1
python app.py
```

### Option 2: Revert Import
```python
# In app.py or app_v2.py
# Change this:
from backend.core.call_assistant.call_assistant_v2 import CallAssistantV2
assistant = CallAssistantV2(caller_phone=caller_phone)

# Back to this:
from backend.core.call_assistant.call_assistant import CallAssistant
assistant = CallAssistant(caller_phone=caller_phone)
```

Both versions can coexist in the same codebase.

---

## Testing Checklist

Before deploying V2 to production:

- [ ] Test single shift cancellation (happy path)
- [ ] Test viewing shifts (no cancellation)
- [ ] Test multiple shifts selection
- [ ] Test user changing mind (say "no" to confirmation)
- [ ] Test invalid choice handling
- [ ] Test login issues (transfer to agent)
- [ ] Test out-of-scope requests
- [ ] Test error recovery (lost context)
- [ ] Test session cleanup on call end
- [ ] Load test with multiple concurrent calls

---

## Performance Comparison

### V1 Response Time
```
User speaks → Transcribe → Intent Classify → Route → Format → Speak
               ~2s           ~1s              ~1s     ~1s      ~1s
               Total: ~6 seconds
```

### V2 Response Time

**First turn (IDLE)**:
```
User speaks → Transcribe → Intent Classify → Route → Speak
               ~2s           ~1s              ~1s     ~1s
               Total: ~5 seconds (no formatting step)
```

**Subsequent turns**:
```
User speaks → Transcribe → State Handler → Speak
               ~2s           ~0.5s          ~1s
               Total: ~3.5 seconds (faster!)
```

V2 is **30-40% faster** on follow-up questions because it skips intent classification.

---

## Common Issues

### Issue: State Gets Stuck
**Symptom**: System keeps asking for confirmation even after user moves on

**Cause**: State not being reset after conversation ends

**Fix**: Ensure `_speak_and_reset()` is called at conversation end:
```python
# Good
self._speak_and_reset("Anything else?")  # Resets to IDLE

# Bad
self._speak("Anything else?")  # State unchanged
```

### Issue: Context Lost Between Phrases
**Symptom**: "I lost track of which shift to cancel"

**Cause**: `self.context['pending_shift']` was cleared prematurely

**Fix**: Only reset context in `_reset_state()` or `_speak_and_reset()`

### Issue: LLM Gives Wrong Intent
**Symptom**: System classifies "yes" as `<DENY>` instead of confirmation

**Cause**: Using wrong system prompt for the state

**Fix**: Ensure correct prompt is set in each handler:
```python
# In _handle_confirmation
self.llm_client.set_system_prompt(YES_NO_SYSTEM_PROMPT)

# In _handle_new_request
self.llm_client.set_system_prompt(LLM_SYSTEM_PROMPT)
```

---

## FAQ

### Q: Can I run V1 and V2 simultaneously?
**A**: Yes! They're completely separate files. You could even have:
- `app.py` using V1 on port 5000
- `app_v2.py` using V2 on port 5001

### Q: Do I need to migrate my database?
**A**: No database changes needed. V2 only changes the conversation flow, not data storage.

### Q: Will V2 work with my existing webhooks?
**A**: Yes! The webhook API is identical:
- `POST /webhook/call-started`
- `POST /webhook/call-ended`

### Q: Is V2 production-ready?
**A**: V2 is a new implementation. Recommended testing plan:
1. Test locally with recorded audio
2. Deploy to staging environment
3. Run parallel testing (V1 and V2 simultaneously)
4. Monitor error rates and user feedback
5. Gradual rollout (10% → 50% → 100%)

### Q: What if I only want multi-turn for cancellations?
**A**: V2 automatically handles both cases:
- Cancellation → Multi-turn (confirmation + reason)
- Viewing shifts → Single-turn (just show and done)

### Q: How do I add a new conversation state?
**A**: Example adding `AWAITING_DATE`:
```python
# 1. Add to enum
class ConversationState(Enum):
    AWAITING_DATE = "date"
    # ... existing states

# 2. Add handler
def _handle_date(self, phrase: str) -> None:
    # Parse date from phrase
    # Update context
    # Transition to next state
    pass

# 3. Add routing
def on_phrase_complete(self, phrase: str) -> None:
    # ...
    elif self.state == ConversationState.AWAITING_DATE:
        self._handle_date(phrase)
```

---

## Support

If you encounter issues during migration:

1. Check logs for state transitions: `[CONVERSATION STATE]`
2. Review [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md) for expected behavior
3. Compare your implementation with [call_assistant_v2.py](call_assistant_v2.py)
4. Test with `curl` commands to isolate issues

For bugs or feature requests, create an issue in the project repository.
