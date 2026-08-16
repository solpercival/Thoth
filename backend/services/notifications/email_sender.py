"""Compatibility wrapper for email notifications.

This exposes the email sender via the cleaner service namespace while preserving the
legacy backend implementation for current scripts.
"""

from backend.rostering_agent.core.email_agent.email_sender import send_notify_email

__all__ = ["send_notify_email"]
