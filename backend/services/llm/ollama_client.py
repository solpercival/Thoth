"""Compatibility wrapper for the Ollama client service.

This re-exports the canonical implementation from the legacy backend package so
new code can use the cleaner service path without breaking existing imports.
"""

from backend.ollama_client.llm_client import OllamaClient

__all__ = ["OllamaClient"]
