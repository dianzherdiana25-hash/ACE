"""Tests for R8 gate false positives and metadata/cost poisoning."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

from .measurement import Record
from .lineage import Lineage
from .growth_gate import GrowthPlan, screen_growth, _cluster_signflip_p


def hash_of(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def sample(*, delta: bool = True, n_families: int = 8, n_cases: int = 12):
    records, origins = [], []
    for split in ('development', 'validation', 'evaluation'):
        for i in range(n_families):
            family = ('dev_' if split != 'evaluation' else 'eval_') + str(i)
            for j in range(n_cases):
                cid = split + '/' + str(i) + '/' + str(j)
                sem = hash_of('case' + cid)
                novel = split == 'evaluation'
                candidate = bool(delta and novel)
                records.append(Record(cid, split, family, sem, family, novel, novel,
                                      False, candidate, False, candidate,
                                      baseline_ops=10, candidate_ops=10,
                                      baseline_labels=0, candidate_labels=0))
                origins.append(Lineage(cid, split, sem, hash_of('gen'+family),
                                       hash_of('mechanism'+family), hash_of('world'+cid),
                                       exposed_to_candidate=split != 'evaluation'))
    return records, origins


class GrowthScreenTests(unittest.TestCase):
    def test_strong_public_positive_control_is_never_confirmatory(self):
        records, origin = sample()
        result = screen_growth(records, origin)
        self.assertEqual(result['diagnostic_status'], 'PASS_PUBLIC_SCREEN_ONLY')
        self.assertEqual(result['scientific_claim'], 'NOT_CONFIRMED')
        self.assertAlmostEqual(result['novel_family_signflip_one_sided_nominal_p'], 1 / 256)
        self.assertEqual(result['reasons'], [])
        self.assertFalse(result['plan_is_registered'])

    def test_no_progress_fails(self):
        rows, lineage = sample(delta=False)
        out = screen_growth(rows, lineage)
        self.assertIn('INSUFFICIENT_NOVEL_TRANSFER_EFFECT', out['reasons'])
        self.assertIn('NO_NOMINAL_NOVEL_FAMILY_SIGNFLIP_SUPPORT', out['reasons'])

    def test_underpowered_families_fail(self):
        rows, lineage = sample(n_families=3)
        result = screen_growth(rows, lineage)
        self.assertIn('INSUFFICIENT_FAMILY_COVERAGE', result['reasons'])
        self.assertIn('INSUFFICIENT_NOVEL_FAMILIES', result['reasons'])

    def test_many_cheap_cases_in_one_family_cannot_fake_clusters(self):
        rows, lineage = sample(n_families=2, n_cases=96)
        result = screen_growth(rows, lineage)
        self.assertEqual(result['evaluation_families'], 2)
        self.assertEqual(result['diagnostic_status'], 'HOLD_PUBLIC_SCREEN')

    def test_increased_labels_fail_even_if_performance_better(self):
        rows, lineage = sample()
        ix = next(i for i, x in enumerate(rows) if x.split == 'evaluation')
        rows[ix] = replace(rows[ix], candidate_labels=1)
        self.assertIn('CANDIDATE_USES_MORE_RESOURCES', screen_growth(rows, lineage)['reasons'])

    def test_increased_compute_fail_even_if_performance_better(self):
        rows, lineage = sample()
        ix = next(i for i, x in enumerate(rows) if x.split == 'evaluation')
        rows[ix] = replace(rows[ix], candidate_ops=11)
        self.assertIn('CANDIDATE_USES_MORE_RESOURCES', screen_growth(rows, lineage)['reasons'])

    def test_evaluation_exposure_fail_closed(self):
        rows, lineage = sample()
        ix = next(i for i, x in enumerate(lineage) if x.split == 'evaluation')
        lineage[ix] = replace(lineage[ix], exposed_to_candidate=True)
        with self.assertRaisesRegex(ValueError, 'exposure/lineage'):
            screen_growth(rows, lineage)

    def test_changed_case_semantics_fail_closed(self):
        rows, lineage = sample()
        lineage[-1] = replace(lineage[-1], semantic_sha256=hash_of('forged'))
        with self.assertRaisesRegex(ValueError, 'semantic mismatch'):
            screen_growth(rows, lineage)

    def test_same_mechanism_under_new_family_name_fail_closed(self):
        rows, lineage = sample()
        ix = next(i for i, x in enumerate(lineage) if x.split == 'evaluation' and x.case_id.endswith('/1/0'))
        peer = next(x for x in lineage if x.split == 'evaluation' and x.case_id.endswith('/0/0'))
        lineage[ix] = replace(lineage[ix], mechanism_sha256=peer.mechanism_sha256)
        with self.assertRaisesRegex(ValueError, 'family spans'):
            screen_growth(rows, lineage)

    def test_signflip_tied_zero_is_one(self):
        self.assertEqual(_cluster_signflip_p([0,0,0,0,0,0]), 1.0)

    def test_plan_rejects_invalid_effect_limits(self):
        with self.assertRaisesRegex(ValueError, 'invalid bounded plan'):
            GrowthPlan(min_per_family=0)
        with self.assertRaisesRegex(ValueError, 'probability'):
            GrowthPlan(alpha=True)

    def test_source_world_pseudoreplication_fail_closed(self):
        rows, lineage = sample()
        ix = next(i for i, x in enumerate(lineage) if x.split == 'evaluation')
        other = next(x for x in lineage if x.split == 'development')
        lineage[ix] = replace(lineage[ix], source_world_sha256=other.source_world_sha256)
        with self.assertRaisesRegex(ValueError, 'exposure/lineage'):
            screen_growth(rows, lineage)

    def test_compositional_coverage_rule(self):
        rows, lineage = sample()
        rows = [replace(r, compositional=False) if r.split == 'evaluation' and r.family.startswith('eval_6') else r
                for r in rows]
        rows = [replace(r, compositional=False) if r.split == 'evaluation' and r.family.startswith('eval_7') else r
                for r in rows]
        self.assertEqual(screen_growth(rows, lineage)['compositional_families'], 6)
        rows = [replace(r, compositional=False) if r.split == 'evaluation' and r.family.startswith('eval_5') else r
                for r in rows]
        self.assertIn('INSUFFICIENT_COMPOSITIONAL_FAMILIES', screen_growth(rows, lineage)['reasons'])


if __name__ == '__main__':
    unittest.main()
