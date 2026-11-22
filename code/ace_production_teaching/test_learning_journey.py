from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, canonical, identity
from .learning_journey import archive_journey
from .session_manager import Session
from .test_session_manager import commands
from .test_tabular_engine import save


class JourneyTests(unittest.TestCase):
    def test_manifest_records_closed_original_trace_and_rejects_wrong_head(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            start = commands()
            session = Session(start, identity(start))
            first = session.head
            session.receive({"action": "next"})
            session.receive({"action": "answer", "id": "lab", "text": "Suhu tetap", "source_ref": "fixture:answer"})
            session.receive({"action": "close"})
            trace = b"\n".join(map(canonical, session.events))
            plan = {"schema": "ace.teaching.journey-plan.v1", "learner": "anon", "sessions": [
                       {"id": "local", "date": "2025-06-01", "initial_sha256": first,
                        "head_sha256": session.head, "trace": save(root, "trace.jsonl", trace)}]}
            data, proof = archive_journey(plan, identity(plan), root)
            self.assertEqual(unpack(data)["sessions/local.jsonl"], trace)
            self.assertEqual(proof["manifest"]["timeline"][0]["event_count"], 3)
            self.assertEqual(archive_journey(plan, identity(plan), root)[0], data)
            plan["sessions"][0]["head_sha256"] = "1" * 64
            with self.assertRaisesRegex(ProductionError, "Head"):
                archive_journey(plan, identity(plan), root)
