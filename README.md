# Thoth

AI-powered voice agents for Help at Hand Support (HAHS). The system handles both outbound screening calls and inbound shift management calls using LLM-driven conversation.

## What's In This Project

- **Odin** — Outbound screening agent. Calls candidates from a queue and conducts scripted interviews.
- **Thoth** — Inbound call assistant. Answers staff calls, looks up their shifts in Ezaango, and processes cancellation requests.

Both agents use the same core architecture: a 2-state LLM-driven state machine with speech-to-text (Whisper), text-to-speech (Edge TTS), and a local LLM (Ollama).

## Documentation

- **[Google Docs — Installation & Setup Guide](https://docs.google.com/document/d/1ZHizF-zi_VYQaF6xYtD69Fme7T0VE_b6wjua05cOt6Q/edit?tab=t.c4gil4nwtuw7)** — Full installation instructions, configuration, and setup walkthrough.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Detailed technical breakdown of the system architecture, state machines, shared clients, and data flow.

## Project Structure

```
Thoth/
├── backend/                # Python server logic
│   ├── apps/               # Runtime entry points (Thoth & Odin)
│   ├── services/           # Shared infrastructure (LLM, audio, notifications)
│   ├── workflows/          # Business orchestration
│   ├── ollama_client/      # (legacy) LLM client
│   ├── whisper_client/     # (legacy) Speech-to-text
│   ├── tts_client/         # (legacy) Text-to-speech
│   └── requirements.txt    # Python dependencies
├── frontend_qt/            # PyQt6 desktop GUIs
├── scripts/                # Startup and service scripts
├── ARCHITECTURE.md         # Detailed technical breakdown
├── README.md               # This file
└── .env                    # Secrets and configuration (gitignored)
```

## Logs

Call logs are saved automatically after each call in:
- **Odin:** `backend/rostering_agent/screening_agent/logs/`
- **Thoth:** `backend/rostering_agent/core/call_assistant/logs/`

Both GUIs have an "Open Logs" button to view them in File Explorer.

## Note

We are using the frontend_qt not frontend
