"""Verifier batas retry, efek ambigu, dan receipt terminal terbaru."""
import unittest

from ace_web_operator import failed_task_escalator
from ace_web_operator._contracts import identity


def event(key,number=1,status="failed",effect="none_verified"):
    return {"task":key,"attempt":number,"workflow_sha256":"a"*64,"at":f"2026-01-01T00:00:0{number}Z",
            "status":status,"reason":"transport" if status=="failed" else None,"effect":effect,
            "receipt_sha256":"b"*64,"source_ref":"fixture/"+key}


class EscalatorTests(unittest.TestCase):
    def test_retry_allowed_only_when_effect_absent_and_receipt_reported(self):
        data={"schema":"ace.web.failed-task-ledger.v1","source_ref":"fixture/attempts",
              "attempts":[event("retry"),event("unknown",effect="possible"),event("done"),event("done",2,"completed")]}
        plan={"schema":"ace.web.failed-task-policy.v1","source_ref":"fixture/policy","ledger_sha256":identity(data),
              "as_of":"2026-01-01T00:01:01Z","default_owner_ref":"fixture/team",
              "rules":[{"reason":"transport","owner_ref":"fixture/infra","priority":90,"max_retry":1,"wait_seconds":60,
                        "source_ref":"fixture/transport"}]}
        result=failed_task_escalator.triage(plan,identity(plan),data)
        self.assertEqual(result["resolved"],1)
        self.assertFalse(result["executed"])
        self.assertEqual([(row["task"],row["disposition"]) for row in result["actions"]],
                         [("retry","retry_eligible"),("unknown","operator_review")])
        self.assertEqual(result["actions"][0]["next_eligible_at"],plan["as_of"])
