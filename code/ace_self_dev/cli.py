"""CLI interface for ACE Autonomous Self-Development Loop V0.1."""
from __future__ import annotations

import argparse
import json
import sys

from .coordinator import SelfDevelopmentCoordinator
from .models import AuthorType


def main() -> int:
    parser = argparse.ArgumentParser(description="ACE Autonomous Self-Development Loop V0.1")
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number to run (default: 1)")
    parser.add_argument("--task-seed", type=int, default=42, help="Seed for confirmation task suite generation (default: 42)")
    parser.add_argument("--mutation-ordinal", type=int, default=1, help="Mutation rule ordinal (default: 1)")
    parser.add_argument(
        "--author-type",
        type=str,
        default="ACE_AUTONOMOUS_V01",
        choices=["ACE_AUTONOMOUS_V01", "GEMINI", "CODEX", "HUMAN"],
        help="Author provenance identifier",
    )
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints/self_dev", help="Checkpoint storage directory")
    parser.add_argument("--evidence-dir", type=str, default="evidence/self_dev", help="Evidence storage directory")

    args = parser.parse_args()

    author_enum = AuthorType(args.author_type)
    coord = SelfDevelopmentCoordinator(
        checkpoint_dir=args.checkpoint_dir,
        evidence_dir=args.evidence_dir,
    )

    print(f"Starting ACE Autonomous Self-Development Loop Cycle {args.cycle} (Author: {author_enum.value})...")
    res = coord.run_cycle(
        cycle_id=args.cycle,
        task_seed=args.task_seed,
        mutation_ordinal=args.mutation_ordinal,
        author_type=author_enum,
    )

    print(f"Cycle {args.cycle} completed.")
    print(f"  Decision: {res['decision']}")
    print(f"  Promoted: {res['is_promoted']}")
    print(f"  Active Head: {res['active_head_id']}")
    print(f"  Evidence: {res['evidence_path']}")
    print(f"  Governance: release_gate={res['governance']['release_gate']}, scientific_status={res['governance']['scientific_status']}, oaie_established={res['governance']['oaie_established']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
