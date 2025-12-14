# Staff Lookup by Phone Implementation

## Overview

Implemented staff lookup by phone number to enable employee-specific shift checking. When a caller's phone number is available, the system now:

1. Logs into Ezaango as admin
2. Navigates to the Staff page (`/staff/4`)
3. Searches for the employee by phone number
4. Extracts their full name and details
5. Uses the full name to filter shifts with higher accuracy

---

## New File: `staff_lookup.py`

**Location**: `backend/automation/staff_lookup.py`

### Main Function: `lookup_staff_by_phone(page, phone_number)`

**Purpose**: Search for a staff member by phone number on Ezaango's staff page

**Parameters**:
- `page`: Playwright page object (already logged in)
- `phone_number`: Phone number to search (e.g., "+61412345678" or "0412345678")

**Returns**:
```python
{
    "id": "1728",
    "full_name": "Ms Adaelia Thomas",
    "email": "adaeliathomas@gmail.com",
    "team": "VIC Team",
    "mobile": "0490024573",
    "status": "Active",
    "address": "836 Highbury Rd, Glen Waverley VIC 3150, Australia"
}
# Returns None if not found
```

**Workflow**:
```
1. Navigate to /staff/4
2. Wait for search input: input[type='search'].form-control
3. Fill search box with phone number
4. Wait 2 seconds for DataTables to filter
5. Parse table HTML:
   - Find table#task-table
   - Extract first tbody row
   - Parse columns: [ID, Full Name, Team, Email, Mobile, Address, Status]
6. Return staff info dict
```

### Helper Function: `normalize_phone(phone)`

**Purpose**: Normalize phone numbers for flexible comparison

**Examples**:
- `"+61 412 345 678"` → `"61412345678"`
- `"0412 345 678"` → `"61412345678"` (converts leading 0 to 61 for Australian numbers)
- `"+61412345678"` → `"61412345678"`

### Helper Function: `phones_match(phone1, phone2)`

**Purpose**: Check if two phones match (handles various formats)

**Returns**: `True` if normalized phones are equal

---

## Modified File: `login_playwright.py`

### New Method: `navigate_and_scrape(url)`

**Purpose**: Navigate to a specific URL and scrape content

**Parameters**:
- `url`: Full URL to navigate to

**Returns**: Page HTML content

**Example**:
```python
html = await automation.navigate_and_scrape("https://hahs-vic3495.ezaango.app/staff/4")
```

### New Method: `get_page()`

**Purpose**: Get the underlying Playwright page object for advanced operations (like staff lookup)

**Returns**: Playwright `Page` object or `None`

**Example**:
```python
page = await automation.get_page()
staff_info = await lookup_staff_by_phone(page, "+61412345678")
```

---

## Modified File: `check_shifts_handler.py`

### Enhanced `check_shifts_and_notify()` Function

**New Parameter**:
- `caller_phone` (Optional[str]): Phone number of caller

**Workflow** (updated):
```
1. Login to Ezaango with admin credentials
2. If caller_phone provided:
   a. Get Playwright page object
   b. Call lookup_staff_by_phone(page, caller_phone)
   c. Extract staff full name if found
3. Navigate to shifts page and scrape
4. Parse shifts from HTML
5. Filter shifts by:
   - Staff name (if found via phone lookup)
   - Phone number (fallback if name lookup failed)
6. Build payload and notify coordinators
7. Return results + staff_info
```

**Return Value** (enhanced):
```python
{
    "success": True,
    "shifts_found": 2,
    "notified": [{"contact": "coord@example.com", "count": 2, "sent": True}],
    "staff_info": {  # ← NEW
        "id": "1728",
        "full_name": "Ms Adaelia Thomas",
        "email": "adaeliathomas@gmail.com",
        "team": "VIC Team",
        "mobile": "0490024573",
        "status": "Active",
        "address": "..."
    }
}
```

---

## Modified File: `shift_scraper.py`

### Enhanced `filter_real_shifts()` Function

**New Parameters**:
- `staff_name` (Optional[str]): Staff member's full name to match

**Filtering Logic** (updated):
```
1. Check if shift is real (has worker name, not cancelled)
2. If staff_name provided:
   - Case-insensitive name matching
   - Prioritize name match over phone match
   - Log: "Shift matched to staff by name"
3. If phone provided (fallback):
   - Normalize both phones
   - Check for substring match
   - Log: "Shift matched to caller by phone"
4. If neither provided:
   - Include all real shifts (backward compatible)
```

**Example Usage**:
```python
# Match by staff name (preferred)
shifts = filter_real_shifts(candidates, staff_name="Ms Adaelia Thomas")

# Match by phone (fallback)
shifts = filter_real_shifts(candidates, caller_phone="+61412345678")

# Match by name + phone (redundancy)
shifts = filter_real_shifts(
    candidates,
    caller_phone="+61412345678",
    staff_name="Ms Adaelia Thomas"
)

# Get all shifts (backward compatible)
shifts = filter_real_shifts(candidates)
```

---

## Data Flow Diagram

```
3CX Call
├─ caller_phone: "+61412345678"
│
└─ check_shifts_and_notify()
   │
   ├─ Login to Ezaango
   │
   ├─ Staff Lookup (NEW)
   │  ├─ Page: /staff/4
   │  ├─ Search: "+61412345678"
   │  └─ Result: {full_name: "Ms Adaelia Thomas", ...}
   │
   ├─ Scrape Shifts
   │
   ├─ Parse HTML
   │  └─ Extract: worker_name, worker_phone, etc.
   │
   ├─ Filter by Staff Name (NEW)
   │  ├─ Compare: "Ms Adaelia Thomas" in shift worker_name
   │  └─ Result: [Shift{}, Shift{}, ...]
   │
   ├─ Build Payload
   │  └─ Include: id, worker_name, worker_phone, etc.
   │
   ├─ Notify Coordinators
   │
   └─ Return:
      {
        "success": true,
        "shifts_found": 2,
        "notified": [...],
        "staff_info": {...}
      }
```

---

## Usage Example

### In Call Assistant (Future Integration)

```python
from check_shifts_handler import check_shifts_and_notify

# When <SHIFT> intent detected
if "<SHIFT>" in llm_response:
    result = await check_shifts_and_notify(
        service_name="hahs_vic3495",
        notify_method="email",
        caller_phone="+61412345678"  # From 3CX webhook
    )
    
    if result['staff_info']:
        print(f"Found: {result['staff_info']['full_name']}")
        print(f"Shifts: {result['shifts_found']}")
        # Convert to speech: "Found 2 shifts for Ms Adaelia Thomas"
```

### Direct Usage

```python
import asyncio
from check_shifts_handler import check_shifts_and_notify

async def main():
    result = await check_shifts_and_notify(
        service_name="hahs_vic3495",
        caller_phone="+61 412 345 678"  # Flexible format
    )
    
    print(f"Staff: {result.get('staff_info', {}).get('full_name')}")
    print(f"Found {result['shifts_found']} shifts")

asyncio.run(main())
```

---

## Testing

### Test 1: Staff Lookup
```python
# Navigate to /staff/4 and search for "+61412345678"
# Verify: Returns correct staff info dict
staff = await lookup_staff_by_phone(page, "+61412345678")
assert staff['full_name'] == "Ms Adaelia Thomas"
assert staff['mobile'] == "0490024573"
```

### Test 2: Phone Normalization
```python
# Test various phone formats
assert normalize_phone("+61412345678") == "61412345678"
assert normalize_phone("+61 412 345 678") == "61412345678"
assert normalize_phone("0412345678") == "61412345678"
assert phones_match("+61412345678", "0412345678") == True
```

### Test 3: Shift Filtering by Name
```python
shifts = [
    Shift(..., worker_name="Ms Adaelia Thomas", ...),
    Shift(..., worker_name="John Smith", ...),
]
filtered = filter_real_shifts(shifts, staff_name="Ms Adaelia Thomas")
assert len(filtered) == 1
assert filtered[0].worker_name == "Ms Adaelia Thomas"
```

### Test 4: End-to-End Staff Lookup
```python
# Simulate full workflow
result = await check_shifts_and_notify(
    service_name="hahs_vic3495",
    caller_phone="+61412345678"
)
assert result['success'] == True
assert result['staff_info'] is not None
assert result['shifts_found'] > 0
```

---

## Advantages of This Approach

1. **Higher Accuracy**: Matches by full name is more accurate than phone-only matching
2. **Redundancy**: Falls back to phone matching if name lookup fails
3. **Staff Context**: Provides full staff details in response
4. **Flexible Phone Formats**: Handles Australian phone number variations
5. **Backward Compatible**: Works with or without phone numbers
6. **Audit Trail**: Includes staff_info in logs for debugging

---

## Files Modified (3 Total)

1. ✅ `staff_lookup.py` - **NEW** - Staff lookup by phone
2. ✅ `check_shifts_handler.py` - **MODIFIED** - Added staff lookup integration
3. ✅ `login_playwright.py` - **MODIFIED** - Added page access methods
4. ✅ `shift_scraper.py` - **MODIFIED** - Enhanced filtering with staff name

---

## Next Steps

1. **Test staff lookup**: Verify HTML parsing matches actual Ezaango page structure
2. **Test phone formats**: Ensure all Australian phone variations work
3. **Integrate with CallAssistant**: Wire staff lookup into voice processing
4. **Add TTS**: Convert shift results to speech for caller
5. **Monitor**: Track lookup success/failure rates in logs
