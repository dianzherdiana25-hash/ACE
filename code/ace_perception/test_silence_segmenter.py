"""Verifier quiet/hysteresis, batas durasi, dan partisi tepat sampel."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import silence_segmenter as model
from ace_perception.test_audio_pipeline import wav


def frames(*values):
    return wav([sample for value in values for sample in [value]*160])


def split(src, minimum_ms=40):
    return model.split(src, enter_rms=100, exit_rms=200, minimum_ms=minimum_ms)


class SilenceTests(unittest.TestCase):
    def test_internal_short_spaces_hysteresis_and_boundaries(self):
        sequence = frames(0, 100, 200, 170, 90, 200, 90, 150, 199, 200, 20, 0)
        report = split(sequence)
        self.assertEqual(report["source_sha256"], sha256(sequence).hexdigest())
        self.assertEqual([(row["start_sample"], row["end_sample"]) for row in report["quiet_intervals"]],
                         [(0, 320), (960, 1440), (1600, 1920)])
        self.assertEqual([row["peak_window_rms"] for row in report["quiet_intervals"]], [100, 199, 20])
        self.assertEqual(report["measured_silence_samples"], 1120)
        self.assertEqual([(row["start_us"], row["end_us"]) for row in report["remaining_intervals"]],
                         [(40000, 120000), (180000, 200000)])
        self.assertEqual(report["suggested_cuts"], [{"sample": 1200, "time_us": 150000}])

    def test_exact_minimum_duration_and_truncated_last_frame(self):
        source = wav([300]*160+[25]*321)
        allowed = split(source, 40)
        excluded = split(source, 41)
        self.assertEqual(allowed["measured_silence_samples"], 321)
        self.assertEqual(allowed["quiet_intervals"][0]["end_sample"], 481)
        self.assertEqual(allowed["suggested_cuts"], [])
        self.assertEqual(excluded["quiet_intervals"], [])
        self.assertEqual(excluded["remaining_intervals"][0]["end_sample"], 481)

    def test_full_silence_or_all_signal_gives_complementary_intervals(self):
        all_quiet = split(frames(0, 0))
        self.assertEqual(all_quiet["quiet_intervals"][0]["start_sample"], 0)
        self.assertFalse(all_quiet["remaining_intervals"])
        self.assertFalse(all_quiet["suggested_cuts"])
        all_sound = split(frames(200, 300, 500))
        self.assertEqual(all_sound["quiet_intervals"], [])
        self.assertEqual(all_sound["remaining_intervals"][0]["end_sample"], 480)

    def test_interval_budget_exact_and_refuses_overflow(self):
        source = frames(0, 0, 300, 0, 0)
        with patch.object(model, "MAX_INTERVALS", 2):
            self.assertEqual(len(split(source)["quiet_intervals"]), 2)
        with patch.object(model, "MAX_INTERVALS", 1), self.assertRaisesRegex(ValueError, "melampaui batas"):
            split(source)

    def test_cli_and_bad_policies(self):
        path = Path(self.enterContext(TemporaryDirectory()))/"fixture.wav"
        source = frames(0, 0, 200, 0, 0)
        path.write_bytes(source)
        args = [sys.executable, "-m", "ace_perception.silence_segmenter", str(path),
                "--minimum-ms", "40", "--enter-rms", "100", "--exit-rms", "200"]
        run = subprocess.run(args, check=True, capture_output=True)
        self.assertEqual(json.loads(run.stdout), split(source))
        self.assertEqual(path.read_bytes(), source)
        for params in ({"minimum_ms": 0}, {"frame_ms": True}, {"enter_rms": 300}, {"exit_rms": 100}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                model.split(source, **params)
