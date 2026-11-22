"""Verifier sumber nyata, threshold yang terukur dan gate sebelum penyerapan."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import source_quality_gate
from ace_web_operator._contracts import identity
from ace_web_operator.test_skill_absorber import package_input


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.curriculum=package_input(self.root,"a"*64)
        self.policy={"schema":"ace.web.source-quality-policy.v1","source_ref":"fixture/admission",
                     "curriculum_sha256":identity(self.curriculum),"as_of":"2026-01-08T00:00:00Z",
                     "rules":[{"source":"notes","source_ref":"fixture/criteria","observed_at":"2026-01-01T00:00:00Z",
                               "max_age_days":7,"min_words":3,"max_duplicate_bp":0,
                               "topics":[{"id":"pair","phrase":"dua operand","source_ref":"fixture/terms"}]}]}

    def apply(self):
        return source_quality_gate.sift_and_absorb(self.root,self.policy,identity(self.policy),self.curriculum)

    def test_accepted_source_is_used_to_make_anchored_curriculum(self):
        package,proof=self.apply()
        self.assertEqual(proof["status"],"eligible")
        self.assertEqual(proof["absorption_receipt"]["package_sha256"],identity(package))
        self.assertTrue(proof["sources"][0]["topics"][0]["found"])

    def test_missing_topic_and_old_source_do_not_generate_package(self):
        self.policy["rules"][0]["topics"][0]["phrase"]="absent terms"
        self.policy["as_of"]="2026-01-08T00:00:01Z"
        package,receipt=self.apply()
        self.assertIsNone(package)
        self.assertEqual(receipt["sources"][0]["findings"],["source_stale","topic_not_observed"])
