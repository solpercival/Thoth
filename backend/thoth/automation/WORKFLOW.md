# Complete Automation Workflow

## End-to-End Data Flow

```
INPUT: Phone number + User transcript
    ↓
    test_integrated_workflow.py (ORCHESTRATOR)
        │
        ├─→ 1. AUTHENTICATION
        │       │
        │       └─→ login_playwright.py
        │           │
        │           ├─ Uses: website_configs_playwright.py (CSS selectors)
        │           ├─ Uses: secrets.py (credentials + TOTP codes)
        │           └─ Output: Authenticated Playwright page object
        │
        ├─→ 2. STAFF LOOKUP
        │       │
        │       └─→ staff_lookup.py::lookup_staff_by_phone(page, phone_number)
        │           │
        │           ├─ Navigates to: /staff/4
        │           ├─ Searches for: phone_number
        │           └─ Output: staff dict {id, full_name, email, team}
        │
        ├─→ 3. DATE REASONING
        │       │
        │       └─→ shift_date_reasoner.py::ShiftDateReasoner.reason_dates(transcript)
        │           │
        │           ├─ Sends user query to: Ollama (local LLM)
        │           ├─ Model used: gemma3:1b
        │           └─ Output: date range {start_date, end_date, reasoning}
        │
        ├─→ 4. SHIFT SEARCH (WITH DATE FILTERING)
        │       │
        │       └─→ staff_lookup.py::search_staff_shifts_by_name(page, name, start_date, end_date)
        │           │
        │           ├─ Navigates to: /search?keyword=staff_name
        │           ├─ Fills search field with date range from LLM
        │           ├─ Presses Enter to filter results
        │           ├─ Parses: filtered shift table results
        │           └─ Output: list of shifts {client, date, time, shift_id}
        │
        └─→ 5. DATE FILTERING
                │
                └─→ Local filtering in test_integrated_workflow.py
                    │
                    ├─ Filter: shifts with valid dates
                    ├─ Filter: only within reasoned date range
                    └─ Output: FINAL SHIFTS FOR USER
                        {
                            "staff": {...},
                            "date_info": {...},
                            "all_shifts": [...],
                            "filtered_shifts": [...]
                        }

OUTPUT: Staff info + interpreted dates + filtered shifts
```

## Module Connections

### test_integrated_workflow.py
**Role:** Main orchestrator that coordinates everything  
**Calls:**
- `login_playwright.LoginAutomation.login_with_retry()` → Step 1
- `staff_lookup.lookup_staff_by_phone()` → Step 2
- `shift_date_reasoner.ShiftDateReasoner.reason_dates()` → Step 3
- `staff_lookup.search_staff_shifts_by_name()` → Step 4
- Local filtering → Step 5

**Dependencies:**
- login_playwright.py
- staff_lookup.py
- shift_date_reasoner.py (imported from call_assistant folder)

---

### login_playwright.py
**Role:** Handles all browser automation and 2FA login  
**Provides:**
- `LoginAutomation` - High-level context manager
- `PlaywrightAutoLogin` - Low-level automation

**Uses:**
- `website_configs_playwright.get_config()` → Gets CSS selectors
- `secrets.get_admin_credentials()` → Gets username/password
- `secrets.get_admin_totp_code()` → Gets 2FA code

**Critical Fix Applied:** Added explicit wait for page navigation
```python
# After 2FA submission, wait for page to reach /home
await self.page.wait_for_url("**/home**", timeout=10000)
```
This ensures subsequent functions don't fail with "Still on login page" errors.

**Returns:** Authenticated Playwright `page` object

---

### website_configs_playwright.py
**Role:** Stores CSS selectors and login form configuration  
**Provides:**
- `HAHS_VIC3495_CONFIG` - Ezaango configuration
  - `url`: https://hahs-vic3495.ezaango.app/login
  - `username_selector`: input[id='email'][type='email']
  - `password_selector`: input[id='password'][type='password']
  - `two_fa_selector`: input[id='one_time_password']
  - `expected_url_after_login`: https://hahs-vic3495.ezaango.app/

**Used By:** login_playwright.py

---

### secrets.py
**Role:** Manages credentials and TOTP code generation  
**Provides:**
- `get_admin_credentials(service_name)` → {"username": "...", "password": "..."}
- `get_admin_totp_code(service_name)` → "123456" (6-digit, regenerates every 30 sec)

**Environment Variables:**
```
ADMIN_USERNAME_HAHS_VIC3495=admin@example.com
ADMIN_PASSWORD_HAHS_VIC3495=your_password
TOTP_SECRET_HAHS_VIC3495=your_base32_totp_secret
```

**Used By:**
- login_playwright.py
- test_integrated_workflow.py

---

### staff_lookup.py
**Role:** Finds staff and their shifts on Ezaango with date filtering  
**Provides:**
- `lookup_staff_by_phone(page, phone_number)` → staff dict
- `search_staff_shifts_by_name(page, staff_name, start_date, end_date)` → filtered shifts
- `_remove_title(name)` → cleans staff names

**Key Enhancement:** Date Range Filtering
- Now accepts `start_date` and `end_date` parameters from `shift_date_reasoner.py`
- Fills the search input field with date range: `input[type="search"].form-control-sm`
- Converts dates from YYYY-MM-DD → DD-MM-YYYY for the search field
- Presses Enter to apply filter
- Returns pre-filtered shifts from Ezaango server

**Uses:**
- `website_configs_playwright` (selectors)
- BeautifulSoup (HTML parsing)
- Playwright page object from login_playwright.py

**Workflow in staff_lookup.py:**
1. `lookup_staff_by_phone()`
   - Navigates to /staff/4
   - Searches for phone
   - Parses HTML
   - Returns staff details
   - Calls `_remove_title()` to clean name

2. `search_staff_shifts_by_name(page, name, start_date, end_date)`
   - Navigates to /search?keyword=name
   - **NEW:** If dates provided, fills search field with date range
   - **NEW:** Presses Enter to apply server-side filtering
   - Waits for table results
   - Parses each row
   - Extracts client, date, time, shift_id
   - Returns list of **already-filtered** shifts

**Used By:**
- test_integrated_workflow.py (calls both functions, passes reasoned dates to search)
- test_automation.py (individual testing)

---

### shift_date_reasoner.py
**Role:** Interprets user queries using LLM  
**Provides:**
- `ShiftDateReasoner` class
  - `__init__(model="gemma3:1b")` → Initialize with Ollama model
  - `reason_dates(user_query)` → Interpret transcript

**How it works:**
1. Takes user transcript: "Cancel my shift tomorrow"
2. Builds system prompt + user query
3. Sends to Ollama: POST http://127.0.0.1:11434/api/chat
4. Ollama (gemma3:1b) processes and responds with JSON
5. Parses JSON response
6. Returns: {is_shift_query, date_range_type, start_date, end_date, reasoning}

**Data Format:** Returns dates in YYYY-MM-DD format
- Example: "2025-12-16" → Can be directly used by search_staff_shifts_by_name()

**Uses:**
- llm_client.py (OllamaClient)
- Ollama server (must be running: `ollama serve`)

**Used By:**
- test_integrated_workflow.py (uses dates in search_staff_shifts_by_name call)
- test_date_reasoner.py (individual testing)

---

## Key Data Structures

### Staff Object (from lookup_staff_by_phone)
```python
{
    "id": 1906,
    "full_name": "Alannah Courtnay",
    "email": "larnsie9@gmail.com",
    "team": "VIC Team",
    "mobile": "0431256441",
    "address": "...",
    "status": "..."
}
```

### Date Info (from reason_dates)
```python
{
    "is_shift_query": True,
    "date_range_type": "tomorrow",
    "start_date": "2025-12-16",
    "end_date": "2025-12-16",
    "reasoning": "Cancellation of shift tomorrow."
}
```

### Shift Object (from search_staff_shifts_by_name)
```python
{
    "type": "Shift",
    "staff_name": "Alannah Courtnay",
    "client_name": "Anthea Bassi",
    "date": "08-11-2025",
    "time": "12:00 PM",
    "shift_id": "196437",
    "shift_url": "https://hahs-vic3495.ezaango.app/roster/196437"
}
```

## Testing Each Module

### Test Individual Components
```bash
# Test staff lookup
python test_automation.py --staff-by-phone "0431256441"

# Test shift search
python test_automation.py --shifts-by-name "Alannah Courtnay"

# Test date reasoning
python test_date_reasoner.py
```

### Test Complete Workflow
```bash
python test_integrated_workflow.py --phone "0431256441" --transcript "Hi I would like to cancel my shift tomorrow"
```

## Critical Fixes Applied

### 1. Async Navigation Wait (login_playwright.py)
**Problem:** After 2FA, code didn't wait for page to navigate to /home  
**Solution:** Added `await self.page.wait_for_url("**/home**", timeout=10000)`  
**Result:** Page navigation completes before returning, prevents subsequent errors

### 2. Saved Session Handling (login_playwright.py)
**Problem:** Cached sessions would try to navigate to login page that auto-redirects to /home  
**Solution:** Added check to detect already-logged-in state  
**Result:** Skips login form if already authenticated

### 3. Date Filter Safety (test_integrated_workflow.py)
**Problem:** Some shifts had None for date field, causing comparison errors  
**Solution:** Added check: `if s['date'] is not None`  
**Result:** Filters out malformed shifts gracefully

## Dependencies Installation

```bash
pip install playwright
pip install pyotp
pip install beautifulsoup4
pip install httpx  # For Ollama client

playwright install
ollama pull gemma3:1b
```

## Running the Complete Workflow

```bash
# Start Ollama in one terminal
ollama serve

# In another terminal, run the test
cd backend/automation
python test_integrated_workflow.py --phone "0431256441" --transcript "Hi I would like to cancel my shift tomorrow"
```

Expected output shows all 5 steps completing successfully with final filtered shifts.
