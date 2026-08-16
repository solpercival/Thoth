"""Canonical workflow for outbound screening orchestration.

This module exposes the legacy screening session flow through the new workflow
layer while preserving compatibility.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_root))

from screening_agent.screening_agent.app_v2 import start_screening

__all__ = ["start_screening"]
