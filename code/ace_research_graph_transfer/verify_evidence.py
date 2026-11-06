"""Exact-run public evidence validation, not a sealed independent reviewer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import study


class EvidenceError(ValueError):
    pass


def verify(raw):
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeError,TypeError) as exc:
        raise EvidenceError("invalid serialized evidence") from exc
    if type(data) is not dict or study.canonical(data)!=raw:
        raise EvidenceError("noncanonical or invalid report")
    if (data.get("preregistered_protocol_commit")!=study.PRESCORE_SHA or
            data.get("source_main_sha")!=study.SOURCE_SHA):
        raise EvidenceError("prescore/source custody mismatch")
    if (data.get("scientific_status")!="NOT_ASSESSED" or
            data.get("release_decision")!="BLOCK_RELEASE" or
            data.get("candidate_deployed") is not False or
            data.get("oaie_established") is not False or
            data.get("independent_evaluator_sealed") is not False or
            data.get("compute_matched") is not False or
            data.get("native_programs_are_researcher_supplied") is not True):
        raise EvidenceError("false promotion, invention or evidence claim")
    independently_reproduced=study.canonical(study.experiment())
    if independently_reproduced!=raw:
        raise EvidenceError("report/score/program/baseline/invariance differs from actual source replay")
    return {"status":"PASS_EXACT_SOURCE_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO",
            "sha256":hashlib.sha256(raw).hexdigest(),
            "source_sha":study.SOURCE_SHA,
            "scientific_status":"NOT_ASSESSED",
            "release_decision":"BLOCK_RELEASE"}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("report",type=Path)
    args=parser.parse_args(argv)
    try:
        out=verify(args.report.read_bytes())
    except (EvidenceError,ValueError,RuntimeError,TypeError,KeyError,OSError) as exc:
        print(json.dumps({"status":"HALT_UNVERIFIED_EVIDENCE","error":str(exc)}))
        return 2
    print(json.dumps(out,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
