"""Uji checkpoint yang bisa diputar ulang dan resume optimizer fixture."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import train_runner as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_lora_trainer import fixture as dense_fixture
from ace_forge.test_preference_trainer import fixture as preference_fixture


def fixture():
    jobs, inputs = [], []
    for key, kind, make in (("dense", "lora_dense", dense_fixture), ("preference", "dpo_linear", preference_fixture)):
        recipe, source, anchor = make()
        jobs.append({"id": key, "optimizer": kind, "recipe_sha256": identity(recipe), "source_sha256": anchor})
        inputs.append({"id": key, "recipe": recipe, "source": source})
    plan = {"plan_ref": "fixture/plan", "jobs": jobs}
    return plan, inputs, identity(plan)


def wire(records):
    return b"".join(canonical(record) + b"\n" for record in records)


class RunnerTests(unittest.TestCase):
    def test_local_optimizer_receipts_form_deterministic_chain(self):
        plan, inputs, anchor = fixture()
        first, second = list(model.run(plan, inputs, anchor))
        self.assertEqual((first["id"], second["id"]), ("dense", "preference"))
        self.assertEqual(first["previous_sha256"], model.genesis(anchor))
        self.assertEqual(second["previous_sha256"], first["sha256"])
        for index, checkpoint in enumerate((first, second), 1):
            self.assertEqual(checkpoint["sequence"], index)
            header = {key: value for key, value in checkpoint.items() if key != "sha256"}
            self.assertEqual(checkpoint["sha256"], identity(header))
            product = checkpoint["receipt"]
            self.assertEqual(product["adapter_sha256"], identity(product["adapter"]))
        self.assertEqual([first, second], list(model.run(plan, inputs[::-1], anchor)))

    def test_resume_skips_completed_job_and_emits_identical_suffix(self):
        plan, inputs, anchor = fixture()
        first, second = list(model.run(plan, inputs, anchor))
        with patch.object(model.lora_trainer, "fit", side_effect=AssertionError("resume repeated dense job")):
            resumed = list(model.run(plan, inputs, anchor, checkpoints=[first], expected_head=first["sha256"]))
        self.assertEqual(resumed, [second])
        self.assertEqual(list(model.run(plan, inputs, anchor,
                                        checkpoints=[first, second], expected_head=second["sha256"])), [])

    def test_failure_after_first_job_does_not_erase_completed_prefix(self):
        plan, inputs, anchor = fixture()
        expected = list(model.run(plan, inputs, anchor))
        with patch.object(model.preference_trainer, "fit", side_effect=ValueError("fixture optimizer abort")):
            stream = model.run(plan, inputs, anchor)
            recorded = next(stream)
            self.assertEqual(recorded, expected[0])
            with self.assertRaisesRegex(model.InputError, "preference.*abort"):
                next(stream)
        pending = list(model.run(plan, inputs, anchor, checkpoints=[recorded], expected_head=recorded["sha256"]))
        self.assertEqual(pending, expected[1:])

    def test_failed_receipt_integrity_never_yields_a_checkpoint(self):
        plan, inputs, anchor = fixture()
        with patch.object(model.lora_trainer, "fit", return_value={"schema": "ace.lora-train-receipt.v1"}):
            with self.assertRaisesRegex(model.InputError, "Receipt"):
                next(model.run(plan, inputs, anchor))

    def test_tampered_inputs_are_refused_before_any_optimizer_call(self):
        plan, inputs, anchor = fixture()
        with patch.object(model.lora_trainer, "fit", side_effect=AssertionError("optimizer called")):
            inputs[1]["source"]["pairs"][0]["chosen"]["baseline_logp"] = -5
            with self.assertRaisesRegex(model.InputError, "Bundel.*berubah"):
                next(model.run(plan, inputs, anchor))
            plan["jobs"].reverse()
            with self.assertRaisesRegex(model.InputError, "Rencana.*anchor"):
                next(model.run(plan, inputs, anchor))

    def test_changed_truncated_rehashed_and_reordered_logs_fail_closed(self):
        plan, inputs, anchor = fixture()
        completed = list(model.run(plan, inputs, anchor))
        expected = completed[-1]["sha256"]
        edited = deepcopy(completed)
        edited[1]["receipt"]["trace"].pop()
        recomputed = {**edited[1], "sha256": identity({k: v for k, v in edited[1].items() if k != "sha256"})}
        for logs in (edited, [completed[0], recomputed], completed[:-1], completed[::-1]):
            with self.subTest(logs=len(logs)), self.assertRaises(model.InputError):
                list(model.run(plan, inputs, anchor, checkpoints=logs, expected_head=expected))
        self.assertEqual(len(completed), 2)

    def test_resume_requires_both_log_and_anchor_even_for_empty_prefix(self):
        plan, inputs, anchor = fixture()
        for inputs_only in ({"checkpoints": []}, {"expected_head": model.genesis(anchor)}):
            with self.subTest(inputs_only=inputs_only), self.assertRaisesRegex(model.InputError, "Resume"):
                list(model.run(plan, inputs, anchor, **inputs_only))
        stream = list(model.run(plan, inputs, anchor, checkpoints=[], expected_head=model.genesis(anchor)))
        self.assertEqual(len(stream), 2)

    def test_cli_emits_increment_only_and_keeps_source_and_resume_files(self):
        plan, inputs, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        plan_path, inputs_path, log = (root / key for key in ("plan.json", "bundles.json", "run.jsonl"))
        plan_path.write_bytes(canonical(plan))
        inputs_path.write_bytes(canonical(inputs))
        full = list(model.run(plan, inputs, anchor))
        log.write_bytes(wire(full[:1]))
        args = [str(plan_path), str(inputs_path), "--expect-plan-sha256", anchor,
                "--checkpoint-from", str(log), "--expect-head", full[0]["sha256"]]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(out.getvalue()), full[-1])
        self.assertEqual(log.read_bytes(), wire(full[:1]))
        self.assertEqual(inputs_path.read_bytes(), canonical(inputs))

    def test_truncated_file_rejected_without_any_cli_output(self):
        plan, inputs, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        plan_file, bundle_file, log = (root / name for name in ("plan.json", "bundle.json", "log.jsonl"))
        plan_file.write_bytes(canonical(plan))
        bundle_file.write_bytes(canonical(inputs))
        only = next(model.run(plan, inputs, anchor))
        log.write_bytes(wire([only]).rstrip(b"\n"))
        with redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            model.main([str(plan_file), str(bundle_file), "--expect-plan-sha256", anchor,
                        "--checkpoint-from", str(log), "--expect-head", only["sha256"]])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(output.getvalue(), "")

    def test_cli_keeps_fully_flushed_checkpoint_when_next_optimizer_errors(self):
        plan, inputs, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        plan_file, bundle_file = root / "plan.json", root / "bundle.json"
        plan_file.write_bytes(canonical(plan))
        bundle_file.write_bytes(canonical(inputs))
        args = [str(plan_file), str(bundle_file), "--expect-plan-sha256", anchor]
        with patch.object(model.preference_trainer, "fit", side_effect=ValueError("fixture abort")):
            with redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()) as errors:
                with self.assertRaises(SystemExit) as error:
                    model.main(args)
        self.assertEqual(error.exception.code, 2)
        self.assertIn("preference", errors.getvalue())
        first, = output.getvalue().splitlines()
        self.assertEqual(json.loads(first), next(model.run(plan, inputs, anchor)))
