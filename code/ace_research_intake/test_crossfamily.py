"""Precommitted transfer, negative control, and integrity tests."""
from __future__ import annotations
import copy
import unittest
from . import crossfamily as x
from . import verify_crossfamily as v

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=x.run()
        cls.raw=x.canonical(cls.result)

    def test_all_targets(self):
        self.assertEqual(16,len(self.result["comparisons"]))
        self.assertEqual(16,len(self.result["nominal"]))
        self.assertEqual(2,len(self.result["controls"]))
    def test_distinct_families(self):
        for t in self.result["comparisons"]:
            self.assertNotIn(t["family"],t["predecessors"])
            self.assertEqual(t["retained"]["observed_hash"],t["fresh"]["observed_hash"])
    def test_same_terminal_inputs(self):
        for t in self.result["comparisons"]:
            self.assertEqual(t["retained"]["terminal_words_hash"],t["fresh"]["terminal_words_hash"])
            self.assertEqual(t["retained"]["terminal_labels_hash"],t["fresh"]["terminal_labels_hash"])
    def test_original_source_receipts(self):
        self.assertEqual("80104ce50ecbcea21080bed8c0eabce88d47ccb5",self.result["source_base_sha"])
        self.assertEqual(x.PRESCORE,self.result["prescore_commit"])
        for trial in self.result["nominal"]+self.result["controls"]:
            self.assertEqual(len(trial["families"]),trial["status"]["completed"])
            self.assertEqual(0,trial["status"]["failed"])
            self.assertEqual(0,trial["status"]["pending"])
    def test_coverage_is_not_fabricated(self):
        for t in self.result["comparisons"]:
            for arm in ("retained","fresh"):
                self.assertEqual(t[arm]["terminal"] is not None,t[arm]["staged"])
    def test_shift_indistinguishable(self):
        for t in self.result["controls"]:
            a,b=t["results"]
            self.assertEqual(a["observed_hash"],b["observed_hash"])
            self.assertEqual(a["terminal_words_hash"],b["terminal_words_hash"])
            self.assertNotEqual(a["terminal_labels_hash"],b["terminal_labels_hash"])
    def test_gate_recomputed(self):
        summary=self.result["summary"]
        self.assertEqual(summary["H1_transfer_efficiency_without_regression"],
            summary["reuse_validated"]>=2 and not summary["lost_or_regressed"])
        self.assertEqual(summary["H2_hidden_shift_safe"],summary["shift_false_admissions"]==0)
    def test_no_unsafe_claims(self):
        for k in ("compute_matched","independent_holdout","open_world_safe","candidate_deployed","oaie_established"):
            self.assertIs(self.result[k],False)
        self.assertEqual("NOT_ASSESSED",self.result["scientific_status"])
        self.assertEqual("BLOCK_RELEASE",self.result["release_decision"])
    def test_public_replay(self):
        self.assertEqual("PASS_PUBLIC_REPLAY_ONLY",v.verify(self.raw)["status"])
    def test_tamper_baseline(self):
        data=copy.deepcopy(self.result)
        data["summary"]["fresh_correct_on_all_targets"]+=1
        with self.assertRaises(v.IntegrityError):v.verify(x.canonical(data))
    def test_tamper_model(self):
        data=copy.deepcopy(self.result)
        data["comparisons"][0]["retained"]["model_id"]="0"*64
        with self.assertRaises(v.IntegrityError):v.verify(x.canonical(data))
    def test_tamper_bool_alias(self):
        data=copy.deepcopy(self.result)
        data["candidate_deployed"]=0
        with self.assertRaises(v.IntegrityError):v.verify(x.canonical(data))
    def test_tamper_source(self):
        data=copy.deepcopy(self.result)
        data["prescore_commit"]="0"*40
        with self.assertRaises(v.IntegrityError):v.verify(x.canonical(data))

if __name__=="__main__":unittest.main()
