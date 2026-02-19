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
├── backend/
│   ├── odin/               Odin screening agent
│   ├── thoth/              Thoth call assistant + Ezaango automation
│   ├── whisper_client/     Speech-to-text (shared)
│   ├── tts_client/         Text-to-speech (shared)
│   └── ollama_client/      LLM client (shared)
├── frontend_qt/            PyQt6 desktop GUIs
├── frontend/               Electron/React frontend (alternative)
├── install_deps.bat        Dependency installer
├── ARCHITECTURE.md         Detailed system architecture docs
└── .env                    Secrets and configuration (gitignored)
```

## Logs

Call logs are saved automatically after each call:
- **Odin:** `backend/odin/screening_agent/logs/`
- **Thoth:** `backend/thoth/core/call_assistant/logs/`

Both GUIs have an "Open Logs" button to view them in File Explorer.

## Note

We are using the frontend_qt not frontend
