import unittest

from ._contracts import ProductionError, identity
from .session_manager import Session, verify_session
from .test_grader import grade


def commands():
    old = grade("lab")
    looks = {key: old[key] for key in ("criteria", "passing_bp")}
    return {"schema": "ace.teaching.session-plan.v1", "id": "local", "consent_ref": "fixture:consent",
            "tasks": [{"id": "lab", "prompt": "Jelaskan pengukuran.", "source_ref": "fixture:lab", "rubric": looks}]}


class SessionTests(unittest.TestCase):
    def test_state_and_chain_validate_from_prompt_to_close(self):
        plan = commands()
        session = Session(plan, identity(plan))
        initial = session.head
        with self.assertRaisesRegex(ProductionError, "prompt aktif"):
            session.receive({"action": "answer", "id": "lab", "text": "suhu", "source_ref": "fixture:eq"})
        session.receive({"action": "next"})
        receipt = session.receive({"action": "answer", "id": "lab", "text": "suhu tetap", "source_ref": "fixture:eq"})
        self.assertEqual(receipt["grade"]["score_bp"], 3000)
        self.assertNotIn("suhu tetap", str(receipt))
        closed = session.receive({"action": "close"})
        self.assertEqual(closed["completed"], 1)
        self.assertEqual(verify_session(session.events, initial), closed["event_sha256"])
        session.events[0]["prompt"] = "Berubah"
        with self.assertRaisesRegex(ProductionError, "Hash receipt"):
            verify_session(session.events, initial)
