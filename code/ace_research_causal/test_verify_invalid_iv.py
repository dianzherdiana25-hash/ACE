"""Deliberately adversarial validation of causal evidence replay."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib
from . import verify_invalid_iv as v


class VerifyInvalidIVTests(unittest.TestCase):
    def test_archive_and_expected_groups(self):
        raw,data=v.read_archive()
        self.assertEqual(len(data['results']),5)
        self.assertEqual(data['protocol']['worlds_per_group'],100)
        self.assertTrue(raw.endswith(b'\n'))

    def test_malicious_repacked_digest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad'
            path.write_text(base64.b64encode(zlib.compress(b'{}')).decode())
            with patch.object(v,'ARCHIVE',path):
                with self.assertRaises(ValueError):v.read_archive()

    def test_wrong_replay_rejected(self):
        with patch.object(v.invalid_iv,'experiment',return_value={'garbage':True}):
            with self.assertRaisesRegex(ValueError,'replay mismatch'):
                v.verify(replay=True)

    def test_conditional_wrong_rate_not_silent_zero(self):
        _,results=v.read_archive()
        g=v.gates(results)
        w=g['accepted_case_error_warning']['weak_first_stage']
        self.assertEqual(w['accepted_count'],0)
        self.assertIsNone(w['conditional_wrong_rate'])
        x=g['accepted_case_error_warning']['direct_exclusion']
        self.assertEqual(x['wrong_accepted_count'],x['accepted_count'])

    def test_all_predeclared_criteria_are_descriptive_only(self):
        _,results=v.read_archive()
        gates=v.gates(results)
        self.assertEqual(gates['scientific_acceptance'],'NOT_ASSESSED')
        self.assertEqual(len(gates['exploratory_descriptive_criteria']),5)


if __name__=='__main__':
    unittest.main()
