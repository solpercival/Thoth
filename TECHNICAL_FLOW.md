# Thoth Technical Flow: End-to-End Architecture

## Overview
Thoth is an AI-powered call center assistant that:
1. Receives incoming calls via 3CX webhook
2. Transcribes voice to text using Whisper
3. Classifies intent using local LLM (Ollama)
4. Executes actions (login, check shifts, notify)
5. Responds via text-to-speech

---

## 1. Call Initiation Flow

### Entry Point: 3CX Webhook
```
3CX Phone Call
    ↓
POST /webhook/call-started
    ├─ call_id: "call_123"
    ├─ from: "+61412345678"  (CALLER PHONE - NEW)
    └─ to: "+61298765432"
    ↓
app.py::call_started()
    ├─ Create CallAssistant(caller_phone)
    ├─ Start in separate thread
    └─ Return: {"status": "success"}
```

---

## 2. Voice Processing Pipeline

### Audio → Text Transcription
```
System Audio Input (Microphone)
    ↓
SystemAudioWhisperClient (whisper_client.py)
    ├─ Model: "base"
    ├─ Phrase timeout: 5 seconds
    └─ Detects complete phrases
    ↓
on_phrase_complete(phrase) callback
    ├─ Input: "When is my shift tomorrow?"
    └─ Trigger: LLM processing
```

---

## 3. LLM Intent Classification

### Text → Intent Classification
```
Whisper transcript: "When is my shift tomorrow?"
    ↓
CallAssistant.on_phrase_complete()
    ├─ Pause Whisper
    └─ Send to LLM
    ↓
OllamaClient.ask_llm(phrase)
    ├─ Model: "gemma3:1b" (local, fast)
    ├─ System Prompt: "Classify user requests into 4 tags"
    └─ Classification rules:
        ├─ <LOGIN>  → App login issues
        ├─ <SHIFT>  → Work shift/schedule questions
        ├─ <REAL>   → Transfer to real person
        └─ <DENY>   → All other requests
    ↓
LLM Response: "<SHIFT>"
    ↓
CallAssistant processes intent...
```

### LLM System Prompt
```
Rules:
- ONLY output ONE tag (no explanations)
- <LOGIN> → "I can't log into the app"
- <SHIFT> → "When is my shift?" "What shifts do I have?"
- <REAL>  → "Talk to someone" "Speak with agent"
- <DENY>  → Everything else (jokes, weather, etc.)
```

---

## 4. Intent Execution (What happens next)

### Scenario 1: <SHIFT> Intent
```
LLM detects: <SHIFT>
    ↓
CallAssistant routes to shift checking
    ├─ Extract caller_phone from 3CX
    ├─ Call: check_shifts_for_caller(
    │       service_name="hahs_vic3495",
    │       caller_phone="+61412345678"
    │   )
    ↓
check_shifts_handler.py::check_shifts_for_caller()
    ├─ Get admin credentials (from .env)
    ├─ Login to Ezaango via Playwright
    ├─ Scrape shift page HTML
    ├─ Parse shifts with BeautifulSoup
    ├─ Filter shifts by caller_phone
    │   (search in worker_name or phone column)
    ├─ Return: List of matching shifts
    └─ Notify coordinator (if configured)
    ↓
shift_scraper.py::parse_shifts_from_html()
    ├─ HTML parsing with BeautifulSoup
    ├─ Extract: ID, worker, client, time, status
    └─ Return: Shift[] dataclass
    ↓
notifier.py::notify_coordinator()
    ├─ Log to console
    └─ Email to coordinator (if SMTP configured)
    ↓
Return shifts to CallAssistant
```

### Scenario 2: <LOGIN> Intent
```
LLM detects: <LOGIN>
    ↓
CallAssistant routes to login assistance
    ├─ Prompt user for username/email
    ├─ Prompt user for password
    ├─ Call: run_admin_login_prompt_2fa()
    ↓
login_playwright.py::PlaywrightAutoLogin
    ├─ Initialize Playwright browser
    ├─ Navigate to Ezaango login
    ├─ Fill credentials
    ├─ Generate TOTP code (automatic)
    ├─ Submit 2FA
    └─ Return: success/failure
    ↓
TTS Response: "You've been logged in"
```

### Scenario 3: <REAL> Intent
```
LLM detects: <REAL>
    ↓
CallAssistant routes to agent transfer
    ├─ Log the interaction
    └─ Transfer call to real agent (3CX native)
```

---

## 5. Full Request-Response Cycle

```
┌─────────────────────────────────────────────────────┐
│  3CX Call Incoming                                  │
│  Phone: +61412345678                                │
│  Call ID: call_123                                  │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  POST /webhook/call-started                         │
│  app.py::call_started()                             │
│  ├─ Create CallAssistant(caller_phone)              │
│  └─ Start in thread                                 │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Voice Input Loop                                   │
│  SystemAudioWhisperClient.start()                   │
│  (Listening for phrases)                            │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  User Speaks                                        │
│  "When is my shift tomorrow?"                       │
│  (5 second silence → phrase complete)               │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Transcription                                      │
│  Whisper: "When is my shift tomorrow?"              │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  LLM Classification                                 │
│  OllamaClient.ask_llm(phrase)                       │
│  Response: "<SHIFT>"                                │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Action Execution                                   │
│  check_shifts_for_caller(                           │
│    service="hahs_vic3495",                          │
│    phone="+61412345678"                             │
│  )                                                  │
│  ├─ Login (secrets.py → .env)                       │
│  ├─ Scrape (Playwright → shift_scraper.py)          │
│  ├─ Parse (BeautifulSoup)                           │
│  ├─ Filter (by phone)                               │
│  └─ Result: [Shift{id, worker, time, status}]       │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Response Generation & TTS                          │
│  TTSClient.speak()                                  │
│  "You have 2 shifts this week: Monday 9am-5pm..."   │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Call Continues                                     │
│  (Loop back to voice input)                         │
└─────────────────────────────────────────────────────┘
```

---

## 6. Component Interaction Map

```
3CX PBX
  │
  └─→ app.py (Flask webhook listener)
       │
       ├─→ CallAssistant (main orchestrator)
       │    │
       │    ├─→ SystemAudioWhisperClient (audio→text)
       │    │    └─→ Whisper Model: base
       │    │
       │    ├─→ OllamaClient (intent classification)
       │    │    └─→ LLM Model: gemma3:1b
       │    │
       │    ├─→ check_shifts_handler.py (if <SHIFT>)
       │    │    ├─→ secrets.py (read .env)
       │    │    ├─→ login_playwright.py (Playwright browser)
       │    │    │    └─→ totp code generation
       │    │    ├─→ shift_scraper.py (BeautifulSoup HTML parse)
       │    │    └─→ notifier.py (email/log)
       │    │
       │    ├─→ run_admin_login_prompt_2fa.py (if <LOGIN>)
       │    │    └─→ Interactive login flow
       │    │
       │    └─→ TTSClient (text→speech)
       │         └─→ Play audio back on call
       │
       └─→ active_sessions dict (manage call state)

Data Flow:
.env ────→ secrets.py
              │
              └─→ check_shifts_handler.py
                   │
                   └─→ login_playwright.py
                        │
                        └─→ Ezaango website (Playwright)
                             │
                             └─→ shift_scraper.py
                                  │
                                  └─→ Shifts[] data
```

---

## 7. Data Files & Secrets

```
.env (GITIGNORED)
├─ ADMIN_USERNAME_HAHS_VIC3495=...
├─ ADMIN_PASSWORD_HAHS_VIC3495=...
└─ TOTP_SECRET_HAHS_VIC3495=2FASTEST

.sessions/ (GITIGNORED)
└─ hahs_vic3495_admin_auth.json (Playwright cookies)

.gitignore
├─ .env
├─ .sessions/
└─ .venv/
```

---

## 8. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Webhook Listener | Flask | Receive 3CX calls |
| Voice-to-Text | Whisper (OpenAI) | Transcribe audio |
| Intent Classification | Ollama + Gemma3 | Local LLM |
| Shift Checking | Playwright + BeautifulSoup | Web automation |
| 2FA | TOTP (pyotp) | Auto 2FA codes |
| Secrets Management | Python dotenv | Store credentials |
| Notifications | SMTP/Logging | Notify coordinators |
| Text-to-Speech | TTS Client | Speak responses |

---

## 9. Next Steps for Phone Number Integration

### Changes Needed:

**1. Update app.py (webhook)**
```python
@app.route('/webhook/call-started', methods=['POST'])
def call_started():
    data = request.json
    caller_phone = data.get('from')  # ← Extract phone
    call_id = data.get('call_id')
    
    assistant = CallAssistant(caller_phone=caller_phone)
```

**2. Update CallAssistant (caller context)**
```python
class CallAssistant:
    def __init__(self, caller_phone=None):
        self.caller_phone = caller_phone  # ← Store phone
        ...
    
    def on_phrase_complete(self, phrase):
        if "<SHIFT>" in response:
            # Pass caller_phone to shift checking
            await check_shifts_for_caller(
                service_name="hahs_vic3495",
                caller_phone=self.caller_phone
            )
```

**3. Update check_shifts_handler.py**
```python
async def check_shifts_for_caller(service_name, caller_phone, ...):
    # Filter shifts by phone number
    for shift in real_shifts:
        if shift.worker_phone == caller_phone or \
           shift.worker_name == caller_phone:
            # Include this shift
```

**4. Update shift_scraper.py**
```python
@dataclass
class Shift:
    id: str
    worker_name: str
    worker_phone: str  # ← NEW: Phone number
    ...
```

---

## Summary

**Call Flow:**
```
3CX Phone → Webhook → CallAssistant → Whisper → LLM → Action → TTS → Response
                         ↑____________________________________________↓
                         (Loop while call is active)
```

**Shift Checking Flow:**
```
Caller Phone + <SHIFT> Intent 
    ↓
check_shifts_for_caller(phone)
    ↓
Login to Ezaango (auto 2FA)
    ↓
Scrape shifts from page
    ↓
Filter by phone number
    ↓
Return matching shifts
    ↓
Convert to speech
```
