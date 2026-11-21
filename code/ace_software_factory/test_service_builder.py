"""Verifier pekerja SQLite dari proses berbeda dengan antrean persisten."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import service_builder
from ace_software_factory._contracts import decode, identity
from ace_software_factory.repo_scaffolder import materialize


def plan():
    return {"schema": "ace.factory-service-plan.v1", "id": "fixture_worker", "description": "worker inventaris",
            "max_payload_bytes": 200, "max_numbers": 8, "max_pending": 2,
            "routes": [{"id": "aggregate", "operation": "sum", "source_ref": "fixture/routes/0"},
                       {"id": "floor", "operation": "minimum", "source_ref": "fixture/routes/1"}]}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.product = self.root / "product"
        self.db = self.root / "queue state.sqlite"
        data = plan()
        files, report = service_builder.build(data, identity(data))
        materialize(self.product, files)
        self.entry = [sys.executable, "-B", "-m", report["product_id"], "--db", str(self.db)]

    def invoke(self, *arguments, payload=b"", expected=0):
        result = subprocess.run([*self.entry, *arguments], cwd=self.product, input=payload, capture_output=True, timeout=8)
        self.assertEqual(result.returncode, expected, result.stderr)
        return decode(result.stdout) if result.stdout else result.stderr.decode()

    def test_worker_survives_process_restarts_and_preserves_fifo(self):
        self.assertEqual(self.invoke("init")["state"], "ready")
        self.invoke("enqueue", "first", "aggregate", payload=b"[1,-3,8]")
        self.invoke("enqueue", "second", "floor", payload=b"[]")
        first = self.invoke("consume", "--limit", "1")
        self.assertEqual(first["jobs"], [{"id": "first", "result": {"value": 6}, "state": "done"}])
        self.assertEqual(self.invoke("inspect", "second")["state"], "queued")
        second = self.invoke("consume")
        self.assertEqual(second["jobs"], [{"id": "second", "result": {"reason": "empty_operand"}, "state": "failed"}])
        self.assertEqual(self.invoke("inspect", "second")["state"], "failed")
        self.assertEqual(self.invoke("consume")["processed"], 0)

    def test_repeated_identical_id_is_idempotent_and_conflicting_payload_rejected(self):
        self.invoke("init")
        self.assertFalse(self.invoke("enqueue", "same", "aggregate", payload=b"[9]")["reused"])
        self.assertTrue(self.invoke("enqueue", "same", "aggregate", payload=b"[ 9 ]")["reused"])
        self.assertIn("berbeda", self.invoke("enqueue", "same", "aggregate", payload=b"[8]", expected=2))
        self.assertEqual(self.invoke("consume")["processed"], 1)
        self.assertEqual(self.invoke("inspect", "same")["result"], {"value": 9})

    def test_queue_does_not_create_database_during_read_or_exceed_capacity(self):
        self.invoke("inspect", "a", expected=2)
        self.assertFalse(self.db.exists())
        self.invoke("init")
        for job in ("a", "b"):
            self.invoke("enqueue", job, "aggregate", payload=b"[]")
        self.assertIn("penuh", self.invoke("enqueue", "c", "aggregate", payload=b"[]", expected=2))
        self.assertEqual(self.invoke("inspect", "c", expected=1)["state"], "missing")
