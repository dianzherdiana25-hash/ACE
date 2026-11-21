"""Verifier rasio noise terukur, output tanpa isian, dan batas clip."""
import unittest

from ace_perception import audio_quality_gate as model
from ace_perception.test_audio_pipeline import wav


def policy(**changes):
    return model._canonical({"schema": "ace.perception-audio-quality.v1", "minimum_duration_ms": 40,
                            "minimum_rms": 50, "clipping_abs": 32760, "maximum_clip_bp": 0,
                            "maximum_dc_abs": 100, "quiet_rms": 20, "maximum_quiet_window_bp": 5000,
                            "frame_ms": 20, "noise_box_ms": [0, 20], "minimum_signal_noise_ratio": 20, **changes})


class QualityTests(unittest.TestCase):
    def test_ratio_from_nonprofile_frames_and_exact_boundaries(self):
        audio = wav([30, -30]*80+[300, -300]*160)
        output = model.assess(audio, policy())
        self.assertEqual(output["status"], "pass")
        self.assertEqual(output["clip_count"], 0)
        self.assertEqual(output["signal_noise_energy_ratio"], {"numerator": 100, "denominator": 1})
        self.assertEqual(output["noise_span"]["end_sample"], 160)
        self.assertEqual(output["windows"], 3)
        self.assertEqual(output["dc_mean"], {"numerator": 0, "denominator": 1})

    def test_null_no_noise_and_real_failures_differ(self):
        audio = wav([0]*160+[800, -800]*160)
        self.assertEqual(model.assess(audio, policy())["snr_status"], "noise_energy_zero")
        self.assertEqual(model.assess(audio, policy())["status"], "incomplete")
        self.assertEqual(model.assess(audio, policy(noise_box_ms=None))["snr_status"], "noise_reference_missing")
        clipped = model.assess(wav([10]*160+[32767]*160), policy())
        self.assertEqual(clipped["status"], "held")
        self.assertEqual(clipped["blockers"], ["excess_clipping", "excess_dc"])
        self.assertEqual(clipped["clip_fraction"], {"numerator": 1, "denominator": 2})

    def test_too_low_measured_signal_ratio_holds(self):
        data = wav([30, -30]*80+[90, -90]*160)
        result = model.assess(data, policy())
        self.assertEqual(result["signal_noise_energy_ratio"], {"numerator": 9, "denominator": 1})
        self.assertIn("signal_noise_ratio_low", result["blockers"])
