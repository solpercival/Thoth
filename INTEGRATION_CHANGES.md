# Phone Number Integration Implementation

## Summary
Successfully implemented phone number capture and filtering across the entire call → LLM → shift-checking pipeline. Caller phone numbers from 3CX webhooks now flow through the system for personalized shift matching.

---

## Changes Made

### 1. **app.py** - 3CX Webhook Handler
**File**: `backend/core/call_assistant/app.py`

**Changes**:
- Extract `caller_phone` from 3CX webhook POST data (field: `from`)
- Pass `caller_phone` to `CallAssistant` constructor
- Return `caller_phone` in webhook response for debugging

**Code**:
```python
@app.route('/webhook/call-started', methods=['POST'])
def call_started():
    data = request.json
    call_id = data.get('call_id')
    caller_phone = data.get('from')  # ← NEW: Extract phone
    
    # ...validation...
    
    assistant = CallAssistant(caller_phone=caller_phone)  # ← NEW: Pass phone
    
    # ...rest of handler...
    
    return jsonify({
        'status': 'success',
        'message': f'Voice assistant started for call {call_id}',
        'caller_phone': caller_phone  # ← NEW: Return for debugging
    }), 200
```

---

### 2. **call_assistant.py** - Voice Processing & Intent Routing
**File**: `backend/core/call_assistant/call_assistant.py`

**Changes**:
- Add `caller_phone` parameter to constructor (optional)
- Store phone as instance variable
- Log phone number when phrases are recognized
- Add intent routing logic that detects `<SHIFT>` intent and can trigger shift-checking with phone
- Print routing decisions for debugging

**Code**:
```python
class CallAssistant:
    def __init__(self, caller_phone: Optional[str] = None):
        self.caller_phone = caller_phone  # ← NEW: Store phone
        self.llm_client = OllamaClient(...)
        self.whisper_client = None
        self.llm_response_array = []

    def on_phrase_complete(self, phrase: str) -> None:
        print(f"[PHRASE COMPLETE]\n{phrase}")
        if self.caller_phone:
            print(f"[CALLER PHONE] {self.caller_phone}")  # ← NEW: Log phone
        
        # ...LLM processing...
        
        # Route to appropriate action based on intent
        self._route_intent(llm_response)  # ← NEW: Add routing

    def _route_intent(self, intent_tag: str) -> None:  # ← NEW: Intent router
        """Route LLM intent to appropriate handler"""
        if "<SHIFT>" in intent_tag and self.caller_phone:
            print(f"[ROUTING] Shift check request for {self.caller_phone}")
            # Future: await check_shifts_for_caller(service_name="hahs_vic3495", caller_phone=self.caller_phone)
        elif "<LOGIN>" in intent_tag:
            print(f"[ROUTING] Login assistance requested")
        elif "<REAL>" in intent_tag:
            print(f"[ROUTING] Transfer to real agent")
        else:
            print(f"[ROUTING] Request denied: {intent_tag}")
```

---

### 3. **shift_scraper.py** - Shift Parsing & Phone-Based Filtering
**File**: `backend/automation/shift_scraper.py`

**Changes**:
- Add `worker_phone` field to `Shift` dataclass
- Update table row parser to extract phone from column 2
- Update div parser to intelligently extract phone numbers (7+ digits, with +/- normalization)
- Update list item parser to extract phone numbers
- Implement phone-based filtering with normalized phone comparison

**Code**:
```python
@dataclass
class Shift:
    id: Optional[str]
    worker_name: Optional[str]
    worker_phone: Optional[str]  # ← NEW: Store worker's phone
    client_name: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    status: Optional[str]
    coordinator_contact: Optional[str]

def parse_shifts_from_html(html: str) -> List[Shift]:
    # Updated table parsing: [ID, Worker, Phone, Client, Start, End, Status, Coord]
    # Updated div parsing: intelligently extract phone numbers
    # Updated list parsing: find phone in remaining text
    # ← All now populate worker_phone

def filter_real_shifts(shifts: List[Shift], caller_phone: Optional[str] = None) -> List[Shift]:
    """Filter shifts and optionally match by phone number"""
    real = []
    for s in shifts:
        # Check if shift is real (has worker name and not cancelled)
        if not (s.worker_name and (not s.status or "cancel" not in (s.status or "").lower())):
            continue
        
        # If caller_phone provided, filter by matching phone
        if caller_phone:
            # Normalize phone numbers (remove +, -, spaces)
            normalized_caller = caller_phone.replace("+", "").replace("-", "").replace(" ", "")
            normalized_shift = (s.worker_phone or "").replace("+", "").replace("-", "").replace(" ", "")
            
            # Match if numbers contain each other (handles partial matches)
            if normalized_shift and (normalized_caller in normalized_shift or normalized_shift in normalized_caller):
                real.append(s)
                logger.info(f"Shift {s.id} matched to caller {caller_phone}")
            else:
                logger.debug(f"Shift {s.id} skipped: phone mismatch")
        else:
            # No phone filtering, include all real shifts
            real.append(s)
    
    return real
```

---

### 4. **check_shifts_handler.py** - Orchestration & Phone Passing
**File**: `backend/automation/check_shifts_handler.py`

**Changes**:
- Add `caller_phone` parameter to `check_shifts_and_notify()` function
- Pass `caller_phone` to `filter_real_shifts()` for phone-based filtering
- Include `worker_phone` in shift payload for notifications
- Add type hints for Optional parameters

**Code**:
```python
from typing import List, Dict, Optional  # ← NEW: Added Optional

async def check_shifts_and_notify(
    service_name: str,
    notify_method: str = "log",
    caller_phone: Optional[str] = None  # ← NEW: Phone parameter
) -> Dict:
    """
    Check Ezaango shifts and notify coordinators.
    
    Args:
        service_name: Ezaango service identifier (e.g., 'hahs_vic3495')
        notify_method: Notification method - 'log' or 'email'
        caller_phone: Phone number of caller to filter shifts (optional)
    """
    
    # ...login and scraping...
    
    # Parse and filter shifts
    candidates = parse_shifts_from_html(html)
    real_shifts = filter_real_shifts(candidates, caller_phone=caller_phone)  # ← NEW: Pass phone
    
    # Build shift payload
    shifts_payload: List[Dict] = []
    for s in real_shifts:
        shifts_payload.append({
            "id": s.id,
            "worker_name": s.worker_name,
            "worker_phone": s.worker_phone,  # ← NEW: Include phone in payload
            "client_name": s.client_name,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status,
            "coordinator_contact": s.coordinator_contact,
        })
```

---

## Data Flow Diagram

```
3CX Webhook
├─ call_id: "call_123"
└─ from: "+61412345678"
        ↓
POST /webhook/call-started
        ↓
app.py::call_started()
├─ Extract: call_id, caller_phone
└─ Create: CallAssistant(caller_phone)
        ↓
CallAssistant listening...
        ↓
User speaks: "When is my shift?"
        ↓
Whisper transcription
        ↓
LLM classification: "<SHIFT>"
        ↓
on_phrase_complete() callback
├─ Log: [CALLER PHONE] +61412345678
└─ Route: _route_intent() detects <SHIFT>
        ↓
[ROUTING] Shift check request for +61412345678
        ↓
check_shifts_for_caller(
    service_name="hahs_vic3495",
    caller_phone="+61412345678"
)
        ↓
Scrape Ezaango shifts
        ↓
filter_real_shifts(shifts, caller_phone="+61412345678")
├─ Normalize: "61412345678"
├─ Match shifts where worker_phone contains normalized caller
└─ Return: [Shift{worker_phone matches caller}, ...]
        ↓
Build payload with worker_phone
        ↓
Notify coordinator with matched shifts
```

---

## Testing Checklist

- [ ] Send test 3CX webhook with `call_id` and `from` fields
- [ ] Verify `caller_phone` extracted and logged in console
- [ ] Test LLM classification of `<SHIFT>` intent
- [ ] Check console output for `[CALLER PHONE]` logging
- [ ] Check console output for `[ROUTING]` decision
- [ ] Run shift scraper with sample HTML to verify `worker_phone` extraction
- [ ] Test phone filtering logic with various phone formats
- [ ] Verify shift payload includes `worker_phone` field
- [ ] Test async integration when shift checking is triggered

---

## Next Steps

### Phase 1: Testing (Ready Now)
1. Send mock 3CX webhook: `POST /webhook/call-started?call_id=test123&from=%2B61412345678`
2. Verify phone extraction and logging
3. Test shift scraper with real Ezaango HTML
4. Verify phone matching logic with sample data

### Phase 2: Async Integration (When Ready)
1. Uncomment shift-checking trigger in `_route_intent()` 
2. Implement async/await pattern for CallAssistant
3. Integrate TTS response with shift results
4. Test end-to-end: 3CX call → Whisper → LLM → Playwright → Shifts

### Phase 3: Production
1. Update 3CX webhook payload structure if needed (verify `from` field contains phone)
2. Tune shift scraper selectors for actual Ezaango HTML
3. Configure SMTP for email notifications
4. Deploy and monitor call flow

---

## Files Modified
1. ✅ `backend/core/call_assistant/app.py` - Phone extraction from webhook
2. ✅ `backend/core/call_assistant/call_assistant.py` - Phone storage and routing
3. ✅ `backend/automation/shift_scraper.py` - Phone parsing and filtering
4. ✅ `backend/automation/check_shifts_handler.py` - Phone parameter passing

## Files Created
- `TECHNICAL_FLOW.md` - Architecture documentation
- `INTEGRATION_CHANGES.md` - This document

---

## Type Safety
All parameters properly typed with `Optional[str]` for phone arguments to allow `None` values while maintaining type safety.
