"""Verifier skor berkurang, nol, dan suite sama atau fixture yang ditahan."""
import unittest

from ace_web_operator import skill_retention_probe
from ace_web_operator._contracts import identity


def receipt(when,score,anchor,scope="controlled"):
    return {"schema":"ace.web.skill-verification-receipt.v1","skill":"paired","cluster":"k01","version":1,
            "package_sha256":"b"*64,"suite_sha256":anchor*64,"answer_sha256":"c"*64,"at":when,"scope":scope,
            "source_ref":"fixture/answers","suite_ref":"fixture/suite","solver_ref":"fixture/solver","evaluator_ref":"fixture/evaluator",
            "score_bp":score,"passed":score==10000,"status":"heldout_passed" if score==10000 else "below_criteria",
            "objectives":{"sum":{"tested":2,"passed":score//5000,"missing":0,"score_bp":score,"qualified":score==10000}},
            "cases":[{"id":"test_"+str(index),"objective":"sum","criterion_ref":"fixture/case",
                      "answer_ref":"fixture/answer","answer_sha256":"c"*64,"expected_sha256":"a"*64,
                      "status":"passed" if index<score//5000 else "failed"} for index in range(2)]}


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.first=receipt("2026-01-01T00:00:00Z",10000,"a")
        self.next=receipt("2026-01-10T00:00:00Z",5000,"d")
        self.plan={"schema":"ace.web.skill-retention-plan.v1","source_ref":"fixture/retention",
                   "skill":"paired","package_sha256":"b"*64,"comparability_ref":"fixture/protocol",
                   "minimum_days":7,"maximum_drop_bp":2000,"minimum_cases":2}

    def run_probe(self):
        self.plan.update(baseline_sha256=identity(self.first),followup_sha256=identity(self.next))
        return skill_retention_probe.compare(self.plan,identity(self.plan),self.first,self.next)

    def test_drift_reported_with_exact_denominator_and_zero_supported(self):
        report=self.run_probe()
        self.assertEqual((report["status"],report["delta_bp"]),("fragile",-5000))
        self.assertEqual(report["objectives"][0]["before_cases"],2)
        self.next=receipt("2026-01-10T00:00:00Z",10000,"d")
        self.assertEqual((self.run_probe()["status"],self.run_probe()["delta_bp"]),("retained",0))

    def test_reused_or_fixture_suite_does_not_measure_retention(self):
        self.next["suite_sha256"]=self.first["suite_sha256"]
        self.assertEqual(self.run_probe()["reason"],"reused_suite")
        self.next["scope"]="fixture"
        self.assertEqual(self.run_probe()["reason"],"fixture_scope")
