"""JSON-in/JSON-out local contract adapter for ACE visual research tasks.

Usage: PYTHONPATH=code python3 -m ace_visual_bridge.cli plan|review < request.json
No image is generated, edited, uploaded or analyzed by this CLI.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .contract import Anchor, Observation, plan_edit, review_batch


def process(mode: str, request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    if request.get("schema") != "ace.ava.request.v1":
        raise ValueError("unsupported request schema")
    source = Anchor(**request["anchor"])
    plan = plan_edit(source, request.get("axis", "micro_detail"))

    if mode == "plan":
        return {
            "schema": "ace.ava.receipt.v1", "mode": mode,
            "status": "PLAN_ONLY",
            "source_asset_id": plan.source_asset_id,
            "change_axis": plan.change_axis,
            "locked_axes": sorted(plan.locked_axes),
            "native_generator_called": False,
        }

    observations = []
    for item in request.get("observations", []):
        data = dict(item)
        # Validate at the JSON boundary: frozenset("face_identity")
        # silently becomes a set of characters, so a bare string
        # here would let locked-axis drift evade detection.
        raw_axes = data.get("drifted_axes", [])
        if isinstance(raw_axes, str) or not isinstance(
                raw_axes, (list, tuple)):
            raise ValueError(
                "drifted_axes must be a list of axis names")
        data["drifted_axes"] = frozenset(raw_axes)
        observations.append(Observation(**data))
    result = review_batch(source, plan, observations, int(request.get("expected", 5)))
    return {
        "schema": "ace.ava.receipt.v1", "mode": mode,
        "status": result.status,
        "observed_original_assets": result.observed_original_assets,
        "qualified": result.qualified,
        "expected": result.expected,
        "selected_asset_id": result.selected_asset_id,
        "reviews": [asdict(review) for review in result.reviews],
        "native_generator_called": False,
        "native_quality_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACE-AVA evidence-first contract adapter")
    parser.add_argument("mode", choices=["plan", "review"])
    args = parser.parse_args(argv)
    try:
        data = json.load(sys.stdin)
        result = process(args.mode, data)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        result = {"schema": "ace.ava.receipt.v1", "status": "INVALID_REQUEST", "reason": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
