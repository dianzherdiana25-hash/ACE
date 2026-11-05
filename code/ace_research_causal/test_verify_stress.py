"""Fail-closed evidence-check tests; no network or paid evaluation."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from ace_research_causal import verify_stress as v


class VerifyStressTests(unittest.TestCase):
    def test_archive_integrity_and_counts(self):
        raw,data=v.verified_archive()
        self.assertEqual(len(raw),13083)
        self.assertEqual(data['protocol']['worlds_per_cohort'],80)
        self.assertEqual(len(data['cohorts']),5)

    def test_tampered_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'a.b64'
            f.write_text(base64.b64encode(zlib.compress(b'{}')).decode())
            with patch.object(v,'ARCHIVE',f):
                with self.assertRaisesRegex(RuntimeError,'digest mismatch'):
                    v.verified_archive()

    def test_replay_mismatch_rejected(self):
        with patch.object(v.stress,'experiment',return_value={'bogus':True}):
            with self.assertRaisesRegex(RuntimeError,'replay disagrees'):
                v.verify(replay=True)

    def test_weak_zero_acceptance_is_not_pass(self):
        _,results=v.verified_archive()
        flags=v.descriptive_gates(results)
        self.assertEqual(flags['H2_weak_accepted_wrong_rate'],
                         'INDETERMINATE_ZERO_ACCEPTANCE')
        self.assertEqual(flags['scientific_acceptance'],'NOT_ASSESSED')


if __name__=='__main__':
    unittest.main()
