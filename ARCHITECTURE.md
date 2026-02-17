# Thoth - System Architecture

> High-level documentation for developers to understand the overall system design.

## Table of Contents

- [Project Structure](#project-structure)
- [System Overview](#system-overview)
- [LLM-Driven State Machine Pattern](#llm-driven-state-machine-pattern)
- [Odin - Outbound Screening Agent](#odin---outbound-screening-agent)
- [Thoth - Inbound Call Assistant](#thoth---inbound-call-assistant)
- [Shared Clients](#shared-clients)
- [3CX Integration](#3cx-integration)
- [Frontend Architecture](#frontend-architecture)
- [Data Flow Diagrams](#data-flow-diagrams)

---

## Project Structure

```
Thoth/
├── backend/                    # All Python server-side logic
│   ├── odin/                   # Odin: outbound screening agent
│   │   └── screening_agent/
│   │       ├── app_v2.py               # Flask API server
│   │       ├── screening_agent_v2.py   # LLM state machine
│   │       ├── call_3cx_client.py      # 3CX call control
│   │       ├── questions.txt           # Interview questions
│   │       └── logs/                   # Call logs (gitignored)
│   ├── thoth/                  # Thoth: inbound call assistant
│   │   ├── core/
│   │   │   ├── call_assistant/
│   │   │   │   ├── app_v5.py               # Flask API + webhook server
│   │   │   │   ├── call_assistant_v5.py     # LLM state machine
│   │   │   │   ├── call_3cx_client.py       # 3CX call control
│   │   │   │   └── logs/                    # Call logs (gitignored)
│   │   │   └── email_agent/            # Email notification system
│   │   └── automation/                 # Playwright browser automation (Ezaango)
│   ├── whisper_client/         # Shared speech-to-text clients
│   ├── tts_client/             # Shared text-to-speech client
│   └── ollama_client/          # Shared local LLM client (Ollama)
├── frontend_qt/                # PyQt6 desktop GUIs
│   ├── odin/                   # Odin control panel
│   └── thoth/                  # Thoth control panel
├── frontend/                   # Electron/React web frontend (alternative UI)
└── misc/                       # Utilities, OTP generator, listener tests
```

---

## System Overview

The project contains two independent voice agents that share a common architecture:

| | **Odin** | **Thoth** |
|---|---|---|
| **Purpose** | Outbound screening interviews | Inbound shift cancellation assistant |
| **Call direction** | Agent calls out to candidates | Staff call in to the agent |
| **Trigger** | Frontend queues phone numbers | 3CX webhook fires on incoming call |
| **Backend port** | `localhost:5000` | `localhost:5000` |

Both agents follow the same core pattern:
1. A **Flask API** manages call sessions
2. An **LLM-driven state machine** handles the conversation
3. **Shared clients** provide STT, TTS, and LLM capabilities
4. Audio is routed through a **virtual audio cable** (VB-Audio CABLE) to bridge the agent and the phone call via 3CX

---

## LLM-Driven State Machine Pattern

Both agents use the same architectural pattern: a **2-state machine where the LLM controls transitions via output tags**.

### How It Works

1. The user speaks, and the **Whisper client** transcribes speech to text.
2. The transcribed text is passed to the **LLM** along with a dynamic system prompt that includes:
   - The current state and its instructions
   - The full chat history (last 10 messages)
   - Any relevant context (available shifts, current question, etc.)
3. The LLM responds with **natural language + optional XML-style tags**.
4. The response is parsed: tags are extracted to determine actions, and the remaining text is spoken via TTS.

### Tag-Based Transitions

Instead of hardcoded rules, the LLM decides when to transition between states by including special tags in its response:

```
LLM Response: "Let me look up your shifts for tomorrow. <FETCH>tomorrow"
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^
                Text (spoken via TTS)                    Tag (triggers action)
```

Tags are stripped from the spoken text, so the caller only hears natural speech. The system parses tags to execute actions like fetching data, submitting forms, or ending the call.

### Why This Pattern?

- **Minimal states**: Only 2 states per agent instead of 5-7, reducing complexity.
- **Flexible conversation flow**: The LLM handles follow-up questions, clarifications, and edge cases without explicit code paths.
- **Single point of control**: All behavior is governed by the system prompt, making it easy to tweak without code changes.
- **Context-aware**: Chat history gives the LLM full conversational context across turns.

---

## Odin - Outbound Screening Agent

### States and Tags

```
AVAILABILITY ──[<INTER>]──> INTERVIEW ──[<NEXT>]──> (next question)
     │                           │                        │
     │                           └────[loop for clarity]──┘
     │
     └──[<NO> date]──> END CALL
```

| State | Purpose |
|---|---|
| `AVAILABILITY` | Confirms the candidate can talk now |
| `INTERVIEW` | Asks questions from `questions.txt`, LLM evaluates answer adequacy |

| Tag | Meaning | Action |
|---|---|---|
| `<INTER>` | User is available | Transition to INTERVIEW, ask first question |
| `<NO> date/time` | User not available | Store callback time, end call |
| `<NEXT> answer` | Answer is adequate | Store answer, advance to next question |
| `<END>` | User wants to end | Terminate call |

### Silence Detection

- **25 seconds** of silence: plays "Are you still there?" (once)
- **45 seconds** of silence: plays goodbye and terminates

### Flask API (`app_v2.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /start` | POST | Start a screening session for a phone number |
| `POST /stop` | POST | Stop an active session |
| `GET /status` | GET | List all active sessions |
| `GET /call-result/<id>` | GET | Retrieve result of a completed call |
| `GET /health` | GET | Health check |

### Session Lifecycle

1. Frontend POSTs to `/start` with a phone number
2. Backend calls `make_call()` via 3CX API, then polls `poll_call_answered()`
3. If unanswered within 60s, result is `no_answer`
4. If answered, `ScreeningAgentV2` is created and runs in a background thread
5. On completion, `drop_call()` hangs up and result is stored for the frontend

---

## Thoth - Inbound Call Assistant

### States and Tags

```
GATHERING_INFO ──[<FETCH>]──> (fetch shifts) ──> CONFIRMING_DETAILS
      ▲                                                  │
      └──────────────[<DONE>]────────────────────────────┘
```

| State | Purpose |
|---|---|
| `GATHERING_INFO` | Understand intent (cancellation/query) and collect date info |
| `CONFIRMING_DETAILS` | Present shifts, confirm selection, collect cancellation reason |

| Tag | Meaning | Action |
|---|---|---|
| `<FETCH>date_query` | LLM has enough info to look up shifts | Runs Ezaango automation workflow |
| `<SUBMIT>shift_id\|reason>` | LLM has shift + reason | Sends cancellation notification email |
| `<DONE>` | Current task complete | Reset to GATHERING_INFO (supports multi-request calls) |
| `<END>` | Caller is done | Ends call via 3CX |

Tag priority (when multiple appear): `END > SUBMIT > FETCH > DONE`

### Flask API (`app_v5.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /webhook/call-started` | GET/POST | 3CX webhook: incoming call detected |
| `GET /webhook/call-ended` | GET/POST | 3CX webhook: caller hung up |
| `GET /status` | GET | List active sessions |
| `GET /health` | GET | Health check |

### Automation Workflow

When `<FETCH>` is triggered, the system runs a Playwright browser automation pipeline against the **Ezaango** rostering web app:

```
1. Login           → Authenticates with username/password + TOTP 2FA
2. Staff Lookup    → Searches Ezaango by caller's phone number → name, ID, email
3. Date Reasoning  → Sends transcript to LLM → extracts start/end date range
4. Shift Search    → Navigates Ezaango shift search, filters by date range
5. Return          → Returns { staff, dates, filtered_shifts } to the state machine
```

On `<SUBMIT>`, the system formats the shift data and sends a notification email to the rostering team (rather than making a direct API call to Ezaango).

### Email Notification System

Lives in `backend/thoth/core/email_agent/`. When the call assistant emits a `<SUBMIT>` tag, the system sends a cancellation notification email to the rostering team.

**How it works:**

1. `email_formatter.py` — `format_ezaango_shift_data()` takes the shift data dict (staff name/ID/email, shift client/date/time) and the cancellation reason, and builds a plain-text email body.
2. `email_sender.py` — `send_notify_email()` sends the formatted email from the sender to the collector address using Python's `smtplib`.

**Gmail App Password authentication:**

The system uses Gmail's SMTP server with an **App Password** (not the account's regular password). App Passwords are 16-character codes generated from Google Account settings that bypass 2FA for SMTP access.

- Connects to `smtp.gmail.com` on port `465` (direct SSL via `SMTP_SSL`)
- Authenticates with the sender email + app password
- Also supports port `587` (STARTTLS) for non-Gmail providers like Outlook

**Environment variables:**

| Variable | Purpose |
|---|---|
| `SENDER_EMAIL` | Gmail address used to send emails |
| `EMAIL_APP_PASSWORD` | Gmail App Password (spaces are auto-stripped) |
| `COLLECTOR_EMAIL` | Recipient address (the rostering team) |
| `SMTP_SERVER` | SMTP host (default: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default: `465`) |

---

## Shared Clients

All clients live under `backend/` and are shared by both agents.

### Whisper Client (Speech-to-Text)

Two variants exist:

| Client | Used By | Engine | Speed |
|---|---|---|---|
| `SystemAudioWhisperClient` | Thoth | OpenAI Whisper | Standard |
| `SystemAudioWhisperFastClient` | Odin | Faster Whisper (CTranslate2) | 4-5x faster |

**How they work:**
- Captures **system/desktop audio** (not microphone) using WASAPI loopback on Windows
- Two threads: audio capture loop + transcription loop
- Accumulates audio chunks until silence exceeds `phrase_timeout`, then transcribes
- Fires `on_phrase_complete(text)` callback with the transcribed text
- Supports `pause()`/`resume()` to avoid transcribing the agent's own TTS output

### TTS Client (Text-to-Speech)

**Engine:** Microsoft Edge TTS (`edge-tts` library)
**Default voice:** `en-AU-NatashaNeural` (Australian female)

**Pipeline:**
1. Edge TTS generates audio → saves as temporary MP3
2. Converts MP3 to WAV via `pydub`
3. Plays WAV through PyAudio to a named output device (default: `"CABLE Input"`)

The virtual audio cable routes the agent's voice into 3CX, which transmits it to the caller.

### Ollama Client (LLM)

**Engine:** Locally running Ollama instance
**Default model:** `qwen3:8b` (configurable via `LLM_MODEL` env var)

- Maintains persistent conversation history across calls
- `set_system_prompt()` dynamically replaces the system message before each call (this is how state/context is injected)
- Thinking mode enabled by default (supports reasoning models)

---

## 3CX Integration

Both agents interact with the **3CX Call Control REST API** via `call_3cx_client.py`. Authentication uses OAuth2 client credentials.

| Function | Purpose |
|---|---|
| `make_call()` | Initiate outbound call (Odin) |
| `poll_call_answered()` | Wait for remote party to pick up (Odin) |
| `is_call_active()` | Check if caller is still connected (Thoth) |
| `close_all_calls_for_extension()` | Hang up all calls on an extension (Thoth) |
| `drop_call()` | End a specific call participant (Odin) |

**Key difference:**
- **Odin** initiates calls (`make_call` → `poll_call_answered`) and manages cleanup
- **Thoth** is triggered by 3CX webhooks and only monitors/ends calls

### Audio Routing

```
Caller's Phone ←→ 3CX PBX ←→ VB-Audio Virtual Cable ←→ Agent
                                    │                       │
                              CABLE Output            CABLE Input
                              (Whisper captures)      (TTS plays to)
```

---

## Frontend Architecture

Both frontends are **PyQt6 desktop apps** that manage their respective Flask backends as subprocesses.

### Common Pattern

1. User clicks "Start" → frontend spawns `app_v*.py` using the `.venv` Python binary
2. Frontend polls `GET /health` every 500ms until the backend responds (15s timeout)
3. Once healthy, the UI switches to "Stop" mode
4. User clicks "Stop" → frontend terminates the subprocess

### Odin Frontend

Additional features beyond Start/Stop:
- **Phone List** — A call queue with add/remove/reorder. Persisted to `phone_numbers_in_queue.txt`
- **Auto-Dial** — Works through the queue automatically with configurable delay between calls
- **Failed Calls List** — Tracks unanswered/failed calls with retry functionality
- **Open Logs** — Opens the log folder in File Explorer

### Thoth Frontend

Additional features beyond Start/Stop:
- **Auto-Start** — Schedule automatic backend start/stop at configured times (e.g., 5:30 PM to 8:30 AM for after-hours operation)
- **Open Logs** — Opens the log folder in File Explorer

---

## Data Flow Diagrams

### Odin (Outbound Screening)

```
Frontend (PyQt6)
    │ POST /start {phone}
    ▼
Flask app_v2.py
    │ make_call() + poll_call_answered()
    ▼
3CX PBX ──────────────────────► Candidate's Phone
    │ (call answered)
    ▼
ScreeningAgentV2
    │ TTSClient    → CABLE Input  → 3CX    (agent speaks)
    │ 3CX          → CABLE Output → Whisper (candidate speaks)
    │ OllamaClient (LLM processes speech, emits tags)
    │ <INTER> / <NEXT> / <NO> / <END>
    ▼
Log file + call result
    │ GET /call-result/<id>
    ▼
Frontend (updates failed list or moves to next call)
```

### Thoth (Inbound Call Assistant)

```
Staff calls in
    ▼
3CX PBX
    │ GET /webhook/call-started?from={phone}
    ▼
Flask app_v5.py
    ▼
CallAssistantV5
    │ TTSClient    → CABLE Input  → 3CX    (agent speaks)
    │ 3CX          → CABLE Output → Whisper (staff speaks)
    │ OllamaClient (LLM processes speech, emits tags)
    │
    │ <FETCH>date
    │   └─► Playwright automation → Ezaango
    │       ├── Login (2FA)
    │       ├── Staff lookup (by phone)
    │       ├── Date reasoning (LLM)
    │       └── Shift search → return shifts
    │
    │ <SUBMIT>id|reason
    │   └─► Email notification → rostering team
    │
    │ <DONE> → reset state (handle another request)
    │ <END>  → close_all_calls_for_extension()
    ▼
Log file
```
