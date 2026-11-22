"""Periksa ulang bukti fixture lewat recall dan ringkasan nyata serta label waktu terpisah."""
from ._contracts import PresenceError, anchor, cli, decode, identity, items, obj, schema, source_bytes
from .conversation_memory import recall
from .dialogue_eval import evaluate
from .promise_extractor import extract
from .rolling_summary import summarize
from .time_bench import bench

def assess(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.closed-bench.v1", ("recall", "summary", "dialogue_labels", "time"))
    summary = summarize(plan["summary"], identity(plan["summary"]), root)
    ref = plan["summary"]["dialogue"]
    labels = obj(plan["dialogue_labels"], ("path", "sha256"))
    gold = items(decode(source_bytes(root, labels["path"], labels["sha256"])), 200, 1)
    retrieved = recall(plan["recall"], identity(plan["recall"]), root)
    promise_plan = {"schema": "ace.presence.promises-plan.v1", "dialogue": ref}
    promises = {row["turn_sha256"] for row in extract(promise_plan, identity(promise_plan), root)["promises"]}
    found = []
    for entry in retrieved["matches"]:
        if entry["source"]["sha256"] != ref["sha256"]:
            raise PresenceError("Bench dialog hanya menerima recall dari ekspor terlabel yang sama.")
        if entry["turn_sha256"] in promises:
            kind = "promise"
        elif entry["excerpt"].startswith("Fakta: "):
            kind = "fact"
        else:
            continue
        found.append({"id": entry["turn"], "kind": kind, "turn_sha256": entry["turn_sha256"]})
    selected = [{"id": row["id"], "message": row["message"], "turn_sha256": row["source_turn_sha256"]}
                for row in summary["selected"]]
    if not selected:
        raise PresenceError("Bench ringkasan memerlukan petikan agar audit dapat dinilai.")
    eval_plan = {"schema": "ace.presence.dialogue-eval.v1", "dialogue": ref, "gold": gold,
                 "recalled": found, "summary": selected}
    dialog = evaluate(eval_plan, identity(eval_plan), root)
    time = bench(plan["time"], identity(plan["time"]), root)
    return {"schema": "ace.presence.closed-result.v1", "scope": "closed_fixture",
            "plan_sha256": expected, "dialogue_labels": labels, "dialogue": dialog, "time": time}

if __name__ == "__main__":
    raise SystemExit(cli(assess, __doc__, rooted=True))
