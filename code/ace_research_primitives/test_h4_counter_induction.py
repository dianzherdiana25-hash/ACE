"""ACE R1 H4 tests: reproducible construction, abstention, OOD failure and audit."""
from __future__ import annotations

import copy
import json
import unittest

try:
    from . import h4_counter_induction as h4
    from . import audit_h4 as auditor
    from . import primitive_discovery as d
except ImportError:
    import h4_counter_induction as h4
    import audit_h4 as auditor
    import primitive_discovery as d


class CounterInductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(json.dumps(h4.run_h4()))

    def test_01_all_bank_lengths_and_counts(self):
        self.assertEqual(len(h4.TARGET_NAMES), 12)
        for i,name in enumerate(h4.TARGET_NAMES):
            with self.subTest(name=name):
                words=h4.sample_holdout(name,i)
                self.assertEqual(len(words),48)
                self.assertEqual(len(set(words)),48)
                self.assertTrue(all(len(s)>=8 for s in words))
                self.assertEqual(sum(h4.judge(name,s) for s in words),24)
                self.assertEqual(words,h4.sample_holdout(name,i))
                self.assertFalse(set(words)&set(d.training_words()+d.validation_words()))

    def test_02_counter_is_derived_from_positive_training(self):
        for name,wa,wb in [('equal_counts',1,-1),('a_twice_b',1,-2),
                           ('b_twice_a',2,-1),('a_three_b',1,-3)]:
            with self.subTest(name=name):
                training=[(s,h4.judge(name,s)) for s in d.training_words()]
                result=h4.infer_counter(training)
                self.assertEqual(result['status'],'constructed')
                self.assertEqual((result['model'].w_a,result['model'].w_b),(wa,wb))
                self.assertEqual(result['model'].target,0)
                self.assertEqual(result['model'].guard_kind,'none')

    def test_03_guard_residual_specialization(self):
        guard={'dyck':('min',0),'reverse_dyck':('max',0),
               'a_block_b_block':('forbid','ba'),'b_block_a_block':('forbid','ab')}
        for name,(kind,parameter) in guard.items():
            with self.subTest(name=name):
                examples=[(s,h4.judge(name,s)) for s in d.training_words()]
                fit=h4.infer_counter(examples)
                self.assertEqual(fit['status'],'constructed')
                self.assertEqual(fit['model'].guard_kind,kind)
                self.assertEqual(fit['model'].guard_parameter,parameter)
                self.assertTrue(all(fit['model'].predict(s)==y for s,y in examples))

    def test_04_specificity_rejects_out_of_class(self):
        for name in h4.H4_SPECIFICITY:
            examples=[(s,h4.judge(name,s)) for s in d.training_words()]
            self.assertIsNone(h4.infer_counter(examples)['model'])

    def test_05_same_training_different_late_truth(self):
        self.assertEqual([h4.judge('equal_counts',s) for s in d.training_words()],
                         [h4.judge('late_flip_equal',s) for s in d.training_words()])
        equality=h4.infer_counter([(s,h4.judge('equal_counts',s)) for s in d.training_words()])
        switched=h4.infer_counter([(s,h4.judge('late_flip_equal',s)) for s in d.training_words()])
        self.assertEqual(equality['model'],switched['model'])
        holdout=h4.sample_holdout('late_flip_equal',11)
        self.assertEqual(sum(switched['model'].predict(s)==h4.judge('late_flip_equal',s)
                             for s in holdout),0)

    def test_06_no_train_leak_or_reordering_effect(self):
        samples=[(s,h4.judge('dyck',s)) for s in d.training_words()]
        fwd=h4.infer_counter(samples)
        rev=h4.infer_counter(list(reversed(samples)))
        self.assertEqual(fwd['model'],rev['model'])

    def test_07_input_types_and_duplicate_samples_fail_closed(self):
        for x in [[('c',True)],[('a',1)],[('a',True),('a',True)],
                  [('a',True)]*64,[]]:
            with self.assertRaises(ValueError):
                h4.infer_counter(x)

    def test_08_training_observations_only(self):
        for name in h4.H4_PRIMARY:
            examples=[(s,h4.judge(name,s)) for s in d.training_words()]
            learned=h4.infer_counter(examples)
            self.assertTrue(all(learned['model'].predict(s)==y for s,y in examples))
            self.assertLessEqual(learned['proposal_attempts'],1000)
            self.assertLessEqual(learned['guard_attempts'],1000)

    def test_09_all_primary_h4_gates(self):
        self.assertEqual(self.evidence['synthetic_label_evaluations'],3636)
        self.assertTrue(self.evidence['primary']['h4a_pass'])
        self.assertTrue(self.evidence['primary']['h4b_pass'])
        self.assertEqual(self.evidence['primary']['primary_at_least_90_percent'],8)
        self.assertEqual(self.evidence['primary']['adversarial_correct'],0)
        self.assertEqual(sum(t['scores']['constructed_or_fallback']['holdout']['correct']
                             for t in self.evidence['tasks'][:8]),384)

    def test_10_full_independent_score_audit(self):
        result=auditor.check(self.evidence)
        self.assertEqual(result['audited_tasks'],12)
        self.assertEqual(result['scored_cells'],252)
        self.assertEqual(result['source_labels_recomputed'],3636)

    def test_11_detect_score_tampering(self):
        bad=copy.deepcopy(self.evidence)
        bad['tasks'][0]['scores']['constructed_or_fallback']['holdout']['correct']-=1
        with self.assertRaises(AssertionError):auditor.check(bad)

    def test_12_detect_register_tampering(self):
        bad=copy.deepcopy(self.evidence)
        bad['tasks'][4]['feature']['guard_kind']='none'
        with self.assertRaises(AssertionError):auditor.check(bad)

    def test_13_detect_dfa_tampering(self):
        bad=copy.deepcopy(self.evidence)
        bad['tasks'][0]['rpni_automaton'][0][0]=False
        with self.assertRaises(AssertionError):auditor.check(bad)

    def test_14_detect_holdout_hash_tampering(self):
        bad=copy.deepcopy(self.evidence)
        bad['tasks'][0]['data_hash']['holdout']='0'*64
        with self.assertRaises(AssertionError):auditor.check(bad)

    def test_15_detect_gate_tampering(self):
        bad=copy.deepcopy(self.evidence)
        bad['primary']['adversarial_correct']=48
        with self.assertRaises(AssertionError):auditor.check(bad)

    def test_16_long_runtime_strings_beyond_train_budget(self):
        m=h4.infer_counter([(s,h4.judge('equal_counts',s)) for s in d.training_words()])['model']
        for n in (100,1000,5000):
            self.assertTrue(m.predict('a'*n+'b'*n))
            self.assertFalse(m.predict('a'*(n+1)+'b'*n))


if __name__=='__main__':unittest.main()
