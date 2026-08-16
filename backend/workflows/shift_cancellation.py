"""Canonical workflow for shift lookup and cancellation processing.

This module re-exports the legacy Ezaango automation workflow so the project gets a
cleaner orchestration boundary without breaking existing runtime behavior.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_root))

from rostering_agent.automation.test_integrated_workflow import test_integrated_workflow

__all__ = ["test_integrated_workflow"]
