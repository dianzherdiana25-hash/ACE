"""Ajukan satu klarifikasi berdasar slot yang belum terisi atau bukti yang saling bertentangan."""
from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text

def ask(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.clarify-plan.v1", ("slots",))
    open_slots = []
    selected = {}
    seen = set()
    for row in items(plan["slots"], 80):
        obj(row, ("id", "question", "required", "cost_if_wrong", "candidates"))
        key = identifier(row["id"], "Slot")
        question = text(row["question"], "Pertanyaan")
        if not question.endswith("?") or type(row["required"]) is not bool or key in seen:
            raise PresenceError("Slot atau pertanyaan klarifikasi tidak sah.")
        seen.add(key)
        priority = integer(row["cost_if_wrong"], "Biaya salah", 0, 100)
        candidates = {}
        for candidate in items(row["candidates"], 30):
            obj(candidate, ("value", "source"))
            value = text(candidate["value"], "Nilai")
            source = text(candidate["source"], "Pointer")
            candidates.setdefault(value, set()).add(source)
        if len(candidates) == 1:
            value = next(iter(candidates))
            selected[key] = {"value": value, "sources": sorted(candidates[value])}
        elif len(candidates) > 1 or row["required"]:
            open_slots.append((-priority, not row["required"], key, question, sorted(candidates)))
    open_slots.sort()
    question = None
    if open_slots:
        _, _, key, wording, choices = open_slots[0]
        question = {"slot": key, "question": wording, "choices": choices}
    return {"resolved": selected, "clarify": question, "remaining": [row[2] for row in open_slots]}

if __name__ == "__main__":
    raise SystemExit(cli(ask, __doc__))
