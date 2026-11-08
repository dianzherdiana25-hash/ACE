"""Schema definitions and validation for ace.mission.v1."""
from __future__ import annotations

import datetime
from typing import Any, Dict, List


class MissionSchemaError(ValueError):
    """Raised when a mission dictionary fails ace.mission.v1 schema validation."""
    pass


REQUIRED_FIELDS = [
    "schema_version",
    "id",
    "goal",
    "hypothesis",
    "task_family_ids",
    "inputs",
    "budget",
    "acceptance",
    "forbidden",
    "deadline",
    "status",
]

ALLOWED_STATUSES = {
    "PENDING",
    "CLAIMED",
    "SUBMITTED",
    "ACCEPTED",
    "REJECTED",
    "ESCALATED",
}


def validate_mission(mission: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and return mission dictionary according to ace.mission.v1 specification."""
    if not isinstance(mission, dict):
        raise MissionSchemaError(f"Mission must be a JSON dictionary, got {type(mission).__name__}")

    for field in REQUIRED_FIELDS:
        if field not in mission:
            raise MissionSchemaError(f"Mission missing required field: '{field}'")

    if mission["schema_version"] != "ace.mission.v1":
        raise MissionSchemaError(
            f"Invalid schema_version '{mission['schema_version']}', expected 'ace.mission.v1'"
        )

    if not isinstance(mission["id"], str) or not mission["id"].strip():
        raise MissionSchemaError("Mission id must be a non-empty string")

    if not isinstance(mission["goal"], str) or not mission["goal"].strip():
        raise MissionSchemaError("Mission goal must be a non-empty string")

    if not isinstance(mission["hypothesis"], str) or not mission["hypothesis"].strip():
        raise MissionSchemaError("Mission hypothesis must be a non-empty string")

    if not isinstance(mission["task_family_ids"], list) or not mission["task_family_ids"]:
        raise MissionSchemaError("task_family_ids must be a non-empty list of family IDs")

    if not isinstance(mission["inputs"], list):
        raise MissionSchemaError("inputs must be a list of input objects (path and hash)")

    budget = mission["budget"]
    if not isinstance(budget, dict) or "time_sec" not in budget or "max_candidates" not in budget:
        raise MissionSchemaError("budget must be an object with 'time_sec' and 'max_candidates'")

    acceptance = mission["acceptance"]
    if not isinstance(acceptance, dict) or not all(k in acceptance for k in ("metric", "threshold", "comparator")):
        raise MissionSchemaError(
            "acceptance must be an object with 'metric', 'threshold', and 'comparator'"
        )

    if not isinstance(mission["forbidden"], list):
        raise MissionSchemaError("forbidden must be a list of file path patterns that agents must not touch")

    if not isinstance(mission["deadline"], str) or not mission["deadline"].strip():
        raise MissionSchemaError("deadline must be an ISO-8601 timestamp string")

    if mission["status"] not in ALLOWED_STATUSES:
        raise MissionSchemaError(
            f"Invalid status '{mission['status']}', allowed: {sorted(ALLOWED_STATUSES)}"
        )

    return mission
