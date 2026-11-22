"""Verifier seleksi pasangan dari penilaian dan integrasi optimizer DPO."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import preference_trainer, receipt_preference_miner as model
from ace_forge._forge_io import canonical, identity


RUBRIC = "a"*64
REFERENCE = "b"*64
BASELINE = "c"*64
FEATURES = "fixture/features"


def scored(key, label, score, vector=None):
    return {"prompt_id": key, "receipt_ref": f"fixture/assessment/{key}/{label}", "rubric_sha256": RUBRIC,
            "status": "verified" if score is not None else "unverified", "score_bp": score,
            "choice": {"ref": f"fixture/choice/{key}/{label}", "features": [0, 1] if vector is None else vector,
                       "baseline_logp": -0.3, "reference_logp": -0.4}}


def fixture():
    groups = {
        "good": [scored("good", "c", 0), scored("good", "a", 8000, [1, 0]), scored("good", "b", 7500),
                 scored("good", "unreviewed", None)],
        "tie": [scored("tie", "a", 9999, [1, 0]), scored("tie", "b", 9999), scored("tie", "c", 100)],
        "narrow": [scored("narrow", "a", 7999, [1, 0]), scored("narrow", "b", 7500)],
        "same": [scored("same", "a", 8000), scored("same", "b", 7500), scored("same", "c", 7200, [1, 0])],
        "few": [scored("few", "a", 8000), scored("few", "b", None)],
        "held": [scored("held", "a", 9000, [1, 0]), scored("held", "b", 0)],
    }
    source = {"source_ref": "fixture/receipt_snapshot", "baseline_sha256": BASELINE, "reference_sha256": REFERENCE,
              "feature_spec_ref": FEATURES, "evaluations": [row for group in groups.values() for row in group]}
    plan = {"pairs_ref": "fixture/pairs", "rubric_sha256": RUBRIC, "receipt_snapshot_sha256": identity(source),
            "baseline_sha256": BASELINE, "reference_sha256": REFERENCE, "feature_spec_ref": FEATURES,
            "width": 2, "min_margin_bp": 500,
            "prompts": [{"id": key, "prompt_ref": f"fixture/prompt/{key}", "split": "held_out" if key == "held" else "train"}
                        for key in [*groups, "empty"]]}
    return plan, source


def mine(plan, source):
    return model.mine(plan, source, identity(plan))


def fresh(plan, source):
    plan["receipt_snapshot_sha256"] = identity(source)
    return mine(plan, source)


class ReceiptMiningTests(unittest.TestCase):
    def test_selects_runner_up_and_inclusive_margin_without_heldout_leakage(self):
        plan, source = fixture()
        result = mine(plan, source)
        self.assertEqual(result["counts"], {"held_out": 1, "identical_features": 1, "insufficient_margin": 1,
                                            "insufficient_verified_receipts": 2, "mined": 1, "top_score_tie": 1})
        pair, = result["dataset"]["pairs"]
        self.assertEqual(pair["id"], "good")
        self.assertEqual(pair["chosen"]["ref"], "fixture/choice/good/a")
        self.assertEqual(pair["rejected"]["ref"], "fixture/choice/good/b")
        listed = {row["id"]: row for row in result["prompts"]}
        decision = listed["good"]
        self.assertEqual(decision["margin_bp"], 500)
        self.assertEqual(decision["verified_count"], 3)
        self.assertEqual(decision["unverified_count"], 1)
        self.assertEqual(decision["evidence"]["runner_up_receipt_ref"], "fixture/assessment/good/b")
        self.assertEqual(pair["assessment_ref"], "sha256:" + identity(decision["evidence"]))
        self.assertIsNone(listed["held"]["evidence"])
        self.assertEqual(result["receipt_snapshot_ref"], source["source_ref"])

    def test_emitted_pair_runs_real_preference_optimizer_with_same_anchor(self):
        result = mine(*fixture())
        dataset = result["dataset"]
        raw_recipe = {"recipe_ref": "fixture/dpo_fit", "feature_spec_ref": FEATURES,
                      "baseline_sha256": BASELINE, "reference_sha256": REFERENCE,
                      "pairs_sha256": result["pairs_sha256"], "width": 2, "epochs": 20,
                      "beta": 1, "l2": 0, "learning_rate": 0.1}
        trained = preference_trainer.fit(raw_recipe, dataset, result["pairs_sha256"])
        self.assertEqual(trained["pairs"][0]["assessment_ref"], dataset["pairs"][0]["assessment_ref"])
        self.assertLess(trained["trace"][-1]["mean_dpo_loss"], trained["trace"][0]["mean_dpo_loss"])
        self.assertEqual(result["pairs_sha256"], identity(dataset))

    def test_ties_and_uncertain_margin_are_not_broken_with_a_third_candidate(self):
        report = {row["id"]: row for row in mine(*fixture())["prompts"]}
        for name, status, margin in (("tie", "top_score_tie", 0), ("narrow", "insufficient_margin", 499),
                                     ("same", "identical_features", 500)):
            row = report[name]
            self.assertEqual(row["status"], status)
            self.assertEqual(row["margin_bp"], margin)
            self.assertIsNone(row["evidence"])

    def test_receipt_anchor_binding_separates_recipe_source_and_declared_artifacts(self):
        plan, receipts = fixture()
        anchor = identity(plan)
        receipts["reference_sha256"] = "d"*64
        with self.assertRaisesRegex(model.InputError, "komitmen snapshot"):
            mine(plan, receipts)
        plan["receipt_snapshot_sha256"] = identity(receipts)
        with self.assertRaisesRegex(model.InputError, "Rencana.*anchor"):
            model.mine(plan, receipts, anchor)
        with self.assertRaisesRegex(model.InputError, "probabilitas berbeda"):
            mine(plan, receipts)

    def test_bad_receipt_never_earns_classification_by_score(self):
        for changes in ({"rubric_sha256": "f"*64}, {"prompt_id": "unknown"}, {"score_bp": True},
                        {"status": "unverified"}, {"status": "unknown"}, {"score_bp": None}):
            plan, receipts = fixture()
            receipts["evaluations"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(model.InputError):
                fresh(plan, receipts)

    def test_shared_choice_or_receipt_across_prompts_cannot_count_again(self):
        for name in ("receipt_ref", "choice"):
            plan, receipts = fixture()
            rows = receipts["evaluations"]
            rows[-1][name] = rows[0][name]
            with self.subTest(name=name), self.assertRaisesRegex(model.InputError, "ganda"):
                fresh(plan, receipts)

    def test_reordered_receipts_produce_same_dpo_dataset_and_named_findings(self):
        plan, receipt = fixture()
        reference = mine(plan, receipt)
        receipt["evaluations"].reverse()
        result = fresh(plan, receipt)
        self.assertNotEqual(result["receipt_snapshot_sha256"], reference["receipt_snapshot_sha256"])
        self.assertEqual(result["prompts"], reference["prompts"])
        self.assertEqual(result["pairs_sha256"], reference["pairs_sha256"])

    def test_bounded_log_probability_and_shape_are_enforced_before_emitting_pair(self):
        for changed in ({"baseline_logp": 1}, {"reference_logp": -10001}, {"features": [1]}):
            plan, receipts = fixture()
            receipts["evaluations"][0]["choice"].update(changed)
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                fresh(plan, receipts)

    def test_cli_export_roundtrips_and_empty_set_stays_a_report_only(self):
        plan, receipts = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        path, source = root / "plan", root / "receipts"
        source.write_bytes(canonical(receipts))
        path.write_bytes(canonical(plan))
        args = [str(path), str(source), "--expect-sha256", identity(plan)]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([*args, "--dataset"]), 0)
        self.assertEqual(json.loads(out.getvalue()), mine(plan, receipts)["dataset"])
        self.assertEqual(source.read_bytes(), canonical(receipts))
        plan.update(min_margin_bp=10_000)
        path.write_bytes(canonical(plan))
        args[-1] = identity(plan)
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["dataset"]["pairs"], [])
        with redirect_stderr(StringIO()), redirect_stdout(StringIO()) as out, self.assertRaises(SystemExit) as failure:
            model.main([*args, "--dataset"])
        self.assertEqual(failure.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
