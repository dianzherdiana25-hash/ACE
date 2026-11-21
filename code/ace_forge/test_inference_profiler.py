"""Verifier pengelompokan receipt, kuantil, throughput, dan mutu."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import inference_profiler as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


ARTIFACT = "9" * 64
SECOND = 10**9


def obs(key, prompt, generated, elapsed, first, assessment, *, phase="measured"):
    return {"id": key, "source_ref": f"fixture/receipt/{key}", "artifact_sha256": ARTIFACT,
            "input_tokens": prompt, "output_tokens": generated, "elapsed_ns": elapsed, "first_token_ns": first,
            "quality": {"assessment_ref": f"fixture/score/{key}", "passed": assessment}
            if assessment is not None else None,
            "peak_bytes": elapsed // 10**7, "phase": phase}


def fixture():
    return {"protocol_ref": "fixture/profile", "artifact_sha256": ARTIFACT, "minimum_samples": 2,
            "context_boundaries": [4, 8, 12], "receipts": [
                obs("warm", 3, 1000, 60 * SECOND, 300, True, phase="warmup"),
                obs("a", 3, 10, SECOND, SECOND // 5, True),
                obs("b", 4, 8, 3 * SECOND, 7 * SECOND // 10, False),
                obs("c", 8, 12, 2 * SECOND, None, None),
                obs("d", 15, 0, SECOND, None, False),
            ]}


def profile(raw):
    return model.profile(raw, identity(raw))


class InferenceTests(unittest.TestCase):
    def test_descriptive_aggregates_exclude_warmup_and_support_fractional_rate(self):
        result = profile(fixture())
        total = result["summary"]
        self.assertEqual(total["warmups"], 1)
        self.assertEqual(total["measured"], 4)
        self.assertEqual(total["output_tokens"], 30)
        self.assertEqual(total["elapsed_ns"], 7 * SECOND)
        self.assertEqual(total["token_rate_per_second"], q(30, 7))
        self.assertEqual(total["latency_ns"], {"p50": SECOND, "p95": 3 * SECOND, "p99": 3 * SECOND})
        self.assertEqual(total["first_token_ns"], {"p50": 200_000_000, "p95": 700_000_000, "p99": 700_000_000})
        self.assertEqual(total["peak_bytes"], 300)
        self.assertEqual(total["quality"], {"assessed": 3, "passed": 1, "coverage": q(3, 4), "pass_rate": q(1, 3)})
        self.assertEqual(result["receipts"][0]["quality"]["assessment_ref"], "fixture/score/a")

    def test_stratification_applies_inclusive_upper_and_separate_sparse_buckets(self):
        rows = profile(fixture())["context_profiles"]
        self.assertEqual([(row["context_min"], row["context_max"]) for row in rows],
                         [(1, 4), (5, 8), (9, 12), (13, None)])
        self.assertEqual(rows[0]["receipt_ids"], ["a", "b", "warm"])
        self.assertEqual(rows[0]["status"], "profiled")
        self.assertEqual(rows[0]["token_rate_per_second"], q(9, 2))
        self.assertEqual(rows[1]["measured"], 1)
        self.assertEqual(rows[1]["status"], "insufficient_samples")
        self.assertIsNone(rows[1]["latency_ns"])
        self.assertIsNone(rows[2]["quality"]["coverage"])
        self.assertEqual(rows[3]["receipt_ids"], ["d"])

    def test_measured_zero_rate_and_no_receipt_are_distinct(self):
        raw = {**fixture(), "minimum_samples": 1}
        raw["receipts"] = [obs("one", 1, 0, SECOND, None, None)]
        self.assertEqual(profile(raw)["summary"]["token_rate_per_second"], q(0))
        raw["receipts"].clear()
        blank = profile(raw)["summary"]
        self.assertIsNone(blank["token_rate_per_second"])
        self.assertIsNone(blank["latency_ns"])
        self.assertIsNone(blank["peak_bytes"])

    def test_quality_status_without_provenance_or_first_token_with_no_return_is_invalid(self):
        raw = fixture()
        for update in ({"first_token_ns": 1, "output_tokens": 0}, {"first_token_ns": 2 * SECOND},
                       {"quality": {"passed": 1, "assessment_ref": "fixture/bad"}},
                       {"quality": {"passed": True, "assessment_ref": None}},
                       {"artifact_sha256": "1" * 64}, {"elapsed_ns": 0}, {"peak_bytes": -1}):
            default = raw["receipts"][1]
            with self.subTest(update=update), self.assertRaises(model.InputError):
                profile({**raw, "receipts": [{**default, **update}]})

    def test_missing_quality_is_explicit_even_if_latency_is_profiled(self):
        raw = fixture()
        for item in raw["receipts"]:
            item["quality"] = None
        result = profile(raw)["summary"]
        self.assertEqual(result["status"], "profiled")
        self.assertEqual(result["quality"]["coverage"], q(0))
        self.assertIsNone(result["quality"]["pass_rate"])

    def test_bad_roster_anchor_duplicate_evidence_and_reordered_boundaries_are_rejected(self):
        raw = fixture()
        expected = identity(raw)
        raw["receipts"].pop()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.profile(raw, expected)
        with self.assertRaisesRegex(model.InputError, "Batas konteks"):
            profile({**raw, "context_boundaries": [4, 8, 8]})
        with self.assertRaisesRegex(model.InputError, "ganda"):
            profile({**raw, "receipts": [raw["receipts"][0]] * 2})
        with self.assertRaisesRegex(model.InputError, "ganda"):
            first, second = raw["receipts"][:2]
            profile({**raw, "receipts": [first, {**second, "source_ref": first["source_ref"]}]})

    def test_exact_rank_estimator_uses_observations_and_single_sample_quantiles(self):
        self.assertIsNone(model._quantiles([]))
        self.assertEqual(model._quantiles([6]), {"p50": 6, "p95": 6, "p99": 6})
        self.assertEqual(model._quantiles(reversed(range(1, 101))), {"p50": 50, "p95": 95, "p99": 99})

    def test_cli_receipt_report_stable_with_unchanged_source_bytes(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "inputs.json"
        original = canonical(raw)
        path.write_bytes(original)
        args = [str(path), "--expect-input-sha256", identity(raw)]
        traces = []
        for _ in range(2):
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main(args), 0)
            traces.append(out.getvalue())
        self.assertEqual(*traces)
        self.assertEqual(json.loads(traces[0]), profile(raw))
        self.assertEqual(path.read_bytes(), original)

    def test_warmups_only_leave_empty_profile_and_keep_source_refs(self):
        raw = {**fixture(), "receipts": [fixture()["receipts"][0]], "context_boundaries": []}
        result = profile(raw)
        self.assertEqual(result["summary"]["warmups"], 1)
        self.assertEqual(result["summary"]["measured"], 0)
        self.assertIsNone(result["summary"]["quality"]["coverage"])
        self.assertEqual(result["context_profiles"][0]["receipt_ids"], ["warm"])
        self.assertEqual(result["receipts"][0]["source_ref"], "fixture/receipt/warm")

    def test_first_token_sample_floor_is_separate_from_elapsed_time_floor(self):
        raw = fixture()
        raw["receipts"][2]["first_token_ns"] = None
        result = profile(raw)["summary"]
        self.assertEqual(result["first_token_measured"], 1)
        self.assertIsNone(result["first_token_ns"])
        self.assertIsNotNone(result["latency_ns"])

    def test_all_failed_assessments_produce_measured_zero_when_sufficient(self):
        raw = fixture()
        for item in raw["receipts"]:
            if item["quality"] is not None:
                item["quality"]["passed"] = False
        score = profile(raw)["summary"]["quality"]
        self.assertEqual((score["assessed"], score["passed"]), (3, 0))
        self.assertEqual(score["pass_rate"], q(0))

    def test_reordered_receipts_keep_exact_bucket_metrics_with_new_snapshot_anchor(self):
        raw = fixture()
        old = profile(raw)
        raw["receipts"].reverse()
        new = profile(raw)
        self.assertNotEqual(old.pop("snapshot_sha256"), new.pop("snapshot_sha256"))
        self.assertEqual(old, new)

    def test_all_context_counts_including_upper_bound_land_in_exactly_one_bucket(self):
        raw = fixture()
        raw["receipts"] = [obs(f"point-{i}", i, 1, SECOND, 1, None) for i in range(1, 16)]
        value = profile(raw)
        self.assertEqual([group["measured"] for group in value["context_profiles"]], [4, 4, 4, 3])
        self.assertEqual(sum(len(group["receipt_ids"]) for group in value["context_profiles"]), 15)
