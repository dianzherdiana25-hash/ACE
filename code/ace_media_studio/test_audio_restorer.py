from hashlib import sha256
import unittest

from ._audio import Audio, parse_wav, wav
from ._contracts import ContractError, identity
from .audio_restorer import restore


class RestorationTests(unittest.TestCase):
    def test_estimated_noise_drops_and_punch_remains_with_channel_order(self):
        quiet = [130, 170, 130, 170] * 200
        loud = [150, 4150, 150, -3850] * 200
        source = wav(Audio(8000, 2, tuple(value for left in quiet + loud for value in (left, 100 - left))))
        plan = {"schema": "ace.media.restore-plan.v1", "source_ref": "fixture:dual-track",
                "audio_sha256": sha256(source).hexdigest(), "noise_sample_ms": 100,
                "suppression_milli": 900, "peak_target": 9000, "max_gain_milli": 1500}
        bytes_out, report = restore(source, plan, identity(plan))
        result = parse_wav(bytes_out)
        self.assertEqual((result.frames, result.channels), (1600, 2))
        self.assertEqual(report["gain_milli"], 1500)
        self.assertTrue(5700 < result.receipt()["peak"] <= 9000)
        for channel in report["noise_reduction"]:
            self.assertLess(channel["quiet_output_rms"], channel["quiet_input_rms"] // 2)
        self.assertGreater(result.samples[1800 + 2], 5000)
        self.assertLess(result.samples[1800 + 3], -5000)
        self.assertEqual(report["output_wav_sha256"], sha256(bytes_out).hexdigest())
        plan["audio_sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "Hash WAV"):
            restore(source, plan, identity(plan))
