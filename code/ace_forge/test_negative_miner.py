"""Verifier pasangan negatif, alias eksklusif, dan rujukan verifier."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import negative_miner as model
from ace_forge._forge_io import canonical, identity
from ace_forge.dataset_custody import seal
from ace_forge.dataset_forge import _partition, forge
from ace_forge.test_dataset_custody import wire
from ace_forge.test_dataset_forge import inputs, source


def fixture():
    families = [f"family/{i}" for i in range(100)]
    training, held = [next(family for family in families if _partition(52, family, 2500) == split)
                      for split in ("train", "held_out")]
    rows = [source("known", family=training, target="JALUR_SATU"), source("second", family=training, target="jalur dua"),
            source("unknown", family=training, target="not in vocabulary"),
            source("held", family=held, target="jalur satu"),
            {**source("outside", family=training, target="jalur satu"), "task_kind": "outside"}]
    records, _ = forge(*inputs(*rows))
    data = wire(records)
    manifest = seal(data, "fixture/source")
    policy = {"policy_ref": "fixture/negative", "maximum_per_case": 2, "taxonomies": [
        {"task_kind": "fixture-logic", "rule_ref": "fixture/taxonomy", "exclusive": True, "labels": [
            {"label": name, "label_ref": f"fixture/labels/{i}", "aliases": extra} for i, (name, extra) in enumerate((
                ("jalur satu", ["jalur_satu"]), ("jalur dua", []), ("jalur sunu", []), ("negara", []),
            ))
        ]}
    ]}
    return data, manifest, manifest["head_sha256"], policy, identity(policy)


class NegativeTests(unittest.TestCase):
    def test_keeps_gold_aliases_out_and_ranks_wrong_choices_by_edit_distance(self):
        result = model.mine(*fixture())
        self.assertEqual(result["examples_seen"], 2)
        self.assertEqual(result["negative_count"], 4)
        self.assertEqual({item["reason"] for item in result["skipped"]}, {
            "held_out", "task_without_taxonomy", "gold_outside_taxonomy"})
        known = [item for item in result["negatives"] if item["evidence_ref"] == "fixture/evidence/known"]
        self.assertEqual([item["negative_label"] for item in known], ["jalur sunu", "jalur dua"])
        first = known[0]
        self.assertEqual(first["gold_label"], "jalur satu")
        self.assertEqual(first["edit_distance"], 2)
        self.assertEqual(first["gold_label_ref"], "fixture/labels/0")
        self.assertEqual(first["negative_label_ref"], "fixture/labels/2")
        self.assertEqual(first["taxonomy_ref"], "fixture/taxonomy")
        self.assertEqual(len({item["id"] for item in result["negatives"]}), 4)

    def test_lexical_ties_are_deterministic_exactly_after_prioritized_distance(self):
        prior = fixture()
        data, manifest, head, raw, _ = prior
        raw["taxonomies"][0]["labels"] = [
            {"label": label, "label_ref": f"fixture/a/{i}", "aliases": alias}
            for i, (label, alias) in enumerate((("cat", ["jalur_satu"]), ("cot", []), ("bat", [])))
        ]
        result = model.mine(data, manifest, head, raw, identity(raw))
        self.assertEqual([item["negative_label"] for item in result["negatives"]], ["bat", "cot"])
        self.assertTrue(all(item["edit_distance"] == 1 for item in result["negatives"]))

    def test_partial_or_ambiguous_taxonomy_rejects_job_before_output(self):
        for issue in ("not-exclusive", "duplicate-alias", "no-decoy", "duplicate-task"):
            data, manifest, head, raw, _ = fixture()
            node = raw["taxonomies"][0]
            if issue == "not-exclusive":
                node["exclusive"] = False
            elif issue == "duplicate-alias":
                node["labels"][1]["aliases"] = ["JALUR_SATU"]
            elif issue == "no-decoy":
                node["labels"].pop()
                node["labels"] = node["labels"][:1]
            else:
                raw["taxonomies"].append(node)
            with self.subTest(issue=issue), self.assertRaises(model.InputError):
                model.mine(data, manifest, head, raw, identity(raw))

    def test_anchor_stops_mutated_policy_and_custody_detects_partial_bytes(self):
        data, manifest, head, raw, bound = fixture()
        raw["maximum_per_case"] = 1
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.mine(data, manifest, head, raw, bound)
        with self.assertRaisesRegex(model.InputError, "kustodi"):
            model.mine(data[:-1], manifest, head, raw, identity(raw))

    def test_decoy_cap_changes_number_without_changing_gold_or_promoting_unknowns(self):
        data, manifest, head, raw, _ = fixture()
        raw["maximum_per_case"] = 16
        report = model.mine(data, manifest, head, raw, identity(raw))
        self.assertEqual(report["negative_count"], 6)
        self.assertEqual(report["examples_seen"], 2)
        self.assertTrue(all(item["negative_label"] != item["gold_label"] for item in report["negatives"]))
        self.assertNotIn(b'"examples":', canonical(report))

    def test_candidate_bound_and_work_limit_each_fail_closed(self):
        with patch.object(model, "MAX_JOBS", 1), self.assertRaisesRegex(model.InputError, "batas"):
            model.mine(*fixture())
        with patch.object(model, "operation_budget", side_effect=model.InputError("operasi terlalu besar")):
            with self.assertRaisesRegex(model.InputError, "operasi"):
                model.mine(*fixture())

    def test_edit_distance_matches_small_hand_examples(self):
        for first, second, expected in (("", "abc", 3), ("β", "", 1), ("cat", "cut", 1), ("cat", "cat", 0),
                                         ("kitten", "sitting", 3), ("send", "sent", 1)):
            with self.subTest(first=first, second=second):
                self.assertEqual(model._distance(first, second), expected)
                self.assertEqual(model._distance(second, first), expected)

    def test_cli_emits_contrastive_records_only_and_keeps_source_identical(self):
        data, manifest, head, policy, bound = fixture()
        folder = Path(self.enterContext(TemporaryDirectory()))
        files = [folder / path for path in ("source.jsonl", "manifest.json", "policy.json")]
        for path, raw in zip(files, (data, canonical(manifest), canonical(policy)), strict=True):
            path.write_bytes(raw)
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([*map(str, files), "--expect-head", head, "--expect-policy-sha256", bound]), 0)
        self.assertEqual(json.loads(output.getvalue()), model.mine(data, manifest, head, policy, bound))
        self.assertEqual(files[0].read_bytes(), data)

    def test_nfc_and_whitespace_alias_resolve_same_gold_and_never_become_decoys(self):
        raw, proof = inputs(source("accent", target="CAFE\u0301  HITAM"))
        raw["held_out_basis_points"] = 0
        rows, _ = forge(raw, proof)
        data = wire(rows)
        manifest = seal(data, "fixture/corpus")
        policy = {
            "policy_ref": "fixture/rule", "maximum_per_case": 2, "taxonomies": [
                {"task_kind": "fixture-logic", "rule_ref": "fixture/set", "exclusive": True, "labels": [
                    {"label": "gelap", "label_ref": "fixture/gold", "aliases": ["café hitam"]},
                    {"label": "terang", "label_ref": "fixture/other", "aliases": ["putih"]},
                ]}
            ]}
        result = model.mine(data, manifest, manifest["head_sha256"], policy, identity(policy))
        self.assertEqual(result["negative_count"], 1)
        candidate, = result["negatives"]
        self.assertEqual(candidate["gold_label"], "gelap")
        self.assertEqual(candidate["negative_label"], "terang")
        self.assertEqual(candidate["gold_label_ref"], "fixture/gold")

    def test_selection_cap_one_returns_nearest_decoy_per_example(self):
        data, manifest, head, raw, _ = fixture()
        raw["maximum_per_case"] = 1
        report = model.mine(data, manifest, head, raw, identity(raw))
        self.assertEqual(report["negative_count"], 2)
        self.assertEqual(len({item["example_id"] for item in report["negatives"]}), 2)
        first = next(item for item in report["negatives"] if item["evidence_ref"] == "fixture/evidence/known")
        self.assertEqual(first["negative_label"], "jalur sunu")

    def test_dataset_order_has_independent_binding_but_identical_negatives(self):
        data, manifest, head, raw, checksum = fixture()
        before = model.mine(data, manifest, head, raw, checksum)
        new_data = b"\n".join(data.splitlines()[::-1]) + b"\n"
        new_manifest = seal(new_data, "fixture/new")
        after = model.mine(new_data, new_manifest, new_manifest["head_sha256"], raw, checksum)
        self.assertNotEqual(before.pop("dataset_head_sha256"), after.pop("dataset_head_sha256"))
        self.assertEqual(before, after)

    def test_empty_kustodi_data_emits_zero_known_examples_without_training_receipts(self):
        _, _, _, rules, anchor = fixture()
        packed = seal(b"", "fixture/no-data")
        value = model.mine(b"", packed, packed["head_sha256"], rules, anchor)
        self.assertEqual((value["examples_seen"], value["negative_count"]), (0, 0))
        self.assertEqual(value["negatives"], [])
