"""Siapkan perubahan aturan berversi setelah regression cases mencapai hasil yang dideklarasikan."""
from collections import Counter

from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, items, obj, schema
from .action_gate import decide
from .rule_compiler import compile_rules

OUTCOMES = {"allow", "deny", "review"}

def review(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rule-change.v1", ("parent", "previous", "candidate", "cases"))
    before, after = (compile_rules(plan[name], identity(plan[name])) for name in ("previous", "candidate"))
    if before["compiled_sha256"] != digest(plan["parent"]) or before["revision"] == after["revision"]:
        raise GuardianError("Parent kebijakan berbeda atau versi belum naik.")
    result = []
    coverage = Counter()
    seen = set()
    for case in items(plan["cases"], 2000, 1):
        obj(case, ("action", "baseline", "candidate"))
        if case["baseline"] not in OUTCOMES or case["candidate"] not in OUTCOMES:
            raise GuardianError("Label regression tidak dikenal.")
        old, new = decide(case["action"], before), decide(case["action"], after)
        key = identifier(old["action_id"], "Kasus")
        if key in seen:
            raise GuardianError("Kasus regression ganda.")
        seen.add(key)
        kind = old["kind"]
        coverage[kind] += 1
        checks = (old["outcome"] == case["baseline"], new["outcome"] == case["candidate"])
        result.append({"id": key, "kind": kind, "baseline": old["outcome"], "candidate": new["outcome"],
                       "matched_expectations": all(checks)})
    absent = sorted((before["catalog"].keys() | after["catalog"].keys()) - coverage.keys())
    payload = {"parent": plan["parent"], "proposal": after["compiled_sha256"], "uncovered": absent, "cases": result,
               "disposition": "ready_for_review" if not absent and all(row["matched_expectations"] for row in result) else "held"}
    return {**payload, "dossier_sha256": identity(payload)}

if __name__ == "__main__":
    raise SystemExit(cli(review, __doc__))
