"""Compatibility wrapper for the email formatter.

This exposes the formatter via the cleaner service namespace while preserving the
legacy backend implementation for current scripts.
"""

from backend.rostering_agent.core.email_agent.email_formatter import format_ezaango_shift_data

__all__ = ["format_ezaango_shift_data"]
