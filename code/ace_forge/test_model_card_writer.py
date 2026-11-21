"""Verifier kartu yang menambatkan angka, gap, dan referensi artefak."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import model_card_writer as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_brain_bench import AFTER, BEFORE, fixture as benchmark
from ace_forge.test_forgetting_guard import q


def fixture():
    bench, anchor = benchmark()
    return {"artifact": {"id": "fixture-card", "sha256": AFTER, "format": "dense_adapter",
                         "source_ref": "fixture/adapter", "license": "Fixture-License", "parents": [BEFORE]},
            "training": {"recipe_ref": "fixture/recipe", "receipt_ref": "fixture/receipt", "datasets": [
                {"head_sha256": "c" * 64, "dataset_ref": "fixture/data", "train": 17, "held_out": 3,
                 "license_audit_ref": "fixture/audit"},
            ]},
            "intended_use": [{"text": "Latihan aritmetika tabel.", "ref": "fixture/use"}],
            "limitations": [{"text": "Aktivasi dense sudah direkam.", "ref": "fixture/limit"}],
            "registry": {"ref": "fixture/review", "artifact_sha256": AFTER, "status": "registered"},
            "benchmark": {"ref": "fixture/bench", "input": bench, "bench_sha256": anchor}}


def card(raw):
    return model.compose(raw, identity(raw))


class CardTests(unittest.TestCase):
    def test_markdown_and_structured_scores_come_from_paired_evidence(self):
        result = card(fixture())
        row = result["benchmark"]["domains"][0]
        self.assertEqual(row["baseline_score_bp"], q(6000))
        self.assertEqual(row["artifact_score_bp"], q(6500))
        self.assertEqual(row["score_delta_bp"], q(500))
        self.assertEqual(result["benchmark"]["baseline_sha256"], BEFORE)
        rendered = model.markdown(result)
        self.assertIn("| reading | 2/2 | 6000 | 6500 | 500 |", rendered)
        self.assertIn("Train 17, held-out 3.", rendered)
        self.assertIn("Sumber fixture/data.", rendered)
        self.assertIn("Batas penggunaan", rendered)
        self.assertIn("Aktivasi dense sudah direkam. Sumber fixture/limit.", rendered)
        self.assertIn("Status registry `registered`", rendered)

    def test_absent_training_and_bench_have_explicit_gaps(self):
        raw = fixture()
        raw.update(training=None, benchmark=None, intended_use=[], limitations=[])
        raw["artifact"]["license"] = None
        rendered = model.markdown(card(raw))
        self.assertIn("TIDAK TAHU. Hasil bench belum disertakan.", rendered)
        self.assertIn("TIDAK TAHU. Receipt pelatihan belum disertakan.", rendered)
        self.assertIn("Lisensi TIDAK TAHU", rendered)
        self.assertNotIn("| Domain |", rendered)

    def test_incomplete_domain_carries_count_and_unknown_without_fake_zero(self):
        raw = fixture()
        raw["benchmark"]["input"]["results"][0]["after"] = None
        result = card(raw)
        reading = result["benchmark"]["domains"][0]
        self.assertEqual(reading["status"], "incomplete")
        self.assertEqual(reading["compared"], 1)
        self.assertIsNone(reading["score_delta_bp"])
        self.assertIn("| reading | 1/2 | TIDAK TAHU | TIDAK TAHU | TIDAK TAHU |", model.markdown(result))

    def test_wrong_artifact_and_mismatched_registry_cannot_be_reported(self):
        raw = fixture()
        artifact = "9" * 64
        raw["artifact"]["sha256"] = artifact
        raw["registry"] = None
        with self.assertRaisesRegex(model.InputError, "bench.*berbeda"):
            card(raw)
        raw = fixture()
        raw["registry"]["artifact_sha256"] = artifact
        with self.assertRaisesRegex(model.InputError, "registry"):
            card(raw)

    def test_source_anchor_covers_user_supplied_claims_and_raw_bench(self):
        raw = fixture()
        actual = identity(raw)
        raw["intended_use"][0]["text"] = "Diubah."
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.compose(raw, actual)
        raw = fixture()
        raw["benchmark"]["input"]["rubric_ref"] = "fixture/other"
        with self.assertRaisesRegex(model.InputError, "anchor bench"):
            card(raw)

    def test_escape_source_markup_and_prevent_line_injection(self):
        raw = fixture()
        raw["artifact"]["id"] = "Card\n## extra"
        raw["limitations"][0] = {"text": "[Taut](https://example.invalid) <img> \n\n |", "ref": "`fixture`"}
        value = model.markdown(card(raw))
        self.assertIn("# Kartu artefak Card &#35;&#35; extra\n", value)
        self.assertIn("&#91;Taut&#93;(https://example.invalid) &lt;img&gt; &#124;", value)
        self.assertNotIn("\n## extra", value)
        self.assertNotIn("<img>", value)
        self.assertIn("&#96;fixture&#96;", value)

    def test_malformed_status_lineage_or_duplicate_dataset_receipts_are_rejected(self):
        for change in ("double_parent", "self_parent", "unknown_status", "dataset", "kind"):
            raw = fixture()
            if change == "dataset":
                raw["training"]["datasets"] *= 2
            elif change == "unknown_status":
                raw["registry"]["status"] = []
            elif change == "self_parent":
                raw["artifact"]["parents"].append(AFTER)
            elif change == "double_parent":
                raw["artifact"]["parents"] *= 2
            else:
                raw["artifact"]["format"] = "unlisted"
            with self.subTest(change=change), self.assertRaises(model.InputError):
                card(raw)

    def test_cli_exports_both_formats_from_same_attested_snapshot(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "source.json"
        path.write_bytes(canonical(raw))
        args = [str(path), "--expect-input-sha256", identity(raw)]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(out.getvalue(), model.markdown(card(raw)))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([*args, "--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), card(raw))
        self.assertEqual(path.read_bytes(), canonical(raw))
