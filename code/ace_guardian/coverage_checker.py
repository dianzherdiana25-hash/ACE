"""Laporkan kelas aksi tanpa aturan serta bukti outcome yang belum pernah diperiksa."""
from collections import defaultdict

from ._contracts import GuardianError, anchor, cli, identifier, identity, items, obj, schema
from .gate_receipt_ledger import verify_ledger
from .rule_compiler import compile_rules

def check(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.policy-coverage.v1", ("policy", "classes", "ledger"))
    compiled = compile_rules(plan["policy"], identity(plan["policy"]))
    head, _, receipts = verify_ledger(plan["ledger"])
    observed = defaultdict(set)
    obsolete = []
    for row in receipts.values():
        decision = row["decision"]
        if decision["policy_sha256"] != compiled["compiled_sha256"]:
            obsolete.append(decision["action_id"])
        else:
            observed[decision["kind"]].add(decision["outcome"])
    rows = []
    seen = set()
    for row in items(plan["classes"], 300, 1):
        obj(row, ("kind", "expected_outcomes"))
        key = identifier(row["kind"], "Kelas")
        targets = set(items(row["expected_outcomes"], 3, 1))
        if key in seen or targets - {"allow", "deny", "review"}:
            raise GuardianError("Kelas ganda atau tipe outcome salah.")
        seen.add(key)
        reason = "unregistered" if key not in compiled["catalog"] else "no_rule" if not compiled["by_kind"][key] else "covered"
        rows.append({"kind": key, "classification": reason, "observed_outcomes": sorted(observed[key]),
                     "untested_outcomes": sorted(targets - observed[key])})
    return {"coverage": sorted(rows, key=lambda row: row["kind"]), "receipt_head": head,
            "obsolete_receipts": sorted(obsolete), "policy_only": sorted(compiled["catalog"].keys() - seen),
            "complete": all(row["classification"] == "covered" and not row["untested_outcomes"] for row in rows)}

if __name__ == "__main__":
    raise SystemExit(cli(check, __doc__))
