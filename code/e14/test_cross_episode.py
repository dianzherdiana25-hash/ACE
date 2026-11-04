"""Pre-score tests for E1.4c bank integrity, strict source/target separation and policies."""

import json
import unittest
from collections import Counter
from unittest.mock import patch

from e13.contract import canonical_json
from e14.query_bank import oracle
from .cross_episode_bank import _pairs, _distance, bank, digest
from .cross_episode_candidate import POLICIES, choose, fit, inventory, predict
from .cross_episode import select_inherited, decide


class CrossEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs=bank()

    def test_disjoint_new_rules_and_input_roles(self):
        self.assertEqual(len(self.pairs),12)
        self.assertEqual(Counter(x.family for x,_ in self.pairs),{"S":6,"G":6})
        for family in ("S","G"):
            rules=[w for pair in _pairs(family) for w in pair[1:]]
            self.assertEqual(len(set(rules)),12)
            self.assertTrue(all(len(w)==4 for w in rules))
        identities=set()
        for source,target in self.pairs:
            self.assertNotEqual(source.word,target.word)
            self.assertEqual(source.regime,target.regime)
            d=_distance(source.word,target.word)
            self.assertEqual(d==1,source.regime=="related")
            a=[source,target]
            for task in a:
                self.assertNotIn(task.task_id,identities)
                identities.add(task.task_id)
                self.assertEqual(len(task.demos),2)
                self.assertEqual(len(task.pool),8)
                self.assertEqual(len(task.probes),8)
                keys=[canonical_json(x["input"]) for x in (*task.demos,*task.probes)]
                keys.extend(canonical_json(x) for x in task.pool)
                self.assertEqual(len(set(keys)),len(keys))
                self.assertTrue(all(oracle(task.family,task.word,x["input"])==x["output"]
                                    for x in (*task.demos,*task.probes)))
        self.assertEqual(digest(self.pairs),digest(bank()))
        from e14.query_bank import bank as old_pilot
        from e14.query_replication import bank as old_replication
        for family in ("S","G"):
            older={c.word for c in (*old_pilot(),*old_replication())
                   if c.episode.family==family}
            recent={t.word for pair in self.pairs for t in pair if t.family==family}
            self.assertFalse(older.intersection(recent))

    def test_candidate_predict_agrees_with_separate_evaluator_on_public_rules(self):
        for source,target in self.pairs:
            for task in (source,target):
                for example in (*task.demos,*task.probes):
                    self.assertEqual(predict(task.family,task.word,example["input"]),
                                     oracle(task.family,task.word,example["input"]))

    def test_question_selection_does_not_call_oracle(self):
        for source,_ in self.pairs[:2]:
            candidates,_=fit(source.family,source.demos)
            with patch("e14.cross_episode_bank.oracle",side_effect=AssertionError("oracle forbidden")),\
                 patch("e14.cross_episode.oracle",side_effect=AssertionError("oracle forbidden")):
                for p in POLICIES:
                    index,reason=choose(p,source.family,candidates,source.pool,seed=123)
                    self.assertIn(index,range(8))
                    self.assertIn(reason,("disagreement","no_disagreement","uniform"))

    def test_family_policy_training_reads_only_source_scores(self):
        fake=[]
        for family in ("S","G"):
            for i in range(6):
                fake.append({"family":family,"policies":{p:{"correct":(8 if p=="long_disagreement" else 2)}
                           for p in POLICIES}})
        chosen=select_inherited(fake)
        self.assertEqual(chosen["S"]["policy"],"long_disagreement")
        self.assertEqual(chosen["G"]["policy"],"long_disagreement")
        self.assertEqual(chosen["S"]["source_training_labels"],48)
        self.assertNotEqual(chosen["S"]["sham_policy"],chosen["S"]["policy"])

    def test_gate_requires_all_family_regimes_and_controls(self):
        values=[{"inherited":15,"task_local":14,"sham":14,"uniform_expected":14.5,"no_label":10}
                for _ in range(4)]
        self.assertEqual(decide(values,0),"GO_CROSS_EPISODE_TRANSFER_DEVELOPMENT_ONLY")
        values[0]["task_local"]=15
        self.assertEqual(decide(values,0),"HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS")
        self.assertEqual(decide(values,1),"HOLD_RESOURCE_INTEGRITY")


if __name__=="__main__":
    unittest.main()
