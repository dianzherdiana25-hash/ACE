"""Nilai recall fakta/janji terhadap label, dan audit petikan ringkasan langsung dari rantai."""
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, digest, identifier, items, obj, schema, source_bytes
from ._journal import load_export

def evaluate(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.dialogue-eval.v1", ("dialogue", "gold", "recalled", "summary"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    export = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    rows = {row["turn"]["id"]: row for row in export["events"]}
    gold = set()
    for item in items(plan["gold"], 500):
        obj(item, ("id", "kind"))
        key = identifier(item["id"], "Turn gold")
        if key not in rows or item["kind"] not in ("fact", "promise") or (key, item["kind"]) in gold:
            raise PresenceError("Label gold tanpa turn, ganda, atau jenis tidak dikenal.")
        gold.add((key, item["kind"]))
    accepted = set()
    bad = []
    for item in items(plan["recalled"], 500):
        obj(item, ("id", "kind", "turn_sha256"))
        key = identifier(item["id"], "Turn recall")
        sha = digest(item["turn_sha256"])
        label = (key, item["kind"])
        if key in rows and rows[key]["sha256"] == sha and label in gold and label not in accepted:
            accepted.add(label)
        else:
            bad.append(key)
    bad_summary = []
    seen = set()
    for item in items(plan["summary"], 500):
        obj(item, ("id", "message", "turn_sha256"))
        key = identifier(item["id"], "Turn ringkasan")
        hit = rows.get(key)
        if hit is None or key in seen or hit["sha256"] != digest(item["turn_sha256"]) or hit["turn"]["message"] != item["message"]:
            bad_summary.append(key)
        seen.add(key)
    return {"source": ref, "gold": len(gold), "correct": len(accepted),
            "recall": str(Fraction(len(accepted), len(gold))) if gold else None,
            "invalid_recall": bad, "summary_checked": len(plan["summary"]), "unsupported_summary": bad_summary}

if __name__ == "__main__":
    raise SystemExit(cli(evaluate, __doc__, rooted=True))
