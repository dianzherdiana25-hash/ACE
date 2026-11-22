"""Verifikasi derivasi skor fixture dari pixel, WAV, receipt, dan label terpisah."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from .audio_pipeline import _canonical
from .closed_suite import run
from .perception_bench import report, UNRESOLVED_CELL

FIXTURE = Path(__file__).parent / "fixtures" / "closed_perception"


class ClosedPerceptionTests(unittest.TestCase):
    def test_exact_fixture_scores_and_retained_unresolved_cell(self):
        plan = (FIXTURE / "plan.json").read_bytes()
        scores = run(FIXTURE, plan, sha256(plan).hexdigest())
        self.assertEqual(scores, json.loads((FIXTURE / "run.json").read_bytes()))
        rows = {row["kind"]: row for row in scores["scores"]["metrics"]}
        self.assertEqual((rows["document"]["correct"], rows["document"]["units"]), (11, 12))
        self.assertEqual((rows["table"]["correct"], rows["table"]["missing_units"]), (11, 1))
        self.assertEqual((rows["asr"]["substitutions"], rows["asr"]["units"]), (1, 6))
        traces = {row["case"]: row for row in scores["derivations"]}
        self.assertEqual(traces["a1"]["scope"], "provided_transcript_against_fixture_reference")
        self.assertEqual(traces["t3"]["status"], "text_partial")

    def test_tampered_image_is_refused_even_if_plan_is_unchanged(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / "fixture"
            shutil.copytree(FIXTURE, folder)
            data = (folder / "plan.json").read_bytes()
            (folder / "d1.pgm").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError, "Hash byte"):
                run(folder, data, sha256(data).hexdigest())

    def test_unresolved_prediction_cannot_match_gold_empty_cell(self):
        ref = "a" * 64
        row = {"id": "case", "kind": "table", "media_sha256": ref, "gold_ref": "fixture/gold", "reference": [[None]]}
        expected = _canonical({"schema": "ace.perception-held-out.v1", "protocol_ref": "fixture/plan", "cases": [row]})
        observed = _canonical({"schema": "ace.perception-held-out-results.v1", "results": [
            {"id": "case", "media_sha256": ref, "receipt_ref": "fixture/observed", "result": [[UNRESOLVED_CELL]]}
        ]})
        result = report(expected, observed, sha256(expected).hexdigest())
        self.assertEqual(result["cases"][0]["score"], {"units": 1, "correct": 0, "missing_units": 1, "extra_units": 0})
        row["reference"] = [[UNRESOLVED_CELL]]
        bad_gold = _canonical({"schema": "ace.perception-held-out.v1", "protocol_ref": "fixture/plan", "cases": [row]})
        with self.assertRaises(ValueError):
            report(bad_gold, observed, sha256(bad_gold).hexdigest())
