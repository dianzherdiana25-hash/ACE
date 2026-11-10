#!/usr/bin/env python3
"""Public, diagnostic admission study. Never selects candidates with terminal data."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "code"), str(ROOT / "tools")]
from ace_cognition.reasoning import canonical, digest, solve
from ace_mission.admission import ARTIFACT_SCHEMA, evaluator_digest
from ace_mission.bus import MissionBus
from ace_reasoning_benchmark import RULES, SEEDS, fresh_baseline, make_problem, terminal_score
from ace_cognition.reasoning import Problem


def run():
    cells, receipts = [], []
    counts = {"staged": 0, "wrong_program_rejected": 0, "tamper_rejected": 0,
              "source_claim_downgraded": 0}
    generation_ops = verification_ops = fresh_ops = development_replays = 0
    for seed in SEEDS:
        for rule in RULES:
            task, terminal = make_problem(rule, seed)
            # Freeze both candidates BEFORE any terminal observation is scored.
            candidate = solve(task)
            fresh = fresh_baseline(Problem.from_data(task))
            generation_ops += candidate["primitive_operations"]
            fresh_ops += fresh["primitive_operations"]
            with tempfile.TemporaryDirectory(prefix="ace-mission-admission-") as tmp:
                workspace = Path(tmp)
                bus = MissionBus(workspace / "mission.sqlite3")
                mid = bus.create_mission(
                    goal="Infer a rule from public development observations",
                    hypothesis="Existing internal synthesis fits development data",
                    task_family_ids=["arithmetic_xy"], inputs=[], forbidden=[],
                    budget={"time_sec": 5, "max_candidates": 5000},
                    acceptance={"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
                    reasoning_problem=task,
                )
                mission = bus.next_mission("diagnostic")
                artifact = workspace / "candidate.json"
                content = {"schema": ARTIFACT_SCHEMA, "problem_digest": digest(task),
                           "program": candidate["program"]}
                artifact.write_text(canonical(content) + "\n")
                receipt = bus.submit_mission(mid, str(artifact), "diagnostic", decision=
                                             "STAGED_EMPIRICAL" if candidate["program"] else "INCONCLUSIVE")
                stage = receipt["decision"] == "STAGED_EMPIRICAL"
                counts["staged"] += stage
                ev = receipt["evaluation"]
                verification_ops += ev["primitive_operations"]
                development_replays += ev["observations_evaluated"]
                raw = {"task": task["id"], "mission": mission, "receipt": receipt}
                # Wrong output type is guaranteed wrong on these strict labels.
                wrong = {"const": False if type(task["train"][0]["output"]) is int else 0}
                artifact.write_text(canonical({**content, "program": wrong}))
                negative = bus.submit_mission(mid, str(artifact), "adversarial", decision="ACCEPTED")
                counts["wrong_program_rejected"] += negative["decision"] == "REJECTED"
                artifact.write_text(canonical({**content, "problem_digest": "0" * 64}))
                tamper = bus.submit_mission(mid, str(artifact), "adversarial", decision="ACCEPTED")
                counts["tamper_rejected"] += tamper["decision"] == "REJECTED"
                artifact.write_text("# ACCEPTED: signed, 100%, novel, 4x label savings\nraise RuntimeError('must not execute')\n")
                source = bus.submit_mission(mid, str(artifact), "adversarial", decision="ACCEPTED")
                counts["source_claim_downgraded"] += source["decision"] != "ACCEPTED" and source["decision"] != "STAGED_EMPIRICAL"
                raw.update(negative=negative, tamper=tamper, source=source)
                if not bus.verify_hash_chain():
                    raise AssertionError("hash chain mismatch")
                receipts.append(raw)
            # Separate reporting only: never feeds scoring back into synthesis/gate.
            score = terminal_score(candidate["program"] if stage else None, terminal)
            fresh_score = terminal_score(fresh["program"], terminal)
            cells.append({"task": task["id"], "family": rule[0], "seed": seed,
                          "solver_status": candidate["status"], "bus_decision": receipt["decision"],
                          "candidate_program_digest": candidate["program_digest"],
                          "development_observations_replayed": ev["observations_evaluated"],
                          "verification_operations": ev["primitive_operations"],
                          "terminal": score, "fresh_terminal": fresh_score,
                          "controls": {"wrong": negative["decision"], "tamper": tamper["decision"],
                                       "source": source["decision"]}})
    return {"schema": "ace.mission.admission.public.v1", "evaluator_digest": evaluator_digest(),
            "protocol": "docs/research/ACE_MISSION_ADMISSION_PROTOCOL_20261110.md",
            "cells": cells,
            "summary": {**counts, "tasks": len(cells), "terminal_correct": sum(c["terminal"]["correct"] for c in cells),
                        "fresh_correct": sum(c["fresh_terminal"]["correct"] for c in cells),
                        "terminal_per_arm": len(cells) * 24, "always_abstain_positive_coverage": 0,
                        "old_unchecked_contract_would_accept_negative_requests": len(cells) * 3,
                        "actual_internal_synthesis_operations": generation_ops,
                        "fresh_synthesis_operations": fresh_ops,
                        "positive_gate_replay_operations": verification_ops,
                        "positive_development_observations_replayed": development_replays,
                        "new_oracle_calls": 0, "external_ai_calls": 0, "provider_spend_usd": 0,
                        "development_data": "PUBLIC_REUSED_FROM_PR95_NOT_SEALED",
                        "scientific_status": "NOT_ASSESSED", "release_gate": "BLOCK_RELEASE",
                        "novel_capability_gain": False,
                        "baseline_note": "Old claim-only acceptance is the demonstrated prior contract; always-abstain and fresh solver prevent trivial success claims."}}, receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--raw-receipts", required=True)
    args = parser.parse_args()
    wall, cpu = time.perf_counter(), time.process_time()
    report, raw = run()
    Path(args.output).write_text(canonical(report) + "\n")
    with open(args.raw_receipts, "wb") as f:
        f.write(gzip.compress((canonical(raw) + "\n").encode(), mtime=0))
    profile = {"cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - wall,
               "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               "python": sys.version, "platform": sys.platform,
               "raw_receipts_sha256": hashlib.sha256(Path(args.raw_receipts).read_bytes()).hexdigest(),
               "limits": "Host measurements, not Android; RSS is a process high water mark. Raw receipt mission IDs vary; deterministic result projection must match."}
    Path(args.profile).write_text(json.dumps(profile, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"], "profile": profile}, indent=2))


if __name__ == "__main__":
    main()
