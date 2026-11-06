"""Fail-closed exact full public replay of retained runtime trials."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import crossfamily as x

class IntegrityError(ValueError):
    pass

def verify(raw):
    try: data=json.loads(raw)
    except (TypeError,ValueError,UnicodeError) as exc: raise IntegrityError("malformed") from exc
    if x.canonical(data)!=raw: raise IntegrityError("noncanonical")
    if data.get("prescore_commit")!=x.PRESCORE or data.get("source_base_sha")!=x.BASE:
        raise IntegrityError("source or preregistration tampered")
    if any(data.get(k) is not False for k in ("compute_matched","independent_holdout",
            "open_world_safe","candidate_deployed","oaie_established")):
        raise IntegrityError("unsafe claim")
    if data.get("scientific_status")!="NOT_ASSESSED" or data.get("release_decision")!="BLOCK_RELEASE":
        raise IntegrityError("false promotion")
    if x.canonical(x.run())!=raw:
        raise IntegrityError("score, baseline, runtime decision, or model changed")
    return {"status":"PASS_PUBLIC_REPLAY_ONLY","sha256":hashlib.sha256(raw).hexdigest()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("report",type=Path)
    args=p.parse_args()
    try: result=verify(args.report.read_bytes())
    except (IntegrityError,RuntimeError,ValueError,TypeError,KeyError) as exc:
        print(json.dumps({"status":"HALT","error":str(exc)}));return 2
    print(json.dumps(result,sort_keys=True));return 0

if __name__=="__main__":sys.exit(main())
