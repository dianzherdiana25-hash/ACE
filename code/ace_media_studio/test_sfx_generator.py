from hashlib import sha256
import unittest

from ._audio import parse_wav
from ._contracts import ContractError, identity
from .sfx_generator import synthesize_effect


class FoleyTests(unittest.TestCase):
    def test_envelope_and_seed_on_actual_effect(self):
        plan = {"schema": "ace.media.effect-plan.v1", "description": " Ketuk Kayu ", "source_ref": "fixture:foley",
                "rate": 8000, "duration_ms": 280, "peak": 13000, "seed": 42}
        raw, report = synthesize_effect(plan, identity(plan))
        pcm = parse_wav(raw)
        self.assertEqual((pcm.frames, pcm.samples[0], pcm.samples[-1]), (2240, 0, 0))
        self.assertEqual(report["carrier_hz"], [130, 211])
        self.assertEqual(report["peak"], 13000)
        self.assertEqual(report["wav_sha256"], sha256(raw).hexdigest())
        self.assertEqual(raw, synthesize_effect(plan, identity(plan))[0])
        plan["description"] = "gerimis"
        self.assertNotEqual(raw, synthesize_effect(plan, identity(plan))[0])
        plan["description"] = "efek baru"
        with self.assertRaisesRegex(ContractError, "resep"):
            synthesize_effect(plan, identity(plan))
