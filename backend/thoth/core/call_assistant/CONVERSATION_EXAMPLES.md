# Multi-Turn Conversation Examples

This document demonstrates how the state machine in [call_assistant_v2.py](call_assistant_v2.py) handles various conversation flows.

## Legend

- **User**: What the user says
- **State**: Current conversation state
- **System**: What the AI responds
- **Next State**: State after processing

---

## Scenario 1: Cancel Single Shift (Happy Path)

```
User: "I want to cancel my shift tomorrow"
State: IDLE
  → Classify intent: <SHIFT>
  → Query shifts for tomorrow
  → Found 1 shift at ABC Hospital
System: "You have a shift at ABC Hospital on December 18th at 2pm. Do you want to cancel this shift?"
Next State: AWAITING_CONFIRMATION
```

```
User: "Yes"
State: AWAITING_CONFIRMATION
  → Yes/No detector: YES
  → Intent is <CNCL>
System: "Please tell me the reason for cancellation"
Next State: AWAITING_REASON
```

```
User: "I'm sick"
State: AWAITING_REASON
  → Store reason: "I'm sick"
  → Submit cancellation API call
  → Success
System: "Your shift at ABC Hospital on December 18th at 2pm has been cancelled. The reason recorded is: I'm sick. Is there anything else I can help you with?"
Next State: IDLE
```

---

## Scenario 2: View Shifts (No Cancellation)

```
User: "What shifts do I have this week?"
State: IDLE
  → Classify intent: <SHIFT>
  → Query shifts for this week
  → Found 1 shift at DEF Clinic
System: "You have a shift at DEF Clinic on December 20th at 4pm."
Next State: AWAITING_CONFIRMATION
```

```
User: "Okay, thanks"
State: AWAITING_CONFIRMATION
  → Yes/No detector: YES (acknowledging)
  → Intent is <SHOW> (not cancellation)
System: "Okay, is there anything else I can help you with?"
Next State: IDLE
```

---

## Scenario 3: Multiple Shifts - User Chooses One

```
User: "Cancel my shift this week"
State: IDLE
  → Classify intent: <SHIFT>
  → Query shifts for this week
  → Found 3 shifts
System: "You have 3 shifts. Number 1: ABC Hospital on December 18th at 2pm. Number 2: DEF Clinic on December 20th at 4pm. Number 3: GHI Medical on December 22nd at 9am. Which shift do you want to cancel?"
Next State: AWAITING_CHOICE
```

```
User: "The second one"
State: AWAITING_CHOICE
  → Extract number: 2
  → Select shift: DEF Clinic
System: "You selected the shift at DEF Clinic on December 20th at 4pm. Do you want to cancel this shift?"
Next State: AWAITING_CONFIRMATION
```

```
User: "Yes"
State: AWAITING_CONFIRMATION
  → Yes/No detector: YES
  → Intent is <CNCL>
System: "Please tell me the reason for cancellation"
Next State: AWAITING_REASON
```

```
User: "Family emergency"
State: AWAITING_REASON
  → Store reason: "Family emergency"
  → Submit cancellation
System: "Your shift at DEF Clinic on December 20th at 4pm has been cancelled. The reason recorded is: Family emergency. Is there anything else I can help you with?"
Next State: IDLE
```

---

## Scenario 4: User Changes Mind

```
User: "Cancel my shift tomorrow"
State: IDLE
  → Found 1 shift
System: "You have a shift at ABC Hospital on December 18th at 2pm. Do you want to cancel this shift?"
Next State: AWAITING_CONFIRMATION
```

```
User: "No, never mind"
State: AWAITING_CONFIRMATION
  → Yes/No detector: NO
System: "Okay, no problem. Is there anything else I can help you with?"
Next State: IDLE
```

---

## Scenario 5: Login Issue (Transfer to Agent)

```
User: "I can't log into the app"
State: IDLE
  → Classify intent: <LOGIN>
System: "I understand you're having trouble logging in. Please hold while I transfer you to a live agent for assistance."
Next State: IDLE
  → [Transfer call to live agent]
```

---

## Scenario 6: Request for Real Person

```
User: "Can I speak to a real person?"
State: IDLE
  → Classify intent: <REAL>
System: "Of course. Please hold while I transfer you to a live agent."
Next State: IDLE
  → [Transfer call to live agent]
```

---

## Scenario 7: Out of Scope Request

```
User: "What's the weather today?"
State: IDLE
  → Classify intent: <DENY>
System: "I'm sorry, I can't help with that request. Is there anything else I can assist you with?"
Next State: IDLE
```

---

## Scenario 8: No Shifts Found

```
User: "What shifts do I have tomorrow?"
State: IDLE
  → Classify intent: <SHIFT>
  → Query shifts for tomorrow
  → Found 0 shifts
System: "You don't have any shifts in that time period. Is there anything else I can help you with?"
Next State: IDLE
```

---

## Scenario 9: Natural Language Choice Selection

```
User: "Cancel my shifts this week"
State: IDLE
  → Found 3 shifts
System: "You have 3 shifts. Number 1: ABC Hospital on Monday at 2pm. Number 2: DEF Clinic on Wednesday at 4pm. Number 3: GHI Medical on Friday at 9am. Which shift do you want to cancel?"
Next State: AWAITING_CHOICE
```

```
User: "The Monday one"
State: AWAITING_CHOICE
  → LLM extracts: "1" (Monday is the first option)
  → Select shift: ABC Hospital
System: "You selected the shift at ABC Hospital on Monday at 2pm. Do you want to cancel this shift?"
Next State: AWAITING_CONFIRMATION
```

---

## Scenario 10: Ambiguous Confirmation Response

```
User: "I want to cancel my shift tomorrow"
State: IDLE
System: "You have a shift at ABC Hospital on December 18th at 2pm. Do you want to cancel this shift?"
Next State: AWAITING_CONFIRMATION
```

```
User: "Yeah, sure"
State: AWAITING_CONFIRMATION
  → Yes/No detector: YES
System: "Please tell me the reason for cancellation"
Next State: AWAITING_REASON
```

```
User: "Okay" or "I changed my mind"
State: AWAITING_CONFIRMATION
  → Yes/No detector: NO
System: "Okay, no problem. Is there anything else I can help you with?"
Next State: IDLE
```

---

## State Transition Diagram

```
┌──────┐
│ IDLE │ ◄─────────────────────────────────┐
└──┬───┘                                    │
   │                                        │
   │ User: "Cancel my shift"                │
   │ Intent: <SHIFT>                        │
   │                                        │
   ├──► 0 shifts found ─────────────────────┤
   │                                        │
   ├──► 1 shift found                       │
   │    ↓                                   │
   │    ┌───────────────────────┐           │
   │    │ AWAITING_CONFIRMATION │           │
   │    └──────────┬────────────┘           │
   │               │                        │
   │    ┌──────────┴─────────┐              │
   │    │                    │              │
   │    Yes                 No ─────────────┤
   │    │                                   │
   │    ├─► <SHOW> intent ──────────────────┤
   │    │                                   │
   │    └─► <CNCL> intent                   │
   │        ↓                               │
   │        ┌────────────────┐              │
   │        │ AWAITING_REASON│              │
   │        └───────┬────────┘              │
   │                │                       │
   │                User: "I'm sick"        │
   │                Submit cancellation     │
   │                │                       │
   │                └───────────────────────┤
   │                                        │
   └──► Multiple shifts found                │
        ↓                                   │
        ┌──────────────┐                    │
        │AWAITING_CHOICE│                   │
        └──────┬───────┘                    │
               │                            │
               User: "Number 2"             │
               Select shift #2              │
               │                            │
               └────────────────────────────┘
```

---

## Key Differences from V1

### V1 (call_assistant.py)
- Each phrase is processed independently
- No state tracking between phrases
- Cannot ask follow-up questions
- System prompt gets changed but not properly managed

### V2 (call_assistant_v2.py)
- State machine tracks conversation flow
- Context preserved between phrases
- Can ask follow-up questions (confirmation, reason, choice)
- Separate handlers for each state
- Proper error recovery with `_speak_and_reset()`

---

## Testing the Implementation

### Manual Testing
```bash
# Start the V2 app
cd backend/core/call_assistant
python app_v2.py

# In another terminal, simulate a call start
curl -X POST http://localhost:5000/webhook/call-started \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test123", "from": "+1234567890"}'

# Speak into your microphone (through virtual cable)
# The system will respond through speakers

# End the call
curl -X POST http://localhost:5000/webhook/call-ended \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test123"}'
```

### Check Active Sessions
```bash
curl http://localhost:5000/status
```

---

## Error Handling

### Invalid Choice
```
State: AWAITING_CHOICE
User: "Um, the purple one"
  → LLM cannot extract valid number
System: "I didn't understand which shift you meant. Please say the number, like 'one' or 'two'."
State: AWAITING_CHOICE (stays in same state)
```

### Lost Context
```
State: AWAITING_REASON
  → context['pending_shift'] is None
System: "Sorry, I lost track of which shift to cancel. Let's start over."
State: IDLE
```

### General Exception
```
State: Any
  → Exception occurs
System: "Sorry, I encountered an error. Let's start over."
State: IDLE
```

---

## Future Enhancements

1. **Timeout Handling**: Reset to IDLE after N seconds of inactivity
2. **Context Interruption**: Handle when user changes topic mid-conversation
3. **Conversation History**: Log all state transitions for debugging
4. **Partial Cancellation**: Allow canceling multiple shifts at once
5. **Rescheduling**: Add ability to reschedule instead of just cancel
6. **Confirmation Summary**: Read back all details before final submission
