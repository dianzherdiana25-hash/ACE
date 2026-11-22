"""Regresi rilis kebijakan memeriksa outcome dan aturan penentu lalu menyegel hasil per kasus."""
from collections import Counter

from ._contracts import GuardianError, anchor, cli, identifier, identity, items, obj, schema
from .action_gate import decide
from .rule_compiler import compile_rules

def regress(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.gate-regression.v1", ("policy", "cases", "required_kinds"))
    policy = compile_rules(plan["policy"], identity(plan["policy"]))
    require = {identifier(value, "Kelas wajib") for value in items(plan["required_kinds"], 200, 1)}
    checks, found = [], Counter()
    seen = set()
    for row in items(plan["cases"], 4000, 1):
        obj(row, ("id", "action", "expect", "first_rule"))
        case = identifier(row["id"], "Kasus")
        if case in seen or row["expect"] not in ("allow", "deny", "review"):
            raise GuardianError("Kasus regresi ganda atau outcome asing.")
        seen.add(case)
        decision = decide(row["action"], policy)
        found[decision["kind"]] += 1
        rules = decision["matched_rules"]
        matched = rules[0] if rules else None
        ok = decision["outcome"] == row["expect"] and matched == row["first_rule"]
        checks.append({"id": case, "ok": ok, "outcome": decision["outcome"], "first_rule": matched,
                       "request_sha256": decision["request_sha256"]})
    missing = sorted(require - found.keys())
    successful = sum(row["ok"] for row in checks)
    payload = {"policy_sha256": policy["compiled_sha256"], "cases": checks, "verified": successful,
               "out_of": len(checks), "missing_kinds": missing, "passed": not missing and successful == len(checks)}
    return {**payload, "ledger_sha256": identity(payload)}

if __name__ == "__main__":
    raise SystemExit(cli(regress, __doc__))
