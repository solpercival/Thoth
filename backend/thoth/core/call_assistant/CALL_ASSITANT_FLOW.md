# Call Assistant Cancellation Flow

This document explains how the shift cancellation flow works in `call_assistant_v3.py`.

## Single Shift Flow

When there is only **1 shift** found, the LLM may chain commands (output `<CONFIRM_CANCEL>` immediately).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TURN 1: User speaks                                                   MAX DEPTH: 4
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ User: "Cancel my shift tomorrow"                                                │
│                    ↓                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ DEPTH 0: on_phrase_complete()                                               │ │
│ │                  ↓                                                          │ │
│ │ llm_response = ask_llm("Cancel my shift tomorrow")                          │ │
│ │ LLM returns: "<GETSHIFTS>shift tomorrow"                                    │ │
│ │                  ↓                                                          │ │
│ │ ┌─────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ DEPTH 1: _process_response("<GETSHIFTS>...")                            │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ Detects <GETSHIFTS> tag                                                 │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │ │
│ │ │ │ DEPTH 2: _handle_get_shifts("shift tomorrow")                       │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Calls backend API → gets 1 shift                                    │ │ │ │
│ │ │ │ Stores in self.context['current_shifts']                            │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Builds & sends SYSTEM message:                                      │ │ │ │
│ │ │ │ "SYSTEM: Found 1 shift(s): [{John, Jan 25, 9am, id:123}] | CANCEL"  │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ LLM returns: "Found your shift at John. <CONFIRM_CANCEL>123"        │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ ┌─────────────────────────────────────────────────────────────────┐ │ │ │ │
│ │ │ │ │ DEPTH 3: _process_response("<CONFIRM_CANCEL>123")               │ │ │ │ │
│ │ │ │ │              ↓                                                  │ │ │ │ │
│ │ │ │ │ Detects <CONFIRM_CANCEL> tag                                    │ │ │ │ │
│ │ │ │ │              ↓                                                  │ │ │ │ │
│ │ │ │ │ ┌─────────────────────────────────────────────────────────────┐ │ │ │ │ │
│ │ │ │ │ │ DEPTH 4: _handle_confirm_cancel("123")                      │ │ │ │ │ │
│ │ │ │ │ │              ↓                                              │ │ │ │ │ │
│ │ │ │ │ │ Finds shift in context, stores in selected_shift            │ │ │ │ │ │
│ │ │ │ │ │              ↓                                              │ │ │ │ │ │
│ │ │ │ │ │ Sends SYSTEM message: "Now ask for the reason"              │ │ │ │ │ │
│ │ │ │ │ │              ↓                                              │ │ │ │ │ │
│ │ │ │ │ │ LLM returns: "Please tell me the reason"                    │ │ │ │ │ │
│ │ │ │ │ │              ↓                                              │ │ │ │ │ │
│ │ │ │ │ │ return "Please tell me the reason" ──────────────────────┐  │ │ │ │ │ │
│ │ │ │ │ └─────────────────────────────────────────────────────────┐│  │ │ │ │ │ │
│ │ │ │ │ return ←───────────────────────────────────────────────────┘│  │ │ │ │ │
│ │ │ │ └─────────────────────────────────────────────────────────────┘  │ │ │ │
│ │ │ │ return ←─────────────────────────────────────────────────────────┘ │ │ │
│ │ │ └───────────────────────────────────────────────────────────────────┘ │ │
│ │ │ return ←─────────────────────────────────────────────────────────────┘ │ │
│ │ └───────────────────────────────────────────────────────────────────────┘ │
│ │ return ←─────────────────────────────────────────────────────────────────┘ │
│ └───────────────────────────────────────────────────────────────────────────┘
│                    ↓                                                            │
│ response_to_speak = "Please tell me the reason"                                 │
│                    ↓                                                            │
│ TTS speaks it                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                 ↓
                    (User listens, thinks, speaks)
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TURN 2: User provides reason                                          MAX DEPTH: 2
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ User: "I'm sick"                                                                │
│                    ↓                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ DEPTH 0: on_phrase_complete()                                               │ │
│ │                  ↓                                                          │ │
│ │ llm_response = ask_llm("I'm sick")                                          │ │
│ │ LLM returns: "<REASON>I'm sick"                                             │ │
│ │                  ↓                                                          │ │
│ │ ┌─────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ DEPTH 1: _process_response("<REASON>I'm sick")                          │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ Detects <REASON> tag                                                    │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │ │
│ │ │ │ DEPTH 2: _handle_cancellation_reason("I'm sick")                    │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Gets shift from self.context['selected_shift']                      │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ _submit_cancellation() → formats and sends email                    │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Sends SYSTEM message: "Cancellation successful..."                  │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ LLM returns: "Your shift has been cancelled. Anything else?"        │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Clears self.context                                                 │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ return "Your shift has been cancelled. Anything else?" ──────────┐  │ │ │ │
│ │ │ └─────────────────────────────────────────────────────────────────┐│  │ │ │ │
│ │ │ return ←───────────────────────────────────────────────────────────┘│  │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘  │ │
│ │ return ←─────────────────────────────────────────────────────────────────┘ │
│ └───────────────────────────────────────────────────────────────────────────┘
│                    ↓                                                            │
│ response_to_speak = "Your shift has been cancelled. Anything else?"             │
│                    ↓                                                            │
│ TTS speaks it                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Multiple Shifts Flow

When there are **multiple shifts**, the LLM needs to ask "which one?" before proceeding.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TURN 1: User speaks                                                   MAX DEPTH: 2
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ User: "I want to cancel one of my shifts"                                       │
│                    ↓                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ DEPTH 0: on_phrase_complete()                                               │ │
│ │                  ↓                                                          │ │
│ │ llm_response = ask_llm("I want to cancel one of my shifts")                 │ │
│ │ LLM returns: "<GETSHIFTS>shifts"                                            │ │
│ │                  ↓                                                          │ │
│ │ ┌─────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ DEPTH 1: _process_response("<GETSHIFTS>...")                            │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ Detects <GETSHIFTS> tag                                                 │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │ │
│ │ │ │ DEPTH 2: _handle_get_shifts("shifts")                               │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Calls backend API → gets 3 shifts                                   │ │ │ │
│ │ │ │ Stores in self.context['current_shifts']                            │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Builds & sends SYSTEM message:                                      │ │ │ │
│ │ │ │ "SYSTEM: Found 3 shift(s): [{John},{Mary},{Bob}] | CANCEL"          │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ LLM returns: "I found 3 shifts:                                     │ │ │ │
│ │ │ │               1. John on Jan 25 at 9am                              │ │ │ │
│ │ │ │               2. Mary on Jan 26 at 2pm                              │ │ │ │
│ │ │ │               3. Bob on Jan 27 at 10am                              │ │ │ │
│ │ │ │               Which one would you like to cancel?"                  │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ _process_response() called → NO TAGS FOUND (depth 3 not entered)    │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ return cleaned text ─────────────────────────────────────────────┐  │ │ │ │
│ │ │ └─────────────────────────────────────────────────────────────────┐│  │ │ │ │
│ │ │ return ←───────────────────────────────────────────────────────────┘│  │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘  │ │
│ │ return ←─────────────────────────────────────────────────────────────────┘ │
│ └───────────────────────────────────────────────────────────────────────────┘
│                    ↓                                                            │
│ response_to_speak = "I found 3 shifts... Which one would you like to cancel?"   │
│                    ↓                                                            │
│ TTS speaks it                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                 ↓
                    (User listens, thinks, speaks)
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TURN 2: User selects a shift                                          MAX DEPTH: 2
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ User: "The second one"                                                          │
│                    ↓                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ DEPTH 0: on_phrase_complete()                                               │ │
│ │                  ↓                                                          │ │
│ │ llm_response = ask_llm("The second one")                                    │ │
│ │ LLM returns: "<CONFIRM_CANCEL>456"                                          │ │
│ │                  ↓                                                          │ │
│ │ ┌─────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ DEPTH 1: _process_response("<CONFIRM_CANCEL>456")                       │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ Detects <CONFIRM_CANCEL> tag                                            │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │ │
│ │ │ │ DEPTH 2: _handle_confirm_cancel("456")                              │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Finds Mary's shift in context                                       │ │ │ │
│ │ │ │ Stores in self.context['selected_shift']                            │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Sends SYSTEM message: "Now ask for the reason"                      │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ LLM returns: "Got it. Please tell me the reason for cancelling"     │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ return cleaned text ─────────────────────────────────────────────┐  │ │ │ │
│ │ │ └─────────────────────────────────────────────────────────────────┐│  │ │ │ │
│ │ │ return ←───────────────────────────────────────────────────────────┘│  │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘  │ │
│ │ return ←─────────────────────────────────────────────────────────────────┘ │
│ └───────────────────────────────────────────────────────────────────────────┘
│                    ↓                                                            │
│ response_to_speak = "Got it. Please tell me the reason for cancelling"          │
│                    ↓                                                            │
│ TTS speaks it                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                 ↓
                    (User listens, thinks, speaks)
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TURN 3: User provides reason                                          MAX DEPTH: 2
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ User: "I have a doctor's appointment"                                           │
│                    ↓                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ DEPTH 0: on_phrase_complete()                                               │ │
│ │                  ↓                                                          │ │
│ │ llm_response = ask_llm("I have a doctor's appointment")                     │ │
│ │ LLM returns: "<REASON>I have a doctor's appointment"                        │ │
│ │                  ↓                                                          │ │
│ │ ┌─────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ DEPTH 1: _process_response("<REASON>...")                               │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ Detects <REASON> tag                                                    │ │ │
│ │ │              ↓                                                          │ │ │
│ │ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │ │
│ │ │ │ DEPTH 2: _handle_cancellation_reason("I have a doctor's...")        │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Gets Mary's shift from self.context['selected_shift']               │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ _submit_cancellation() → sends email                                │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Sends SYSTEM message: "Cancellation successful..."                  │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ LLM returns: "Your shift with Mary has been cancelled."             │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ Clears self.context                                                 │ │ │ │
│ │ │ │              ↓                                                      │ │ │ │
│ │ │ │ return cleaned text ─────────────────────────────────────────────┐  │ │ │ │
│ │ │ └─────────────────────────────────────────────────────────────────┐│  │ │ │ │
│ │ │ return ←───────────────────────────────────────────────────────────┘│  │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘  │ │
│ │ return ←─────────────────────────────────────────────────────────────────┘ │
│ └───────────────────────────────────────────────────────────────────────────┘
│                    ↓                                                            │
│ response_to_speak = "Your shift with Mary has been cancelled. Anything else?"   │
│                    ↓                                                            │
│ TTS speaks it                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Depth Summary Table

| Flow | Turn | Max Depth | Call Stack |
|------|------|-----------|------------|
| **Single shift** | Turn 1 | **4** | `on_phrase_complete` → `_process_response` → `_handle_get_shifts` → `_process_response` → `_handle_confirm_cancel` |
| **Single shift** | Turn 2 | 2 | `on_phrase_complete` → `_process_response` → `_handle_cancellation_reason` |
| **Multiple shifts** | Turn 1 | 2 | `on_phrase_complete` → `_process_response` → `_handle_get_shifts` (no chaining) |
| **Multiple shifts** | Turn 2 | 2 | `on_phrase_complete` → `_process_response` → `_handle_confirm_cancel` |
| **Multiple shifts** | Turn 3 | 2 | `on_phrase_complete` → `_process_response` → `_handle_cancellation_reason` |

## Key Differences

| Shifts | Turn 1 LLM response | What happens |
|--------|---------------------|--------------|
| **1 shift** | `"Found your shift. <CONFIRM_CANCEL>123"` | Tag detected → immediately calls `_handle_confirm_cancel()` |
| **Multiple** | `"Found 3 shifts: 1. John... Which one?"` | No tag → returns text, waits for user's next turn |

## Command Chain Summary

```
Single shift:    User → <GETSHIFTS> → <CONFIRM_CANCEL> → <REASON> → Done
                        └────────── can chain ──────────┘

Multiple shifts: User → <GETSHIFTS> → [wait] → User picks → <CONFIRM_CANCEL> → <REASON> → Done
                                        ↑
                                  extra turn here
```

## Why `_process_response()` Is Called Twice in `_handle_get_shifts()`

After sending the SYSTEM message with shift data to the LLM, the LLM's response might contain a command tag (like `<CONFIRM_CANCEL>`). Without the second `_process_response()` call, that tag would be spoken aloud by TTS.

```python
# In _handle_get_shifts():
llm_response = self.llm_client.ask_llm(system_message)
# llm_response might be: "I found your shift. <CONFIRM_CANCEL>123"

processed = self._process_response(llm_response, system_message)
# If <CONFIRM_CANCEL> found → calls _handle_confirm_cancel()
# If no tags → returns cleaned text

return processed if processed else self._clean_response(llm_response)
```

This is a **recursive safety net** to catch chained commands.
