"""Non-anticipating coordinator cross-class H7 test guards."""
from __future__ import annotations
import unittest
from tools import ace_research_intake_h7 as x


class H7CrossClassTests(unittest.TestCase):
    def test_bank_seed_and_syntactic_constraints(self):
        rows=x.targets()
        self.assertEqual(rows,x.targets())
        self.assertEqual(24,len(rows))
        self.assertEqual([5,5,6,6,7,7]*4,[r['length'] for r in rows])
        for r in rows:
            self.assertGreaterEqual(r['pattern'].count('a'),2)
            self.assertGreaterEqual(r['pattern'].count('b'),2)
            self.assertLess(r['draw'],10000)
            self.assertEqual(r['length'],len(r['pattern']))
        for i in range(0,24,2):
            self.assertNotEqual(rows[i]['pattern'],rows[i+1]['pattern'])

    def test_terminal_splits_and_balanced_absence_of_leakage(self):
        for item in x.targets():
            train,val,natural,balanced,attempts=x.splits(item['id'],item['pattern'])
            self.assertEqual((len(train),len(val),len(natural),len(balanced)),
                             (128,128,256,256))
            self.assertEqual(len(set(train+val+natural+balanced)),768)
            self.assertEqual(128,sum(item['pattern'] in w for w in balanced))
            self.assertLessEqual(attempts,x.MAX_ATTEMPTS)
            self.assertEqual(x.splits(item['id'],item['pattern'])[0],train)

    def test_expanded_no_fabricated_feature_without_support(self):
        train=[('aaaabbbb',False),('bbbbaaaa',False)]
        val=[('aabbaa',False),('bbabab',False)]
        got=x.expanded_fit(train,val)
        self.assertFalse(got['accepted'])
        self.assertIsNone(got['pattern'])

    def test_balanced_metric_sensitive_to_positive_errors(self):
        hold=['aaaaa','bbbbb']
        self.assertEqual(1,x.score_pattern(None,hold,'aaaaa')['correct'])
        self.assertEqual(2,x.score_pattern('aaaaa',hold,'aaaaa')['correct'])
        self.assertEqual(0,x.score_pattern('bbbbb',hold,'aaaaa')['correct'])

    def test_full_exact_pinned_source_and_open_world_gate(self):
        from ace_research_primitives import h7_residual_memory as source
        report=x.evaluate(source)
        self.assertEqual(24,len(report['rows']))
        self.assertEqual('NOT_ASSESSED_NO_PROMOTION',report['scientific_decision'])
        self.assertEqual(18432,report['label_budget']['total_task_specific_judgments'])
        self.assertEqual(12288,report['label_budget']['terminal_reporting'])
        self.assertEqual(12288,report['summary']['total_forced_final_predictions'])
        self.assertFalse(report['summary']['precommitted_gates']['G4_open_world_safe_to_deploy'])
        self.assertEqual(['5','6','7'],list(report['summary']['by_length']))
        for r in report['rows']:
            self.assertEqual(128,r['methods']['base']['balanced']['correct'])
            self.assertEqual(0,r['semantic_final_abstentions'])
            self.assertEqual(512,r['forced_final_predictions'])

    def test_canonical_evidence_hash_stable(self):
        self.assertEqual(x.canonical({'b':2,'a':1}),x.canonical({'a':1,'b':2}))


if __name__=='__main__':
    unittest.main()
