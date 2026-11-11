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
    args = parser.parse_args(argv)

    try:
        registry = load_registry(args.manifest)
        result = plan_capabilities(
            registry, available_types=args.have, goal_types=args.want,
            allowed_effects=args.allow_effect or ("none", "read"),
            max_steps=args.max_steps, max_expansions=args.max_expansions,
            max_cost_units=args.max_cost,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error": str(exc)}, ensure_ascii=False))
        return 3

    output: dict[str, Any] = {
        "status": result.status,
        "structurally_routable": result.executable,
        "execution_performed": False,
        "capability_ids": list(result.capability_ids),
        "acquired_types": sorted(result.acquired_types),
        "missing_types": sorted(result.missing_types),
        "expanded_states": result.expanded_states,
        "total_cost_units": result.total_cost_units,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if result.executable else 2


if __name__ == "__main__":
    sys.exit(main())
