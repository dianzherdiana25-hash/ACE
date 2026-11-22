"""Susun transisi flag yang ditinjau dengan baseline, rollback, dan bukti trial yang cocok."""
import re

from ._contracts import GuardianError, anchor, cli, digest, identity, items, obj, schema
from .snapshot_scheduler import instant

FLAG = re.compile(r"ACE_[A-Z][A-Z0-9_]{1,70}")
PHASES = {"off": {"fixture"}, "fixture": {"off", "review"}, "review": {"off", "fixture"}}

def transition(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.flag-transition.v1", ("at", "flags", "change", "readiness"))
    now = instant(plan["at"])
    flags = {}
    for row in items(plan["flags"], 400, 1):
        obj(row, ("name", "phase", "revision"))
        name = row["name"]
        if not isinstance(name, str) or not FLAG.fullmatch(name) or name in flags or row["phase"] not in PHASES:
            raise GuardianError("Flag ganda, format asing, atau fase tidak dikenal.")
        digest(row["revision"])
        flags[name] = row
    change = obj(plan["change"], ("name", "from", "to", "parent"))
    digest(change["parent"])
    if change["name"] not in flags:
        raise GuardianError("Flag belum terdaftar.")
    prior = flags[change["name"]]
    if prior["phase"] != change["from"] or change["to"] not in PHASES[prior["phase"]] or change["parent"] != prior["revision"]:
        return {"status": "held", "reason": "invalid_or_stale_transition"}
    test = obj(plan["readiness"], ("to", "passed", "source", "at", "expires"))
    ref = digest(test["source"])
    first, last = instant(test["at"]), instant(test["expires"])
    if test["to"] != change["to"] or test["passed"] is not True or not first <= now < last:
        return {"status": "held", "reason": "evidence_unavailable"}
    payload = {"status": "review_only", "change": change, "readiness": ref,
               "rollback": {"name": change["name"], "phase": prior["phase"], "revision": prior["revision"]}}
    return {**payload, "draft_sha256": identity(payload)}

if __name__ == "__main__":
    raise SystemExit(cli(transition, __doc__))
