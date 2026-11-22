"""Verifier penilaian held-out deterministik dengan WER dan penalti klaim ekstra."""
from hashlib import sha256
import unittest
from unittest.mock import patch

from ace_perception import perception_bench as model


def case(key, kind, expected):
    return {"id": key, "kind": kind, "media_sha256": sha256(key.encode()).hexdigest(),
            "gold_ref": f"fixture/gold/{key}", "reference": expected}


def raw_plan():
    return {"schema": "ace.perception-held-out.v1", "protocol_ref": "fixture/perception-protocol",
            "cases": [case("doc", "document", {"first": "Alpha", "amount": {"scale": 2, "unscaled": 123}, "ready": True}),
                      case("grid", "table", [[1, 2], [3, 4]]), case("speech", "asr", "HELLO THE WHITE CAT")]}


def observation(key, result):
    return {"id": key, "media_sha256": sha256(key.encode()).hexdigest(),
            "receipt_ref": f"fixture/result/{key}", "result": result}


def bytes_observations(doc=None, table=None, audio="hello white dog cheers cheers"):
    full = {"first": "Alpha", "amount": {"unscaled": 123, "scale": 2}, "ready": True}
    rows = [observation("doc", doc if doc is not None else full),
            observation("grid", table if table is not None else [[1, 2], [3, 4]]),
            observation("speech", audio)]
    return model._canonical({"schema": "ace.perception-held-out-results.v1", "results": rows})


def evaluate(observations, plan=None):
    original = raw_plan() if plan is None else plan
    return model.report(model._canonical(original), observations, model._sha(original))


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def by_kind(result):
    return {row["kind"]: row for row in result["metrics"]}


class BenchTests(unittest.TestCase):
    def test_counts_fields_cells_and_word_edits_by_kind(self):
        observations = bytes_observations({"first": "Alpha", "ready": 1, "fabricated": "x"}, [[1], [3], [5]])
        report = evaluate(observations)
        measures = by_kind(report)
        doc, table, voice = (measures[kind] for kind in model.KINDS)
        self.assertEqual(doc["full_rate"], q(1, 4))
        self.assertEqual((doc["missing_units"], doc["extra_units"]), (1, 1))
        self.assertEqual(table["full_rate"], q(2, 5))
        self.assertEqual((table["missing_units"], table["extra_units"]), (2, 1))
        self.assertEqual(voice["full_rate"], q(1))
        self.assertEqual(sum(voice[name] for name in ("substitutions", "deletions", "insertions")), 4)
        self.assertEqual(voice["rate_denominator"], 4)
        self.assertEqual(report["receipts_sha256"], sha256(observations).hexdigest())
        self.assertEqual(report["cases"][0]["gold_ref"], "fixture/gold/doc")
        self.assertEqual(report["cases"][0]["receipt_ref"], "fixture/result/doc")

    def test_empty_output_is_counted_and_wer_can_exceed_one(self):
        report = evaluate(bytes_observations(table=[], audio="hello "+ "added "*8))
        measures = by_kind(report)
        self.assertEqual(measures["table"]["full_rate"], q(0))
        self.assertEqual(measures["table"]["missing_units"], 4)
        voice = measures["asr"]
        self.assertGreater(voice["full_rate"]["numerator"], voice["full_rate"]["denominator"])

    def test_missing_observation_distinct_from_failure_and_zero_reference(self):
        raw = raw_plan()
        raw["cases"][2]["reference"] = ""
        result = evaluate(bytes_observations(audio="hallucinated"), raw)
        voice = by_kind(result)["asr"]
        self.assertTrue(voice["complete"])
        self.assertIsNone(voice["full_rate"])
        self.assertEqual(voice["insertions"], 1)
        missing = model._canonical({"schema": "ace.perception-held-out-results.v1", "results": []})
        metrics = by_kind(evaluate(missing))
        self.assertEqual(metrics["asr"]["expected_units"], 4)
        self.assertIsNone(metrics["asr"]["observed_rate"])
        self.assertFalse(metrics["asr"]["complete"])

    def test_hash_wrong_media_and_work_limit_refuse_scoring(self):
        raw = raw_plan()
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.report(model._canonical(raw), bytes_observations(), "a"*64)
        different = observation("doc", {"first": "Alpha"})
        different["media_sha256"] = "b"*64
        with self.assertRaisesRegex(ValueError, "tidak terikat"):
            evaluate(model._canonical({"schema": "ace.perception-held-out-results.v1", "results": [different]}))
        with patch.object(model, "MAX_WORK", 1), self.assertRaisesRegex(ValueError, "edit distance"):
            evaluate(bytes_observations())

    def test_alignment_separates_named_edit_operations(self):
        self.assertEqual(model._align(["a", "b"], ["a", "c"]), (1, 1, 0, 0))
        self.assertEqual(model._align(["a", "b"], ["b"]), (1, 0, 1, 0))
        self.assertEqual(model._align(["a", "b"], ["a", "x", "b"]), (1, 0, 0, 1))
