"""Issue #13 public engineering smoke matrix; NOT a scientific benchmark.

Preselected hand-coded cases intentionally include aliases and an out-of-basis
example. Candidate and trusted oracle share one Python process, so never use
this as an evaluator-isolation or OAIE result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from e14.e14_integrated_graph import DurableGraphBudget, audit_journal, execute_protocol, graph_oracle
from e14.e14_integrated_policy import mapped_only_policy
from e14.e14r_worker import mappings

SOURCE_WORD = (1, 2, 1, 1, 2, 2, 1)
ARTIFACT = {"kind": "edge-relative-word-v1", "word": list(SOURCE_WORD),
            "source_sha256": "0" * 64}
TRUTHS = (
    ("mapped-0", mappings(SOURCE_WORD)[0]),
    ("mapped-1", mappings(SOURCE_WORD)[1]),
    ("mapped-2", mappings(SOURCE_WORD)[2]),
    ("short-prefix", SOURCE_WORD[:-1]),
    ("short-suffix", SOURCE_WORD[1:]),
    ("out-of-basis", (1,) * 10),
)
MODES = ("active", "fixed", "receipt")


def matrix():
    rows = []
    with tempfile.TemporaryDirectory() as home:
        for mode in MODES:
            for name, truth in TRUTHS:
                journal = DurableGraphBudget(Path(home) / "smoke.sqlite", mode + ":" + name)
                oracle = lambda g, truth=truth: graph_oracle(g, truth)
                row = execute_protocol(journal, mapped_only_policy(ARTIFACT, mode), oracle)
                audit = audit_journal(row["journal"], oracle)
                outcome = row["actions"][-1]
                accepted = row["decision"] == "accept"
                correct = accepted and tuple(outcome["word"]) == truth
                rows.append({"mode": mode, "case": name, "decision": row["decision"],
                             "labels": audit["purchased"], "replay_calls": audit["auditor_oracle_calls"],
                             "nodes": audit["resource_totals"]["nodes"],
                             "edges": audit["resource_totals"]["edges"],
                             "events": audit["resource_totals"]["events"],
                             "correct_accepted": int(correct),
                             "wrong_accepted": int(accepted and not correct),
                             "abstain": int(not accepted)})
    summary = {m: {k: sum(r[k] for r in rows if r["mode"] == m)
                   for k in ("labels", "replay_calls", "nodes", "edges", "events",
                             "correct_accepted", "wrong_accepted", "abstain")}
               for m in MODES}
    report = {"version": 1, "status": "engineering_smoke_only", "worlds": len(TRUTHS),
              "arms": len(rows), "source_word": list(SOURCE_WORD),
              "scoring": "descriptive hand-chosen controls, no inferential GO/HOLD",
              "summary": summary, "rows": rows}
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return report, hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report, digest = matrix()
    result = {**report, "report_sha256": digest}
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"status": report["status"], "arms": report["arms"],
                      "summary": report["summary"], "sha256": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
