from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, wav
from ._contracts import identity
from .subtitle_maker import make_subtitles


class SubtitleTests(unittest.TestCase):
    def test_signal_regions_produce_both_tracks_at_measured_times(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            clip = wav(Audio(8000, 1, (0,) * 800 + (5000,) * 2400 + (0,) * 1600 + (-4000,) * 2400))
            (root / "fixture.wav").write_bytes(clip)
            plan = {"schema": "ace.media.subtitle-plan.v1", "audio": {"path": "fixture.wav",
                    "sha256": sha256(clip).hexdigest()}, "threshold": 1000, "gap_ms": 40,
                    "minimum_ms": 100, "max_chars_per_sec": 45, "phrases": [
                        {"id": "one", "id_text": "Satu < dua", "en_text": "One & two", "source_ref": "fixture:one"},
                        {"id": "two", "id_text": "Mari lihat", "en_text": "Look", "source_ref": "fixture:two"}]}
            result, report = make_subtitles(plan, identity(plan), root)
            self.assertEqual(report["speech_regions"], [[100, 400], [600, 900]])
            self.assertIn(b"00:00:00.600 --> 00:00:00.900", result["id"])
            self.assertIn(b"Satu &lt; dua", result["id"])
            self.assertIn(b"One &amp; two", result["en"])
            self.assertEqual(report["output_sha256"]["en"], sha256(result["en"]).hexdigest())
            plan["phrases"].pop()
            result, report = make_subtitles(plan, identity(plan), root)
            self.assertEqual(result, {})
            self.assertEqual(report["blocking"], [{"rule": "speech_phrase_count", "speech_regions": 2, "phrases": 1}])
