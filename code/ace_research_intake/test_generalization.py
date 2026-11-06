"""Generalization method, class balance, source and negative-control tests."""
from __future__ import annotations

import copy
import unittest
from . import generalization_admission as study, verify_generalization as verifier


class GeneralizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=study.experiment()
        cls.raw=study.canonical(cls.result)

    def test_five_families_and_three_disjoint_splits(self):
        for seed in study.SEEDS:
            for family in study.FAMILIES + ("ratio3_late_flip",):
                with self.subTest(seed=seed,family=family):
                    bank=study.bank(family,seed)
                    self.assertEqual([63,128,128],[len(bank[k]) for k in ("train","validation","terminal")])
                    words=[set(w for w,_ in bank[k]) for k in ("train","validation","terminal")]
                    self.assertFalse(words[0]&words[1])
                    self.assertFalse(words[0]&words[2])
                    self.assertFalse(words[1]&words[2])
                    self.assertEqual(64,sum(y for _,y in bank["validation"]))
                    self.assertEqual(64,sum(y for _,y in bank["terminal"]))

    def test_shift_has_identical_observed_data_and_inverted_terminal(self):
        for seed in study.SEEDS:
            original=study.bank("ratio3",seed)
            shift=study.bank("ratio3_late_flip",seed)
            self.assertEqual(original["train"],shift["train"])
            self.assertEqual(original["validation"],shift["validation"])
            self.assertEqual([w for w,_ in original["terminal"]],[w for w,_ in shift["terminal"]])
            self.assertEqual([not y for _,y in original["terminal"]],[y for _,y in shift["terminal"]])

    def test_sources_frozen_and_models_not_selected_on_terminal(self):
        self.assertEqual("80104ce50ecbcea21080bed8c0eabce88d47ccb5",self.result["base_source_sha"])
        self.assertEqual(study.PROTOCOL_COMMIT,self.result["pre_score_commit"])
        self.assertEqual(10,self.result["label_budget"]["worlds"])
        self.assertEqual(3190,self.result["label_budget"]["overall_label_presentations"])
        for row in self.result["nominal"]+self.result["shift_controls"]:
            for arm in study.ARMS:
                self.assertEqual(64,len(row["arms"][arm]["terminal"]["program_id"]))
                self.assertEqual(128,row["arms"][arm]["terminal"]["total"])
                self.assertEqual(128,row["runtime"]["validation_total"])
            if row["runtime"]["staged"]:
                self.assertIsNotNone(row["runtime"]["terminal"])
            else:
                self.assertIsNone(row["runtime"]["terminal"])

    def test_all_nominal_per_family_and_balanced_majority(self):
        self.assertEqual(8,len(self.result["nominal"]))
        self.assertEqual(2,len(self.result["shift_controls"]))
        self.assertEqual(1024,self.result["totals"]["terminal_total"])
        self.assertEqual(512,self.result["totals"]["majority_correct"])
        self.assertEqual(set(study.FAMILIES),set(self.result["family_summary"]))

    def test_hidden_shift_cannot_change_candidate_model(self):
        for seed in study.SEEDS:
            ordinary=next(t for t in self.result["nominal"] if t["seed"]==seed and t["family"]=="ratio3")
            shift=next(t for t in self.result["shift_controls"] if t["seed"]==seed)
            self.assertEqual(ordinary["runtime"]["model_id"],shift["runtime"]["model_id"])
            self.assertEqual(ordinary["runtime"]["staged"],shift["runtime"]["staged"])
            for arm in study.ARMS:
                self.assertEqual(ordinary["arms"][arm]["terminal"]["program_id"],
                                 shift["arms"][arm]["terminal"]["program_id"])
                self.assertEqual(128,ordinary["arms"][arm]["terminal"]["correct"]+
                                     shift["arms"][arm]["terminal"]["correct"])

    def test_gates_do_not_claim_oaie_or_open_world_safety(self):
        for k in ("candidate_deployed","oaie_established","open_world_safe","compute_matched",
                  "evaluation_independently_sealed"):
            self.assertIs(self.result[k],False)
        self.assertIs(self.result["gates"]["G4_safe_open_world"],False)
        self.assertEqual("NOT_ASSESSED",self.result["scientific_status"])
        self.assertEqual("BLOCK_RELEASE",self.result["release_decision"])

    def test_same_experiment_exact_bytes_twice(self):
        self.assertEqual(self.raw,study.canonical(study.experiment()))

    def test_independent_against_source_full_replay(self):
        self.assertEqual("PASS_PUBLIC_REPLAY_ONLY",verifier.validate(self.raw)["status"])

    def test_tamper_candidate_result_is_rejected(self):
        fake=copy.deepcopy(self.result)
        fake["nominal"][0]["arms"]["composition"]["terminal"]["correct"]+=1
        with self.assertRaises(verifier.EvidenceError):
            verifier.validate(study.canonical(fake))

    def test_tamper_baseline_cannot_create_false_progress(self):
        fake=copy.deepcopy(self.result)
        fake["totals"]["arm_correct"]["fixed_product"]-=1
        with self.assertRaises(verifier.EvidenceError):
            verifier.validate(study.canonical(fake))

    def test_bool_as_int_and_false_science_claim_rejected(self):
        fake=copy.deepcopy(self.result)
        fake["candidate_deployed"]=0
        with self.assertRaises(verifier.EvidenceError):
            verifier.validate(study.canonical(fake))
        fake=copy.deepcopy(self.result)
        fake["scientific_status"]="ACCEPTED"
        with self.assertRaises(verifier.EvidenceError):
            verifier.validate(study.canonical(fake))

    def test_bad_source_and_prescore_rejected(self):
        for field in ("pre_score_commit","base_source_sha"):
            fake=copy.deepcopy(self.result)
            fake[field]="0"*40
            with self.assertRaises(verifier.EvidenceError):
                verifier.validate(study.canonical(fake))


if __name__=="__main__":
    unittest.main()
