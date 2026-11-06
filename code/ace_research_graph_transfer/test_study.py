"""Fail-closed cross-family graph transfer tests with actual ACE engine."""
from __future__ import annotations

import copy
import itertools
import unittest

from . import study as s, verify_evidence as verification


class GraphTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=s.experiment()
        cls.encoded=s.canonical(cls.report)

    def test_graph_encoding_is_lossless_and_typed(self):
        for n in (4,5,7):
            for bits in (0,(1<<s.edge_count(n))-1,21):
                bits%=1<<s.edge_count(n)
                w="".join("a" if bits>>k&1 else "b" for k in range(s.edge_count(n)))
                self.assertEqual(w,s.encode(s.decode(w)))
                self.assertEqual(n,s.size_for(w))
        with self.assertRaises(ValueError):
            s.decode("a"*99)
        with self.assertRaises(ValueError):
            s.decode("a"*21+"x")
        with self.assertRaises(ValueError):
            s.encode([[1,0],[0,1]])

    def test_two_native_candidates_have_independent_exact_oracle(self):
        for n in (4,5):
            for word in s.all_words(n):
                self.assertEqual(s.truth("undirected_st_connectivity",word),
                                 s.native_model("bfs_reachability",word)[0])
                self.assertEqual(s.truth("undirected_bipartite",word),
                                 s.native_model("bfs_bipartite",word)[0])

    def test_balanced_disjoint_split_and_exact_graph_budget(self):
        for seed in s.SEEDS:
            for family in s.FAMILIES:
                data=s.bank(family,seed)
                self.assertEqual([16,64,128],[len(data[k]) for k in ("train","validation","terminal")])
                self.assertEqual([8,32,64],[sum(y for _,y in data[k]) for k in ("train","validation","terminal")])
                sets=[{word for word,_ in data[k]} for k in ("train","validation","terminal")]
                self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
                for p,k in (("train",6),("validation",10),("terminal",21)):
                    self.assertTrue(all(len(word)==k for word,_ in data[p]))
                self.assertEqual(64,len(data["pairs"]))

    def test_all_terminal_permutations_are_isomorphic_and_label_preserving(self):
        for seed in s.SEEDS:
            for family in s.FAMILIES:
                data=s.bank(family,seed)
                for i,j in data["pairs"]:
                    self.assertEqual(data["terminal"][i][1],data["terminal"][j][1])
                    self.assertNotEqual(data["terminal"][i][0],data["terminal"][j][0])
                self.assertEqual(128,len({word for word,_ in data["terminal"]}))

    def test_fixed_native_selector_does_not_receive_task_identity(self):
        for seed in s.SEEDS:
            for family in s.FAMILIES:
                data=s.bank(family,seed)
                selected,inventory=s.fit_graph_library(data["train"],data["validation"])
                self.assertEqual(2,len(inventory))
                self.assertEqual(16,selected["training_correct"])
                self.assertEqual(64,selected["validation_correct"])
                self.assertEqual(s.NATIVE[s.FAMILIES.index(family)],selected["kind"])

    def test_no_output_claims_invention_or_safe_release(self):
        for key in ("oaie_established","compute_matched","independent_evaluator_sealed",
                    "candidate_deployed","graph_task_native_interface_in_core_ACE"):
            self.assertIs(self.report[key],False)
        self.assertIs(self.report["native_programs_are_researcher_supplied"],True)
        self.assertIs(self.report["gates"]["T4_ACE_invented_graph_method"],False)
        self.assertIs(self.report["gates"]["T5_safe_cross_task_reuse_without_validation"],False)
        self.assertEqual("NOT_ASSESSED",self.report["scientific_status"])
        self.assertEqual("BLOCK_RELEASE",self.report["release_decision"])

    def test_unsupported_runtime_models_have_no_fictitious_evaluation(self):
        self.assertEqual(4,len(self.report["trials"]))
        self.assertEqual(832,self.report["label_budget"]["total_presentations"])
        for trial in self.report["trials"]:
            outcome=trial["runtime"]
            if outcome["staged"]:
                self.assertIsNotNone(outcome["terminal"])
                self.assertEqual(128,outcome["terminal"]["total"])
            else:
                self.assertIsNone(outcome["terminal"])
            self.assertEqual(128,trial["native_oracle"]["correct"])
            self.assertEqual(128,trial["graph_selector"]["terminal_total"])
            self.assertEqual(64,trial["graph_selector"]["permutation_agree_pairs"])

    def test_native_graph_versus_other_task_semantics_disagree(self):
        self.assertGreater(self.report["totals"]["task_identity_swap_disagreements"],0)

    def test_two_full_evaluations_are_byte_identical(self):
        self.assertEqual(self.encoded,s.canonical(s.experiment()))

    def test_verifier_replays_all_trials_on_frozen_ace_source(self):
        self.assertEqual("PASS_EXACT_SOURCE_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO",
                         verification.verify(self.encoded)["status"])

    def test_terminal_forgery_is_rejected(self):
        forged=copy.deepcopy(self.report)
        forged["trials"][0]["source"]["composition"]["terminal_correct"]+=1
        with self.assertRaises(verification.EvidenceError):
            verification.verify(s.canonical(forged))

    def test_forged_baseline_and_coverage_are_rejected(self):
        for target in ("fixed_product","dfa"):
            forged=copy.deepcopy(self.report)
            forged["totals"]["source_terminal_correct"][target]-=1
            with self.assertRaises(verification.EvidenceError):
                verification.verify(s.canonical(forged))
        forged=copy.deepcopy(self.report)
        forged["totals"]["runtime_admitted_worlds"]+=1
        with self.assertRaises(verification.EvidenceError):
            verification.verify(s.canonical(forged))

    def test_permutation_invariance_forgery_rejected(self):
        forged=copy.deepcopy(self.report)
        forged["trials"][0]["graph_selector"]["permutation_agree_pairs"]-=1
        with self.assertRaises(verification.EvidenceError):
            verification.verify(s.canonical(forged))

    def test_source_pin_and_reviewer_custody_forgery_rejected(self):
        forged=copy.deepcopy(self.report)
        forged["source_main_sha"]="0"*40
        with self.assertRaises(verification.EvidenceError):
            verification.verify(s.canonical(forged))
        forged=copy.deepcopy(self.report)
        forged["independent_evaluator_sealed"]=True
        with self.assertRaises(verification.EvidenceError):
            verification.verify(s.canonical(forged))

    def test_boolean_alias_and_unsafe_promotion_rejected(self):
        for key,value in (("candidate_deployed",0),("oaie_established",True),
                          ("release_decision","GO")):
            forged=copy.deepcopy(self.report)
            forged[key]=value
            with self.assertRaises(verification.EvidenceError):
                verification.verify(s.canonical(forged))

    def test_train_validation_cannot_share_graphs(self):
        from ace_runtime.engine import validate_task
        row=("a"*6,True)
        with self.assertRaises(ValueError):
            validate_task({"name":"bad","train":[row],"validation":[row]})


if __name__=="__main__":
    unittest.main()
