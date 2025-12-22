# Automation Module: Staff Lookup & Shift Scraping

This module provides automated website interaction for the Thoth system, enabling staff lookup by phone number, shift searching by staff name, and intelligent date reasoning using LLM. It integrates with Ezaango and other websites for 2FA-aware login and content scraping.

**📖 See [WORKFLOW.md](WORKFLOW.md) for detailed data flow and module connections**

## Architecture

### Core Flow: Staff Lookup → Date Reasoning → Shift Filtering

```
User calls with phone number + transcript
    ↓
[1] lookup_staff_by_phone (staff_lookup.py)
    ├─→ Navigate to Ezaango /staff/4 page
    ├─→ Search by phone number
    ├─→ Extract staff details (name, id, email, team, mobile)
    └─→ Remove titles from name (Ms, Mr, Dr, etc.)
    ↓
[2] reason_dates (shift_date_reasoner.py)
    ├─→ Pass user transcript to LLM (Ollama)
    ├─→ LLM interprets date query (tomorrow, next week, etc.)
    ├─→ Output: start_date, end_date, reasoning
    └─→ Return structured date range
    ↓
[3] search_staff_shifts_by_name (staff_lookup.py)
    ├─→ Navigate to Ezaango /search?keyword=staff+name
    ├─→ Parse shift table results
    ├─→ Filter shifts within date range
    ├─→ Extract: client, type, date, time, shift_id
    └─→ Return list of relevant shifts
    ↓
[4] Return to CallAssistant for TTS/response
```

### Module Dependencies

```
├── login_playwright.py          (Browser automation, 2FA login)
├── website_configs_playwright.py (Ezaango selectors)
├── staff_lookup.py               (Staff/Shift lookup)
│   ├── lookup_staff_by_phone()   - Find staff by phone
│   ├── search_staff_shifts_by_name() - Find shifts by name
│   └── _remove_title()           - Clean staff names
├── shift_date_reasoner.py        (LLM-based date interpretation)
│   └── ShiftDateReasoner.reason_dates() - Ask LLM about dates
├── secrets.py                    (Credential management)
├── notifier.py                   (Email/log notifications)
├── check_shifts_handler.py       (Orchestrator)
└── test_automation.py            (Consolidated test suite)
```

## Features

✅ **Staff Lookup** - Find employees by phone number with automatic title removal
✅ **Shift Search** - Find all shifts for a staff member with date parsing
✅ **LLM Date Reasoning** - Use local Ollama to interpret date queries intelligently  
✅ **2FA Support** - Automatic TOTP code generation for 2FA login
✅ **Session Persistence** - Save browser sessions across runs
✅ **Headless Mode** - Run browser automation without GUI
✅ **Flexible Testing** - Consolidated test suite with CLI arguments
✅ **Error Handling** - Comprehensive logging and error recovery

## Components

### 1. **staff_lookup.py** - Staff & Shift Search
Main module for finding employees and their shifts.

**Key Functions:**
- `_remove_title(full_name)` - Remove Ms/Mr/Dr/Prof from names
- `lookup_staff_by_phone(page, phone_number)` - Find staff by phone on /staff/4
  - Returns: id, full_name, email, team, mobile, address, status
- `search_staff_shifts_by_name(page, staff_name)` - Find shifts by name on /search
  - Returns: List of shifts with client, type, date, time, shift_id

**Usage:**
```python
staff = await lookup_staff_by_phone(page, "0431256441")
shifts = await search_staff_shifts_by_name(page, staff['full_name'])
```

### 2. **shift_date_reasoner.py** - LLM Date Interpretation
Uses local Ollama to intelligently determine date ranges from user queries.

**Key Class:**
- `ShiftDateReasoner` - Reasons dates from transcripts
  - `reason_dates(user_query)` - "When is my shift tomorrow?" → {"start_date": "2025-12-16", "end_date": "2025-12-16", ...}
  - Uses Ollama with gemma3:1b model
  - Returns structured JSON with date range and reasoning

**Usage:**
```python
reasoner = ShiftDateReasoner(model="gemma3:1b")
result = reasoner.reason_dates("Hi I would like to cancel my shift tomorrow")
# Returns: is_shift_query=True, start_date=2025-12-16, end_date=2025-12-16
```

### 3. **login_playwright.py** - Browser Automation & 2FA Login
Handles website login with automated 2FA code generation.

**Key Classes:**
- `LoginAutomation` - Main login orchestrator
  - `login_with_retry(page, credentials, max_attempts)` - Login with TOTP
  - `open_page(headless)` - Open browser context with optional saved session
- `WebsiteConfig` - Configuration for website selectors

**Features:**
- Session persistence (saves cookies to `.sessions/`)
- Automatic TOTP code generation from secrets
- Headless mode support
- Retry logic with exponential backoff

### 4. **website_configs_playwright.py** - Website Selectors
Pre-configured selectors for Ezaango and other websites.

**Configuration:**
```python
HAHS_VIC3495_CONFIG = {
    'url': 'https://hahs-vic3495.ezaango.app/login',
    'username_selector': "input[id='email'][type='email']",
    'password_selector': "input[id='password'][type='password']",
    'submit_selector': "button[type='submit']",
    '2fa_selector': "input[id='one_time_password']",
    ...
}
```

### 5. **check_shifts_handler.py** - Orchestrator
Main entry point combining all components.

**Key Function:**
- `check_shifts_and_notify(service_name, notify_method)` - Orchestrates entire flow
  - Logins, scrapes, filters, and notifies

### 6. **notifier.py** - Email/Log Notifications
Sends notifications about found shifts.

**Key Function:**
- `notify_coordinator(contact_email, shifts, method)` - Send notifications
  - Methods: "log" (to console), "email" (via SMTP)

### 7. **secrets.py** - Credential Management
Manages credentials from environment variables, .env, or defaults.

**Key Function:**
- `get_admin_credentials(service_name)` - Get credentials
- `get_admin_totp_code(service_name)` - Generate TOTP code

### 8. **test_automation.py** - Consolidated Test Suite
Unified test runner for all automation functions.

**Usage:**
```bash
python test_automation.py --staff-by-phone "0431256441"
python test_automation.py --shifts-by-name "Alannah Courtnay"
```

## Installation

### Prerequisites
- Python 3.8+
- Playwright browser drivers
- Ollama (for local LLM, models: gemma3:1b or higher)
- Docker (optional)

### Local Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install playwright pyotp

# Download Playwright browsers
playwright install

# Start Ollama (if using local)
ollama serve

# In another terminal, pull model
ollama pull gemma3:1b
```

### Environment Setup

Create `.env` in workspace root:
```bash
# Admin credentials
ADMIN_USERNAME_HAHS_VIC3495="admin@example.com"
ADMIN_PASSWORD_HAHS_VIC3495="your_password"
TOTP_SECRET_HAHS_VIC3495="your_totp_secret_here"

# SMTP (optional, for email notifications)
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="your_email@gmail.com"
SMTP_PASS="your_app_password"
```

## Configuration

### Website Selectors

For a new website, update `website_configs_playwright.py`:

```python
NEW_SITE_CONFIG = {
    'url': 'https://new-site.com/login',
    'username_selector': "input[name='username']",
    'password_selector': "input[name='password']",
    'submit_selector': "button[type='submit']",
    'totp_selector': "input[id='otp']",  # Optional
    'expected_url_after_login': 'https://new-site.com/dashboard',
    'wait_timeout': 10
}
```

**Finding Selectors:**
1. Open website in browser
2. Right-click login form elements
3. Select "Inspect" to view HTML
4. Copy CSS selector or use `id`, `name`, `class`, `data-testid` attributes

### LLM Model Selection

Change model in `shift_date_reasoner.py`:
```python
reasoner = ShiftDateReasoner(model="gemma3:270m")  # Larger model
# or
reasoner = ShiftDateReasoner(model="llama2")       # Different model
```

### Headless Mode

Control browser visibility:
```python
# Headless (no browser window)
async with await login_automation.open_page(headless=True) as page:
    ...

# Visible (useful for debugging)
async with await login_automation.open_page(headless=False) as page:
    ...
```

## Usage Examples

### Example 1: Staff Lookup by Phone

```bash
# Using test_automation.py
python test_automation.py --staff-by-phone "0431256441"
```

Or programmatically:
```python
from staff_lookup import lookup_staff_by_phone
from login_playwright import LoginAutomation
from website_configs_playwright import get_config
from secrets import get_admin_credentials, get_admin_totp_code

async def lookup_staff():
    config = get_config("hahs_vic3495")
    login = LoginAutomation(config)
    
    creds = get_admin_credentials("hahs_vic3495")
    creds['two_fa_code'] = get_admin_totp_code("hahs_vic3495")
    
    async with await login.open_page(headless=True) as page:
        await login.login_with_retry(page, creds)
        staff = await lookup_staff_by_phone(page, "0431256441")
        print(f"Found: {staff['full_name']}")
```

### Example 2: Search Shifts by Staff Name

```bash
# Using test_automation.py
python test_automation.py --shifts-by-name "Alannah Courtnay"
```

Or programmatically:
```python
from staff_lookup import search_staff_shifts_by_name

shifts = await search_staff_shifts_by_name(page, "Alannah Courtnay")
print(f"Found {len(shifts)} shifts")
for shift in shifts[:3]:
    print(f"  {shift['client_name']} on {shift['date']} at {shift['time']}")
```

### Example 3: LLM Date Reasoning

```python
from shift_date_reasoner import ShiftDateReasoner

reasoner = ShiftDateReasoner(model="gemma3:1b")
result = reasoner.reason_dates("Hi I would like to cancel my shift tomorrow")

print(f"Is Shift Query: {result['is_shift_query']}")
print(f"Start Date: {result['start_date']}")
print(f"End Date: {result['end_date']}")
print(f"Search Query: {reasoner.format_search_query(result)}")
```

Output:
```
Is Shift Query: True
Start Date: 2025-12-16
End Date: 2025-12-16
Search Query: from=2025-12-16&to=2025-12-16
```

### Example 4: Complete Integration Workflow ✅ NOW IMPLEMENTED

Complete end-to-end workflow combining all components:

```bash
# Run the comprehensive integration test
python test_integrated_workflow.py --phone "0431256441" --transcript "Hi I would like to cancel my shift tomorrow"
```

Programmatically:
```python
from staff_lookup import lookup_staff_by_phone, search_staff_shifts_by_name
from shift_date_reasoner import ShiftDateReasoner
from login_playwright import LoginAutomation
from website_configs_playwright import get_config
from secrets import get_admin_credentials, get_admin_totp_code

async def get_staff_shifts_for_dates(phone_number, transcript):
    """
    Complete workflow: phone → staff → dates → filtered shifts
    
    Args:
        phone_number: User's phone number (e.g., "0431256441")
        transcript: User's spoken request (e.g., "cancel my shift tomorrow")
    
    Returns:
        dict with staff info, reasoned dates, and filtered shifts
    """
    
    # Get credentials and config
    config = get_config("hahs_vic3495")
    admin_creds = get_admin_credentials("hahs_vic3495")
    admin_creds["two_fa_code"] = get_admin_totp_code("hahs_vic3495")
    
    # Perform complete workflow within logged-in session
    async with LoginAutomation(headless=False, use_saved_session=False) as auto:
        # Step 1: Login with 2FA
        success = await auto.login_with_retry(
            config=config,
            service_name="hahs_vic3495_admin",
            llm_credentials=admin_creds
        )
        if not success:
            return None
        
        page = await auto.get_page()
        
        # Step 2: Lookup staff by phone
        staff = await lookup_staff_by_phone(page, phone_number)
        if not staff:
            return None
        
        # Step 3: Reason dates from user transcript
        reasoner = ShiftDateReasoner(model="gemma3:1b")
        date_info = reasoner.reason_dates(transcript)
        
        # Step 4: Search shifts by staff name
        all_shifts = await search_staff_shifts_by_name(page, staff['full_name'])
        
        # Step 5: Filter shifts by reasoned date range
        start_date = date_info['start_date']
        end_date = date_info['end_date']
        filtered_shifts = [
            s for s in all_shifts
            if s['date'] is not None and start_date <= s['date'] <= end_date
        ]
        
        return {
            'staff': staff,
            'date_info': date_info,
            'all_shifts': all_shifts,
            'filtered_shifts': filtered_shifts
        }
```

**Example Output:**
```
Phone: 0431256441
User Query: "Hi I would like to cancel my shift tomorrow"

✓ Staff Found: Alannah Courtnay (ID: 1906)
✓ LLM Interpreted: tomorrow → 2025-12-16
✓ Total Shifts Found: 97
✓ Shifts on 2025-12-16: 0 (no shifts scheduled that day)
```

**Key Features:**
- Automatically logs in with 2FA (TOTP code generation)
- Waits for navigation to complete before proceeding
- Handles session persistence (disabled in tests for fresh login)
- Filters malformed shifts (None dates)
- Returns structured data for further processing
    }
```

## Docker Compose Usage

### Start Services

```bash
# Build and start containers
docker-compose -f docker-compose.automation.yml up --build

# Run in background
docker-compose -f docker-compose.automation.yml up -d
```

### Stop Services

```bash
docker-compose -f docker-compose.automation.yml down
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.automation.yml logs -f

# Specific service
docker-compose -f docker-compose.automation.yml logs -f login-automation
```

## Testing & Debugging

### Running Tests

```bash
# Individual component tests
python test_automation.py --staff-by-phone "0431256441"
python test_automation.py --shifts-by-name "Alannah Courtnay"

# Complete integration test (all components together)
python test_integrated_workflow.py --phone "0431256441" --transcript "Hi I would like to cancel my shift tomorrow"

# Show help
python test_automation.py --help
python test_integrated_workflow.py --help
```

### Integration Test Output

The integration test runs the complete workflow and produces detailed output:

```
======================================================================
COMPREHENSIVE INTEGRATION TEST
======================================================================
Phone Number: 0431256441
User Transcript: Hi I would like to cancel my shift tomorrow
======================================================================

[STEP 1] Logging into Ezaango...
[+] Generated TOTP code: 775283

[STEP 2] Authenticating...
[*] Browser window will now open - you can watch the automation
✓ Login successful! Current URL: https://hahs-vic3495.ezaango.app/home

[STEP 3] Looking up staff by phone...
[+] FOUND Staff:
    Name: Alannah Courtnay
    ID: 1906
    Email: larnsie9@gmail.com
    Team: VIC Team
    Mobile: 0431256441

[STEP 4] Reasoning dates from transcript...
[+] LLM Analysis:
    Is Shift Query: True
    Date Range Type: tomorrow
    Start Date: 2025-12-16
    End Date: 2025-12-16

[STEP 5] Searching for shifts and filtering by date range...
[+] Found 97 total shifts
[+] Filtered to 0 shifts in date range (2025-12-16 to 2025-12-16)

======================================================================
INTEGRATION TEST RESULTS
======================================================================
✓ Staff Found: Alannah Courtnay (ID: 1906)
✓ Date Range Reasoned: 2025-12-16 to 2025-12-16
✓ Total Shifts: 97
✓ Shifts in Date Range: 0
======================================================================
```

### Debugging Browser Issues

```python
# Run with visible browser (not headless)
async with LoginAutomation(headless=False) as auto:
    # Browser window will show what's happening in real-time
    await auto.login_with_retry(config, service_name, creds)
```

### Logging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues

| Issue | Solution |
|-------|----------|
| "Ollama not running" | Run `ollama serve` in another terminal |
| "Connection refused" | Check Ollama is running on localhost:11434 |
| "Model not found" | Run `ollama pull gemma3:1b` |
| "Login fails" | Check credentials in .env file |
| "TOTP code invalid" | Run `python test_totp_generator.py` to verify codes are generating |
| "Staff not found" | Check phone format (with/without leading 0) |
| "Playwright not installed" | Run `pip install playwright` then `playwright install` |
| "Page navigation timeout" | Website server may be slow; check internet connection |

## File Structure

```
backend/automation/
├── staff_lookup.py                 # Staff & shift lookup functions
├── shift_date_reasoner.py          # LLM date interpretation
├── login_playwright.py             # Browser automation & 2FA
├── website_configs_playwright.py   # Website selectors
├── check_shifts_handler.py         # Orchestrator
├── notifier.py                     # Email/log notifications
├── secrets.py                      # Credential management
├── test_automation.py              # Unified test suite
├── credentials_api.py              # Credential API client
├── data_processing.py              # Data processing utilities
├── .sessions/                      # Saved browser sessions (gitignored)
├── README.md                       # This file
└── __pycache__/                    # Python cache (gitignored)
```

## Security

### Credential Management
- Credentials stored in `.env` (gitignored, local only)
- Environment variables take priority over .env
- TOTP secrets never logged to console
- Session cookies stored in `.sessions/` (gitignored)

### Browser Isolation
- Run in headless mode for reduced attack surface
- Use containers for better isolation in production
- Clear sessions after use with `await login.context.close()`

### Data Privacy
- Don't log raw page HTML
- Sanitize error messages before returning
- Use HTTPS for all external requests

## Performance Tips

- Use `headless=True` for faster execution
- Adjust `wait_timeout` in configs based on network speed
- Cache website configs for frequently accessed sites
- Run tests serially if Ezaango rate-limits concurrent requests

## Next Steps / To-Do

- [ ] Create unified integration function (phone + transcript → shifts)
- [ ] Add shift filtering by date range in staff_lookup.py
- [ ] Integrate with Flask app for API endpoint
- [ ] Add email notifications for shift changes
- [ ] Create Docker container for automated runs
- [ ] Add Redis queue for background job processing

## Docker Setup (Optional)

```bash
# Build automation container
docker build -f Dockerfile.automation -t thoth-automation .

# Run with Docker Compose
docker-compose -f docker-compose.automation.yml up --build

# View logs
docker-compose -f docker-compose.automation.yml logs -f
```
