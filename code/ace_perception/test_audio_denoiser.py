"""Verifier gain, batas interval noise, dan WAV yang dihasilkan lokal."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _audio, audio_denoiser as model
from ace_perception.test_audio_pipeline import RATE, wav


class DenoiseTests(unittest.TestCase):
    def test_noise_profile_at_known_time_attenuates_then_passes_strong_steady_signal(self):
        window = RATE//40
        source = wav([96]*window*2+[1500]*window*2)
        payload, report = model.denoise(source, noise_start_ms=0, noise_end_ms=50, margin=0,
                                        minimum_gain_bp=2500, transition_width=320)
        result = list(_audio.decode(payload).mono)
        self.assertEqual(result[:2*window], [24]*(2*window))
        self.assertEqual(result[-window:], [1500]*window)
        self.assertGreater(result[2*window], 375)
        self.assertLess(result[2*window], result[3*window-1])
        self.assertEqual(report["profile_rms"], 96)
        self.assertEqual(report["gate_floor_rms"], 96)
        self.assertEqual(report["profile_output_sum_squares"], 24**2*2*window)
        self.assertEqual(report["reduced_windows"], 2)
        self.assertEqual(report["output_sha256"], sha256(payload).hexdigest())
        self.assertEqual(report["source_sha256"], sha256(source).hexdigest())

    def test_negative_rounding_and_identity_gain(self):
        signed = [-32768, 32767, -3, 2]*70
        src = wav(signed)
        artifact, data = model.denoise(src, noise_start_ms=0, noise_end_ms=25, minimum_gain_bp=10000)
        self.assertEqual(list(_audio.decode(artifact).mono), signed)
        self.assertEqual(data["input_sum_squares"], data["output_sum_squares"])
        self.assertEqual(data["reduced_windows"], 0)
        muted, _ = model.denoise(wav([-96]*400), noise_start_ms=0, noise_end_ms=50, minimum_gain_bp=0)
        self.assertEqual(set(_audio.decode(muted).mono), {0})

    def test_stereo_mix_is_declared_and_output_length_preserved(self):
        signal = [value for _ in range(240) for value in (50, 150)]
        source = wav(signal, channels=2)
        artifact, report = model.denoise(source, noise_start_ms=0, noise_end_ms=30, minimum_gain_bp=10_000)
        self.assertEqual((report["input_channels"], report["output_channels"], report["sample_count"]), (2, 1, 240))
        self.assertEqual(list(_audio.decode(artifact).mono), [100]*240)

    def test_profile_and_parameter_validation(self):
        source = wav([0]*400)
        for change in ({"noise_end_ms": 1}, {"noise_start_ms": 51},
                       {"noise_end_ms": 51}, {"frame_ms": 0}, {"minimum_gain_bp": 10_001},
                       {"transition_width": False}):
            params = {"noise_start_ms": 0, "noise_end_ms": 50, **change}
            with self.subTest(params=params), self.assertRaises(ValueError):
                model.denoise(source, **params)

    def test_cli_writes_only_new_artifact(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        data, out = folder/"before.wav", folder/"after.wav"
        signal = wav([200]*400)
        data.write_bytes(signal)
        args = [sys.executable, "-m", "ace_perception.audio_denoiser", str(data), "--output", str(out),
                "--noise-start-ms", "0", "--noise-end-ms", "50"]
        run = subprocess.run(args, capture_output=True, check=True)
        artifact, result = model.denoise(signal, noise_start_ms=0, noise_end_ms=50)
        self.assertEqual(out.read_bytes(), artifact)
        self.assertEqual(json.loads(run.stdout), result)
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)
        self.assertEqual(data.read_bytes(), signal)
