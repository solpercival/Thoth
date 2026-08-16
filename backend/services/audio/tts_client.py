"""Compatibility wrapper for the text-to-speech service.

This keeps the cleaner service namespace available while the original module stays
in place for legacy imports.
"""

from backend.tts_client.tts_client import TTSClient

__all__ = ["TTSClient"]
