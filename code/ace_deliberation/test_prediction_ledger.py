"""Uji semua versi ramalan, batas waktu, dan checkpoint kustodi."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from ace_deliberation import prediction_ledger as ledger


def event(identifier, kind, at, **rest):
    return {"event_id": identifier, "question_id": "test1", "source_ref": f"fixture/{identifier}",
            "kind": kind, "at": f"2026-11-20T{at}Z", **rest}


def registration():
    return event("registration", "register", "00:00:00",
                 locks_at="2026-11-20T01:00:00Z", resolution_rule_ref="fixture/rule")


def first():
    return event("first", "forecast", "00:15:00", forecaster="forecaster-a", probability="0.3")


class PredictionTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "predictions.jsonl"
        ledger.append_event(self.path, registration())

    def test_revision_and_resolution_keep_entire_prefix_and_original_record(self):
        first_row = ledger.append_event(self.path, first())
        prefix = self.path.read_bytes()
        ledger.append_event(self.path, event("revision", "forecast", "00:30:00",
                                             forecaster="forecaster-a", probability="0.8"))
        ledger.append_event(self.path, event("observed", "resolve", "01:00:00", outcome=1))
        result = ledger.audit(self.path)
        question = result["questions"]["test1"]
        self.assertEqual(result["events"][1], first_row)
        self.assertTrue(self.path.read_bytes().startswith(prefix))
        self.assertEqual(question["latest"]["forecaster-a"]["probability"], "0.8")
        self.assertEqual(question["forecast_version_counts"], {"forecaster-a": 2})
        self.assertEqual(question["resolution"]["source_ref"], "fixture/observed")

    def test_forecast_after_cutoff_or_out_of_order_refused_without_append(self):
        ledger.append_event(self.path, first())
        previous = self.path.read_bytes()
        for clock in ("00:10:00", "00:15:00", "01:00:00", "01:01:00"):
            with self.subTest(clock=clock), self.assertRaises(ledger.PredictionError):
                ledger.append_event(self.path, event("late", "forecast", clock, forecaster="b", probability="0.1"))
            self.assertEqual(self.path.read_bytes(), previous)

    def test_anchor_detects_shortened_and_tampered_ledger(self):
        prefix = self.path.read_bytes()
        ledger.append_event(self.path, first())
        result = ledger.audit(self.path)
        anchor = result["checkpoint"]
        self.assertTrue(ledger.audit(self.path, anchor=anchor)["anchor_checked"])
        previous = self.path.read_bytes()
        self.path.write_bytes(prefix)
        with self.assertRaisesRegex(ledger.PredictionError, "terpotong"):
            ledger.audit(self.path, anchor=anchor)
        self.path.write_bytes(previous.replace(b'"0.3"', b'"0.8"'))
        with self.assertRaisesRegex(ledger.PredictionError, "Record 2"):
            ledger.audit(self.path)

    def test_resolution_before_valid_forecast_or_second_resolution_is_refused(self):
        with self.assertRaises(ledger.PredictionError):
            ledger.append_event(self.path, event("r0", "resolve", "01:00:00", outcome=1))
        ledger.append_event(self.path, first())
        ledger.append_event(self.path, event("r1", "resolve", "01:00:00", outcome=1))
        with self.assertRaises(ledger.PredictionError):
            ledger.append_event(self.path, event("r2", "resolve", "01:10:00", outcome=0))

    def test_cli_reports_exact_hash_from_event_file_without_rewriting(self):
        source = self.path.with_name("event.json")
        source.write_text(json.dumps(first()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(ledger.main(["append", str(self.path), str(source)]), 0)
        self.assertEqual(ledger.audit(self.path)["checkpoint"]["sha256"], json.loads(output.getvalue())["sha256"])
