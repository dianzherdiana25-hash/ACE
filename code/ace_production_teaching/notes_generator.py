"""Susun catatan sesi dari receipt berantai dengan kemajuan dan tindak lanjut bernama."""
from ._contracts import ProductionError, anchor, cli, decode, digest, identifier, items, obj, schema, source_bytes
from .session_manager import verify_session


def notes(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.notes-plan.v1", ("receipt", "session", "initial_sha256", "head_sha256"))
    session = identifier(plan["session"], "Sesi")
    link = obj(plan["receipt"], ("path", "sha256"))
    content = source_bytes(root, link["path"], link["sha256"], 2_000_000)
    logs = [decode(row) for row in content.splitlines() if row.strip()]
    items(logs, 161, 1)
    head = verify_session(logs, digest(plan["initial_sha256"]))
    if head != digest(plan["head_sha256"]):
        raise ProductionError("Receipt sesi berhenti di head yang tidak cocok.")
    expected_item = None
    topics = []
    state = "incomplete"
    for index, row in enumerate(logs, 1):
        if row["session"] != session or state == "closed":
            raise ProductionError("Receipt lintas sesi atau memiliki acara sesudah penutupan.")
        action = row["action"]
        if action == "prompt" and expected_item is None:
            expected_item = row
        elif action == "graded" and expected_item and row["id"] == expected_item["id"]:
            result = row["grade"]
            misses = [{"criterion": value["id"], "rubric_ref": value["source_ref"],
                       "status": value["status"]} for value in result["criteria"] if value["status"] != "met"]
            topics.append({"item": row["id"], "prompt_ref": expected_item["source_ref"], "response_ref": row["response_ref"],
                           "score_bp": result["score_bp"], "review": misses, "evidence_events": [expected_item["event"], index],
                           "grade_event_sha256": row["event_sha256"]})
            expected_item = None
        elif action == "closed" and expected_item is None and row["completed"] == len(topics):
            state = "closed"
        else:
            raise ProductionError("Receipt tidak mengikuti urutan prompt, penilaian, atau penutupan.")
    return {"schema": "ace.teaching.session-notes.v1", "plan_sha256": expected, "session": session, "head_sha256": head,
            "receipt": link, "state": state, "completed": topics, "open_task": expected_item["id"] if expected_item else None}


if __name__ == "__main__":
    raise SystemExit(cli(notes, __doc__, rooted=True))
