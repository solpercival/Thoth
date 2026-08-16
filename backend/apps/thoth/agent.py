"""Canonical Thoth agent implementation.

This module presents the active inbound-call assistant in the cleaner app layout.
The actual implementation still lives in the legacy rostering_agent module so the
move remains incremental and safe.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_root))

from rostering_agent.core.call_assistant.call_assistant_v5 import CallAssistantV5

__all__ = ["CallAssistantV5"]
