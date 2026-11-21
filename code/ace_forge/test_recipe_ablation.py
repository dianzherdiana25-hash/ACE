"""Verifier parameter tunggal, coverage kontrol, dan delta eksak."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import recipe_ablation as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


BASE, FAST, SMALL = "1"*64, "2"*64, "3"*64


def fixture():
    recipe = {"schedule": {"rate": 5, "epochs": 4}, "batch": [8, 16], "precision": "fixture-int"}
    rate = {**recipe, "schedule": {**recipe["schedule"], "rate": 10}}
    batch = {**recipe, "batch": [16, 8]}
    protocol = {"protocol_ref": "fixture/ablation", "minimum_pairs": 1,
                "baseline": {"artifact_sha256": BASE, "recipe_ref": "fixture/base", "recipe": recipe},
                "variants": [
                    {"id": "rate", "artifact_sha256": FAST, "recipe_ref": "fixture/fast", "recipe": rate,
                     "parameter_path": ["schedule", "rate"]},
                    {"id": "batch", "artifact_sha256": SMALL, "recipe_ref": "fixture/batch", "recipe": batch,
                     "parameter_path": ["batch"]},
                ], "test_cases": [
                    {"id": "a", "domain": "one", "case_ref": "fixture/cases/a"},
                    {"id": "b", "domain": "two", "case_ref": "fixture/cases/b"},
                ]}
    evidence = {"baseline": [
        {"case_id": key, "observation": {"artifact_sha256": BASE, "score_bp": 5000, "tokens": 100,
                                         "receipt_ref": f"fixture/base/{key}"}} for key in "ab"
    ], "variants": [
        {"variant_id": arm, "case_id": key, "observation": {"artifact_sha256": artifact, "score_bp": score,
                                                           "tokens": tokens, "receipt_ref": f"fixture/{arm}/{key}"}}
        for arm, artifact, key, score, tokens in (
            ("rate", FAST, "a", 6000, 200), ("rate", FAST, "b", 3500, 20), ("batch", SMALL, "a", 5000, 25),
        )
    ]}
    return protocol, evidence


def replay(plan, evidence):
    return model.analyze(plan, evidence, identity(plan))


class AblationTests(unittest.TestCase):
    def test_single_change_metrics_are_paired_with_same_control(self):
        report = replay(*fixture())
        short, complete = report["variants"]
        self.assertEqual(short["id"], "batch")
        self.assertEqual(short["after_value"], [16, 8])
        self.assertEqual(short["summary"]["status"], "insufficient_evidence")
        self.assertIsNone(short["summary"]["mean_delta_tokens"])
        self.assertEqual(short["domains"][0]["mean_delta_tokens"], q(-75))
        self.assertEqual(complete["parameter_path"], ["schedule", "rate"])
        self.assertEqual((complete["before_value"], complete["after_value"]), (5, 10))
        self.assertEqual(complete["summary"]["mean_delta_score_bp"], q(-250))
        self.assertEqual(complete["summary"]["mean_delta_tokens"], q(10))
        self.assertEqual(complete["cases"][0]["baseline"], short["cases"][0]["baseline"])
        self.assertEqual(complete["cases"][1]["variant"]["receipt_ref"], "fixture/rate/b")

    def test_confounds_removed_paths_or_false_variable_declarations_fail(self):
        for change in ("confound", "extra", "removed", "same", "wrong-path"):
            plan, records = fixture()
            example = plan["variants"][0]
            if change == "confound":
                example["recipe"]["schedule"]["epochs"] -= 1
            if change == "extra":
                example["recipe"]["new-key"] = True
            if change == "removed":
                example["recipe"].pop("batch")
            if change == "same":
                example["recipe"] = deepcopy(plan["baseline"]["recipe"])
            if change == "wrong-path":
                example["parameter_path"] = ["schedule", "epochs"]
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "persis satu"):
                replay(plan, records)

    def test_missing_observation_keeps_provenance_and_is_not_zero_delta(self):
        plan, evidence = fixture()
        evidence["baseline"][1]["observation"] = None
        report = replay(plan, evidence)["variants"][1]
        self.assertEqual(report["summary"]["paired"], 1)
        self.assertIsNone(report["cases"][1]["delta_score_bp"])
        self.assertEqual(report["cases"][1]["variant"]["tokens"], 20)

    def test_receipts_from_unregistered_case_or_incorrect_artifact_rejected(self):
        for update in ({"case_id": "ghost"}, {"variant_id": "ghost"}):
            spec, evidence = fixture()
            evidence["variants"][0].update(update)
            with self.subTest(update=update), self.assertRaises(model.InputError):
                replay(spec, evidence)
        spec, evidence = fixture()
        evidence["variants"][0]["observation"]["artifact_sha256"] = BASE
        with self.assertRaisesRegex(model.InputError, "artefak"):
            replay(spec, evidence)

    def test_plan_anchor_detects_edits_and_duplicate_observations_cannot_inflate_n(self):
        plan, evidence = fixture()
        checksum = identity(plan)
        plan["minimum_pairs"] = 2
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.analyze(plan, evidence, checksum)
        evidence["baseline"].append(evidence["baseline"][0])
        with self.assertRaisesRegex(model.InputError, "baseline ganda"):
            replay(plan, evidence)

    def test_one_numeric_to_boolean_change_is_tracked_as_typed_value(self):
        plan, evidence = fixture()
        recipe = plan["baseline"]["recipe"]
        recipe["schedule"]["rate"] = 1
        plan["variants"][0]["recipe"]["schedule"]["rate"] = True
        goal = replay(plan, evidence)["variants"][1]
        self.assertEqual(goal["before_value"], 1)
        self.assertIs(goal["after_value"], True)

    def test_cli_reports_hash_and_fractional_deltas_without_modifying_input(self):
        plan, evidence = fixture()
        path = Path(self.enterContext(TemporaryDirectory()))
        p, data = path / "protocol.json", path / "obs.json"
        p.write_bytes(canonical(plan))
        data.write_bytes(canonical(evidence))
        with redirect_stdout(StringIO()) as result:
            self.assertEqual(model.main([str(p), str(data), "--expect-protocol-sha256", identity(plan)]), 0)
        self.assertEqual(json.loads(result.getvalue()), replay(plan, evidence))
        self.assertEqual(p.read_bytes(), canonical(plan))

    def test_repeated_variants_cannot_relabel_same_artifact(self):
        plan, rows = fixture()
        plan["variants"][0]["artifact_sha256"] = SMALL
        with self.assertRaisesRegex(model.InputError, "berulang"):
            replay(plan, rows)

    def test_sample_floor_is_enforced_per_domain_without_hiding_pair_provenance(self):
        plan, evidence = fixture()
        plan["minimum_pairs"] = 2
        report = replay(plan, evidence)["variants"][1]
        self.assertEqual(report["summary"]["status"], "measured")
        self.assertTrue(all(row["status"] == "insufficient_evidence" for row in report["domains"]))
        self.assertEqual(report["cases"][0]["delta_score_bp"], 1000)
        self.assertEqual(report["cases"][0]["case_ref"], "fixture/cases/a")

    def test_parameter_tokens_distinguish_literal_slash_from_nested_paths(self):
        plan, evidence = fixture()
        for recipe in (plan["baseline"]["recipe"], *(item["recipe"] for item in plan["variants"])):
            recipe["schedule/rate"] = 7
        plan["variants"][0]["recipe"]["schedule/rate"] = 8
        with self.assertRaisesRegex(model.InputError, "persis satu"):
            replay(plan, evidence)
        plan["variants"][0]["recipe"]["schedule"]["rate"] = 5
        plan["variants"][0]["parameter_path"] = ["schedule/rate"]
        self.assertEqual(replay(plan, evidence)["variants"][1]["after_value"], 8)
