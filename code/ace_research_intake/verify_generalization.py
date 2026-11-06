"""Fail-closed public exact-source replay. Not independent blind review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import generalization_admission as study


class EvidenceError(ValueError):
    pass


def validate(raw):
    try:
        item=json.loads(raw)
    except (ValueError,UnicodeError,TypeError) as exc:
        raise EvidenceError("invalid JSON") from exc
    if type(item) is not dict or study.canonical(item)!=raw:
        raise EvidenceError("noncanonical receipt")
    if item.get("pre_score_commit")!=study.PROTOCOL_COMMIT or item.get("base_source_sha")!=study.BASE_HEAD:
        raise EvidenceError("source/protocol mismatch")
    if (item.get("scientific_status")!="NOT_ASSESSED"
            or item.get("release_decision")!="BLOCK_RELEASE"
            or item.get("candidate_deployed") is not False
            or item.get("oaie_established") is not False
            or item.get("open_world_safe") is not False):
        raise EvidenceError("false scientific/release/safety promotion")
    calculated=study.canonical(study.experiment())
    if raw!=calculated:
        raise EvidenceError("trial, gate, score, model, or baseline differs from rerun")
    return {"status":"PASS_PUBLIC_REPLAY_ONLY","sha256":hashlib.sha256(raw).hexdigest(),
            "scientific_status":"NOT_ASSESSED","release_decision":"BLOCK_RELEASE"}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("path",type=Path)
    args=parser.parse_args(argv)
    try:
        outcome=validate(args.path.read_bytes())
    except (EvidenceError,RuntimeError,KeyError,TypeError,OSError,ValueError) as exc:
        print(json.dumps({"status":"HALT_EVIDENCE_INTEGRITY","error":str(exc)}))
        return 2
    print(json.dumps(outcome,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
