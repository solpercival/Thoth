"""Compatibility wrapper for the whisper service.

This keeps the cleaner service namespace available while the original module stays
in place for legacy imports.
"""

from backend.whisper_client.system_audio_whisper_fast_client import SystemAudioWhisperFastClient

__all__ = ["SystemAudioWhisperFastClient"]
