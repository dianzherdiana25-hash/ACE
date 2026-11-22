"""Verifier held-out, tipe jawaban, split dan perbedaan fixture/pengukuran."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import skill_absorber,skill_verifier
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_skill_absorber import package_input


def evidence(root,scope="fixture"):
    suite={"schema":"ace.web.heldout-suite.v1","skill":"two_values","scope":scope,"source_ref":"fixture/suite",
           "evaluator_ref":"fixture/verifier","min_cases_per_objective":2,"target_bp":7500,
           "cases":[{"id":key,"objective":"sum","prompt":prompt,"op":"int_exact","expected":value,
                       "source_ref":"fixture/"+key} for key,prompt,value in (
                           ("first_test","Jumlahkan tiga dan tujuh.",10),("second_test","Jumlahkan dua dan lima.",7))]}
    plan=package_input(root,identity(suite))
    package,_=skill_absorber.absorb(root,plan,identity(plan))
    inputs={"schema":"ace.web.heldout-answers.v1","package_sha256":identity(package),"suite_sha256":identity(suite),
            "source_ref":"fixture/answer-file","solver_ref":"fixture/solver","at":"2026-01-01T00:00:00Z",
            "answers":[{"id":key,"value":value,"source_ref":"fixture/answers/"+key}
                       for key,value in (("first_test",10),("second_test",7))]}
    return package,suite,inputs


class HeldoutTests(unittest.TestCase):
    def setUp(self):
        root=Path(self.enterContext(TemporaryDirectory()))
        self.package,self.suite,self.answers=evidence(root)

    def verify(self):
        return skill_verifier.evaluate(self.package,identity(self.package),self.suite,self.answers,identity(self.answers))

    def test_fixture_success_has_distinct_verdict_and_lost_answer_reduces_score(self):
        proof=self.verify()
        self.assertEqual(proof["status"],"fixture_passed")
        self.assertEqual(proof["score_bp"],10000)
        self.answers["answers"].pop()
        proof=self.verify()
        self.assertEqual(proof["score_bp"],5000)
        self.assertEqual(proof["objectives"]["sum"]["missing"],1)
        self.assertFalse(proof["passed"])

    def test_contamination_rejected_even_when_new_suite_has_valid_commitments(self):
        self.suite["cases"][0]["prompt"]="  JUMLAHKAN ENAM  DAN DUA. "
        self.package["heldout_sha256"]=identity(self.suite)
        self.answers["suite_sha256"]=identity(self.suite)
        self.answers["package_sha256"]=identity(self.package)
        with self.assertRaisesRegex(ContractError,"tumpang tindih"):
            self.verify()
