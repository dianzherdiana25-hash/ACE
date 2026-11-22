"""Buat putusan aksi dengan bukti aturan yang cocok, default deny, dan pengetikan input ketat."""
from ._contracts import ID, GuardianError, anchor, cli, identifier, identity, items, obj, schema
from .rule_compiler import TYPE, compile_rules

def decide(action, table):
    obj(action, ("id", "kind", "facts"))
    key = identifier(action["id"], "Aksi")
    kind = identifier(action["kind"], "Kelas aksi")
    fields = table["catalog"].get(kind)
    valid = fields is not None and isinstance(action["facts"], dict) and action["facts"].keys() == fields.keys()
    if valid:
        for field, val in action["facts"].items():
            if type(val) is not TYPE[fields[field]]:
                valid = False
            elif isinstance(val, str) and not ID.fullmatch(val):
                valid = False
            elif type(val) is int and not 0 <= val <= 9_999_999:
                valid = False
    rows = []
    if valid:
        rows = [row for row in table["by_kind"][kind]
                if all(action["facts"][field] == value for field, value in row["conditions"].items())]
    outcome, reason = "deny", "invalid_action_facts" if fields is not None else "unregistered_action"
    if valid:
        outcome, reason = (rows[0]["effect"], "matching_rule") if rows else ("deny", "default_deny")
    return {"action_id": key, "kind": kind, "outcome": outcome, "reason": reason,
            "matched_rules": [row["rule"] for row in rows], "request_sha256": identity(action),
            "policy_sha256": table["compiled_sha256"]}

def assess(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.action-gate.v1", ("policy", "actions"))
    table = compile_rules(plan["policy"], identity(plan["policy"]))
    result = []
    seen = set()
    for action in items(plan["actions"], 5000):
        row = decide(action, table)
        if row["action_id"] in seen:
            raise GuardianError("Keputusan aksi dengan ID sama.")
        seen.add(row["action_id"])
        result.append(row)
    return {"revision": table["revision"], "decisions": result}

if __name__ == "__main__":
    raise SystemExit(cli(assess, __doc__))
