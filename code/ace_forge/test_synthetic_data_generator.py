"""Verifier kualitas mekanis dan determinisme bahan sintetis."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import synthetic_data_generator as model
from ace_forge._forge_io import canonical
from ace_forge.dataset_forge import forge


def fixture():
    return {"seed": 52, "per_task_kind": dict.fromkeys(model.PROMPTS, 6),
            "held_out_basis_points": 3000, "license": "CC0-1.0"}


def row(kind, body, answer):
    return {"event_id": "example", "family_id": f"synthetic/{kind}", "language": "id", "task_kind": kind,
            "prompt": model.PROMPTS[kind] + "\n" + canonical(body).decode(), "target": answer}


class SyntheticTests(unittest.TestCase):
    def test_all_requested_rows_pass_mechanical_checks_and_keep_explicit_origin(self):
        candidates, report = model.generate(fixture())
        self.assertEqual(report["examples"], 18)
        self.assertIsNone(report["verification_index"])
        self.assertEqual(candidates["allowed_licenses"], ["CC0-1.0"])
        self.assertEqual(len({item["event_id"] for item in candidates["examples"]}), 18)
        for kind, info in report["families"].items():
            self.assertEqual((info["requested"], info["written"], info["shortfall"]), (6, 6, 0))
            records = [item for item in candidates["examples"] if item["task_kind"] == kind]
            self.assertEqual({item["family_id"] for item in records}, {f"synthetic/{kind}"})
            self.assertEqual(len({item["prompt"] for item in records}), 6)
            for example in records:
                self.assertTrue(model.check(example)["valid"])

    def test_examples_do_not_self_promote_as_independently_verified(self):
        candidates, _ = model.generate(fixture())
        records, report = forge(candidates, {"index_ref": "fixture/empty", "records": []})
        self.assertEqual(records, [])
        self.assertEqual({item["reason"] for item in report["rejected"]}, {"verification_missing"})

    def test_frequency_zero_and_signed_prefix_are_recomputed(self):
        frequency = {"values": [-1, -1, 4, 0], "query": -1}
        prefix = {"values": [-2, 4, -9, 4], "n": 3}
        for kind, payload, correct in (("frequency", frequency, "2"), ("prefix_sum", prefix, "-7"),
                                       ("prefix_sum", {**prefix, "n": 0}, "0"),
                                       ("frequency", {**frequency, "query": 12}, "0")):
            with self.subTest(kind=kind, payload=payload):
                self.assertEqual(model.check(row(kind, payload, correct)), {"valid": True, "reason": "valid"})
                self.assertFalse(model.check(row(kind, payload, f" {correct}"))["valid"])
                self.assertFalse(model.check(row(kind, payload, f"{correct}.0"))["valid"])

    def test_interval_union_counts_nested_overlapping_and_disjoint_points_once(self):
        body = {"intervals": [[-3, 1], [-2, 2], [-1, 0], [3, 3], [10, 10], [-3, -3]]}
        self.assertTrue(model.check(row("interval_coverage", body, "8"))["valid"])
        self.assertEqual(model.check(row("interval_coverage", body, "9"))["reason"],
                         "incorrect_or_noncanonical_answer")

    def test_bad_generator_is_filtered_until_shortfall_and_emits_no_wrong_answers(self):
        raw = fixture()
        raw["per_task_kind"] = {"frequency": 2, "prefix_sum": 0, "interval_coverage": 0}
        sample = ({"values": [0, 0, 0, 0], "query": 0}, 999)
        with patch.object(model, "_sample", return_value=sample):
            examples, report = model.generate(raw)
        self.assertEqual(examples["examples"], [])
        self.assertEqual(report["families"]["frequency"], {
            "requested": 2, "written": 0, "duplicate_prompt": 0, "rejected_quality": 16, "shortfall": 2,
        })

    def test_repeated_valid_shape_does_not_fill_dataset_with_copies(self):
        raw = fixture()
        raw["per_task_kind"] = {"frequency": 3, "prefix_sum": 0, "interval_coverage": 0}
        with patch.object(model, "_sample", return_value=({"values": [0, 0, 0, 0], "query": 0}, 4)):
            candidates, report = model.generate(raw)
        self.assertEqual(len(candidates["examples"]), 1)
        self.assertEqual(report["families"]["frequency"]["shortfall"], 2)
        self.assertEqual(report["families"]["frequency"]["duplicate_prompt"], 23)

    def test_template_or_noncanonical_or_malformed_input_is_labeled(self):
        data = row("frequency", {"values": [1, 2, 3, 4], "query": 3}, "1")
        cases = (
            ({**data, "family_id": "different"}, "template_mismatch"),
            ({**data, "language": "en"}, "template_mismatch"),
            ({**data, "task_kind": "invented"}, "unknown_task_kind"),
            ({**data, "prompt": data["prompt"] + " "}, "noncanonical_payload"),
            ({**data, "prompt": data["prompt"].split("\n")[0] + '\n{"query":3,"query":3}'}, "invalid_payload"),
            (row("frequency", {"values": [1, 2, 3, True], "query": 3}, "1"), "invalid_payload"),
            (row("interval_coverage", {"intervals": [[4, 1], [2, 2]]}, "0"), "invalid_payload"),
        )
        for changed, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(model.check(changed), {"valid": False, "reason": reason})

    def test_seed_and_limits_are_explicit(self):
        raw = fixture()
        for bad in ({**raw, "seed": True}, {**raw, "held_out_basis_points": 10001}, {**raw, "license": ""},
                    {**raw, "per_task_kind": {"frequency": 6}},
                    {**raw, "per_task_kind": {**raw["per_task_kind"], "frequency": model.MAX_COUNT + 1}}):
            with self.subTest(bad=bad), self.assertRaises(model.InputError):
                model.generate(bad)
        changed = model.generate({**raw, "seed": raw["seed"] + 1})[0]
        source = model.generate(raw)[0]
        self.assertNotEqual(changed["examples"][0]["prompt"], source["examples"][0]["prompt"])

    def test_cli_is_byte_stable_under_input_key_permutations_and_report_only_mode(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "recipe.json"
        raw = fixture()
        output = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as result:
                self.assertEqual(model.main([str(path)]), 0)
            output.append(result.getvalue())
            raw["per_task_kind"] = dict(reversed(list(raw["per_task_kind"].items())))
        self.assertEqual(output[0], output[1])
        with redirect_stdout(StringIO()) as result:
            self.assertEqual(model.main([str(path), "--report-only"]), 0)
        self.assertEqual(json.loads(result.getvalue())["examples"], 18)

    def test_unrequested_kinds_are_reported_with_zero_coverage(self):
        raw = {**fixture(), "per_task_kind": dict.fromkeys(model.PROMPTS, 0)}
        candidates, report = model.generate(raw)
        self.assertEqual(candidates["examples"], [])
        self.assertEqual(len(report["families"]), len(model.PROMPTS))
        self.assertTrue(all(item["shortfall"] == 0 for item in report["families"].values()))

    def test_candidate_ids_remain_stable_when_request_size_increases(self):
        raw = fixture()
        first = model.generate(raw)[0]["examples"]
        raw["per_task_kind"]["frequency"] += 1
        second_by_id = {item["event_id"]: item for item in model.generate(raw)[0]["examples"]}
        self.assertTrue(all(second_by_id[item["event_id"]] == item for item in first))
