"""Read-only CLI for domain-neutral ACE capability contracts.

Example:
    PYTHONPATH=code python -m ace_operational.open_world_cli \
        --manifest examples/open_world_capabilities.json \
        --have dataset:raw --want report:verified

This prints a structural plan, not an executed task.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .open_world_planner import Capability, CapabilityRegistry, EFFECTS, plan_capabilities


def load_registry(path: Path) -> CapabilityRegistry:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("capabilities"), list):
        raise ValueError("manifest must contain a capabilities array")
    registry = CapabilityRegistry()
    required = {"capability_id", "provider", "consumes", "produces"}
    allowed = required | {"evidence_ref", "status", "effect", "cost_units"}
    for index, item in enumerate(document["capabilities"]):
        if not isinstance(item, dict):
            raise ValueError(f"capability #{index} must be an object")
        if required - item.keys() or item.keys() - allowed:
            raise ValueError(f"capability #{index} has missing or unexpected fields")
        registry.register(Capability(**item))
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ACE open-world typed planning (READ-ONLY, no execution)"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--have", action="append", required=True, help="Input type (repeat)")
    parser.add_argument("--want", action="append", required=True, help="Desired output type (repeat)")
    parser.add_argument("--allow-effect", action="append", choices=sorted(EFFECTS))
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--max-expansions", type=int, default=1000)
    parser.add_argument("--max-cost", type=int, default=100)
    parser.add_argument("--workspace", type=Path, help="Existing ACE workspace for durable planning")
    parser.add_argument("--task-id", help="Existing OperationalStore task for durable planning")
    parser.add_argument("--stage-review", action="store_true", help="Queue a review-only MissionBus mission")
    parser.add_argument(
        "--authorize-local-queue", action="store_true",
        help="Explicitly authorize staging local review mission (never tool execution)"
    )
    args = parser.parse_args(argv)

    output: dict[str, Any]
    try:
        if bool(args.workspace) != bool(args.task_id):
            raise ValueError("--workspace and --task-id must be supplied together")
        if args.stage_review and not args.authorize_local_queue:
            raise ValueError("--stage-review requires --authorize-local-queue")
        if args.stage_review and not args.workspace:
            raise ValueError("--stage-review requires persistent workspace and task")
        if args.authorize_local_queue and not args.stage_review:
            raise ValueError("--authorize-local-queue only applies to --stage-review")

        registry = load_registry(args.manifest)
        options = {
            "available_types": args.have,
            "goal_types": args.want,
            "allowed_effects": args.allow_effect or ("none", "read"),
            "max_steps": args.max_steps,
            "max_expansions": args.max_expansions,
            "max_cost_units": args.max_cost,
        }
        if args.workspace:
            from ace_mission.bus import MissionBus
            from .store import OperationalStore
            from .open_world_task_bridge import OpenWorldTaskBridge

            with OperationalStore(args.workspace) as store:
                bridge = OpenWorldTaskBridge(store)
                recorded = bridge.plan_and_record(args.task_id, registry, **options)
                record_result = recorded["result"]
                output = {
                    "status": record_result["status"],
                    "structurally_routable": record_result["status"] == "READY",
                    "execution_performed": False,
                    "capability_ids": record_result["capability_ids"],
                    "acquired_types": record_result["acquired_types"],
                    "missing_types": record_result["missing_types"],
                    "expanded_states": record_result["expanded_states"],
                    "total_cost_units": record_result["total_cost_units"],
                    "plan_key": recorded["plan_key"],
                    "record_sha256": recorded["record_sha256"],
                    "scientific_status": "NOT_ASSESSED",
                    "release_gate": "BLOCK_RELEASE",
                }
                if args.stage_review:
                    bus = MissionBus(store.workspace / "mission_bus.sqlite3")
                    output["review_mission"] = bridge.stage_review_mission(
                        recorded["plan_key"], bus, authorize_local_queue=True
                    )
        else:
            result = plan_capabilities(registry, **options)
            output = {
                "status": result.status,
                "structurally_routable": result.executable,
                "execution_performed": False,
                "capability_ids": list(result.capability_ids),
                "acquired_types": sorted(result.acquired_types),
                "missing_types": sorted(result.missing_types),
                "expanded_states": result.expanded_states,
                "total_cost_units": result.total_cost_units,
            }
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error": str(exc)}, ensure_ascii=False))
        return 3

    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if output["structurally_routable"] else 2


if __name__ == "__main__":
    sys.exit(main())
