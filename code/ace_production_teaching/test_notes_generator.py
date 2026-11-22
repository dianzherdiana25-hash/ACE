from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, canonical, identity
from .notes_generator import notes
from .session_manager import Session
from .test_session_manager import commands
from .test_tabular_engine import save


class NotesTests(unittest.TestCase):
    def test_provenance_links_grading_events_and_pending_tasks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            setup = commands()
            session = Session(setup, identity(setup))
            initial = session.head

            def output():
                return save(root, "trace.jsonl", b"\n".join(map(canonical, session.events)))

            session.receive({"action": "next"})
            plan = {"schema": "ace.teaching.notes-plan.v1", "session": "local",
                    "receipt": output(), "initial_sha256": initial, "head_sha256": session.head}
            self.assertEqual(notes(plan, identity(plan), root)["open_task"], "lab")
            session.receive({"action": "answer", "id": "lab", "text": "massa gas", "source_ref": "fixture:reply"})
            session.receive({"action": "close"})
            plan.update(receipt=output(), head_sha256=session.head)
            result = notes(plan, identity(plan), root)
            self.assertEqual(result["state"], "closed")
            self.assertEqual(result["completed"][0]["evidence_events"], [1, 2])
            plan["head_sha256"] = "d" * 64
            with self.assertRaisesRegex(ProductionError, "head"):
                notes(plan, identity(plan), root)
