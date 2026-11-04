"""Audit corruption tests independent of E1.4c candidate/evaluator imports."""
import copy
import json
import unittest
from pathlib import Path
from .cross_episode_audit import audit

EVIDENCE=Path(__file__).resolve().parents[2]/"evidence/e14/e14c_public_development_v1.json"

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=json.loads(EVIDENCE.read_text())

    def test_valid_saved_report(self):
        self.assertEqual(audit(self.r)["decision"],"HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS")

    def bad(self,modify,reason):
        r=copy.deepcopy(self.r)
        modify(r)
        with self.assertRaisesRegex(ValueError,reason):audit(r)

    def test_corrected_v2_report(self):
        path=EVIDENCE.with_name("e14c_v2_public_development_v1.json")
        self.assertEqual(audit(json.loads(path.read_text()))["decision"],
                         "HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS")

    def test_duplicate_task(self):
        self.bad(lambda r:r["targets"][0].__setitem__("task_id",r["sources"][0]["task_id"]),"duplicate task")

    def test_wrong_uniform(self):
        self.bad(lambda r:r["targets"][0].__setitem__("uniform_expected_numerator",999),"uniform numerator")

    def test_wrong_hindsight(self):
        self.bad(lambda r:r["targets"][0].__setitem__("best_possible_one_label",9),"oracle ceiling")

    def test_wrong_family_policy(self):
        self.bad(lambda r:r["learned_policies"]["G"].__setitem__("policy","seeded_uniform"),"selected policy")

    def test_wrong_target_arm(self):
        self.bad(lambda r:r["targets"][0]["policies"]["inherited"].__setitem__("correct",99),"policy arm mismatch")

    def test_wrong_decision(self):
        self.bad(lambda r:r.__setitem__("decision","GO_CROSS_EPISODE_TRANSFER_DEVELOPMENT_ONLY"),"decision mismatch")

if __name__=="__main__":unittest.main()
