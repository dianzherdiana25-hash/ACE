"""Public reproducibility verifier for a versioned ACE runtime demo.

Checks structural invariants and exact bytes on a separately generated sample.
No candidate execution, independent scientific testing or deployment is implied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1_SHA = "475d35bab2d319650de5504e472b76f05d65458d"


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify(candidate: Path, expected: Path | None = None) -> dict:
    historical = (ROOT / "evidence/runtime/v1-demo.json").read_bytes()
    if _git_blob_sha(historical) != V1_SHA:
        raise ValueError("historical v1 receipt bytes changed")
    v1 = json.loads(historical)
    raw = candidate.read_bytes()
    if not raw or len(raw) > 100_000:
        raise ValueError("unbounded or empty demo receipt")
    demo = json.loads(raw)
    if type(demo) is not dict or set(demo) != {"task_ids", "outcomes", "evaluation", "status"}:
        raise ValueError("unexpected demo schema")
    names = ("source_equal", "inherited_equal", "changed_ends")
    task_ids = demo["task_ids"]
    if type(task_ids) is not dict or set(task_ids) != set(names):
        raise ValueError("expected exactly three public tasks")
    if task_ids != v1["task_ids"]:
        raise ValueError("public task identities drifted from historical v1")
    if len(set(task_ids.values())) != 3:
        raise ValueError("task identities must be unique")
    rows = demo["outcomes"]
    if type(rows) is not list or [r.get("name") for r in rows] != list(names):
        raise ValueError("task completion order changed")
    by_name = dict(zip(names, rows))
    phases = ("LEARNED_STAGED", "REUSE_VALIDATED", "LEARNED_STAGED")
    for name, phase in zip(names, phases):
        result = by_name[name]
        if (result.get("task_id") != task_ids[name]
                or result.get("phase") != phase
                or result.get("status") != "completed"
                or result.get("staged") is not True
                or result.get("train_correct") != result.get("train_labels")
                or result.get("validation_correct") != result.get("validation_labels")):
            raise ValueError("stage or task outcome invariant failed: " + name)
    if by_name[names[0]]["model_id"] != by_name[names[1]]["model_id"]:
        raise ValueError("validated model should be reused")
    if by_name[names[0]]["model_id"] == by_name[names[2]]["model_id"]:
        raise ValueError("changed family must not reuse source model")
    if [r.get("learning_called") for r in rows] != [True, False, True]:
        raise ValueError("unexpected learner/reuse decisions")
    evaluations = demo["evaluation"]
    if type(evaluations) is not dict or set(evaluations) != set(names):
        raise ValueError("missing terminal evaluation")
    for name in names:
        report = evaluations[name]
        if (report.get("task_id") != task_ids[name]
                or report.get("model_id") != by_name[name]["model_id"]
                or report.get("total") != 128
                or report.get("correct") != 128
                or report.get("candidate_deployed") is not False
                or report.get("scientific_decision") != "NOT_ASSESSED"):
            raise ValueError("public terminal/report invariant failed: " + name)
    status = demo["status"]
    if (status.get("schema") != "ace.runtime.v1"
            or status.get("capabilities") != 2
            or status.get("completed") != 3
            or status.get("pending") != 0
            or status.get("failed") != 0
            or status.get("evaluations") != 3
            or status.get("events") != 9
            or status.get("scientific_decision") != "NOT_ASSESSED"
            or status.get("oaie_established") is not False
            or status.get("candidate_deployed") is not False):
        raise ValueError("runtime state/scientific boundary invariant failed")
    if (type(status.get("implementation")) is not str
            or len(status["implementation"]) != 64
            or status["implementation"] == v1["status"]["implementation"]):
        raise ValueError("runtime implementation mismatch or not versioned")
    if expected is not None and raw != expected.read_bytes():
        raise ValueError("v2 fixture mismatch: exact public replay changed")
    return {
        "status": "PASS_PUBLIC_ENGINEERING_REPLAY_NOT_SCIENTIFIC_GO",
        "v1_historical_blob": V1_SHA,
        "v2_candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "v2_candidate_bytes": len(raw),
        "candidate_deployed": False,
        "scientific_status": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--check-replay-only", action="store_true")
    args = parser.parse_args()
    if args.check_replay_only and args.expected:
        parser.error("--check-replay-only and --expected are exclusive")
    try:
        print(json.dumps(verify(args.candidate, args.expected), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(1, f"FAIL_RUNTIME_V2: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
