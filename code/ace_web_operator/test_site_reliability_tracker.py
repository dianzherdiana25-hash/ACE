"""Verifier basis rate, pemisahan bukti absen dan tahap pertama gagal."""
import unittest

from ace_web_operator import site_reliability_tracker
from ace_web_operator._contracts import ContractError,identity


def row(key,decision,observed=True):
    state="completed" if decision else "failed" if observed else "not_started"
    receipt={"schema":"ace.web.workflow-receipt.v1","workflow_sha256":"a"*64,"browser_sha256":"b"*64,
             "source_ref":"fixture/workflow","status":"completed" if decision else "held",
             "reason":None if decision else "fixture","requests":1 if observed else None,
             "rejected_requests":0 if observed else None,
             "stages":[{"id":"first","source_ref":"fixture/stage","requires":[],"steps":["step"],
                        "status":state,"observations":[]}]}
    return {"id":key,"site":"a","at":"2026-01-01T00:10:00Z","receipt_sha256":identity(receipt),
            "receipt":receipt,"source_ref":"fixture/"+key}


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.log={"schema":"ace.web.reliability-log.v1","runs":[row("r1",True),row("r2",False),row("r3",False,False)]}
        self.plan={"schema":"ace.web.reliability-plan.v1","source_ref":"fixture/evidence",
                   "from":"2026-01-01T00:00:00Z","until":"2026-01-02T00:00:00Z","minimum_runs":2,
                   "minimum_bp":6000,"sites":["b","a"],"log_sha256":identity(self.log)}

    def summarize(self):
        self.plan["log_sha256"]=identity(self.log)
        return site_reliability_tracker.summarize(self.plan,identity(self.plan),self.log)

    def test_completion_rate_has_explicit_denominator_and_failed_stage(self):
        a,b=self.summarize()["sites"]
        self.assertEqual((a["observed"],a["completed"],a["failed"],a["unobserved"]),(2,1,1,1))
        self.assertEqual(a["completion_bp"],5000)
        self.assertEqual(a["status"],"below_threshold")
        self.assertEqual(a["runs"][1]["first_failed_stage"],"first")
        self.assertIsNone(b["completion_bp"])

    def test_tampered_receipt_at_known_run_cannot_raise_rate(self):
        self.log["runs"][1]["receipt"]["status"]="completed"
        with self.assertRaisesRegex(ContractError,"anchor"):
            self.summarize()
