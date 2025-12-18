# CallAssistant V3 - Architecture Overview

## Core Concept

V3 uses a **LLM-driven conversation flow** instead of a state machine. The LLM maintains conversation context through message history and outputs **action tags** when system operations are needed.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User speaks                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Whisper (Speech-to-Text)                                   │
│  → Transcribes audio to text                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM (Ollama - qwen2.5:7b or other models)                  │
│  → Single comprehensive system prompt                       │
│  → Maintains context via message history                    │
│  → Decides what to say OR what action to trigger            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Action Tag Processor (_process_response)                   │
│  → Checks LLM output for special tags                       │
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
```

---

## Key Components

### 1. Single System Prompt (Lines 23-93)

Defines the ENTIRE conversation flow in one place:
- Intent classification
- Multi-turn dialogue handling
- When to output action tags
- Conversation rules

```python
SYSTEM_PROMPT = """You are a call center agent handling shift queries and cancellations.

Follow this flow EXACTLY and output special commands when needed:
1. INITIAL INTENT CLASSIFICATION...
2. SHIFT QUERY...
3. HANDLING SHIFT RESULTS...
...
"""
```

**Why this is powerful:**
- ✅ Single source of truth for conversation behavior
- ✅ Easy to modify - just edit the prompt
- ✅ No code changes needed for conversation flow updates
- ✅ LLM naturally handles variations and edge cases

---

### 2. Action Tags

Special commands the LLM outputs to trigger system operations:

| Tag | Purpose | Example Output |
|-----|---------|----------------|
| `<GETSHIFTS>` | Query backend for shifts | `<GETSHIFTS>cancel shift tomorrow` |
| `<CONFIRM_CANCEL>` | User confirmed cancellation | `<CONFIRM_CANCEL>shift_123` |
| `<REASON>` | User provided cancellation reason | `<REASON>I'm feeling sick` |
| `<LOGIN>` | Login assistance needed | Routes to support |
| `<REAL>` | User wants real agent | Routes to human |
| `<DENY>` | Request can't be handled | Polite rejection |

**How it works:**
1. LLM receives user input
2. LLM decides if action needed or just conversation
3. If action needed, outputs tag (e.g., `<GETSHIFTS>`)
4. Python code detects tag and calls appropriate function
5. Function result is injected back into LLM conversation
6. LLM generates natural response based on results

---

### 3. Message History

The LLM maintains conversation context automatically through `OllamaClient`:
- ✅ Each user phrase is added to history
- ✅ Each LLM response is added to history
- ✅ LLM "remembers" what was said before
- ✅ No manual state tracking needed!

**Example conversation memory:**
```python
# Turn 1
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "I want to cancel my shift tomorrow"},
    {"role": "assistant", "content": "<GETSHIFTS>cancel shift tomorrow"}
]

# Turn 2 - LLM remembers previous context
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "I want to cancel my shift tomorrow"},
    {"role": "assistant", "content": "<GETSHIFTS>cancel shift tomorrow"},
    {"role": "user", "content": "SYSTEM: Found 1 shift..."},
    {"role": "assistant", "content": "You have a shift at ABC Corp on Dec 19..."},
    {"role": "user", "content": "Yes"},  # ← LLM knows "Yes" refers to cancellation
    {"role": "assistant", "content": "<CONFIRM_CANCEL>shift_123"}
]
```

---

## Example Conversation Flow

### Complete Cancellation Flow

```python
# Turn 1: Initial Request
User: "I want to cancel my shift tomorrow"
  ↓
LLM: <GETSHIFTS>cancel shift tomorrow
  ↓
_process_response() detects <GETSHIFTS>
  ↓
_handle_get_shifts() calls test_integrated_workflow()
  ↓
Backend returns: [shift at ABC Corp, 10AM, Dec 19]
  ↓
Inject into LLM: "SYSTEM: Found 1 shift: {...} | User wants to CANCEL"
  ↓
LLM: "You have a shift at ABC Corp on Dec 19 at 10 AM. Do you want to cancel?"
  ↓
TTS speaks this to user

# Turn 2: Confirmation
User: "Yes"
  ↓
LLM: <CONFIRM_CANCEL>shift_123
  ↓
_process_response() detects <CONFIRM_CANCEL>
  ↓
_handle_confirm_cancel() stores shift_id in context
  ↓
Inject into LLM: "SYSTEM: User confirmed cancellation. Now ask for reason."
  ↓
LLM: "Please tell me the reason for cancellation"
  ↓
TTS speaks this to user

# Turn 3: Reason Collection
User: "I'm feeling sick"
  ↓
LLM: <REASON>I'm feeling sick
  ↓
_process_response() detects <REASON>
  ↓
_handle_cancellation_reason() calls _submit_cancellation()
  ↓
_submit_cancellation():
  - Formats email with shift details + reason
  - Sends notification email
  - Returns success
  ↓
Inject into LLM: "SYSTEM: Cancellation successful. Thank user."
  ↓
LLM: "Your shift at ABC Corp on Dec 19 at 10 AM has been cancelled. Anything else?"
  ↓
TTS speaks this to user
```

---

## Key Methods

### `on_phrase_complete(phrase)` (Line 122)
**Entry point when Whisper completes transcription**

```python
def on_phrase_complete(self, phrase: str) -> None:
    # 1. Pause audio processing
    self.whisper_client.pause()

    # 2. Send phrase to LLM
    llm_response = self.llm_client.ask_llm(phrase)

    # 3. Process response (check for action tags)
    response_to_speak = self._process_response(llm_response, phrase)

    # 4. Speak the response via TTS
    if response_to_speak:
        self._speak(response_to_speak)

    # 5. Resume audio processing
    self.whisper_client.resume()
```

---

### `_process_response(llm_response, user_phrase)` (Line 162)
**Routes LLM output to appropriate handler**

```python
def _process_response(self, llm_response: str, user_phrase: str) -> Optional[str]:
    # Check for action tags in order of priority

    if "<GETSHIFTS>" in llm_response:
        query = llm_response.replace("<GETSHIFTS>", "").strip()
        return self._handle_get_shifts(query or user_phrase)

    if "<CONFIRM_CANCEL>" in llm_response:
        match = re.search(r'<CONFIRM_CANCEL>(\S+)', llm_response)
        if match:
            shift_id = match.group(1)
            return self._handle_confirm_cancel(shift_id)

    if "<REASON>" in llm_response:
        reason = llm_response.replace("<REASON>", "").strip()
        return self._handle_cancellation_reason(reason or user_phrase)

    # ... handle other tags ...

    # No action tag - clean and return text for TTS
    return self._clean_response(llm_response)
```

---

### `_clean_response(response)` (Line 199)
**Strips out hypothetical future dialogue**

Problem: LLM sometimes outputs predicted future turns like:
```
"You have two shifts tomorrow at 10 AM and 1 PM. Which one?

User: "The first one"
You: You selected..."
```

Solution: Strip everything after "User:"
```python
def _clean_response(self, response: str) -> str:
    # Remove predicted future turns
    if "User:" in response:
        response = response.split("User:")[0].strip()

    # Remove "You:" prefix if present
    if response.startswith("You:"):
        response = response[4:].strip()

    return response
```

---

### `_handle_get_shifts(query)` (Line 219)
**Query backend and inject shift data into conversation**

```python
def _handle_get_shifts(self, query: str) -> str:
    # Call integrated workflow (same as V1/V2)
    result = asyncio.run(test_integrated_workflow(self.caller_phone, query))

    # Extract shift data
    shifts = result.get('filtered_shifts', [])
    staff_info = result.get('staff', {})
    reasoning = result.get('reasoning', '')

    # Determine intent from reasoning
    self.context['is_cancellation'] = '<CNCL>' in reasoning
    self.context['current_shifts'] = shifts
    self.context['staff_info'] = staff_info

    # Format shift data as JSON for LLM
    shift_data = json.dumps([{
        'client': s['client_name'],
        'date': s['date'],
        'time': s['time'],
        'shift_id': s['shift_id']
    } for s in shifts])

    # Inject shift data into conversation
    system_message = f"SYSTEM: Found {len(shifts)} shift(s): {shift_data}"
    if self.context['is_cancellation']:
        system_message += " | User wants to CANCEL a shift."
    else:
        system_message += " | User wants to VIEW shift info."

    # Let LLM generate natural response
    llm_response = self.llm_client.ask_llm(system_message)

    return self._clean_response(llm_response)
```

**Key Points:**
- ✅ Uses same date reasoner as V1/V2
- ✅ Validates shifts against backend API
- ✅ Injects structured data into conversation
- ✅ LLM generates natural language response

---

### `_handle_confirm_cancel(shift_id)` (Line 266)
**User confirmed cancellation - prepare for reason collection**

```python
def _handle_confirm_cancel(self, shift_id: str) -> str:
    # Find shift by ID in current shifts
    selected_shift = None
    for shift in self.context['current_shifts']:
        if shift['shift_id'] == shift_id:
            selected_shift = shift
            break

    # Store for later use
    self.context['selected_shift'] = selected_shift

    # Ask LLM to request reason
    system_message = "SYSTEM: User confirmed cancellation. Now ask for the reason."
    llm_response = self.llm_client.ask_llm(system_message)

    return self._clean_response(llm_response)
```

---

### `_handle_cancellation_reason(reason)` (Line 302)
**Submit cancellation and send notification**

```python
def _handle_cancellation_reason(self, reason: str) -> str:
    shift = self.context.get('selected_shift')

    # Submit cancellation (formats and sends email)
    success = self._submit_cancellation(shift, reason)

    if success:
        # Inject confirmation into conversation
        system_message = (
            f"SYSTEM: Cancellation successful. "
            f"Shift at {shift['client_name']} on {shift['date']} at {shift['time']} "
            f"has been cancelled. Reason: {reason}. "
            f"Thank the user and ask if there's anything else."
        )
        llm_response = self.llm_client.ask_llm(system_message)

        # Clear context
        self.context['selected_shift'] = None
        self.context['current_shifts'] = []

        return self._clean_response(llm_response)
```

---

## Why V3 is Simpler Than V2

### No State Machine

**V2 Approach:**
```python
class ConversationState(Enum):
    IDLE = "idle"
    AWAITING_CONFIRMATION = "confirm"
    AWAITING_REASON = "reason"
    AWAITING_CHOICE = "choice"
    PROCESSING = "processing"

# Manual state transitions
if self.state == ConversationState.IDLE:
    self._handle_new_request(phrase)
elif self.state == ConversationState.AWAITING_CONFIRMATION:
    self._handle_confirmation(phrase)
elif self.state == ConversationState.AWAITING_REASON:
    self._handle_reason(phrase)
# ... etc
```

**V3 Approach:**
```python
# LLM manages state implicitly through conversation history
llm_response = self.llm_client.ask_llm(phrase)
response_to_speak = self._process_response(llm_response, phrase)
```

✅ **Result:** 100+ lines of state management code eliminated!

---

### Single System Prompt

**V2 Approach:**
- `LLM_SYSTEM_PROMPT` - Intent classification
- `YES_NO_SYSTEM_PROMPT` - Yes/no detection
- `NUMBER_EXTRACTION_PROMPT` - Choice extraction
- System prompt switching during conversation

**V3 Approach:**
- One comprehensive prompt (lines 23-93)
- No prompt switching needed
- All conversation logic in one place

✅ **Result:** Easier to understand and modify!

---

### Code Statistics

| Metric | V2 | V3 | Improvement |
|--------|----|----|-------------|
| Lines of code | 606 | 493 | -19% |
| System prompts | 3 | 1 | -67% |
| State handlers | 5 | 0 | -100% |
| Complexity | High | Low | Much better! |

---

## Context Storage

V3 maintains minimal context - just what's needed for current operation:

```python
self.context = {
    'current_shifts': [],      # Shifts from last backend query
    'selected_shift': None,    # Currently selected shift
    'staff_info': {},          # Staff info for email
    'is_cancellation': False,  # Whether user wants to cancel
}
```

**Why minimal?**
- LLM message history handles conversation context
- Python context only stores data for system operations
- Simpler = fewer bugs

---

## Integration Points

**Same as V1/V2:**
- ✅ `test_integrated_workflow()` - Date reasoning + backend API
- ✅ `format_ezaango_shift_data()` - Email formatting
- ✅ `send_notify_email()` - Email sending
- ✅ `SystemAudioWhisperClient` - Speech-to-text
- ✅ `TTSClient` - Text-to-speech

**The only difference is the conversation management layer!**

V3 uses the same robust backend integrations as V1/V2, just with a simpler conversation engine.

---

## Advantages of V3

### 1. Simplicity
- Single source of truth (system prompt)
- No manual state tracking
- Easier to understand

### 2. Flexibility
- LLM handles variations naturally
- Edge cases handled gracefully
- More conversational

### 3. Maintainability
- Update prompt, not code
- Fewer places for bugs
- Clear separation of concerns

### 4. Extensibility
Adding new features:
1. Add to system prompt
2. Add action tag
3. Implement handler
4. Done!

No state machine changes needed.

### 5. Better Error Recovery
- LLM can clarify ambiguities
- Context preserved naturally
- Graceful degradation

---

## Design Philosophy

**V2 Philosophy:** "Control the conversation with explicit states"
- Manual state transitions
- Rigid conversation flow
- Fighting against LLM's natural capabilities

**V3 Philosophy:** "Let the LLM do what it does best"
- LLM manages conversation flow
- Action tags for deterministic operations
- Leverages LLM's strengths

**Result:** Simpler, more maintainable, more natural conversations!

---

## Summary

V3 represents a paradigm shift from state machines to LLM-driven conversation management:

1. **Single system prompt** defines entire flow
2. **Action tags** trigger system operations
3. **Message history** maintains context
4. **Minimal Python context** for backend operations
5. **Same backend integrations** as V1/V2

**Bottom line:** V3 is simpler, more flexible, and easier to maintain than V2, while providing the same robust functionality.

🚀 **V3 is the future of the CallAssistant.**
