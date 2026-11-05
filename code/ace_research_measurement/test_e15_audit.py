"""E1.5 aggregate audit invariants, including negative/falsification tests."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from .e15_audit import (TRACKS, SOURCE_GIT_BLOB_SHA1, audit, load_pinned_source)


def metric(worlds, correct, labels):
    return {'worlds': worlds, 'accepted_correct': correct, 'accepted_wrong': 0,
            'abstained': worlds - correct, 'logical_labels': labels,
            'probe_errors': 0, 'utility_units': 20 * correct - 2 * (worlds - correct) - labels}


def fixture():
    results = {}
    for name, key in TRACKS.items():
        is_in = name == 'in_family'
        baseline_val = metric(12, 0, 12)
        candidate_val = metric(12, 3 if is_in else 0, 36 if is_in else 12)
        baseline_h = metric(18, 0, 18)
        candidate_h = metric(18, 1 if is_in else 0, 53 if is_in else 18)
        results[key] = {'status': 'COMPLETE_PUBLIC_DEVELOPMENT', 'scientific_decision': 'NOT_ASSESSED',
                        'baseline_validation': baseline_val, 'champion_validation': candidate_val,
                        'holdout_baseline': baseline_h, 'holdout': candidate_h,
                        'holdout_delta_utility': candidate_h['utility_units'] - baseline_h['utility_units'],
                        'candidate_policy_promoted': False, 'deployment_decision': 'REVERT_TYPED_POLICY_TO_BASELINE'}
    return {'project': 'ACE E1.5', 'scientific_decision': 'NOT_ASSESSED', 'results': results}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.sample = fixture()

    def test_observed_public_aggregate_pattern(self):
        result = audit(self.sample)
        self.assertEqual(result['tracks']['in_family']['validation_delta_utility'], 42)
        self.assertEqual(result['tracks']['in_family']['holdout_delta_utility'], -13)
        self.assertEqual(result['tracks']['in_family']['holdout_delta_accepted_correct'], 1)
        self.assertEqual(result['tracks']['in_family']['holdout_delta_logical_labels'], 35)
        self.assertIn('VALIDATION_HOLDOUT_UTILITY_REVERSAL', result['tracks']['in_family']['signals'])
        self.assertEqual(result['tracks']['mixed_grammar']['holdout_delta_utility'], 0)
        self.assertEqual(result['claim_gate'], 'NOT_ASSESSED')

    def test_wrong_reported_delta_rejected(self):
        x = deepcopy(self.sample)
        x['results'][TRACKS['in_family']]['holdout_delta_utility'] = 2
        with self.assertRaisesRegex(ValueError, 'delta mismatch'):
            audit(x)

    def test_forged_utility_rejected(self):
        x = deepcopy(self.sample)
        x['results'][TRACKS['in_family']]['holdout']['utility_units'] += 1
        with self.assertRaisesRegex(ValueError, 'utility inconsistent'):
            audit(x)

    def test_unmatched_worlds_rejected(self):
        x = deepcopy(self.sample)
        candidate = x['results'][TRACKS['in_family']]['holdout']
        candidate.update(metric(19, 1, 53))
        with self.assertRaisesRegex(ValueError, 'unmatched'):
            audit(x)

    def test_incomplete_track_rejected(self):
        x = deepcopy(self.sample)
        del x['results'][TRACKS['mixed_grammar']]
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            audit(x)

    def test_boolean_metrics_rejected(self):
        x = deepcopy(self.sample)
        x['results'][TRACKS['in_family']]['holdout']['worlds'] = True
        with self.assertRaisesRegex(ValueError, 'non-integer'):
            audit(x)

    def test_non_reversion_rejected(self):
        x = deepcopy(self.sample)
        x['results'][TRACKS['in_family']]['candidate_policy_promoted'] = True
        with self.assertRaisesRegex(ValueError, 'deployment'):
            audit(x)

    def test_pinned_file_rejects_unrecognized_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'source.json'
            p.write_text(json.dumps(self.sample), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'blob mismatch'):
                load_pinned_source(p)

    def test_pinned_source_sha_is_well_formed(self):
        self.assertEqual(len(SOURCE_GIT_BLOB_SHA1), 40)
        self.assertTrue(all(c in '0123456789abcdef' for c in SOURCE_GIT_BLOB_SHA1))

    def test_exact_source_when_available(self):
        source = Path(__file__).resolve().parents[2] / 'evidence/e15/E15_DEVELOPMENT_SUMMARY_v0.json'
        if not source.is_file():
            self.skipTest('full ACE checkout not available in local R8-only staging')
        verified = audit(load_pinned_source(source))
        self.assertEqual(verified['tracks']['in_family']['holdout_delta_utility'], -13)


if __name__ == '__main__':
    unittest.main()
