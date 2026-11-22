from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import wave

from ._contracts import canonical, identity
from .deep_report_writer import make_report
from .report_audio_summary import make_audio
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan


class AudioSummaryTests(unittest.TestCase):
    def test_wav_matches_cue_timeline_report_citations_and_spoken_value(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = report_plan(root)
            report = make_report(initial, identity(initial), root)
            plan = {"schema": "ace.institute.audio-summary-plan.v1",
                    "report": save(root, "report.json", canonical(report)), "max_highlights": 2, "pitch": 115}
            pcm, receipt = make_audio(plan, identity(plan), root)
            self.assertEqual(receipt["audio_sha256"], sha256(pcm).hexdigest())
            opening, numerical, gap = receipt["timeline"]
            self.assertIn("nol koma tiga satu", numerical["line"])
            self.assertEqual(numerical["refs"][0]["path"], "paper.md")
            self.assertEqual(numerical["samples"][0], opening["samples"][-1])
            self.assertEqual(gap["kind"], "evidence_gap")
            with wave.open(BytesIO(pcm), "rb") as track:
                self.assertEqual(track.getnframes(), gap["samples"][-1])
                self.assertNotEqual(set(track.readframes(track.getnframes())), {0})
