"""Review-only MissionBus adapter; leaves frozen evaluator implementation untouched.

Do not modify ace_mission/bus.py for this pilot: its bytes are included in
the published evaluator_digest() identity. This adapter uses the EXISTING
MissionBus transaction primitives with a deterministic review mission ID.

No provider calls, tool execution or code mutations are performed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json

from ace_mission.bus import MissionBus
from ace_mission.schema import validate_mission


def queue_structural_review(
    bus: MissionBus, *, plan_key: str, record_sha256: str
) -> str:
    """Idempotently queue one plan review; never queue candidate execution."""
    if not isinstance(plan_key, str) or not plan_key.startswith("ow_"):
        raise ValueError("Invalid open-world plan key")
    if (not isinstance(record_sha256, str) or len(record_sha256) != 64
            or any(c not in "0123456789abcdef" for c in record_sha256)):
        raise ValueError("Invalid plan snapshot digest")
    # Deterministic identity is scoped to this adapter's review-only lane.
    mission_id = "mission_" + hashlib.sha256(
        ("ace.open_world.review.v1:" + plan_key).encode("utf-8")
    ).hexdigest()[:24]
    now = datetime.now(timezone.utc)
    doc = {
        "schema_version": "ace.mission.v1",
        "id": mission_id,
        "goal": f"Review ACE open-world plan {plan_key}; do NOT execute selected tools",
        "hypothesis": (
            f"Plan snapshot {record_sha256} may be structurally routable; "
            "independent execution and evidence are NOT assessed"
        ),
        "task_family_ids": ["open_world_structural_review"],
        "inputs": [],
        "budget": {"time_sec": 120, "max_candidates": 1},
        "acceptance": {
            "metric": "contract_review_only", "threshold": 1, "comparator": ">="
        },
        "forbidden": [".git/", ".github/workflows/", "main"],
        "deadline": (now + timedelta(hours=1)).isoformat(),
        "status": "PENDING",
        "open_world_plan_key": plan_key,
        "open_world_snapshot_sha256": record_sha256,
    }
    validate_mission(doc)

    # Compare immutable contract fields only: deadline and claim status are
    # expected to change between retries and claims.
    immutable_keys = (
        "schema_version", "id", "goal", "hypothesis", "task_family_ids",
        "inputs", "budget", "acceptance", "forbidden",
        "open_world_plan_key", "open_world_snapshot_sha256",
    )
    with bus._get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        found = con.execute(
            "SELECT data_json FROM missions WHERE id = ?", (mission_id,)
        ).fetchone()
        if found is not None:
            prior = json.loads(found[0])
            if any(prior.get(key) != doc.get(key) for key in immutable_keys):
                raise ValueError("Review mission key reused with changed contract")
            return mission_id
        con.execute(
            "INSERT INTO missions (id,goal,hypothesis,data_json,status,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (mission_id, doc["goal"], doc["hypothesis"], json.dumps(doc),
             "PENDING", now.isoformat()),
        )
        bus._append_hash_chain(
            con, "MISSION_CREATED",
            {"mission_id": mission_id, "goal": doc["goal"], "hypothesis": doc["hypothesis"]},
        )
        con.commit()
    return mission_id
