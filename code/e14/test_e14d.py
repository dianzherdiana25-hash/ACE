"""Structural and source-only tests; they must pass before scoring E1.4d."""
import unittest
from unittest.mock import patch
from e13.contract import canonical_json
from e13.evaluator.selection import input_key
from .e14d_bank import bank,pairs,pools,grammar5,POOL_SEED,_prior_inputs
from .e14d_policy import fit5,context,learn,choose_context,minimax_index,ABSTAIN
from .cross_episode_candidate import predict
from .query_bank import oracle

class E14dPrelockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.items=bank()
    def test_pool_word_independence_and_no_oracle_calls(self):
        with patch('e14.e14d_bank.oracle',side_effect=AssertionError('oracle from pool')):
            a=pools(_prior_inputs())
            b=pools(_prior_inputs())
        self.assertEqual(canonical_json(a if False else list(a.values())),canonical_json(list(b.values())))
        self.assertEqual(len(a),24)
    def test_role_word_disjointness_and_fresh_inputs(self):
        self.assertEqual(len(self.items),12)
        used=_prior_inputs()
        words={'S':set(),'G':set()}
        for source,target in self.items:
            self.assertNotEqual(source.word,target.word)
            for t in (source,target):
                self.assertEqual(len(t.word),5)
                self.assertNotIn(t.word,words[t.family]);words[t.family].add(t.word)
                self.assertEqual(len(t.pool),len(t.probes))
                for raw in [*(x['input'] for x in t.demos),*t.pool,*(p['input'] for p in t.probes)]:
                    key=input_key(t.family,raw)
                    self.assertNotIn(key,used[t.family]);used[t.family].add(key)
                for p in (*t.demos,*t.probes):
                    self.assertEqual(predict(t.family,t.word,p['input']),p['output'])
            diff=sum(x!=y for x,y in zip(source.word,target.word))
            self.assertEqual(source.regime=='related',diff==1)
    def test_source_policy_no_evaluator_during_fit_and_select(self):
        s=self.items[0][0]
        with patch('e14.e14d_bank.oracle',side_effect=AssertionError('oracle')):
            c=fit5(s.family,s.demos)
            result=choose_context(s.family,c,s.pool,{'fallback':'first_disagreement'},141804)
            self.assertIn(result['labels'],(0,1))
    def test_abstain_when_resolved_even_if_learned_selector(self):
        s=self.items[0][0]
        action=choose_context(s.family,(s.word,),s.pool,{'fallback':'first_disagreement'},0)
        self.assertEqual((action['policy'],action['labels']),(ABSTAIN,0))
    def test_learn_never_uses_target_results(self):
        sample=[]
        for family in ('S','G'):
            for _ in range(6):
                sample.append({'family':family,'bucket':'high_ambiguity','no_label':2,
                               'policy_scores':{p:8 if p=='last_disagreement' else 2
                                                for p in ('first_disagreement','last_disagreement',
                                                'short_disagreement','long_disagreement','max_partition',
                                                'min_partition','seeded_disagreement','seeded_uniform')}})
        self.assertEqual(learn(sample,'S')['mapping']['high_ambiguity'],'last_disagreement')
        self.assertEqual(learn(sample,'G')['mapping']['high_ambiguity'],'last_disagreement')
    def test_minimax_is_unlabeled_and_deterministic(self):
        s=self.items[0][0]
        c=fit5(s.family,s.demos)
        with patch("e14.e14d_bank.oracle",side_effect=AssertionError("oracle")):
            a=minimax_index(s.family,c,s.pool)
            b=minimax_index(s.family,c,s.pool)
        self.assertEqual(a,b)
        self.assertTrue(0<=a<8)
    def test_human_known_grammar_limit(self):
        self.assertEqual((len(grammar5('S')),len(grammar5('G'))),(243,48))

if __name__=='__main__':unittest.main()
