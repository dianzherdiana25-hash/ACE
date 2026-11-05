from pathlib import Path
import tempfile
import unittest

from .e14aa_bank import build, canonical
from .e14aa_study import run_arm, QUERY_GRID, PROBE_GRID, GRID, truth_at, production_value, study
from .e14aa_oracle import value
from .e14y_induction import base_ast
from .e14_shared_budget import BudgetContractError


class OnlineStudyIntegrationTests(unittest.TestCase):
    def test_target_split_and_public_bank_determinism(self):
        self.assertEqual(set(QUERY_GRID) | set(PROBE_GRID), set(GRID))
        self.assertFalse(set(QUERY_GRID) & set(PROBE_GRID))
        self.assertEqual(canonical(build()), canonical(build()))
        self.assertEqual(build()['expected_arms'], 192)

    def test_delayed_drift_and_fresh_receipt_replay(self):
        row = {'id': 'aa:999', 'source': {'terms': []}}
        src = {'selected_ast': base_ast(), 'source_labels': 12}
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            result = run_arm(row, src, 18, 'delayed', 'online-random', Path(a))
            replay = run_arm(row, src, 18, 'delayed', 'online-random', Path(b))
            self.assertEqual(canonical(result), canonical(replay))
            self.assertEqual(result['target_labels'], 4)
            self.assertEqual(result['events'][1]['decision'], 'accept_conditional')
            for event in result['events']:
                if event['drift_detected']:
                    self.assertEqual(event['accepted'], 0)
            frozen = run_arm(row, src, 18, 'delayed', 'frozen2', Path(a))
            self.assertEqual(frozen['target_labels'], result['target_labels'])
            self.assertEqual(frozen['events'][-1]['wrong_accepted'], 1)

    def test_two_arithmetic_implementations_on_hand_fixture(self):
        row = {'source': {'terms': [{'kind': 'periodic', 'p': 3, 'r': 1, 'a': 2},
                                    {'kind': 'threshold', 't': 5, 'a': -1}]},
               'needle': {'kind': 'needle', 'lo': 5, 'hi': 8, 'a': 1}}
        for regime in ('stable', 'needle', 'broad', 'delayed'):
            for turn in (1, 3):
                spec = truth_at(row, regime, turn)
                for xy in GRID:
                    self.assertEqual(production_value(spec, xy), value(spec, xy))

    def test_fresh_only_output_protects_pending_evidence(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw)
            (path/'pending.sqlite').write_bytes(b'evidence')
            with self.assertRaisesRegex(BudgetContractError, 'fresh study'):
                study(path, build())
            self.assertEqual((path/'pending.sqlite').read_bytes(), b'evidence')


if __name__ == '__main__':
    unittest.main()
