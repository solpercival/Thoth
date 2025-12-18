# Multi-Turn Conversation Design

## Problem Statement

The current `call_assistant.py` implementation treats each phrase independently, always running it through the intent classifier. This prevents multi-turn conversations like:

```
System: "You have a shift at ABC Hospital at 2pm. Do you want to cancel?"
User: "Yes"  ← This gets sent to intent classifier (wrong!)
System: "Please tell me why you're canceling"
User: "I'm sick"  ← This also gets sent to intent classifier (wrong!)
```

## Root Cause

[call_assistant.py:94-142](call_assistant.py#L94-L142) - The `on_phrase_complete()` callback:
1. Always sends phrases to LLM with the same flow
2. No state tracking between phrases
3. System prompt gets changed but not reset properly
4. Each phrase is treated as an independent transaction

## Proposed Solution: State Machine

### Conversation States

```python
class ConversationState(Enum):
    IDLE = "idle"                          # No active conversation
    AWAITING_CONFIRMATION = "confirm"       # Asked yes/no question
    AWAITING_REASON = "reason"              # Collecting cancellation reason
    AWAITING_CHOICE = "choice"              # Multiple shifts, user choosing one
    PROCESSING = "processing"               # System is working
```

### State Transitions

```
IDLE
  ├─ User: "Cancel my shift tomorrow"
  ├─ Intent: <SHIFT> + <CNCL>
  ├─ Find shift(s)
  │
  ├─ If 1 shift found:
  │   └─→ AWAITING_CONFIRMATION
  │       └─ System: "You have shift at ABC at 2pm. Confirm cancellation?"
  │           └─ User: "Yes" → AWAITING_REASON
  │           └─ User: "No" → IDLE
  │
  └─ If multiple shifts:
      └─→ AWAITING_CHOICE
          └─ System: "You have 3 shifts. Which one? 1) ABC 2pm, 2) DEF 4pm..."
              └─ User: "The first one" → AWAITING_CONFIRMATION

AWAITING_CONFIRMATION
  ├─ User: "Yes" / "Yeah" / "Confirm" → AWAITING_REASON
  └─ User: "No" / "Cancel" / "Nevermind" → IDLE

AWAITING_REASON
  └─ User: "I'm sick" / "Emergency" / etc
      └─ Store reason
      └─ Submit cancellation
      └─→ IDLE
```

### Implementation

```python
class CallAssistant:
    def __init__(self, caller_phone: Optional[str] = None):
        self.caller_phone = caller_phone
        self.llm_client = OllamaClient(model="qwen2.5:7b", system_prompt=LLM_SYSTEM_PROMPT)
        self.whisper_client = None
        self.llm_response_array = []
        self.transcript = ""

        # State management
        self.state = ConversationState.IDLE
        self.context = {
            'pending_shift': None,      # Shift to cancel
            'pending_shifts': [],       # Multiple shifts (if ambiguous)
            'cancellation_reason': None,
            'original_intent': None
        }

    def on_phrase_complete(self, phrase: str) -> None:
        """Route to appropriate handler based on conversation state"""
        print(f"[PHRASE COMPLETE] {phrase}")
        print(f"[STATE] {self.state.value}")

        self.whisper_client.pause()

        try:
            # Route based on current state
            if self.state == ConversationState.IDLE:
                self._handle_new_request(phrase)

            elif self.state == ConversationState.AWAITING_CONFIRMATION:
                self._handle_confirmation(phrase)

            elif self.state == ConversationState.AWAITING_REASON:
                self._handle_reason(phrase)

            elif self.state == ConversationState.AWAITING_CHOICE:
                self._handle_choice(phrase)

        except Exception as e:
            print(f"[ERROR] {e}")
            self._speak_and_reset("Sorry, something went wrong. Let's start over.")

        finally:
            self.whisper_client.resume()

    def _handle_new_request(self, phrase: str) -> None:
        """Handle initial user request (intent classification)"""
        # Reset system prompt for intent classification
        self.llm_client.set_system_prompt(LLM_SYSTEM_PROMPT)

        llm_response = self.llm_client.ask_llm(phrase)
        print(f"[INTENT] {llm_response}")

        route_response = self._route_intent(llm_response, phrase)

        # Route_intent now handles state transitions

    def _handle_confirmation(self, phrase: str) -> None:
        """Handle yes/no confirmation"""
        # Use LLM to interpret yes/no
        prompt = f"Is the user confirming? Respond only 'YES' or 'NO'. User said: {phrase}"
        self.llm_client.set_system_prompt("You are a yes/no detector. Respond only YES or NO.")

        response = self.llm_client.ask_llm(prompt).strip().upper()

        if "YES" in response:
            if self.context['original_intent'] == '<CNCL>':
                # Move to asking for reason
                self.state = ConversationState.AWAITING_REASON
                self._speak("Please tell me the reason for cancellation")
            else:
                # Just showing shifts, done
                self._speak_and_reset("Okay, is there anything else I can help with?")
        else:
            self._speak_and_reset("Okay, cancellation cancelled. Is there anything else?")

    def _handle_reason(self, phrase: str) -> None:
        """Handle cancellation reason"""
        self.context['cancellation_reason'] = phrase

        # Actually submit the cancellation
        shift = self.context['pending_shift']
        reason = phrase

        # TODO: Call API to actually cancel the shift
        success = self._submit_cancellation(shift['shift_id'], reason)

        if success:
            self._speak_and_reset(
                f"Your shift at {shift['client']} on {shift['date']} "
                f"has been cancelled. The reason recorded is: {reason}"
            )
        else:
            self._speak_and_reset("Sorry, there was an error cancelling your shift.")

    def _handle_choice(self, phrase: str) -> None:
        """Handle choosing from multiple shifts"""
        # Use LLM to extract choice number
        shifts = self.context['pending_shifts']

        prompt = f"Extract the shift number (1-{len(shifts)}) from: {phrase}. Respond only with the number."
        self.llm_client.set_system_prompt("Extract only the number. Respond with just a digit.")

        response = self.llm_client.ask_llm(prompt).strip()

        try:
            choice = int(response) - 1  # Convert to 0-based index
            if 0 <= choice < len(shifts):
                self.context['pending_shift'] = shifts[choice]
                self.state = ConversationState.AWAITING_CONFIRMATION

                shift = shifts[choice]
                self._speak(
                    f"You selected the shift at {shift['client']} "
                    f"on {shift['date']} at {shift['time']}. "
                    f"Do you want to cancel this shift?"
                )
            else:
                self._speak("Invalid choice. Please try again.")
        except ValueError:
            self._speak("I didn't understand. Please say the number of the shift.")

    def _route_intent(self, intent_tag: str, original_phrase: str) -> str:
        """Route intent and manage state transitions"""

        if "<SHIFT>" in intent_tag and self.caller_phone:
            result = asyncio.run(test_integrated_workflow(self.caller_phone, original_phrase))

            if result:
                # Parse intention from reasoning
                reasoning = result.get('reasoning', '')
                is_cancellation = '<CNCL>' in reasoning

                shifts = result['filtered_shifts']

                if len(shifts) == 0:
                    self._speak_and_reset("You don't have any shifts in that time period.")
                    return

                elif len(shifts) == 1:
                    # Single shift - ask for confirmation
                    shift = shifts[0]
                    self.context['pending_shift'] = shift
                    self.context['original_intent'] = '<CNCL>' if is_cancellation else '<SHOW>'
                    self.state = ConversationState.AWAITING_CONFIRMATION

                    if is_cancellation:
                        response = f"You have a shift at {shift['client']} on {shift['date']} at {shift['time']}. Do you want to cancel this shift?"
                    else:
                        response = f"You have a shift at {shift['client']} on {shift['date']} at {shift['time']}."

                    self._speak(response)

                else:
                    # Multiple shifts - ask user to choose
                    self.context['pending_shifts'] = shifts
                    self.context['original_intent'] = '<CNCL>' if is_cancellation else '<SHOW>'
                    self.state = ConversationState.AWAITING_CHOICE

                    response = f"You have {len(shifts)} shifts. "
                    for i, shift in enumerate(shifts, 1):
                        response += f"{i}: {shift['client']} on {shift['date']} at {shift['time']}. "
                    response += "Which shift are you asking about?"

                    self._speak(response)

        elif "<LOGIN>" in intent_tag or "<REAL>" in intent_tag:
            self._speak_and_reset("Please hold. You will be transferred to a live agent.")

        else:
            self._speak_and_reset("I'm sorry, I can't help with that request.")

    def _speak(self, text: str) -> None:
        """Convert text to speech"""
        print(f"[TTS] {text}")
        tts_client = TTSClient(output_device_name="CABLE Input")
        tts_client.text_to_speech(text)

    def _speak_and_reset(self, text: str) -> None:
        """Speak and reset conversation state to IDLE"""
        self._speak(text)
        self.state = ConversationState.IDLE
        self.context = {
            'pending_shift': None,
            'pending_shifts': [],
            'cancellation_reason': None,
            'original_intent': None
        }

    def _submit_cancellation(self, shift_id: str, reason: str) -> bool:
        """Submit cancellation to backend API"""
        # TODO: Implement actual API call
        print(f"[CANCEL] Shift {shift_id} - Reason: {reason}")
        return True
```

## Benefits

1. **Multi-turn support**: Can ask follow-up questions
2. **Context preservation**: Remembers what shift we're talking about
3. **Clear state tracking**: Easy to debug and understand flow
4. **Flexible responses**: Can handle ambiguity (multiple shifts, unclear answers)
5. **Error recovery**: Can reset to IDLE on errors

## Testing Scenarios

### Happy Path: Cancel Single Shift
```
User: "Cancel my shift tomorrow"
State: IDLE → AWAITING_CONFIRMATION
System: "You have a shift at ABC at 2pm. Confirm cancellation?"

User: "Yes"
State: AWAITING_CONFIRMATION → AWAITING_REASON
System: "Please tell me the reason"

User: "I'm sick"
State: AWAITING_REASON → IDLE
System: "Shift cancelled. Reason recorded: I'm sick"
```

### Multiple Shifts
```
User: "What shifts do I have this week?"
State: IDLE → AWAITING_CHOICE
System: "You have 3 shifts: 1) ABC 2pm Monday, 2) DEF 4pm Wednesday, 3) GHI 9am Friday"

User: "Cancel the Monday one"
State: AWAITING_CHOICE → AWAITING_CONFIRMATION
System: "Confirm cancellation of ABC at 2pm Monday?"

User: "Yes"
State: AWAITING_CONFIRMATION → AWAITING_REASON
System: "Reason?"

User: "Family emergency"
State: AWAITING_REASON → IDLE
System: "Cancelled. Reason: Family emergency"
```

### User Changes Mind
```
User: "Cancel my shift tomorrow"
System: "You have a shift at ABC at 2pm. Confirm?"

User: "No, never mind"
State: AWAITING_CONFIRMATION → IDLE
System: "Okay, cancellation cancelled"
```

## Migration Path

1. Create new file: `call_assistant_v2.py` with state machine
2. Add tests for state transitions
3. Test with recorded audio samples
4. Gradually migrate from `call_assistant.py`
5. Update `app.py` to use new version

## Open Questions

1. **Timeout**: How long to wait in AWAITING states before resetting to IDLE?
2. **Interrupt handling**: What if user changes topic mid-conversation?
3. **Cancellation API**: What endpoint/method to use for actual cancellations?
4. **Reason validation**: Should we validate cancellation reasons?
5. **Confirmation logging**: Should we log confirmation conversations for audit?
