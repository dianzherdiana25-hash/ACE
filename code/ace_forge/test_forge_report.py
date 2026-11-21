"""Verifier laporan lifecycle, receipt training, dan gap evidence."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import brain_bench, forge_report as model, train_runner
from ace_forge._forge_io import canonical, identity
from ace_forge.test_brain_bench import fixture as brain_fixture
from ace_forge.test_experiment_tracker import event, plan as event_plan
from ace_forge.test_train_runner import fixture as training_fixture


def fixture():
    plan, bundles, key = training_fixture()
    records = list(train_runner.run(plan, bundles, key))
    final = records[-1]
    begin = event_plan("fixture-run", 7)
    begin["values"]["recipe_sha256"] = key
    ledger = {"ledger_ref": "fixture/ledger", "events": [
        begin, event("fixture-run", "start", 1, {"runner_ref": "fixture/runner"}),
        event("fixture-run", "checkpoint", 2, {"checkpoint_sha256": final["sha256"], "checkpoint_ref": "fixture/checkpoint",
                                              "spent_delta_units": 5}),
        event("fixture-run", "finish", 3, {"result_ref": "fixture/result", "spent_delta_units": 3}),
    ]}
    bench, _ = brain_fixture()
    artifact = final["receipt"]["adapter_sha256"]
    bench["after_sha256"] = artifact
    for row in bench["results"]:
        row["after"]["artifact_sha256"] = artifact
    return {"experiment_id": "fixture-run", "report_ref": "fixture/report",
            "ledger": {"data": ledger, "ledger_sha256": identity(ledger)},
            "training": {"plan": plan, "plan_sha256": key, "checkpoints": records,
                         "head_sha256": final["sha256"], "source_ref": "fixture/recorded"},
            "benchmark": {"data": bench, "bench_sha256": brain_bench.bench_digest(bench), "source_ref": "fixture/bench"}}


def report(raw):
    return model.report(raw, identity(raw))


class ReportTests(unittest.TestCase):
    def test_integrates_actual_runner_prefix_experiment_and_heldout_receipts(self):
        raw = fixture()
        result = report(raw)
        self.assertEqual(result["evidence_gaps"], [])
        self.assertEqual(result["experiment"]["spent_units"], 8)
        self.assertTrue(result["experiment"]["over_budget"])
        self.assertEqual(result["training"]["completed_jobs"], 2)
        self.assertEqual(result["training"]["head_sha256"], raw["training"]["head_sha256"])
        self.assertEqual(result["benchmark"]["artifact_sha256"], result["training"]["artifacts"][-1]["adapter_sha256"])
        self.assertEqual(result["benchmark"]["source_ref"], "fixture/bench")
        rendered = model.markdown(result)
        self.assertIn("Unit terpakai 8 dari 7. Selisih -1.", rendered)
        self.assertIn("| reading | 2/2 | 500 |", rendered)
        self.assertIn("Sumber fixture/recorded", rendered)

    def test_absent_run_and_bench_components_are_explicit_gaps(self):
        raw = fixture()
        raw.update(training=None, benchmark=None)
        result = report(raw)
        self.assertEqual(result["evidence_gaps"], ["training_evidence_missing", "held_out_bench_missing"])
        rendered = model.markdown(result)
        self.assertIn("TIDAK TAHU. Prefix checkpoint", rendered)
        self.assertIn("TIDAK TAHU. Bench", rendered)

    def test_training_head_and_ledger_anchor_are_verified_before_building(self):
        raw = fixture()
        raw["training"]["head_sha256"] = "0"*64
        with self.assertRaisesRegex(model.InputError, "Head"):
            report(raw)
        raw = fixture()
        raw["ledger"]["data"]["events"][-1]["values"]["spent_delta_units"] = 2
        with self.assertRaisesRegex(model.InputError, "anchor"):
            report(raw)
        raw = fixture()
        raw["training"]["checkpoints"][0]["receipt"]["trace"].pop()
        with self.assertRaisesRegex(model.InputError, "Rantai"):
            report(raw)

    def test_anchored_bench_artifact_must_belong_to_checkpoint_receipt(self):
        raw = fixture()
        bench = raw["benchmark"]["data"]
        bench["after_sha256"] = "0"*64
        for row in bench["results"]:
            row["after"]["artifact_sha256"] = "0"*64
        raw["benchmark"]["bench_sha256"] = brain_bench.bench_digest(bench)
        with self.assertRaisesRegex(model.InputError, "di luar checkpoint"):
            report(raw)

    def test_partial_bench_reports_coverage_and_unknown_delta(self):
        raw = fixture()
        raw["benchmark"]["data"]["results"][0]["after"] = None
        product = report(raw)
        self.assertEqual(product["evidence_gaps"], ["incomplete_bench"])
        self.assertIn("| reading | 1/2 | TIDAK TAHU |", model.markdown(product))

    def test_partial_training_prefix_allowed_only_if_ledger_agrees(self):
        raw = fixture()
        prefix = raw["training"]["checkpoints"][:1]
        raw["training"].update(checkpoints=prefix, head_sha256=prefix[0]["sha256"])
        raw["benchmark"] = None
        with self.assertRaisesRegex(model.InputError, "prefix"):
            report(raw)
        ledger = raw["ledger"]["data"]
        ledger["events"] = ledger["events"][:2]
        raw["ledger"]["ledger_sha256"] = identity(ledger)
        result = report(raw)
        self.assertEqual(result["experiment"]["status"], "running")
        self.assertEqual(result["evidence_gaps"], [
            "incomplete_checkpoint_prefix", "held_out_bench_missing", "lifecycle_not_completed",
        ])

    def test_cli_exports_both_formats_with_stable_source_free_of_mutation(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "report-input.json"
        path.write_bytes(canonical(raw))
        call = [str(path), "--expect-input-sha256", identity(raw)]
        for format_, expected in (("markdown", model.markdown(report(raw))),
                                  ("json", canonical(report(raw)).decode()+"\n")):
            with self.subTest(format_=format_), redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main([*call, "--format", format_]), 0)
            self.assertEqual(out.getvalue(), expected)
        self.assertEqual(path.read_bytes(), canonical(raw))

    def test_unknown_run_and_replaced_snapshot_are_rejected(self):
        raw = fixture()
        previous = identity(raw)
        raw["experiment_id"] = "run-unknown"
        with self.assertRaisesRegex(model.InputError, "terdaftar"):
            report(raw)
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.report(raw, previous)

    def test_completed_lifecycle_does_not_validate_unknown_checkpoint_link(self):
        raw = fixture()
        ledger = raw["ledger"]["data"]
        ledger["events"][2]["values"]["checkpoint_sha256"] = "f"*64
        raw["ledger"]["ledger_sha256"] = identity(ledger)
        with self.assertRaisesRegex(model.InputError, "prefix terverifikasi"):
            report(raw)

    def test_no_checkpoints_cannot_supply_artifact_for_a_bench(self):
        raw = fixture()
        raw["training"] = None
        with self.assertRaisesRegex(model.InputError, "artefak dari checkpoint"):
            report(raw)

    def test_markdown_escapes_source_label_and_source_stays_immutable(self):
        raw = fixture()
        raw["report_ref"] = "fixture/[unsafe](file.md)"
        snapshot = canonical(raw)
        rendered = model.markdown(report(raw))
        self.assertNotIn("[unsafe](file.md)", rendered)
        self.assertIn(identity(raw), rendered)
        self.assertEqual(canonical(raw), snapshot)
