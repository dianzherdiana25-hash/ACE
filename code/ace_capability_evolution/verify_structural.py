"""Fail-closed canonical full replay: no semantic or release promotion."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import structural


class IntegrityError(ValueError):
    pass


def verify_bytes(raw,r1,model):
    try:
        report=json.loads(raw)
    except (ValueError,UnicodeError,TypeError) as exc:
        raise IntegrityError("invalid evidence encoding") from exc
    if type(report) is not dict or structural.canonical(report)!=raw:
        raise IntegrityError("noncanonical evidence")
    if report.get("protocol_commit")!=structural.PRESCORE_COMMIT or report.get("source_heads")!={
          "R1":structural.R1_HEAD,"S2":structural.S2_HEAD}:
        raise IntegrityError("provenance mismatch")
    if report.get("scientific_decision")!="NOT_ASSESSED" or report.get("release_decision")!="BLOCK_RELEASE":
        raise IntegrityError("untrusted scientific or release promotion")
    if report.get("candidate_deployed") is not False or report.get("oaie_established") is not False:
        raise IntegrityError("unsafe deployment or OAIE claim")
    if report.get("unconditional_open_world_safety") is not False:
        raise IntegrityError("unsupported semantic safety")
    reference=structural.evaluate(r1,model)
    if structural.canonical(reference)!=raw:
        raise IntegrityError("score, model, split, stage, type or control differs from rerun")
    return {"status":"PASS_PUBLIC_EXACT_REPLAY_NOT_SCIENTIFIC_GO",
            "report_sha256":hashlib.sha256(raw).hexdigest(),
            "models_staged":sum(row["staged"] for row in report["tasks"]),
            "release_decision":"BLOCK_RELEASE","scientific_decision":"NOT_ASSESSED"}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("report",type=Path)
    args=parser.parse_args(argv)
    from ace_research_primitives import primitive_discovery as r1
    from ace_candidate_search import model
    try:
        result=verify_bytes(args.report.read_bytes(),r1,model)
    except (IntegrityError,ValueError,TypeError,KeyError,RuntimeError,OSError) as exc:
        print(json.dumps({"status":"HALT_INVALID_EVIDENCE","error":str(exc)}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
