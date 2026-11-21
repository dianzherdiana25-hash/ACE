"""Verifier kualitas per tugas, biaya, dan frontier antar kuantisasi."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import quant_matrix as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


BASE = "a" * 64


def fixture():
    versions = {
        "fast": (4, "b"*64, 200, -100, -20), "quality": (8, "c"*64, 400, -20, -10),
        "dominated": (8, "d"*64, 700, -20, -8), "fails": (4, "e"*64, 100, -300, -60),
    }
    tasks = [("a", "logic"), ("b", "logic"), ("c", "format")]
    protocol = {"protocol_ref": "fixture/quant", "maximum_loss_bp": 150, "minimum_per_task": 1,
                "baseline": {"artifact_sha256": BASE, "bytes": 800, "source_ref": "fixture/base"},
                "variants": [{"id": key, "artifact_sha256": sha, "bits": bits, "strategy": f"fixture/{key}",
                              "bytes": size, "source_ref": f"fixture/weight/{key}"}
                             for key, (bits, sha, size, _, _) in versions.items()],
                "cases": [{"id": key, "task_kind": task, "source_ref": f"fixture/case/{key}"} for key, task in tasks]}
    results = {"baseline": [{"case_id": key, "metric": metric(BASE, 6000, 100, f"fixture/original/{key}")}
                            for key, _ in tasks], "variants": []}
    for name, (_, sha, _, delta, time) in versions.items():
        for key, task in tasks:
            change = 100 if name == "fails" and task == "logic" else delta
            results["variants"].append({"case_id": key, "variant_id": name,
                                        "metric": metric(sha, 6000 + change, 100 + time, f"fixture/{name}/{key}")})
    return protocol, results


def metric(artifact, quality, elapsed, ref):
    return {"artifact_sha256": artifact, "quality_bp": quality, "elapsed_us": elapsed, "observation_ref": ref}


def compare(protocol, measurements):
    return model.compare(protocol, measurements, identity(protocol))


class MatrixTests(unittest.TestCase):
    def test_frontier_preserves_tradeoffs_and_excludes_failing_task_despite_gain_elsewhere(self):
        result = compare(*fixture())
        self.assertEqual(result["evaluation_frontier"], ["fast", "quality"])
        rows = {item["id"]: item for item in result["variants"]}
        self.assertEqual(rows["fast"]["bytes_ratio"], q(1, 4))
        self.assertEqual(rows["quality"]["bytes_ratio"], q(1, 2))
        failing = rows["fails"]
        self.assertEqual([row["status"] for row in failing["tasks"]], ["quality_below_floor", "within_floor"])
        self.assertEqual(failing["tasks"][1]["mean_quality_delta_bp"], q(100))
        self.assertFalse(failing["eligible"])
        self.assertEqual(rows["fast"]["cases"][0]["baseline"]["observation_ref"], "fixture/original/a")
        self.assertEqual(rows["fast"]["cases"][0]["delta_elapsed_us"], -20)

    def test_equality_at_declared_loss_boundary_is_allowed(self):
        plan, obs = fixture()
        plan["maximum_loss_bp"] = 100
        record = next(item for item in compare(plan, obs)["variants"] if item["id"] == "fast")
        self.assertTrue(record["eligible"])
        plan["maximum_loss_bp"] -= 1
        record = next(item for item in compare(plan, obs)["variants"] if item["id"] == "fast")
        self.assertFalse(record["eligible"])

    def test_missing_baseline_affects_all_modes_without_imputing_measurements(self):
        plan, obs = fixture()
        obs["baseline"].pop()
        raw = compare(plan, obs)
        self.assertEqual(raw["evaluation_frontier"], [])
        for row in raw["variants"]:
            self.assertFalse(row["eligible"])
            self.assertIsNone(row["tasks"][0]["mean_quality_delta_bp"])
            self.assertEqual(row["tasks"][0]["expected"], 1)
            self.assertEqual(row["tasks"][0]["paired"], 0)
            self.assertIsNotNone(row["cases"][-1]["variant"])

    def test_minimum_per_task_is_independent_of_global_number_of_pairs(self):
        raw, obs = fixture()
        raw["minimum_per_task"] = 2
        result = compare(raw, obs)
        self.assertEqual(result["evaluation_frontier"], [])
        self.assertTrue(all(row["tasks"][0]["status"] == "insufficient_evidence" for row in result["variants"]))

    def test_unknown_ids_duplicates_and_cross_artifact_receipts_are_invalid(self):
        for updated in ({"case_id": "unknown"}, {"variant_id": "other"},
                        {"metric": metric(BASE, 5000, 1, "fixture/fake")}, {"metric": metric("b"*64, True, 1, "fixture/fake")}):
            plan, obs = fixture()
            obs["variants"][0].update(updated)
            with self.subTest(updated=updated), self.assertRaises(model.InputError):
                compare(plan, obs)
        plan, obs = fixture()
        obs["baseline"].append(obs["baseline"][0])
        with self.assertRaisesRegex(model.InputError, "ganda"):
            compare(plan, obs)

    def test_altered_policy_cannot_change_readout_under_fixed_commitment(self):
        raw, obs = fixture()
        committed = identity(raw)
        raw["maximum_loss_bp"] = 10000
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.compare(raw, obs, committed)

    def test_invalid_weight_artifact_metadata_is_rejected(self):
        for changed in ({"artifact_sha256": BASE}, {"bytes": 0}, {"bits": 1}, {"strategy": ""}):
            raw, obs = fixture()
            raw["variants"][0].update(changed)
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                compare(raw, obs)

    def test_identical_pareto_values_keep_both_sources(self):
        self.assertEqual(model._frontier({"a": (1, 2, 4), "b": (1, 2, 4), "c": (2, 2, 4)}), ["a", "b"])

    def test_cli_deterministic_reports_as_proof_linked_json_with_read_only_inputs(self):
        plan, obs = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p, r = root / "protocol.json", root / "observations.json"
        p.write_bytes(canonical(plan))
        r.write_bytes(canonical(obs))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(p), str(r), "--expect-protocol-sha256", identity(plan)]), 0)
        self.assertEqual(json.loads(output.getvalue()), compare(plan, obs))
        self.assertEqual(r.read_bytes(), canonical(obs))

    def test_absent_variant_limb_does_not_dilute_completed_variants(self):
        raw, obs = fixture()
        obs["variants"] = [item for item in obs["variants"] if item["variant_id"] != "fast"]
        result = compare(raw, obs)
        self.assertEqual(result["evaluation_frontier"], ["quality"])
        incomplete = next(item for item in result["variants"] if item["id"] == "fast")
        self.assertEqual(incomplete["tasks"][1]["paired"], 0)
        self.assertEqual(incomplete["cases"][0]["baseline"]["observation_ref"], "fixture/original/a")

    def test_multiple_cases_produce_exact_fractional_delta_without_float_rounding(self):
        plan, obs = fixture()
        value = next(item for item in obs["variants"] if item["variant_id"] == "fast" and item["case_id"] == "a")
        value["metric"]["quality_bp"] -= 1
        value["metric"]["elapsed_us"] -= 1
        row = next(item for item in compare(plan, obs)["variants"] if item["id"] == "fast")
        self.assertEqual(row["tasks"][1]["mean_quality_delta_bp"], q(-201, 2))
        self.assertEqual(row["tasks"][1]["mean_elapsed_delta_us"], q(-41, 2))

    def test_shared_receipt_cannot_recertify_different_observed_arms(self):
        plan, obs = fixture()
        obs["variants"][0]["metric"]["observation_ref"] = obs["baseline"][0]["metric"]["observation_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            compare(plan, obs)

    def test_reordering_input_products_keeps_metrics_under_bound_source(self):
        plan, obs = fixture()
        first = compare(plan, obs)
        obs["variants"].reverse()
        obs["baseline"].reverse()
        second = compare(plan, obs)
        self.assertNotEqual(first.pop("observations_sha256"), second.pop("observations_sha256"))
        self.assertEqual(first, second)
