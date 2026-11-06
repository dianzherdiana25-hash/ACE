"""Reproducibility and adversarial tamper suite for R1 H6."""
import copy
import json
import unittest

try:
    from . import h6_distinguish as h6
    from . import audit_h6 as audit
except ImportError:
    import h6_distinguish as h6
    import audit_h6 as audit


class H6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = h6.run()

    def test_pool_size_and_train_indistinguishability(self):
        self.assertEqual(len(h6.query_pool()),1984)
        for b in h6.BASES:
            for trig in h6.TRIGGERS:
                for s in h6.binary_words(0,5):
                    self.assertEqual(h6.mechanism(b,s,None), h6.mechanism(b,s,trig))

    def test_all_worlds_and_oracle_budget(self):
        self.assertEqual(len(self.report['worlds']),80)
        self.assertEqual(self.report['additional_query_oracle_labels'],256)
        self.assertEqual(sum(x['oracle_queries'] for x in self.report['scores'].values()),240)

    def test_active_identifies_both_worlds(self):
        self.assertEqual(self.report['scores']['active']['correct_identification'],80)
        self.assertEqual(self.report['scores']['active']['abstentions'],0)
        self.assertEqual(self.report['scores']['active']['decided_holdout_correct'],20480)

    def test_random_controls_expose_no_unique_search_gain(self):
        self.assertEqual(self.report['scores']['uniform']['correct_identification'],10)
        self.assertEqual(self.report['scores']['uniform']['abstentions'],70)
        self.assertEqual(self.report['scores']['random_disagreement']['correct_identification'],80)

    def test_late_switch_abstains(self):
        c=self.report['controls']['late_indistinguishable']
        self.assertEqual(len(c),8)
        self.assertTrue(all(x['abstained'] for x in c))

    def test_unmodelled_primitive_gives_false_acceptance(self):
        c=self.report['controls']['misspecified_open_world']
        self.assertEqual(len(c),8)
        self.assertTrue(all(x['false_acceptance'] and x['decision']=='H0' for x in c))
        self.assertFalse(self.report['gates']['overall_go'])

    def test_repeated_run_byte_deterministic(self):
        a=json.dumps(self.report,sort_keys=True)
        b=json.dumps(h6.run(),sort_keys=True)
        self.assertEqual(a,b)

    def test_independent_replay_all_worlds(self):
        self.assertEqual(audit.audit(self.report)['world_method_score_cells'],240)

    def test_tampered_oracle_rejected(self):
        r=copy.deepcopy(self.report)
        r['worlds'][0]['trials']['active']['oracle_label'] ^= 1
        with self.assertRaises(AssertionError): audit.audit(r)

    def test_tampered_decision_rejected(self):
        r=copy.deepcopy(self.report)
        r['worlds'][1]['trials']['uniform']['decision']='H1'
        with self.assertRaises(AssertionError): audit.audit(r)

    def test_tampered_holdout_rejected(self):
        r=copy.deepcopy(self.report)
        r['worlds'][0]['trials']['active']['holdout_correct_if_decided']-=1
        with self.assertRaises(AssertionError): audit.audit(r)

    def test_tampered_aggregate_gate_rejected(self):
        r=copy.deepcopy(self.report)
        r['gates']['overall_go']=True
        with self.assertRaises(AssertionError): audit.audit(r)


if __name__=='__main__':unittest.main()
