"""Verifier transaksi queue, kuota situs dan receipt ketika lease habis."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import web_task_queue
from ace_web_operator._contracts import ContractError,identity


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(self.enterContext(TemporaryDirectory()))/"web.sqlite"
        self.config={"schema":"ace.web.queue-policy.v1","source_ref":"fixture/queue","max_items":3,"lease_seconds":15,
                     "sites":[{"id":"one","parallelism":1},{"id":"two","parallelism":1}]}
        self.queue=web_task_queue.Queue(self.path,self.config,identity(self.config))
        self.queue.initialize()

    def insert(self,key,site,priority):
        return self.queue.enqueue({"schema":"ace.web.queue-task.v1","id":key,"site":site,"priority":priority,
                                    "not_before":"2026-01-01T00:00:00Z","workflow_sha256":"a"*64,"source_ref":"fixture/task"})

    def test_cross_site_claim_cap_priority_and_replay(self):
        self.insert("first","one",100)
        self.insert("second","one",80)
        self.insert("third","two",10)
        self.assertTrue(self.insert("first","one",100)["duplicate"])
        at="2026-01-01T00:00:10Z"
        self.assertEqual(self.queue.claim("worker",at)["id"],"first")
        self.assertEqual(self.queue.claim("other",at)["id"],"third")
        self.assertEqual(self.queue.claim("additional",at)["status"],"idle")
        with self.assertRaisesRegex(ContractError,"berbeda"):
            self.insert("third","two",30)

    def test_expiry_quarantines_task_and_rejects_late_completion(self):
        self.insert("first","one",10)
        receipt=self.queue.claim("worker","2026-01-01T00:00:00Z")
        outcome={"schema":"ace.web.queue-finish.v1","id":"first","actor":"worker","lease":receipt["lease"],
                 "workflow_sha256":"a"*64,"result":"completed","receipt_sha256":"b"*64}
        report=self.queue.finish(outcome,"2026-01-01T00:00:15Z")
        self.assertEqual(report["reason"],"lease_or_workflow_mismatch")
        self.assertEqual(self.queue.summary()["summary"],[{"site":"one","status":"needs_review","count":1}])
