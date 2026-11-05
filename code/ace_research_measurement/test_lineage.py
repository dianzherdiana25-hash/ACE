"""False-novelty, provenance reuse, and exposure detection canaries."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import unittest
from .lineage import Lineage, audit_lineage


def H(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def bank():
    rows = [Lineage('development:' + str(i), 'development', H('devcase'+str(i)),
                    H('devgen'), H('devmech'), H('devworld'+str(i)), True) for i in range(6)]
    rows.extend(Lineage('eval:' + str(i), 'evaluation', H('evalcase'+str(i)),
                        H('evalgen'+str(i)), H('evalmech'+str(i)), H('evalworld'+str(i)), False)
                for i in range(4))
    return rows


class LineageTests(unittest.TestCase):
    def test_disjoint_development_example_passes_structural_gate_only(self):
        x = audit_lineage(bank(), claim='mechanism_disjoint')
        self.assertEqual(x['evaluation_mechanisms'], 4)
        self.assertEqual(x['claim_gate'], 'NOT_CONFIRMED')
        self.assertEqual(x['custody'], 'NOT_AUTHENTICATED_BY_THIS_MODULE')

    def test_shared_generator_under_new_display_name_rejected(self):
        x = bank()
        x[-1] = replace(x[-1], case_id='renamed', generator_sha256=x[0].generator_sha256)
        with self.assertRaisesRegex(ValueError, 'unseen-generator'):
            audit_lineage(x, claim='generator_disjoint')

    def test_shared_mechanism_under_new_generator_rejected(self):
        x = bank()
        x[-1] = replace(x[-1], mechanism_sha256=x[0].mechanism_sha256)
        with self.assertRaisesRegex(ValueError, 'unseen-mechanism'):
            audit_lineage(x, claim='mechanism_disjoint')
        self.assertIn('MECHANISM_REUSED', audit_lineage(x)['signals'])

    def test_derived_world_across_split_detected(self):
        x = bank()
        x[-1] = replace(x[-1], source_world_sha256=x[0].source_world_sha256)
        with self.assertRaisesRegex(ValueError, 'unseen-generator'):
            audit_lineage(x, claim='generator_disjoint')

    def test_exposed_holdout_fails_independent_claim(self):
        x = bank()
        x[-1] = replace(x[-1], exposed_to_candidate=True)
        self.assertIn('EVALUATION_EXPOSED', audit_lineage(x)['signals'])
        with self.assertRaisesRegex(ValueError, 'unseen-generator'):
            audit_lineage(x, claim='generator_disjoint')

    def test_same_instance_alias_rejected_even_public(self):
        x = bank()
        x[-1] = replace(x[-1], semantic_sha256=x[0].semantic_sha256, case_id='alias')
        with self.assertRaisesRegex(ValueError, 'repeated semantic'):
            audit_lineage(x)

    def test_reused_world_inside_evaluation_rejected_as_pseudoreplication(self):
        x = bank()
        x[-1] = replace(x[-1], source_world_sha256=x[-2].source_world_sha256)
        self.assertIn('EVALUATION_WORLD_CLUSTERING', audit_lineage(x)['signals'])
        with self.assertRaisesRegex(ValueError, 'unseen-generator'):
            audit_lineage(x, claim='generator_disjoint')

    def test_fewer_than_four_mechanisms_flagged(self):
        x = bank()
        for n in (-1, -2, -3):
            x[n] = replace(x[n], mechanism_sha256=x[-4].mechanism_sha256)
        self.assertIn('LOW_MECHANISM_COVERAGE', audit_lineage(x)['signals'])

    def test_boolean_and_untrusted_hash_rejected(self):
        x = bank()
        with self.assertRaisesRegex(ValueError, 'invalid exposure'):
            audit_lineage([*x[:-1], replace(x[-1], exposed_to_candidate=1)])
        with self.assertRaisesRegex(ValueError, 'invalid evaluator digest'):
            audit_lineage([*x[:-1], replace(x[-1], generator_sha256='not-a-hash')])

    def test_missing_and_unknown_claim_rejected(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            audit_lineage([])
        with self.assertRaisesRegex(ValueError, 'unsupported claim'):
            audit_lineage(bank(), claim='proved_OAIE')


if __name__ == '__main__':
    unittest.main()
