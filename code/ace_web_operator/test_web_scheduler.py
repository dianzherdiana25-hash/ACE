"""Verifier slot UTC, terminal receipt dan kebijakan catch-up."""
import unittest

from ace_web_operator import web_scheduler
from ace_web_operator._contracts import ContractError,identity


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.web.scheduler-plan.v1","source_ref":"fixture/schedule",
                   "window_start":"2026-01-01T00:00:00Z","window_end":"2026-01-01T00:05:00Z","as_of":"2026-01-01T00:03:00Z",
                   "tasks":[{"id":"page","first_at":"2026-01-01T00:00:00Z","every_seconds":60,
                             "until":"2026-01-01T00:05:00Z","missed_slots":"run_latest","workflow_sha256":"a"*64,
                             "source_ref":"fixture/page"}]}
        self.history={"schema":"ace.web.scheduler-history.v1","receipts":[{
            "task":"page","scheduled_at":"2026-01-01T00:01:00Z","finished_at":"2026-01-01T00:01:30Z",
            "workflow_sha256":"a"*64,"status":"failed","source_ref":"fixture/receipt"}]}

    def report(self):
        return web_scheduler.schedule(self.plan,identity(self.plan),self.history)

    def test_latest_due_records_failed_and_lists_skipped_slots(self):
        result=self.report()
        self.assertEqual(result["counts"],{"due":1,"scheduled":1,"recorded":1,"skipped_by_policy":2})
        self.assertEqual([row["status"] for row in result["slots"]],
                         ["skipped_by_policy","recorded","skipped_by_policy","due","scheduled"])
        self.assertEqual(result["slots"][1]["receipt"]["status"],"failed")
        self.assertEqual(result,self.report())

    def test_mismatched_workflow_receipt_does_not_count_as_terminal(self):
        self.history["receipts"][0]["workflow_sha256"]="b"*64
        with self.assertRaisesRegex(ContractError,"tidak cocok"):
            self.report()
