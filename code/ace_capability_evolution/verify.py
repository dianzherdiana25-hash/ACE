"""Fail-closed exact-report replay and provenance gate; no production approval."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import pilot


class EvidenceError(ValueError):
    pass


def verify_bytes(data: bytes, r1, s2search, s2model) -> dict:
    try:
        reported = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError("invalid JSON evidence") from exc
    if type(reported) is not dict or pilot.canonical(reported) != data:
        raise EvidenceError("noncanonical evidence or root type")
    if reported.get("pinned_sources") != {"R1":pilot.R1_HEAD,"S2":pilot.S2_HEAD}:
        raise EvidenceError("source provenance mismatch")
    if reported.get("protocol_commit") != pilot.PROTOCOL:
        raise EvidenceError("protocol provenance mismatch")
    if reported.get("scientific_status") != "NOT_ASSESSED" or reported.get("release_decision") != "BLOCK_RELEASE":
        raise EvidenceError("untrusted promotion")
    if reported.get("candidate_deployed") is not False or reported.get("oaie_not_established") is not True:
        raise EvidenceError("unsafe capability claim")
    # Validate exact nested types and all scores/decisions, including terminal, against
    # a completely new deterministic replay from the frozen module interfaces.
    expected = pilot.run_pilot(r1,s2search,s2model)
    if pilot.canonical(reported) != pilot.canonical(expected):
        raise EvidenceError("reported observations, decisions, models or hashes differ from replay")
    return {"decision":"PASS_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO",
            "report_sha256":hashlib.sha256(data).hexdigest(),
            "tasks":len(reported["tasks"]),
            "staged":reported["staged_task_capabilities"],
            "release_decision":reported["release_decision"],
            "scientific_status":reported["scientific_status"]}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("report",type=Path)
    args=parser.parse_args(argv)
    from ace_research_primitives import primitive_discovery as r1
    from ace_candidate_search import search as s2search
    from ace_candidate_search import model as s2model
    try:
        receipt=verify_bytes(args.report.read_bytes(),r1,s2search,s2model)
    except (EvidenceError,ValueError,RuntimeError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({"decision":"HALT_UNVERIFIED_EVIDENCE","error":str(exc)}))
        return 2
    print(json.dumps(receipt,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
