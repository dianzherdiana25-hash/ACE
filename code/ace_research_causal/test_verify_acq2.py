"""Adversarial checks for R5 ACQ2 evidence and false claims."""
import json
import base64
import zlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import verify_acq2


class ACQ2VerifierTests(unittest.TestCase):
    def test_original_verified(self):
        raw,r=verify_acq2.read_archive()
        self.assertEqual(len(r['cohorts']),5)
        self.assertTrue(raw.endswith(b'\n'))
        self.assertEqual(len(raw)>1000,True)

    def test_tampered_digest_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'evil.b64';p.write_text(base64.b64encode(zlib.compress(b'{}\n')).decode())
            with self.assertRaisesRegex(ValueError,'digest mismatch'):
                verify_acq2.read_archive(p)

    def test_invented_replay_fails(self):
        with patch.object(verify_acq2.acq2,'experiment',return_value={'invented':True}):
            with self.assertRaisesRegex(ValueError,'replay mismatch'):
                verify_acq2.verify(True)

    def test_cost_understatement_fails(self):
        _,r=verify_acq2.read_archive()
        r['cohorts']['valid']['0.0025']['means']['evpi32']['net_regret']=0
        with self.assertRaisesRegex(ValueError,'cost omitted'):
            verify_acq2.audit(r)

    def test_random_matching_fails(self):
        _,r=verify_acq2.read_archive()
        r['cohorts']['valid']['0.0025']['means']['random_matched32']['total_direct_rows']=0
        with self.assertRaisesRegex(ValueError,'unmatched'):
            verify_acq2.audit(r)

    def test_false_acceptance_denominator_fails(self):
        _,r=verify_acq2.read_archive()
        entry=r['cohorts']['valid']['0.0125']['means']['abstain']
        self.assertIsNone(entry['conditional_wrong_rate'])
        entry['conditional_wrong_rate']=0
        with self.assertRaisesRegex(ValueError,'undefined error'):
            verify_acq2.audit(r)

    def test_negative_hypotheses_preserved(self):
        _,r=verify_acq2.read_archive()
        flags=verify_acq2.audit(r)
        self.assertFalse(flags['F3_superior_targeting_to_random_at_cheap_price'])
        self.assertFalse(flags['F4_valid_world_penalty_within_point05'])
        self.assertEqual(flags['scientific_acceptance'],'NOT_ASSESSED')

if __name__=='__main__':
    unittest.main()
