"""Compact replay proof tests, including corrupted-report rejection."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .e14_shared_budget import BudgetContractError
from .e14w_study import run,IN_FAMILY_EXPRESSIONS
from .e14x_replay import verify

class ReplayOfIndistinguishableWorlds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report=run(pair_indices=(0,),kinds=(IN_FAMILY_EXPRESSIONS[0],),modes=('synthesis-safe',))
        digest=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        cls.report={**report,'sha256':digest}
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.path=Path(cls.temp.name)/'world.json'
        cls.path.write_text(json.dumps(cls.report,sort_keys=True))

    def test_replay_catches_exact_wrong_acceptance(self):
        result=verify([self.path])
        self.assertEqual(result['original_certificates'],1)
        self.assertEqual((result['replay_pass'],result['replay_fail']),(1,0))
        self.assertEqual(result['passed'][0]['adversarial_wrong_accepted'],True)

    def test_same_countermodel_replay_is_deterministic(self):
        self.assertEqual(verify([self.path]),verify([self.path]))

    def test_corrupted_report_blocks_before_oracle_calls(self):
        bad=copy.deepcopy(self.report);bad['rows'][0]['semantic_exact']=0
        with tempfile.TemporaryDirectory() as home:
            path=Path(home)/'forged.json';path.write_text(json.dumps(bad))
            with self.assertRaises(BudgetContractError):verify([path])

if __name__=='__main__':unittest.main()
