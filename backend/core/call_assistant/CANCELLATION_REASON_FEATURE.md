# Cancellation Reason Feature

## Overview
Added support for capturing and storing cancellation reasons in the call assistant workflow, including email notifications with the reason.

## Changes Made

### 1. Email Formatter ([email_formatter.py](../email_agent/email_formatter.py))

**Added Parameter**: `cancellation_reason` (optional)

```python
def format_ezaango_shift_data(
    dict_data: dict,
    custom_message: str = "",
    cancellation_reason: str = None  # NEW
) -> str:
```

**New Section**: REASON block added to email output

```
SHIFT(S):
    · Zak James at 02:00 PM 18-12-2025

REASON:                           # ← NEW SECTION
    She is sick.                  # ← User's cancellation reason
```

### 2. Call Assistant V2 ([call_assistant_v2.py](call_assistant_v2.py))

#### Context Management

**Added** `staff_info` to context:
```python
self.context = {
    'pending_shift': None,
    'pending_shifts': [],
    'cancellation_reason': None,
    'original_intent': None,
    'last_query': None,
    'staff_info': {},  # NEW - stores staff data for email
}
```

#### Intent Routing

**Store staff information** when processing shift queries:
```python
# In _route_intent()
self.context['staff_info'] = result.get('staff', {})  # Store for email
```

#### Cancellation Submission

**Implemented** `_submit_cancellation()` to send email notifications:

```python
def _submit_cancellation(self, shift_id: str, reason: str) -> bool:
    """
    Submit cancellation and send notification email with reason.
    """
    # Get shift and staff info from context
    shift = self.context.get('pending_shift')
    staff_info = self.context.get('staff_info', {})

    # Format email with cancellation reason
    email_data = {
        "reasoning": "Requested cancellation of shift.",
        "staff": {
            "name": staff_info.get('full_name'),
            "id": staff_info.get('id'),
            "email": staff_info.get('email')
        },
        "shifts": [{
            "client": shift.get('client_name'),
            "time": shift.get('time'),
            "date": shift.get('date')
        }]
    }

    formatted_content = format_ezaango_shift_data(
        email_data,
        cancellation_reason=reason  # Pass the reason
    )

    send_notify_email(
        content=formatted_content,
        custom_subject="SHIFT CANCELLATION REQUEST"
    )
```

### 3. Test File ([test_cancellation_email.py](../email_agent/test_cancellation_email.py))

Created test to demonstrate email formatting with and without cancellation reason.

## Workflow

### Multi-Turn Conversation Flow

```
1. User: "Cancel my shift tomorrow"
   State: IDLE → AWAITING_CONFIRMATION
   System: "You have a shift at ABC Hospital at 2pm. Do you want to cancel?"
   Context: Stores staff_info and pending_shift

2. User: "Yes"
   State: AWAITING_CONFIRMATION → AWAITING_REASON
   System: "Please tell me the reason for cancellation"

3. User: "She is sick"
   State: AWAITING_REASON → IDLE
   Actions:
     - Store reason: "She is sick"
     - Call _submit_cancellation(shift_id, "She is sick")
     - Format email with reason
     - Send notification email
   System: "Your shift has been cancelled. Reason recorded: She is sick"
```

## Email Output Examples

### Without Reason (View Shifts)
```
Requested cancellation of shift.

    STAFF:
        · Name: Adaelia Thomas
        · ID: 1728
        · Email: adaeliathomas@gmail.com

    SHIFT(S):
        · Zak James at 02:00 PM 18-12-2025

This is an auto-generated email. Please do not reply.
```

### With Reason (Cancellation)
```
Requested cancellation of shift.

    STAFF:
        · Name: Adaelia Thomas
        · ID: 1728
        · Email: adaeliathomas@gmail.com

    SHIFT(S):
        · Zak James at 02:00 PM 18-12-2025

    REASON:
        She is sick.

This is an auto-generated email. Please do not reply.
```

## Testing

### Manual Test
```bash
cd backend/core/email_agent
python test_cancellation_email.py
```

### Integration Test with Call Assistant

1. Start the call assistant V2:
   ```bash
   python app_v2.py
   ```

2. Simulate a call and test the full flow:
   - "Cancel my shift tomorrow"
   - "Yes"
   - "I'm sick"

3. Check that:
   - Email is sent to collector email
   - Email contains the cancellation reason
   - Reason is properly formatted

## Environment Variables Required

Make sure these are set in `.env`:
```bash
SENDER_EMAIL=your-email@gmail.com
COLLECTOR_EMAIL=collector@example.com
EMAIL_APP_PASSWORD=your-app-password
```

## Future Enhancements

- [ ] Store cancellation in database with reason
- [ ] Add cancellation API integration with Ezaango
- [ ] Support editing/updating cancellation reasons
- [ ] Add reason validation (min length, profanity filter)
- [ ] Track cancellation history with reasons
- [ ] Analytics on common cancellation reasons

## Files Modified

1. `backend/core/email_agent/email_formatter.py` - Added cancellation_reason parameter
2. `backend/core/call_assistant/call_assistant_v2.py` - Implemented cancellation with email
3. `backend/core/email_agent/test_cancellation_email.py` - Created test file

## Breaking Changes

None - the `cancellation_reason` parameter is optional, so existing code continues to work without modifications.
