"""Bounded structural-mutation integration and falsification tests."""
from __future__ import annotations
import copy
from unittest.mock import patch
import unittest

from . import structural as s, verify_structural as verifier


class StructuralResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ace_research_primitives import primitive_discovery as r1
        from ace_candidate_search import model
        cls.r1,cls.model=r1,model
        cls.result=s.evaluate(r1,model)
        cls.raw=s.canonical(cls.result)

    def test_grammar_canonical_coprime_and_excludes_ratio4(self):
        ratios=s.coefficient_grammar()
        self.assertEqual(7,len(ratios))
        self.assertIn((1,-1),ratios)
        self.assertIn((1,-2),ratios)
        self.assertIn((1,-3),ratios)
        self.assertNotIn((1,-4),ratios)
        self.assertTrue(all(abs(__import__("math").gcd(*x))==1 for x in ratios))

    def test_s2_closed_typed_ast(self):
        expr=s.typed_ast(self.model,(1,-3))
        self.assertLessEqual(expr.operations,3)
        self.assertTrue(type(expr.identity) is str and len(expr.identity)==64)
        self.assertEqual(0,self.model.interpret(expr,9,3,self.model.Meter(100)))
        self.assertNotEqual(0,self.model.interpret(expr,9,2,self.model.Meter(100)))

    def test_split_label_budget_and_disjointness(self):
        for idx,task in enumerate(s.TASKS):
            bank=s.bank(task,idx)
            self.assertEqual([63,256,256],[len(bank[p]) for p in ("train","validation","terminal")])
            sets=[{w for w,_ in bank[p]} for p in ("train","validation","terminal")]
            self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
            for part in ("validation","terminal"):
                self.assertEqual(128,sum(y for _,y in bank[part]))

    def test_hidden_shift_has_identical_observable_labels(self):
        stable=s.bank("three_to_one",3)
        drift=s.bank(s.CONTROL,3)
        self.assertEqual(stable["train"],drift["train"])
        self.assertEqual(stable["validation"],drift["validation"])
        self.assertEqual([w for w,_ in stable["terminal"]],[w for w,_ in drift["terminal"]])
        self.assertTrue(all(x!=y for (_,x),(_,y) in zip(
            stable["terminal"],drift["terminal"])))

    def test_seven_worlds_and_three_generations(self):
        self.assertEqual([0,1,2],[g["generation"] for g in self.result["generations"]])
        self.assertEqual(6,len(self.result["tasks"]))
        self.assertEqual(1,int(self.result["hidden_drift"]["task"]==s.CONTROL))
        self.assertEqual(4025,self.result["limits"]["total_task_specific_labels"])
        self.assertEqual(1792,self.result["limits"]["terminal_labels_not_available_to_selection"])

    def test_frozen_old_models_not_refit_after_g2(self):
        before=[r for r in self.result["generations"][1]["retention"]]
        after=[r for r in self.result["generations"][2]["retention"]]
        for earlier in before:
            self.assertIn(earlier,after)
            self.assertIs(earlier["retrained"],False)

    def test_evidence_is_nontechnical_science_go(self):
        self.assertEqual("NOT_ASSESSED",self.result["scientific_decision"])
        self.assertEqual("BLOCK_RELEASE",self.result["release_decision"])
        self.assertIs(self.result["candidate_deployed"],False)
        self.assertIs(self.result["oaie_established"],False)
        self.assertIs(self.result["true_primitive_type_invention"],False)
        self.assertIs(self.result["unconditional_open_world_safety"],False)

    def test_terminal_not_used_to_stage(self):
        original=s.fit("three_to_one",3,self.r1,self.model)
        baseline=s.bank("three_to_one",3)
        alternate=copy.deepcopy(baseline)
        alternate["terminal"]=[(w,not label) for w,label in baseline["terminal"]]
        with patch.object(s,"bank",return_value=alternate):
            shifted=s.fit("three_to_one",3,self.r1,self.model)
        for key in ("staged","selected_model_sha256","selected_val_correct",
                    "validation_gain_over_best_finite"):
            self.assertEqual(original["report"][key],shifted["report"][key])

    def test_no_terminal_truth_in_staging_record(self):
        for row in self.result["tasks"]:
            self.assertEqual(64,len(row["selected_model_sha256"]))
            self.assertIs(type(row["staged"]),bool)
            self.assertLessEqual(row["candidate_count"],7)
            self.assertLessEqual(row["shortlist_count"],3)
            self.assertEqual(256,row["validation_total"])
            self.assertTrue(row["counter_train_node_work"]>=0)
            self.assertTrue(row["counter_validation_node_work"]>=0)
            self.assertIn(row["representation"],("COUNTER_REGISTER","NO_MUTATION"))

    def test_deterministic_public_replay(self):
        replay=s.evaluate(self.r1,self.model)
        self.assertEqual(self.raw,s.canonical(replay))

    def test_verified_exact_public_evidence(self):
        receipt=verifier.verify_bytes(self.raw,self.r1,self.model)
        self.assertEqual("PASS_PUBLIC_EXACT_REPLAY_NOT_SCIENTIFIC_GO",receipt["status"])

    def test_forged_candidate_selection_rejected(self):
        bad=copy.deepcopy(self.result)
        bad["tasks"][0]["staged"]=not bad["tasks"][0]["staged"]
        with self.assertRaises(verifier.IntegrityError):
            verifier.verify_bytes(s.canonical(bad),self.r1,self.model)

    def test_terminal_fake_score_rejected(self):
        bad=copy.deepcopy(self.result)
        bad["tasks"][0]["terminal"]["counter_correct"]+=1
        with self.assertRaises(verifier.IntegrityError):
            verifier.verify_bytes(s.canonical(bad),self.r1,self.model)

    def test_bool_int_alias_rejected(self):
        bad=copy.deepcopy(self.result)
        bad["candidate_deployed"]=0
        with self.assertRaises(verifier.IntegrityError):
            verifier.verify_bytes(s.canonical(bad),self.r1,self.model)

    def test_false_open_world_promotion_rejected(self):
        bad=copy.deepcopy(self.result)
        bad["unconditional_open_world_safety"]=True
        with self.assertRaises(verifier.IntegrityError):
            verifier.verify_bytes(s.canonical(bad),self.r1,self.model)

    def test_forged_source_sha_rejected(self):
        bad=copy.deepcopy(self.result)
        bad["source_heads"]["R1"]="0"*40
        with self.assertRaises(verifier.IntegrityError):
            verifier.verify_bytes(s.canonical(bad),self.r1,self.model)


if __name__=="__main__":
    unittest.main()
