"""CLI interface for ACE Autonomous Runtime (Fase 3)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import Autonomy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACE Durable Autonomous Runtime CLI")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enq = sub.add_parser("enqueue")
    p_enq.add_argument("goal_json", type=Path)

    p_one = sub.add_parser("run-one")
    p_one.add_argument("--goal-id", default=None)

    p_run = sub.add_parser("run")
    p_run.add_argument("--goal-id", default=None)
    p_run.add_argument("--max-iterations", type=int, default=32)

    p_rep = sub.add_parser("report")
    p_rep.add_argument("goal_id")

    sub.add_parser("status")
    sub.add_parser("capabilities")

    p_can = sub.add_parser("cancel")
    p_can.add_argument("goal_id")

    sub.add_parser("demo")

    args = parser.parse_args(argv)
    with Autonomy(args.workspace, args.source_root) as engine:
        if args.cmd == "enqueue":
            goal = json.loads(args.goal_json.read_text(encoding="utf-8"))
            gid = engine.enqueue(goal)
            print(json.dumps({"goal_id": gid}, sort_keys=True))
        elif args.cmd == "run-one":
            print(json.dumps(engine.run_one(args.goal_id), sort_keys=True))
        elif args.cmd == "run":
            print(json.dumps(engine.run_until_stopped(args.goal_id, max_iterations=args.max_iterations), sort_keys=True))
        elif args.cmd == "report":
            print(json.dumps(engine.report(args.goal_id), sort_keys=True))
        elif args.cmd == "status":
            print(json.dumps(engine.status(), sort_keys=True))
        elif args.cmd == "capabilities":
            print(json.dumps(engine.registry.list_capabilities(), sort_keys=True))
        elif args.cmd == "cancel":
            print(json.dumps(engine.cancel(args.goal_id), sort_keys=True))
        elif args.cmd == "demo":
            demo_goal = {
                "schema": "ace.goal.v1",
                "name": "autonomy_demo_cycle",
                "objective": {
                    "kind": "ace_runtime_demo_and_verify",
                    "run_engine_tests": False,
                },
            }
            gid = engine.enqueue(demo_goal)
            history = engine.run_until_stopped(gid)
            print(
                json.dumps(
                    {
                        "goal_id": gid,
                        "final_report": history[-1] if history else engine.report(gid),
                        "status": engine.status(),
                    },
                    sort_keys=True,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
