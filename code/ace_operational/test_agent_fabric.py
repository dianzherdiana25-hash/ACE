"""Development-only controls for local model -> coding-agent task delegation.

Test doubles never contact Ollama, Codex, Antigravity or a paid provider.
A passing test demonstrates parsing/authorization, NOT coding capability.
"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ace_operational.agent_fabric import (
    AgentDirector, CLIWorker, OllamaLocalPlanner, WorkOrder, WorkPlan,
    validate_work_plan, require_isolated_worktree,
)
