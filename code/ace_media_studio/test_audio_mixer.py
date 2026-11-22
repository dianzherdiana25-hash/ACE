from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, parse_wav, wav
from ._contracts import ContractError, identity
from .audio_mixer import mix, mix_tracks


def track(name, role, start=0, **kwargs):
    return dict(id=name, role=role, start_ms=start, gain_milli=1000,
                fade_in_ms=0, fade_out_ms=0, pan=0) | kwargs


def settings(**kwargs):
    return dict(rate=8000, channels=1, duration_ms=100, headroom=32767,
                duck_threshold=1000, duck_milli=250, attack_ms=0, release_ms=0) | kwargs


class MixerTests(unittest.TestCase):
    def test_ducking_tracks_trigger_and_release_on_timeline(self):
        speech = Audio(8000, 1, (4200,) * 160)
        bed = Audio(8000, 1, (4000,) * 800)
        output, report = mix_tracks(settings(), [(track("dialog", "speech", 20), speech),
                                                 (track("bed", "bed"), bed)])
        self.assertEqual((output.samples[10], output.samples[180], output.samples[700]),
                         (4000, 5200, 4000))
        self.assertEqual([160, 320], [report["tracks"][0][key] for key in ("start_frame", "end_frame_exclusive")])
        self.assertEqual(report["pre_normalize_peak"], 5200)
        self.assertTrue(160 < report["ducked_frames"] < 400)

    def test_resample_stereo_pan_fade_normalization_and_bounds(self):
        first = Audio(16000, 1, (20_000,) * 1600)
        options = settings(channels=2, headroom=10_000)
        output, report = mix_tracks(options, [(track("fx", "effect", pan=1000, fade_in_ms=10), first)])
        self.assertEqual(output.frames, 800)
        self.assertEqual(set(output.samples[::2]), {0})
        self.assertLess(output.samples[1], output.samples[199])
        self.assertEqual(output.samples[199], 10_000)
        self.assertEqual(report["normalization"], [10000, 20000])
        with self.assertRaisesRegex(ContractError, "melampaui"):
            mix_tracks(options, [(track("outside", "effect", start=1), first)])

    def test_binds_asset_bytes_and_rejects_traversal_and_symlink(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = wav(Audio(8000, 1, (2000,) * 800))
            (root / "source.wav").write_bytes(raw)
            (root / "alias.wav").symlink_to("source.wav")
            entry = track("example", "effect") | {"path": "source.wav", "sha256": sha256(raw).hexdigest()}
            plan = {"schema": "ace.media.mix-plan.v1", "settings": settings(), "tracks": [entry]}
            output, receipt = mix(plan, identity(plan), root)
            self.assertEqual(2000, parse_wav(output).receipt()["peak"])
            self.assertEqual(receipt["source_sha256"], {"example": entry["sha256"]})
            for path in ("alias.wav", "../source.wav"):
                entry["path"] = path
                with self.subTest(path=path), self.assertRaises(ContractError):
                    mix(plan, identity(plan), root)
            entry["path"] = "source.wav"
            (root / "source.wav").write_bytes(raw[:-1] + b"x")
            with self.assertRaisesRegex(ContractError, "hash"):
                mix(plan, identity(plan), root)
