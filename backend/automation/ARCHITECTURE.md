# Automation Codebase Architecture

## Overview
This automation system enables automated login and shift checking for Ezaango (and other websites), with integrated 2FA support and session management.

## Core Flow: "Check Shifts" Intent

```
User calls: check_shifts_and_notify("hahs_vic3495")
    ↓
check_shifts_handler.py (Orchestrator)
    ├─→ Get admin credentials (from credentials_client or .env)
    ├─→ Get website config (from website_configs_playwright)
    ├─→ Login via PlaywrightAutoLogin
    │   ├─→ Initialize browser & context
    │   ├─→ Navigate to login page
    │   ├─→ Fill username/password
    │   ├─→ Submit login form
    │   ├─→ Generate TOTP code (from totp_manager)
    │   ├─→ Fill 2FA code
    │   ├─→ Submit 2FA form
    │   └─→ Save session cookies
    ├─→ Scrape page HTML (shift_scraper)
    ├─→ Parse shifts (shift_scraper.parse_shifts_from_html)
    ├─→ Filter real shifts (shift_scraper.filter_real_shifts)
    ├─→ Notify coordinator (notifier)
    └─→ Return results
```

## Module Breakdown

### 1. **login_playwright.py** (Core Login Engine)
**Purpose:** Automated 2FA-aware login with session persistence

**Key Classes:**
- `LoginStrategy` (Enum): STANDARD, OAUTH, SSO, API, TWO_FACTOR
- `Credentials` (Dataclass): username, password, email, 2FA code
- `WebsiteConfig` (Dataclass): URL, selectors, timeout, expected post-login URL
- `PlaywrightAutoLogin` (Main class):
  - `__init__()`: Initializes browser & context
  - `login_standard()`: 7-step login flow (username → password → 2FA)
  - `_initialize_context()`: Loads saved session cookies if available
  - `_save_session()`: Persists cookies to `.sessions/{service}_auth.json`
  - `scrape_page_content()`: Returns raw page HTML for parsing

**How it works:**
1. Initialize Playwright browser
2. Create context (optionally loading saved cookies from `.sessions/`)
3. Navigate to login URL
4. Fill username field (using selector from config)
5. Fill password field (using selector from config)
6. Click submit button (using selector from config)
7. **Wait for 2FA input to appear** (with explicit `wait_for_selector`)
8. Fill 2FA code (automatically generated from TOTP secret)
9. Click 2FA submit button
10. Verify login success (check if page URL contains expected_url_after_login)
11. **Save session cookies** for future reuse

**Current Issue:**
- Ezaango sessions don't persist across runs (server-side session invalidation)
- Each automation run requires fresh login + 2FA code generation
- TOTP approach solves the "manual 2FA code entry" problem

---

### 2. **totp_manager.py** (2FA Code Generator)
**Purpose:** Generate 6-digit TOTP codes from secret keys

**Key Class:**
- `TOTPManager`:
  - `generate_totp_secret()`: Create new random secret (Base32)
  - `get_current_code(secret_key)`: Generate current 6-digit code
  - `verify_code(secret_key, code)`: Validate a code
  - `get_provisioning_uri()`: Generate QR code for authenticator apps

**How it works:**
- Uses `pyotp` library for RFC 6238 TOTP algorithm
- Secret key is Base32-encoded string stored securely
- Each 30-second time window generates a new 6-digit code
- No manual authenticator app scanning needed during automation

**Current Status:**
- ✅ Code written, imports working
- ⏳ Waiting for you to provide/confirm TOTP secret

---

### 3. **secrets_manager.py** (Secure Storage)
**Purpose:** Manage sensitive data (TOTP secrets, credentials)

**Key Class:**
- `SecretsManager`:
  - Priority order: Environment vars → .env file → In-memory
  - `get_secret(key)`: Retrieve secret
  - `set_secret(key, value)`: Store secret
  - `get_admin_totp_secret(service_name)`: Get TOTP secret for service

**How it works:**
1. Check environment variables first (highest security)
2. Fall back to `.env` file in workspace root (gitignored)
3. In-memory cache for testing

**Current Status:**
- ✅ Code written
- ⏳ Needs your TOTP secret to be stored here

---

### 4. **website_configs_playwright.py** (Website Selectors)
**Purpose:** Define login form selectors for different websites

**Key Variable:**
- `HAHS_VIC3495_CONFIG`: Ezaango login configuration
  - URL: `https://hahs-vic3495.ezaango.app/login`
  - Username selector: `input[id='email'][type='email']`
  - Password selector: `input[id='password'][type='password']`
  - Submit selector: `button[type='submit']` (uses `.first` to avoid ambiguity)
  - 2FA selector: `input[id='one_time_password']`
  - 2FA submit: `#check_otp`

**Function:**
- `get_config(service_name)`: Returns appropriate config for service

**Current Status:**
- ✅ Ezaango config complete
- ⏳ Shift scraper selectors need tuning (need actual HTML)

---

### 5. **check_shifts_handler.py** (Orchestrator)
**Purpose:** Main entry point for "check shifts" automation

**Main Function:**
- `check_shifts_and_notify(service_name, notify_method)`:
  - Returns dict: `{"success": bool, "shifts_found": int, "notified": [...]}`

**Current Status:**
- ✅ Structure in place
- ⏳ Needs shift scraper to be tuned

---

### 6. **shift_scraper.py** (HTML Parser)
**Purpose:** Extract shift data from page HTML

**Key Classes:**
- `Shift` (Dataclass): id, worker_name, client_name, start_time, end_time, status, coordinator_contact
- `parse_shifts_from_html(html)`: Returns list of Shift candidates
- `filter_real_shifts(candidates)`: Filters out dummy/test shifts
- `get_coordinator_contact(shift_dict)`: Extracts coordinator info

**Current Status:**
- ✅ Generic heuristics written (table rows, div classes, list items)
- ⏳ Needs tuning for actual Ezaango HTML structure

---

### 7. **notifier.py** (Notifications)
**Purpose:** Notify coordinators about found shifts

**Main Function:**
- `notify_coordinator(contact_email, shifts, method)`:
  - `method="log"`: Write to logs
  - `method="email"`: Send via SMTP

**Current Status:**
- ✅ Email + log support
- ⏳ SMTP env vars needed (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)

---

### 8. **credentials_client.py** (Credential Fetching)
**Purpose:** Retrieve admin credentials from API or environment

**Main Function:**
- `get_admin_credentials(service_name, role="admin")`:
  - Tries HTTP API first (localhost:5000)
  - Falls back to environment variables
  - Returns dict or None

**Current Status:**
- ✅ Code written
- ⏳ API optional; can use .env secrets instead

---

### 9. **run_admin_login_prompt_2fa.py** (Interactive Tester)
**Purpose:** Test login + 2FA flow interactively

**Usage:**
```bash
python run_admin_login_prompt_2fa.py hahs_vic3495
```

**Flow:**
- Check if session file exists
- If yes: Load saved session, skip 2FA
- If no: Prompt for credentials, prompt for 2FA code, run login

**Current Status:**
- ✅ Session reuse logic works
- ⏳ TOTP integration pending

---

## Data Flow: Credentials → Login → Shifts → Notify

```
┌─────────────────────────────────────┐
│   Credentials Source                │
├─────────────────────────────────────┤
│ 1. Secrets Manager (.env)           │
│ 2. Environment Variables            │
│ 3. credentials_api (localhost:5000)  │
│ 4. Manual prompt (testing)           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│   Login Automation                  │
├─────────────────────────────────────┤
│ Playwright browser:                 │
│ • Load saved session (if available)  │
│ • Fill login form                    │
│ • Generate TOTP code (from secret)   │
│ • Submit 2FA                         │
│ • Save session cookies               │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│   Shift Scraping                    │
├─────────────────────────────────────┤
│ • Get page HTML                      │
│ • Parse with BeautifulSoup           │
│ • Extract shift data                 │
│ • Filter real vs. test shifts        │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│   Notification                      │
├─────────────────────────────────────┤
│ • Log to console/file                │
│ • Email coordinator (if SMTP set)    │
│ • Return structured result           │
└─────────────────────────────────────┘
```

## Security Architecture

### Secret Storage Hierarchy
```
Priority (Highest → Lowest):
1. Environment variables (set by system/container)
   - TOTP_SECRET_HAHS_VIC3495_ADMIN
   - ADMIN_USERNAME_HAHS_VIC3495
   - ADMIN_PASSWORD_HAHS_VIC3495
   
2. .env file (gitignored, local only)
   - TOTP_SECRET_HAHS_VIC3495_ADMIN=XXXX...
   - ADMIN_USERNAME_HAHS_VIC3495=...
   - etc.
   
3. In-memory (testing only)
   - Fallback if no env var or file
```

### Session Management
```
Session Cookies:
├─ Stored in: .sessions/{service}_{role}_auth.json
├─ Ignored by: .gitignore (never committed)
├─ Format: Playwright storage_state JSON
│   ├─ cookies: [list of HTTP cookies]
│   ├─ origins: [CORS origins]
│   └─ metadata: [expiration, domain, secure flags]
└─ Persistence: Expires per server cookie lifetime
```

### TOTP Secret Management
```
Secret Key Storage:
├─ Location: Environment var TOTP_SECRET_HAHS_VIC3495_ADMIN
│  └─ Format: Base32-encoded string (32+ chars)
├─ Backup: .env file (gitignored)
├─ Generated by: setup_totp.py (one-time setup)
└─ Used by: totp_manager.py (on each login)
```

## Testing & Debugging

### Interactive Testing
```bash
# Test login flow with manual 2FA entry
python run_admin_login_prompt_2fa.py hahs_vic3495

# Test with headless=False to see browser
# (Already configured in run_admin_login_prompt_2fa.py)
```

### Headless Testing (Automation)
```python
from check_shifts_handler import check_shifts_and_notify
result = await check_shifts_and_notify("hahs_vic3495", notify_method="log")
print(result)
# Output: {"success": True, "shifts_found": 5, "notified": [...]}
```

### Debug Output
- Browser screenshots: `phantom.png` (on error)
- Logs: console (configured level = INFO)
- All interactions logged to console with timestamps

## Next Steps

### Immediate (Before Running Automation)
1. ✅ Provide TOTP secret (from authenticator setup)
   - Run: `python setup_totp.py hahs_vic3495`
   - Or set env var: `TOTP_SECRET_HAHS_VIC3495_ADMIN=XXX...`

2. ⏳ Tune shift scraper
   - Get actual Ezaango HTML structure
   - Update selectors in `shift_scraper.py`
   - Test with: `python example_usage_playwright.py`

3. ⏳ Configure SMTP (optional, for email notifications)
   - Set env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS

### Medium-term
4. Integrate with core LLM pipeline
   - Create Flask endpoint `/api/check-shifts`
   - Call `check_shifts_and_notify()` from LLM intent handler

5. Create job queue (Redis + RQ)
   - Make shift checking async
   - Queue multiple service checks

### Long-term
6. Deployment orchestration
   - Docker Compose setup
   - Ollama + LLM integration
   - Start/stop scripts
