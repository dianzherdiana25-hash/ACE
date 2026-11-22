"""Ulang kebijakan lama dan baru atas riwayat aksi yang sama dan beri alasan untuk setiap perubahan."""
from collections import Counter

from ._contracts import GuardianError, anchor, cli, identity, items, schema
from .action_gate import decide
from .rule_compiler import compile_rules

def simulate(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rule-simulation.v1", ("previous", "candidate", "history"))
    baseline, new = (compile_rules(plan[name], identity(plan[name])) for name in ("previous", "candidate"))
    results = []
    seen = set()
    transitions = Counter()
    for action in items(plan["history"], 6000):
        old, changed = decide(action, baseline), decide(action, new)
        key = old["action_id"]
        if key in seen:
            raise GuardianError("Riwayat aksi ganda.")
        seen.add(key)
        transitions[f"{old['outcome']}->{changed['outcome']}"] += 1
        if old["outcome"] != changed["outcome"] or old["matched_rules"] != changed["matched_rules"]:
            results.append({"id": key, "previous": old, "candidate": changed})
    return {"baseline_sha256": baseline["compiled_sha256"], "candidate_sha256": new["compiled_sha256"],
            "assessed": len(seen), "transition_counts": dict(sorted(transitions.items())), "changes": results}

if __name__ == "__main__":
    raise SystemExit(cli(simulate, __doc__))
