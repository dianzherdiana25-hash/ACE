"""CLI interface for ACE Autonomous Continuity & Research State V0.2."""
from __future__ import annotations

import argparse
import json
import sys

from .coordinator import SelfDevelopmentCoordinator
from .models import AuthorType


def main() -> int:
    parser = argparse.ArgumentParser(description="ACE Autonomous Continuity & Research State V0.2")
    parser.add_argument(
        "--autonomous",
        action="store_true",
        default=True,
        help="Run next autonomous cycle driven by persistent research state (default: True)",
    )
    parser.add_argument(
        "--continuous",
        type=int,
        default=0,
        help="Run N continuous autonomous cycles in succession (e.g. --continuous 3)",
    )
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        help="Force release concurrency lock on research state",
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Trigger fail-closed recovery to verified baseline",
    )
    parser.add_argument(
        "--author-type",
        type=str,
        default="ACE_AUTONOMOUS_V02",
        choices=["ACE_AUTONOMOUS_V01", "ACE_AUTONOMOUS_V02", "GEMINI", "CODEX", "HUMAN"],
        help="Author provenance identifier",
    )
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints/self_dev", help="Checkpoint storage directory")
    parser.add_argument("--evidence-dir", type=str, default="evidence/self_dev", help="Evidence storage directory")

    args = parser.parse_args()

    coord = SelfDevelopmentCoordinator(
        checkpoint_dir=args.checkpoint_dir,
        evidence_dir=args.evidence_dir,
    )

    if args.force-unlock if hasattr(args, "force_unlock") and args.force_unlock else False:
        coord.state_manager.force_unlock()
        print("[CLI] Concurrency lock released.")
        return 0

    if args.recover:
        coord.state_manager.recover_from_crash("CLI user request")
        print("[CLI] Fail-closed recovery executed.")
        return 0

    author_enum = AuthorType(args.author_type)

    if args.continuous > 0:
        print(f"Starting ACE Autonomous Continuity: executing {args.continuous} continuous cycles...")
        results = coord.run_continuous_cycles(max_cycles=args.continuous, author_type=author_enum)
        print("\nAll continuous cycles completed.")
        for r in results:
            print(f"  Cycle {r['cycle_id']}: Decision={r['decision']}, Task={r['target_task_id']}, Evidence={r['evidence_path']}")
        return 0

    print(f"Starting ACE Autonomous Continuity Step (Author: {author_enum.value})...")
    res = coord.run_autonomous_cycle(author_type=author_enum)

    print(f"\nCycle {res['cycle_id']} completed.")
    print(f"  Decision: {res['decision']}")
    print(f"  Promoted: {res['is_promoted']}")
    print(f"  Active Head: {res['active_head_id']}")
    print(f"  Target Task: {res['target_task_id']}")
    print(f"  Holdout Score: {res['holdout_score']} (Gain: {res['gain_over_parent']:+.4f})")
    print(f"  Prior Cycle: {res['prior_cycle_id']}")
    print(f"  State Digest: {res['state_digest_after'][:16]}...")
    print(f"  Next Agenda: {res['next_agenda_priority']['strategy']} -> {res['next_agenda_priority']['priority_task_id']}")
    print(f"  Evidence: {res['evidence_path']}")
    print(f"  Governance: release_gate={res['governance']['release_gate']}, scientific_status={res['governance']['scientific_status']}, oaie_established={res['governance']['oaie_established']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
