# Usage Examples - Phone Integration

## 1. Webhook Call (3CX Integration)

### Request Format
```bash
# When a call comes in from caller +61412345678
POST http://localhost:5000/webhook/call-started
Content-Type: application/json

{
  "call_id": "call_20251209_001",
  "from": "+61412345678",
  "to": "+61298765432"
}
```

### Response
```json
{
  "status": "success",
  "message": "Voice assistant started for call call_20251209_001",
  "caller_phone": "+61412345678"
}
```

### Console Output During Call
```
[PHRASE COMPLETE]
When is my shift tomorrow?
[CALLER PHONE] +61412345678
[SENDING TO LLM]
[LLM RESPONSE]
<SHIFT>
[ROUTING] Shift check request for +61412345678
```

---

## 2. Direct CallAssistant Usage

### Example 1: With Caller Phone
```python
from call_assistant import CallAssistant

# Initialize with caller phone (from 3CX webhook)
assistant = CallAssistant(caller_phone="+61412345678")

# The assistant will store this phone and use it for intent routing
assistant.run_with_event(stop_event)
```

### Example 2: Without Caller Phone
```python
# Initialize without phone (falls back to listening mode)
assistant = CallAssistant()
assistant.run()
```

---

## 3. Intent Routing Examples

### Scenario A: Shift Check Request
```
User says: "When is my shift tomorrow?"

LLM Response: <SHIFT>

Routing Output:
[ROUTING] Shift check request for +61412345678
(Would trigger: check_shifts_for_caller(service="hahs_vic3495", caller_phone="+61412345678"))
```

### Scenario B: Login Help
```
User says: "I can't log into the app"

LLM Response: <LOGIN>

Routing Output:
[ROUTING] Login assistance requested
(Would trigger: login_flow())
```

### Scenario C: Transfer to Agent
```
User says: "Can I speak to someone?"

LLM Response: <REAL>

Routing Output:
[ROUTING] Transfer to real agent
(Would trigger: transfer_to_agent())
```

### Scenario D: Denied Request
```
User says: "Tell me a joke"

LLM Response: <DENY>

Routing Output:
[ROUTING] Request denied: <DENY>
```

---

## 4. Shift Scraping with Phone Filtering

### Example 1: Parse with Phone Matching
```python
from shift_scraper import parse_shifts_from_html, filter_real_shifts

# Get HTML from Ezaango (via Playwright)
html = await automation.scrape_page_content()

# Parse all shifts
candidates = parse_shifts_from_html(html)
# Output: [
#   Shift(id="001", worker_name="John Smith", worker_phone="+61412345678", ...),
#   Shift(id="002", worker_name="Jane Doe", worker_phone="+61487654321", ...),
#   Shift(id="003", worker_name="Bob Wilson", worker_phone="+61412345678", ...),
# ]

# Filter for specific caller
caller_phone = "+61412345678"
matched = filter_real_shifts(candidates, caller_phone=caller_phone)
# Output: [
#   Shift(id="001", worker_name="John Smith", worker_phone="+61412345678", ...),
#   Shift(id="003", worker_name="Bob Wilson", worker_phone="+61412345678", ...),
# ]
```

### Example 2: Parse All Shifts (No Filtering)
```python
candidates = parse_shifts_from_html(html)
all_real = filter_real_shifts(candidates)  # Returns all non-cancelled shifts
```

### Example 3: Phone Number Normalization
```python
# The filtering function normalizes phone numbers, so these all match:
filter_real_shifts(shifts, caller_phone="+61412345678")
filter_real_shifts(shifts, caller_phone="61412345678")      # No +
filter_real_shifts(shifts, caller_phone="+61 412 345 678")  # Spaces
filter_real_shifts(shifts, caller_phone="+61-412-345-678")  # Dashes
# All find the same matches!
```

---

## 5. Shift Checking Handler

### Direct Function Call
```python
import asyncio
from check_shifts_handler import check_shifts_and_notify

# With phone filtering
result = await check_shifts_and_notify(
    service_name="hahs_vic3495",
    notify_method="log",
    caller_phone="+61412345678"
)

# Output:
# {
#   "success": True,
#   "shifts_found": 2,
#   "notified": [
#     {"contact": "coordinator@example.com", "count": 2, "sent": True}
#   ]
# }
```

### Without Phone Filtering
```python
# Check all shifts (no phone matching)
result = await check_shifts_and_notify(
    service_name="hahs_vic3495",
    notify_method="email"
)
# Returns all shifts, grouped by coordinator
```

---

## 6. Integration Testing

### Test 1: Phone Extraction from Webhook
```bash
# Send test webhook
curl -X POST http://localhost:5000/webhook/call-started \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test_call_001",
    "from": "+61412345678",
    "to": "+61298765432"
  }'

# Expected console output:
# [PHRASE COMPLETE]
# ...user speaks...
# [CALLER PHONE] +61412345678
```

### Test 2: Shift Scraper with Sample HTML
```python
from shift_scraper import parse_shifts_from_html

# Sample Ezaango HTML structure
html = """
<table>
  <tr><th>ID</th><th>Worker</th><th>Phone</th><th>Client</th><th>Time</th></tr>
  <tr>
    <td>S001</td>
    <td>John Smith</td>
    <td>+61 412 345 678</td>
    <td>HAHS</td>
    <td>9am-5pm Monday</td>
  </tr>
</table>
"""

shifts = parse_shifts_from_html(html)
print(shifts[0].worker_phone)  # Output: +61 412 345 678
```

### Test 3: Phone Matching Logic
```python
from shift_scraper import filter_real_shifts, Shift

# Create test shifts
shifts = [
    Shift(
        id="S001",
        worker_name="John",
        worker_phone="+61412345678",
        client_name="HAHS",
        start_time="9am",
        end_time="5pm",
        status="active",
        coordinator_contact="coord@example.com"
    ),
    Shift(
        id="S002",
        worker_name="Jane",
        worker_phone="+61487654321",
        client_name="HAHS",
        start_time="2pm",
        end_time="10pm",
        status="active",
        coordinator_contact="coord@example.com"
    ),
]

# Test filtering
matched = filter_real_shifts(shifts, caller_phone="+61412345678")
assert len(matched) == 1
assert matched[0].worker_name == "John"
print("✓ Phone matching works correctly!")
```

---

## 7. Async Integration (Future)

### Uncomment in `call_assistant.py::_route_intent()`
```python
def _route_intent(self, intent_tag: str) -> None:
    if "<SHIFT>" in intent_tag and self.caller_phone:
        print(f"[ROUTING] Shift check request for {self.caller_phone}")
        # Uncomment when async is implemented:
        # result = await check_shifts_for_caller(
        #     service_name="hahs_vic3495",
        #     caller_phone=self.caller_phone
        # )
        # # Convert shifts to speech
        # if result['shifts_found'] > 0:
        #     message = f"Found {result['shifts_found']} shifts for you"
        #     self.tts_client.speak(message)
```

---

## 8. Production Deployment

### Environment Variables
```bash
# .env file
ADMIN_USERNAME_HAHS_VIC3495=your_admin_username
ADMIN_PASSWORD_HAHS_VIC3495=your_admin_password
TOTP_SECRET_HAHS_VIC3495=your_totp_secret

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=notifications@yourcompany.com
```

### Flask App Startup
```bash
cd backend/core/call_assistant
python app.py
# Server running on http://localhost:5000
```

### 3CX Webhook Configuration
```
Webhook URL: http://your-server.com:5000/webhook/call-started
Method: POST
Content-Type: application/json
Payload:
{
  "call_id": "<call_id>",
  "from": "<caller_phone>",
  "to": "<destination>"
}
```

---

## Summary of Features

✅ **Phone Extraction**: Automatically captures `from` field from 3CX webhooks
✅ **Phone Storage**: Stores phone in CallAssistant instance for entire call duration
✅ **Phone Logging**: Logs phone number when phrases are recognized
✅ **Intent Routing**: Routes `<SHIFT>` intent to shift-checking with phone context
✅ **Phone Parsing**: Extracts phone numbers from Ezaango shift HTML
✅ **Phone Filtering**: Matches shifts by caller phone with smart normalization
✅ **Phone in Payload**: Includes `worker_phone` in shift notifications
✅ **Type Safety**: Proper Optional type hints for all phone parameters
