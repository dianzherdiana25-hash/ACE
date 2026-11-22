"""Jalankan siklus fixture melalui operasi data tertutup agar kandidat tidak memperoleh akses OS."""
from copy import deepcopy

from ._contracts import GuardianError, anchor, cli, identifier, identity, integer, items, obj, schema

MAX_VALUE = 1_000_000

def run(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.twin-run.v1", ("initial", "cycles", "must_keep"))
    if not isinstance(plan["initial"], dict) or not 1 <= len(plan["initial"]) <= 100:
        raise GuardianError("State fixture perlu pemetaan numerik dalam batas.")
    state = {identifier(key, "Field"): integer(value, "Nilai awal", -MAX_VALUE, MAX_VALUE)
             for key, value in plan["initial"].items()}
    protected = {identifier(key, "Field beku") for key in items(plan["must_keep"], 100)}
    if protected - state.keys():
        raise GuardianError("Field beku belum ada di snapshot.")
    head = identity(state)
    initial = head
    ledger = []
    for index, actions in enumerate(items(plan["cycles"], 100), 1):
        staged = deepcopy(state)
        for action in items(actions, 100, 1):
            obj(action, ("op", "field", "value"))
            name = identifier(action["field"], "Field")
            op = action["op"]
            amount = integer(action["value"], "Operan", -MAX_VALUE, MAX_VALUE)
            if name not in staged or name in protected or op not in ("set", "add", "min", "max"):
                raise GuardianError("Operasi siklus tidak diizinkan atau menyentuh field beku.")
            old = staged[name]
            changes = {"set": amount, "add": old + amount, "min": min(old, amount), "max": max(old, amount)}
            staged[name] = integer(changes[op], "Nilai hasil", -MAX_VALUE, MAX_VALUE)
        record = {"cycle": index, "before_sha256": head, "state_sha256": identity(staged),
                  "actions_sha256": identity(actions)}
        head = record["state_sha256"]
        state = staged
        ledger.append(record)
    return {"schema": "ace.guardian.twin-result.v1", "initial_sha256": initial,
            "state": state, "head_sha256": head, "cycles": ledger}

if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__))
