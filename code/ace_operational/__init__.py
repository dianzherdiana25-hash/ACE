"""ACE Unified Operational Package (Edition 4).

Connects Indonesian conversational intake, durable fenced task store,
autonomous coding and verification loop, offline/local/host model backends,
gap discovery and capability frontier, AI worker orchestration over MissionBus,
skill learning and anti-stagnation pivot ladder, and the localhost Anime Web UI.
"""
from __future__ import annotations

SCHEMA_TASK = "ace.task.v1"
SCHEMA_PROBLEM_IR = "ace.problem_ir.v1"
SCHEMA_WORK_ORDER = "ace.work_order.v1"
SCHEMA_WORK_RESULT = "ace.work_result.v1"
SCHEMA_LEARNING_EXPERIENCE = "ace.learning_experience.v1"
SCHEMA_SKILL = "ace.skill.v1"
SCHEMA_RECEIPT = "ace.receipt.v1"
SCHEMA_ACTIVITY = "ace.activity.v1"
SCHEMA_GAP = "ace.gap.v1"
SCHEMA_FRONTIER = "ace.frontier.v1"
SCHEMA_VERSION_MANIFEST = "ace.version_manifest.v1"

RELEASE_VERSION = "4.0.0-oaie"

__all__ = [
    "SCHEMA_TASK",
    "SCHEMA_PROBLEM_IR",
    "SCHEMA_WORK_ORDER",
    "SCHEMA_WORK_RESULT",
    "SCHEMA_LEARNING_EXPERIENCE",
    "SCHEMA_SKILL",
    "SCHEMA_RECEIPT",
    "SCHEMA_ACTIVITY",
    "SCHEMA_GAP",
    "SCHEMA_FRONTIER",
    "SCHEMA_VERSION_MANIFEST",
    "RELEASE_VERSION",
]
