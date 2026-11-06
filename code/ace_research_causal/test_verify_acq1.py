"""Adversarial replay, archive corruption, and accounting gates for R5 ACQ1."""
import base64
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zlib
from . import verify_acq1 as v


class VerifyTests(unittest.TestCase):
    def test_archive_sha_and_5_cohorts(self):
        raw,data=v.read_archive()
        self.assertEqual(len(data['cohorts']),5)
        self.assertEqual(data['protocol']['worlds_per_cohort'],100)
        self.assertTrue(raw.endswith(b'\n'))

    def test_repacked_truncated_payload_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'tampered.b64'
            p.write_text(base64.b64encode(zlib.compress(b'{}')).decode())
            with patch.object(v,'ARCHIVE',p):
                with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                    v.read_archive()

    def test_wrong_scientific_replay_rejected(self):
        with patch.object(v.acq1,'experiment',return_value={'faked':True}):
            with self.assertRaisesRegex(ValueError,'byte mismatch'):
                v.verify(True)

    def test_purchase_cost_understatement_is_rejected(self):
        _,d=v.read_archive()
        d['cohorts']['valid']['means']['disagreement32']['net_regret']=0
        with self.assertRaisesRegex(ValueError,'omits purchase cost'):
            v.audit(d)

    def test_random_matched_query_mismatch_is_rejected(self):
        _,d=v.read_archive()
        d['cohorts']['valid']['means']['random_matched32']['total_direct_rows']=1
        with self.assertRaisesRegex(ValueError,'matched query budget'):
            v.audit(d)

    def test_negative_gates_preserved(self):
        _,d=v.read_archive()
        g=v.audit(d)
        self.assertFalse(g['F1_exclusion_improvement_ge_point10'])
        self.assertFalse(g['F2_better_than_matched_random_in_both_by_point02'])
        self.assertFalse(g['F3_valid_excess_regret_at_most_point10'])
        self.assertEqual(g['scientific_acceptance'],'NOT_ASSESSED')

if __name__=='__main__':
    unittest.main()
