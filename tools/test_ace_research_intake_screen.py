"""Coordinator science intake: test independent generator and locked reporting."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import unittest

from tools import ace_research_intake_screen as s


class IndependentDfaIntakeTests(unittest.TestCase):
    def test_train_is_full_binary_prefix_bank(self):
        t=s.train_words()
        self.assertEqual(63,len(t))
        self.assertEqual(63,len(set(t)))
        self.assertEqual("",t[0])
        self.assertTrue(all(len(w)<=5 for w in t))

    def test_generator_reproducible_and_source_reachable(self):
        a=s.new_targets()
        self.assertEqual(a,s.new_targets())
        self.assertEqual(24,len(a))
        self.assertEqual([6]*6+[8]*6+[10]*6+[12]*6,
                         [r["nominal_states"] for r in a])
        sigs=set()
        for r in a:
            self.assertEqual(r["nominal_states"],s.reachable(r["target"]))
            sig=tuple(s.truth(r["target"],w) for w in s.train_words())
            self.assertTrue(.2 <= sum(sig)/63 <= .8)
            self.assertNotIn(sig,sigs)
            sigs.add(sig)
            self.assertLess(r["draw_attempt"],s.MAX_DRAWS)

    def test_holdout_is_new_and_repeatable(self):
        for i in range(24):
            a=s.holdout_words(i)
            self.assertEqual(256,len(a))
            self.assertEqual(256,len(set(a)))
            self.assertEqual(a,s.holdout_words(i))
            self.assertFalse(set(a)&set(s.train_words()))
            self.assertTrue(all(12<=len(x)<=20 for x in a))
        self.assertNotEqual(s.holdout_words(0),s.holdout_words(1))

    def test_counterfactual_indistinguishability(self):
        target=s.new_targets()[0]["target"]
        examples=[(w,s.truth(target,w)) for w in s.train_words()]
        stable=[s.truth(target,w) for w in s.holdout_words(0)]
        drift=[not y for y in stable]
        self.assertTrue(all(len(w)<=5 for w,_ in examples))
        self.assertTrue(all(len(w)>11 for w in s.holdout_words(0)))
        self.assertTrue(all(x!=y for x,y in zip(stable,drift)))

    def test_canonical_json_replay_is_deterministic(self):
        report={"x":[3,2,1],"y":True}
        self.assertEqual(s.canonical(report),s.canonical(json.loads(s.canonical(report))))
        self.assertTrue(s.sample_digest(["a"])!=s.sample_digest(["b"]))

    def test_induction_and_evidence_metrics_with_pinned_source(self):
        from ace_research_primitives import primitive_discovery as d
        report, runtime=s.evaluate(d)
        self.assertEqual(24,len(report["tasks"]))
        self.assertEqual(7656,report["label_budget"]["total_unique"])
        self.assertEqual("NOT_ASSESSED_NO_AUTOMATIC_PROMOTION",
                         report["scientific_decision"])
        for row in report["tasks"]:
            self.assertTrue(all(row[arm]["correct"]["induced"]<=256
                                for arm in ("clean","one_flip")))
            self.assertEqual(256,row["indistinguishable_drift"]["forced_predictions"])
            self.assertEqual(0,row["indistinguishable_drift"]["abstentions"])
            self.assertEqual(256-row["clean"]["correct"]["induced"],
                             row["indistinguishable_drift"]["correct_under_inversion"])
        self.assertFalse(report["predeclared_gates"]["semantic_shift_safe_transfer"])
        self.assertTrue(runtime["nondeterministic_runtime_not_in_evidence_hash"])


if __name__=="__main__":
    unittest.main()
