"""CLI entry point for ACE Autonomous Code Agent V0.3."""
from __future__ import annotations

import argparse
import json
import sys

from .controller import AutonomousSoftwareResearcher


def main() -> int:
    parser = argparse.ArgumentParser(description="ACE Autonomous Software Researcher CLI (V0.3)")
    parser.add_argument("--autonomous", action="store_true", help="Execute autonomous research cycle")
    parser.add_argument("--max-cycles", type=int, default=1, help="Maximum cycles to execute")
    parser.add_argument("--auto-pr", action="store_true", help="Automatically generate git branch and PR on success")
    parser.add_argument("--author-type", type=str, default="ACE_AUTONOMOUS_V03", help="Provenance author tag")
    args = parser.parse_args()

    researcher = AutonomousSoftwareResearcher()

    for i in range(args.max_cycles):
        print(f"=== ACE Autonomous Software Researcher: Cycle {i+1}/{args.max_cycles} ===")
        res = researcher.execute_autonomous_cycle(auto_pr=args.auto_pr)
        print(f"Problem: {res.get('problem', {}).get('title')}")
        print(f"Hypothesis: {res.get('hypothesis', {}).get('statement')}")
        print(f"Decision: {res.get('decision')}")
        if res.get("pr_metadata"):
            print(f"PR Branch Created: {res['pr_metadata'].get('branch_name')}")
            print(f"Commit SHA: {res['pr_metadata'].get('commit_sha')}")
            if res["pr_metadata"].get("pr_url"):
                print(f"GitHub PR URL: {res['pr_metadata'].get('pr_url')}")
            if res["pr_metadata"].get("pr_number"):
                print(f"GitHub PR Number: #{res['pr_metadata'].get('pr_number')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
