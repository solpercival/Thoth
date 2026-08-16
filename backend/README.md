# Backend structure

This backend is intentionally split into a small set of canonical layers:

- apps/
  - runtime entry points for each product app
  - examples: thoth and odin
- services/
  - shared infrastructure and adapters
  - examples: llm, audio, notifications
- workflows/
  - orchestration for business flows
  - examples: shift cancellation and screening

## Legacy compatibility

Older directories such as rostering_agent, screening_agent, and older top-level client folders are kept temporarily for compatibility while the codebase is being migrated to the canonical layout above.

They are not the primary structure anymore.
