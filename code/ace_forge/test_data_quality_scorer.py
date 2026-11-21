"""Uji penilaian mutu berbasis rubrik dan bukti dataset berkustodi."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import data_quality_scorer as model
from ace_forge._forge_io import canonical
from ace_forge.dataset_custody import seal
from ace_forge.dataset_forge import forge
from ace_forge.test_dataset_forge import inputs, source
from ace_forge.test_dataset_custody import wire


def rubric():
    return {"rubric_ref": "fixture/quality", "languages": ["id"],
            "task_policies": [{"task_kind": "fixture-logic", "prompt_chars": [5, 50],
                               "target_chars": [1, 6], "target_format": "integer"}],
            "weights": {"prompt_length": 2000, "target_length": 1000, "language_label": 1000,
                        "target_format": 3000, "non_echo": 1000, "control_chars": 2000},
            "required_checks": ["target_format", "control_chars"], "minimum_score_bp": 7000}


def packaged(rows):
    records, _ = forge(*inputs(*rows))
    data = wire(records)
    manifest = seal(data, "fixture/input")
    return data, manifest, manifest["head_sha256"]


def fixture():
    data, manifest, head = packaged([
        source("good", target="21"),
        source("short", prompt="X", target="3"),
        source("bad-format", target="true"),
        {**source("bad-language", target="0"), "language": "de"},
        source("controls", target="12\x07"),
        {**source("uncatalogued", target="21"), "task_kind": "freeform"},
    ])
    return data, manifest, head, rubric()


class QualityTests(unittest.TestCase):
    def test_report_scores_known_cases_and_preserves_unscored(self):
        report = model.score(*fixture())
        by_id = {row["event_id"]: row for row in report["records"]}
        self.assertEqual(by_id["good"]["score_bp"], 10_000)
        self.assertEqual(by_id["short"]["score_bp"], 8_000)
        self.assertEqual(by_id["bad-language"]["score_bp"], 9_000)
        self.assertEqual(by_id["bad-format"]["status"], "hold")
        self.assertEqual(by_id["bad-format"]["blockers"], ["required:target_format"])
        self.assertEqual(by_id["controls"]["blockers"], [
            "required:control_chars", "required:target_format", "score_below_floor",
        ])
        self.assertIsNone(by_id["uncatalogued"]["score_bp"])
        self.assertEqual(by_id["uncatalogued"]["blockers"], ["task_policy_missing"])
        self.assertEqual(report["summary"][0]["mean_score_bp"], {"numerator": 7800, "denominator": 1})
        self.assertEqual(report["summary"][1]["unscored"], 1)
        self.assertEqual(by_id["good"]["evidence_ref"], "fixture/evidence/good")
        self.assertNotIn("Uji kasus", canonical(report).decode())
        self.assertNotIn('"target":', canonical(report).decode())

    def test_unicode_echo_distinguishes_casefold_and_individual_space(self):
        data, manifest, head = packaged([source("echo", prompt="CAFÉ A", target="cafe\u0301    a")])
        policy = rubric()
        policy["task_policies"][0].update(target_format="text", target_chars=[1, 50])
        policy["required_checks"] = ["non_echo"]
        row, = model.score(data, manifest, head, policy)["records"]
        self.assertEqual(row["score_bp"], 9000)
        self.assertEqual(row["blockers"], ["required:non_echo"])

    def test_json_object_and_integer_schema_checks_reject_ambiguous_values(self):
        self.assertTrue(model._formatted('{"one":1}', "json_object"))
        self.assertTrue(model._formatted(' [1,2]\n', "json"))
        self.assertTrue(model._formatted(' -7 ', "integer"))
        for raw, fmt in (("false", "integer"), ("1.0", "integer"), ("[]", "json_object"),
                         ('{"x":5,"x":6}', "json_object"), ("NaN", "json"), ("[", "json")):
            with self.subTest(raw=raw, fmt=fmt):
                self.assertFalse(model._formatted(raw, fmt))

    def test_required_check_can_block_even_when_its_weight_is_zero(self):
        data, manifest, head = packaged([source("one", target="not-json")])
        policy = rubric()
        policy["weights"].update(target_format=0, target_length=0, non_echo=5000)
        result, = model.score(data, manifest, head, policy)["records"]
        self.assertEqual(result["score_bp"], 10_000)
        self.assertEqual(result["blockers"], ["required:target_format"])

    def test_invalid_policy_and_failed_anchor_are_explicit(self):
        data, manifest, head, policy = fixture()
        with self.assertRaisesRegex(model.InputError, "kustodi"):
            model.score(data, manifest, "b" * 64, policy)
        for update in ({"languages": []}, {"required_checks": ["unknown"]},
                       {"weights": {**policy["weights"], "control_chars": 1999}},
                       {"task_policies": policy["task_policies"] * 2}, {"minimum_score_bp": 0}):
            with self.subTest(update=update), self.assertRaises(model.InputError):
                model.score(data, manifest, head, {**policy, **update})

    def test_cutoff_and_lengths_use_inclusive_policy(self):
        data, manifest, head = packaged([source("boundary", prompt="ABCDE", target="-8")])
        policy = rubric()
        policy["task_policies"][0].update(prompt_chars=[5, 5], target_chars=[2, 2])
        policy["minimum_score_bp"] = 10_000
        matched, = model.score(data, manifest, head, policy)["records"]
        self.assertEqual(matched["status"], "ready")
        self.assertEqual(matched["prompt_chars"], 5)
        self.assertEqual(matched["target_chars"], 2)

    def test_control_policy_exempts_only_common_multiline_whitespace(self):
        self.assertTrue(model._allow_chars("a\n\t\runo"))
        for control in ("\x08", "\x0b", "\x7f"):
            self.assertFalse(model._allow_chars("sample" + control))

    def test_empty_attested_input_reports_no_examples_or_numeric_average(self):
        data, manifest, head = packaged([])
        report = model.score(data, manifest, head, rubric())
        self.assertEqual(report["records"], [])
        self.assertEqual(report["summary"], [])
        self.assertEqual(report["dataset_head_sha256"], head)

    def test_cli_receipt_identical_and_uses_dataset_and_rubric_paths_read_only(self):
        data, manifest, head, policy = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        data_path, manifest_path, rubric_path = (root / name for name in ("data.jsonl", "manifest.json", "rubric.json"))
        data_path.write_bytes(data)
        manifest_path.write_bytes(canonical(manifest))
        rubric_path.write_bytes(canonical(policy))
        args = [str(data_path), str(rubric_path), "--manifest", str(manifest_path), "--expect-head", head]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(output.getvalue()), model.score(data, manifest, head, policy))
        self.assertEqual((data_path.read_bytes(), rubric_path.read_bytes()), (data, canonical(policy)))

    def test_nested_nonfinite_number_is_not_accepted_as_roundtrippable_json(self):
        data, manifest, head = packaged([source("overflow", target='{"x":1e1000}')])
        rules = rubric()
        rules["task_policies"][0].update(target_format="json_object", target_chars=[1, 40])
        item, = model.score(data, manifest, head, rules)["records"]
        self.assertFalse(item["checks"]["target_format"])
        self.assertEqual(item["blockers"], ["required:target_format"])

    def test_scores_remain_separate_from_threshold_and_evidence_classification(self):
        data, manifest, head = packaged([source("short", prompt="X", target="9")])
        rules = rubric()
        strict = model.score(data, manifest, head, {**rules, "minimum_score_bp": 9000})["records"][0]
        loose = model.score(data, manifest, head, {**rules, "minimum_score_bp": 8000})["records"][0]
        self.assertEqual(strict["score_bp"], loose["score_bp"])
        self.assertEqual(strict["evidence_ref"], loose["evidence_ref"])
        self.assertEqual(strict["blockers"], ["score_below_floor"])
        self.assertEqual(loose["status"], "ready")

    def test_unconfigured_task_does_not_get_zero_imputed_in_summary(self):
        data, manifest, head = packaged([{**source("new", target="10"), "task_kind": "unregistered"}])
        stats, = model.score(data, manifest, head, rubric())["summary"]
        self.assertIsNone(stats["mean_score_bp"])
        self.assertEqual((stats["hold"], stats["unscored"], stats["ready"]), (0, 1, 0))
