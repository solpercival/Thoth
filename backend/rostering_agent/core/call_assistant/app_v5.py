"""Compatibility wrapper for the canonical Thoth app.

The active implementation now lives under backend/apps/thoth/app.py.
This legacy module remains so old imports keep working.
"""

from backend.apps.thoth.app import *  # noqa: F401,F403
