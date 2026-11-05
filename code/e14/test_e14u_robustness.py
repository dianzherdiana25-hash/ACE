"""Nonconfirmatory sensitivity tests; never infer independent generalization."""
import unittest
from . import e14u_dev
from . import e14u_robustness as robustness

class E14URobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=e14u_dev.SEED
        original=robustness.SEEDS
        try:
            robustness.SEEDS=original[:1]
            cls.report=robustness.evaluate()
        finally:
            robustness.SEEDS=original

    def test_all_postdevelopment_trials_have_explicit_scope(self):
        self.assertEqual(len(self.report['trials']),1)
        self.assertEqual(self.report['status'],'POST_DEVELOPMENT_SENSITIVITY_ONLY')
        self.assertEqual([r['seed'] for r in self.report['trials']],list(robustness.SEEDS[:1]))
        self.assertTrue(all(r['worlds']==28 and r['arms']==112 for r in self.report['trials']))

    def test_all_purchased_labels_within_four_per_world(self):
        self.assertEqual(e14u_dev.SEED,self.original)
        for trial in self.report['trials']:
            for arm in e14u_dev.MODES:
                self.assertLessEqual(trial['summary'][arm]['purchased'],4*28)
                self.assertEqual(trial['summary'][arm]['wrong_accepted'],0)

if __name__=='__main__':unittest.main()
