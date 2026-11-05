"""Portfolio replay negative-path test against original E1.5 portfolio.py."""
from __future__ import annotations
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class FlatAdapter:
    """No policy improves validation: exercise selected=None."""
    def __init__(self, *, outsiders_per_split=0):
        self.outsiders_per_split = outsiders_per_split

    def bank_manifest(self):
        return {'redteam': 'flat synthetic', 'outsiders_per_split': self.outsiders_per_split}

    def evaluate(self, policy, split):
        return {'worlds': 1, 'accepted_correct': 0, 'accepted_wrong': 0,
                'abstained': 1, 'logical_labels': 1, 'probe_errors': 0,
                'utility_units': -3}


class PortfolioRedTeam(unittest.TestCase):
    @unittest.expectedFailure
    def test_rt10_no_gain_allocation_is_idempotent_on_resume(self):
        """P2: valid null allocation is rejected by selected not in engines."""
        stub = types.ModuleType('ace_loop.operators')
        stub.OperatorAdapter = FlatAdapter
        with patch.dict(sys.modules, {'ace_loop.operators': stub}):
            module = importlib.import_module('ace_loop.portfolio')
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'OperatorAdapter', FlatAdapter):
            root = Path(tmp)
            first = module.run_portfolio(root, pilot_trials=1, total_trials=2)
            self.assertIsNone(first['allocation']['selected'])
            self.assertEqual(first['allocation']['reason'], 'all_tracks_paused_no_gain')
            # The same valid checkpoint must be replayable, not an integrity HALT.
            again = module.run_portfolio(root, pilot_trials=1, total_trials=2)
            self.assertEqual(first, again)


if __name__ == '__main__':
    unittest.main()
