"""Third red-team pass: evidence schema, split custody, and replay side effects.

Tests use only temporary paths, deterministic public fixtures and unchanged
GitHub E1.5 implementation blobs. Expected failures indicate missing safeguards.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from ace_loop.engine import HashLedger, ResearchEngine, ResearchIntegrityError, canonical, digest
from ace_loop import source_evolution as source


def reseal(rows):
    prev = '0' * 64
    for row in rows:
        row['prev'] = prev
        row['sha256'] = digest({key: row[key] for key in ('seq', 'prev', 'kind', 'payload')})
        prev = row['sha256']
    return b''.join(canonical(row) + b'\n' for row in rows)


class ConstantAdapter:
    """Fake evaluator for exercising controller contracts, not science."""
    def __init__(self, *, outsiders_per_split=0):
        self.outsiders_per_split = outsiders_per_split
        self.test_calls = 0

    def bank_manifest(self):
        return {'source': 'redteam-owned-public', 'outsiders': self.outsiders_per_split}

    def evaluate(self, policy, split):
        if split == 'test':
            self.test_calls += 1
        return {'worlds': 1, 'accepted_correct': 0, 'accepted_wrong': 0,
                'abstained': 1, 'logical_labels': 1, 'probe_errors': 0,
                'utility_units': -3}


class EvidenceAndReplay(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    @unittest.expectedFailure
    def test_rt11_rehashed_float_and_bool_evidence_must_be_rejected(self):
        """P2: replay compares numeric payload using equality, not exact types."""
        controller = source.SourceEvolution(self.root / 'source')
        controller.run(stop_after=2)
        path = controller.root / 'events.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        forged = next(row for row in rows
                      if row['kind'] == 'trial' and row['payload']['index'] == 1)
        forged['payload']['index'] = True  # True == 1 in Python
        forged['payload']['validation']['count'] = 3.0  # 3.0 == 3
        path.write_bytes(reseal(rows))
        # Confirm this is a valid digest chain, not a mere checksum failure.
        self.assertEqual(len(HashLedger(path).events), len(rows))
        with self.assertRaises(ResearchIntegrityError):
            source.SourceEvolution(controller.root)

    @unittest.expectedFailure
    def test_rt12_overlap_validation_holdout_must_fail_before_experiment(self):
        """P2: evaluator accepts overlapping splits; holdout appears successful."""
        bank = copy.deepcopy(source.synthetic_bank())
        bank['holdout'] = list(bank['validation'])  # full leakage by construction
        with patch.object(source, 'synthetic_bank', return_value=bank):
            with self.assertRaises(ResearchIntegrityError):
                source.SourceEvolution(self.root / 'overlap').run()

    @unittest.expectedFailure
    def test_rt13_corrupt_allocation_schema_must_raise_typed_integrity_error(self):
        """P3: recomputed-hash corrupt allocation gains=None raises TypeError."""
        from ace_redteam.test_portfolio_redteam import FlatAdapter
        stub = types.ModuleType('ace_loop.operators')
        stub.OperatorAdapter = FlatAdapter
        import importlib
        with patch.dict(sys.modules, {'ace_loop.operators': stub}):
            module = importlib.import_module('ace_loop.portfolio')
        root = self.root / 'portfolio'
        with patch.object(module, 'OperatorAdapter', FlatAdapter):
            result = module.run_portfolio(root, pilot_trials=1, total_trials=2)
            self.assertIsNone(result['allocation']['selected'])
            path = root / 'allocation.json'
            row = json.loads(path.read_text())
            row['allocation']['selected'] = 'in_family'
            row['allocation']['gains'] = None
            row['sha256'] = digest(row['allocation'])
            path.write_bytes(canonical(row) + b'\n')
            with self.assertRaises(ResearchIntegrityError):
                module.run_portfolio(root, pilot_trials=1, total_trials=2)

    def test_completed_reopen_reaudits_holdout_multiple_times(self):
        """Observation: reauditing is intentional today, not exactly-once escrow."""
        adapter = ConstantAdapter()
        root = self.root / 'research'
        controller = ResearchEngine(root, adapter, max_cycles=1, patience=1)
        controller.run()
        self.assertEqual(adapter.test_calls, 2)
        resumed = ResearchEngine(root, adapter, max_cycles=1, patience=1)
        self.assertEqual(adapter.test_calls, 4)
        resumed.run()
        self.assertEqual(adapter.test_calls, 6)

    def test_reference_bank_is_disjoint_in_current_source(self):
        """Positive control: PR #27's specific bank has no (x,y) split overlap."""
        bank = source.synthetic_bank()
        xy = {split: {(x, y) for x, y, _ in rows} for split, rows in bank.items()}
        self.assertFalse(xy['train'] & xy['validation'])
        self.assertFalse(xy['train'] & xy['holdout'])
        self.assertFalse(xy['validation'] & xy['holdout'])


if __name__ == '__main__':
    unittest.main()
