"""Canonical Odin agent implementation.

This module presents the active outbound screening assistant in the cleaner app
layout. The actual logic still lives in the legacy screening_agent module so the
refactor remains safe and incremental.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_root))

from screening_agent.screening_agent.screening_agent_v2 import ScreeningAgentV2

__all__ = ["ScreeningAgentV2"]
