"""Verifier dukungan lintas keluarga, persetujuan, dan penilaian held-out."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import owner_correction_forge as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


def correction(key, namespace, context, after="prefer_a", before="defer", **changed):
    raw = {"id": key, "source_ref": f"fixture/correction/{key}", "actor_role": "owner_review",
           "family": f"train/{namespace}", "context": context, "domain": "writing",
           "before": before, "after": after, "consent_ref": f"fixture/consent/{key}"}
    return {**raw, **changed}


def held(key, context, expected="prefer_a", baseline="defer", **changed):
    raw = {"id": key, "source_ref": f"fixture/held/{key}", "context": context, "family": f"held/{key}",
           "domain": "writing", "baseline": baseline, "expected": expected}
    return {**raw, **changed}


def fixture():
    data = [correction("1", "group-a", "topic_x"), correction("2", "group-b", "topic_x"),
            correction("3", "group-c", "topic_y"), correction("4", "group-c", "topic_y"),
            correction("5", "group-d", "topic_z"), correction("6", "group-e", "topic_z", "prefer_b")]
    raw = {"recipe_ref": "fixture/correction_recipe", "corrections_sha256": identity(data),
           "minimum_families": 2, "domains": ["writing", "code"],
           "labels": ["defer", "prefer_a", "prefer_b"],
           "held_out": [held("a", "topic_x"), held("b", "topic_y", "defer"), held("c", "topic_z", "defer"),
                        held("d", "topic_x", "prefer_b", "prefer_b"), held("e", "topic_x")]}
    return raw, data


def train(recipe, rows):
    return model.train(recipe, rows, identity(recipe))


class CorrectionTests(unittest.TestCase):
    def test_unanimous_context_improves_shared_heldout_and_reveals_individual_regression(self):
        result = train(*fixture())
        self.assertEqual(result["summary"], {"held_out": 5, "baseline_correct": 3, "corrected_correct": 4, "delta": q(1, 5)})
        one, repeated, disputed = result["policies"]
        self.assertEqual((one["distinct_families"], one["status"], one["label"]), (2, "ready", "prefer_a"))
        self.assertEqual((repeated["distinct_families"], repeated["status"]), (1, "insufficient_support"))
        self.assertEqual((disputed["distinct_families"], disputed["status"]), (2, "conflicting_labels"))
        self.assertEqual(one["sources"][0]["consent_ref"], "fixture/consent/1")
        gain, _, _, regression, _ = result["evaluation"]
        self.assertEqual((gain["baseline_correct"], gain["corrected_correct"]), (False, True))
        self.assertEqual((regression["baseline_correct"], regression["corrected_correct"]), (True, False))
        self.assertTrue(regression["correction_applied"])

    def test_unknown_context_or_domain_without_fitted_label_uses_baseline(self):
        raw, rows = fixture()
        raw["held_out"] = [held("only", "topic_x", "defer", "defer", domain="code")]
        result = train(raw, rows)
        self.assertEqual(result["summary"]["delta"], q(0))
        self.assertFalse(result["evaluation"][0]["correction_applied"])

    def test_conflicting_corrections_hold_even_in_same_family(self):
        raw, rows = fixture()
        rows[3]["after"] = "prefer_b"
        raw["corrections_sha256"] = identity(rows)
        updated = train(raw, rows)["policies"][1]
        self.assertEqual(updated["status"], "conflicting_labels")
        self.assertEqual(updated["distinct_families"], 1)
        self.assertIsNone(updated["label"])

    def test_duplicates_cannot_create_support_even_with_fresh_anchors(self):
        raw, corrections = fixture()
        for field in ("id", "source_ref"):
            after = [dict(item) for item in corrections]
            after[1][field] = after[0][field]
            with self.subTest(field=field), self.assertRaisesRegex(model.InputError, "ganda"):
                train({**raw, "corrections_sha256": identity(after)}, after)

    def test_train_and_heldout_need_disjoint_families_and_receipts(self):
        for changes, message in (({"family": "train/group-a"}, "tumpang tindih"),
                                 ({"source_ref": "fixture/correction/1"}, "ganda"),
                                 ({"id": "1"}, "ganda")):
            raw, rows = fixture()
            raw["held_out"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(model.InputError, message):
                train(raw, rows)

    def test_role_nonempty_consent_and_known_distinct_labels_required(self):
        mutations = ({"actor_role": "unreviewed"}, {"consent_ref": ""},
                     {"consent_ref": "fixture/correction/1"}, {"after": "defer"},
                     {"after": "invented"}, {"domain": "unknown"}, {"personal_text": "fixture"})
        for changes in mutations:
            raw, rows = fixture()
            rows[0].update(changes)
            raw["corrections_sha256"] = identity(rows)
            with self.subTest(changes=changes), self.assertRaises(model.InputError):
                train(raw, rows)

    def test_snapshot_changes_detected_against_two_distinct_anchors(self):
        raw, rows = fixture()
        expected = identity(raw)
        rows[0]["after"] = "prefer_b"
        with self.assertRaisesRegex(model.InputError, "komitmen"):
            model.train(raw, rows, expected)
        raw["corrections_sha256"] = identity(rows)
        with self.assertRaisesRegex(model.InputError, "Resep.*anchor"):
            model.train(raw, rows, expected)

    def test_missing_evaluation_distinct_from_measured_zero_delta(self):
        raw, rows = fixture()
        raw["held_out"].clear()
        product = train(raw, rows)
        self.assertIsNone(product["summary"]["delta"])
        self.assertEqual(product["summary"]["held_out"], 0)
        self.assertEqual(len(product["policies"]), 3)

    def test_unseen_context_does_not_invent_a_label_from_training_domain(self):
        raw, rows = fixture()
        raw["held_out"] = [held("new", "unknown", "prefer_b", "defer")]
        report = train(raw, rows)
        item, = report["evaluation"]
        self.assertFalse(item["correction_applied"])
        self.assertFalse(item["corrected_correct"])
        self.assertEqual(report["summary"]["delta"], q(0))

    def test_cli_deterministic_and_input_corrections_are_never_written(self):
        raw, rows = fixture()
        base = Path(self.enterContext(TemporaryDirectory()))
        spec, data = base / "recipe", base / "corrections"
        spec.write_bytes(canonical(raw))
        data.write_bytes(canonical(rows))
        outputs = []
        for _ in range(2):
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main([str(spec), str(data), "--expect-recipe-sha256", identity(raw)]), 0)
            outputs.append(out.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(json.loads(outputs[0]), train(raw, rows))
        self.assertEqual(data.read_bytes(), canonical(rows))
        self.assertEqual(spec.read_bytes(), canonical(raw))

    def test_negative_delta_is_retained_and_an_unchanged_decision_not_counted_as_applied(self):
        raw, rows = fixture()
        raw["held_out"] = [held("p", "topic_x", "prefer_a", "prefer_a"), held("q", "topic_x", "prefer_b", "prefer_b")]
        output = train(raw, rows)
        self.assertEqual(output["summary"]["delta"], q(-1, 2))
        self.assertFalse(output["evaluation"][0]["correction_applied"])
        self.assertTrue(output["evaluation"][1]["correction_applied"])
        self.assertFalse(output["evaluation"][1]["corrected_correct"])

    def test_reordering_sources_preserves_fitted_rows_with_new_source_hash(self):
        recipe, rows = fixture()
        first = train(recipe, rows)
        rows.reverse()
        recipe["corrections_sha256"] = identity(rows)
        second = train(recipe, rows)
        self.assertEqual(first["policies"], second["policies"])
        self.assertEqual(first["evaluation"], second["evaluation"])
        self.assertNotEqual(first["corrections_sha256"], second["corrections_sha256"])

    def test_empty_corrections_do_not_create_policy_and_preserve_baseline(self):
        recipe, _ = fixture()
        recipe["corrections_sha256"] = identity([])
        result = train(recipe, [])
        self.assertEqual(result["policies"], [])
        self.assertEqual(result["summary"]["delta"], q(0))
        self.assertEqual(result["summary"]["held_out"], len(recipe["held_out"]))
        self.assertTrue(all(not row["correction_applied"] for row in result["evaluation"]))
