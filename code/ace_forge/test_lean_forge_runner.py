"""Verifier batas worker lokal, checkpoint parsial, dan replay."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import lean_forge_runner as model, train_runner
from ace_forge._forge_io import canonical
from ace_forge.test_train_runner import fixture as runner_fixture, wire


def prepared(root):
    plan, bundles, sha = runner_fixture()
    p, b = root / "plan.json", root / "bundles.json"
    p.write_bytes(canonical(plan))
    b.write_bytes(canonical(bundles))
    checkpoints = list(train_runner.run(plan, bundles, sha))
    return p, b, sha, checkpoints


class LeanTests(unittest.TestCase):
    def test_real_local_worker_reproduces_numeric_fixture_under_limit(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        result = model.run(p, b, sha, memory_mib=128, timeout_seconds=5)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["requested_memory_mib"], 128)
        self.assertEqual(result["new_checkpoints"], checkpoints)
        self.assertEqual(result["head_sha256"], checkpoints[-1]["sha256"])
        self.assertEqual(result["start_head_sha256"], train_runner.genesis(sha))
        self.assertEqual(result["job_count"], result["checkpoint_count"])

    def test_real_worker_resumes_from_external_head_and_leaves_files_untouched(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        path = root / "prefix.jsonl"
        content = wire(checkpoints[:1])
        path.write_bytes(content)
        evidence = model.run(p, b, sha, memory_mib=128, timeout_seconds=5,
                             checkpoint=path, expected_head=checkpoints[0]["sha256"])
        self.assertEqual(evidence["new_checkpoints"], checkpoints[1:])
        self.assertEqual(evidence["checkpoint_count"], 2)
        self.assertEqual(path.read_bytes(), content)

    def test_timeout_replays_only_complete_checkpoint_lines(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        truncated = wire(checkpoints[:1]) + b'{"sequence":2'
        with patch.object(model.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 1, output=truncated)):
            result = model.run(p, b, sha, memory_mib=128, timeout_seconds=1)
        self.assertEqual(result["status"], "deadline")
        self.assertEqual(result["new_checkpoints"], checkpoints[:1])
        self.assertEqual(result["head_sha256"], checkpoints[0]["sha256"])
        self.assertIsNone(result["worker_exit"])

    def test_memory_and_unknown_exit_do_not_fabricate_completed_jobs(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, _ = prepared(root)
        for code, label in ((model.MEMORY_EXIT, "memory_limit"), (model.INPUT_EXIT, "worker_rejected"),
                            (-9, "worker_stopped")):
            with self.subTest(code=code), patch.object(model.subprocess, "run",
                                                       return_value=subprocess.CompletedProcess([], code, stdout=b"")):
                result = model.run(p, b, sha, memory_mib=32, timeout_seconds=4)
            self.assertEqual(result["status"], label)
            self.assertEqual(result["new_checkpoints"], [])
            self.assertEqual(result["worker_exit"], code)

    def test_output_claims_and_tampered_receipt_are_independently_rejected(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        checkpoints[0]["receipt"]["trace"][0]["train_mse"] += 1
        values = (wire(checkpoints), b"", b'{"incomplete":1', b'not json\n')
        for value in values:
            with self.subTest(value=value[:20]), patch.object(model.subprocess, "run",
                                                              return_value=subprocess.CompletedProcess([], 0, stdout=value)):
                with self.assertRaises(ValueError):
                    model.run(p, b, sha, memory_mib=128, timeout_seconds=3)

    def test_invalid_resume_plan_or_limit_never_invoke_worker(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        log = root / "prefix.jsonl"
        log.write_bytes(wire(checkpoints[:1]))
        for changes in (
            {"memory_mib": 0}, {"timeout_seconds": True}, {"checkpoint": log},
            {"checkpoint": log, "expected_head": checkpoints[-1]["sha256"]},
        ):
            options = {"memory_mib": 128, "timeout_seconds": 5, **changes}
            with self.subTest(options=options), patch.object(model.subprocess, "run") as worker:
                with self.assertRaises(model.InputError):
                    model.run(p, b, sha, **options)
                worker.assert_not_called()

    def test_worker_environment_is_local_and_does_not_inherit_external_settings(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        with patch.dict("os.environ", {"FIXTURE_UNRELATED_SETTING": "external", "PYTHONPATH": "/outside"}):
            with patch.object(model.subprocess, "run",
                              return_value=subprocess.CompletedProcess([], 0, stdout=wire(checkpoints))) as worker:
                model.run(p, b, sha, memory_mib=128, timeout_seconds=8)
        args, options = worker.call_args
        self.assertEqual(args[0][1:3], ["-m", "ace_forge.lean_forge_runner"])
        self.assertEqual(options["timeout"], 8)
        self.assertNotEqual(options["env"]["PYTHONPATH"], "/outside")
        self.assertNotIn("FIXTURE_UNRELATED_SETTING", options["env"])

    def test_rlimit_cap_never_raises_an_inherited_soft_or_hard_limit(self):
        linux = model.resource
        for inherited, expected in (((linux.RLIM_INFINITY, linux.RLIM_INFINITY), 128),
                                    ((48 * model.MIB, 64 * model.MIB), 48),
                                    ((linux.RLIM_INFINITY, 32 * model.MIB), 32)):
            with self.subTest(inherited=inherited), patch.object(linux, "getrlimit", return_value=inherited):
                with patch.object(linux, "setrlimit") as set_:
                    model._set_memory(128)
                set_.assert_called_once_with(linux.RLIMIT_AS, (expected * model.MIB, inherited[1]))

    def test_cli_reports_partial_prefix_and_preserves_disk_inputs(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        before = p.read_bytes(), b.read_bytes()
        call = [str(p), str(b), "--expect-plan-sha256", sha, "--memory-mib", "128", "--timeout-seconds", "2"]
        partial = subprocess.CompletedProcess([], model.MEMORY_EXIT, stdout=wire(checkpoints[:1]))
        with patch.object(model.subprocess, "run", return_value=partial), redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(call), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["head_sha256"], checkpoints[0]["sha256"])
        self.assertEqual((p.read_bytes(), b.read_bytes()), before)

    def test_resume_completed_plan_allocates_no_additional_checkpoints(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, checkpoints = prepared(root)
        path = root / "all.jsonl"
        path.write_bytes(wire(checkpoints))
        result = model.run(p, b, sha, memory_mib=128, timeout_seconds=5,
                           checkpoint=path, expected_head=checkpoints[-1]["sha256"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["new_checkpoints"], [])
        self.assertEqual(result["checkpoint_count"], len(checkpoints))

    def test_stdout_entirely_absent_and_incomplete_header_are_handled_differently(self):
        self.assertEqual(model._receipt_prefix(None, "deadline"), [])
        self.assertEqual(model._receipt_prefix(b'{"token":', "worker_stopped"), [])
        with self.assertRaisesRegex(model.InputError, "terpotong"):
            model._receipt_prefix(b'{"token":', "complete")
        with patch.object(train_runner, "MAX_LOG_BYTES", 1):
            with self.assertRaisesRegex(model.InputError, "Output worker"):
                model._receipt_prefix(b'{}\n', "deadline")

    def test_altered_bundle_fails_parent_gate_before_forking_process(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        p, b, sha, _ = prepared(root)
        bundles = json.loads(b.read_bytes())
        bundles[-1]["source"]["pairs"][0]["chosen"]["features"][0] += 1
        b.write_bytes(canonical(bundles))
        with patch.object(model.subprocess, "run") as subprocess_:
            with self.assertRaisesRegex(model.InputError, "berubah"):
                model.run(p, b, sha, memory_mib=128, timeout_seconds=2)
            subprocess_.assert_not_called()

    def test_started_worker_emits_zero_only_when_tasks_already_complete(self):
        self.assertEqual(model._receipt_prefix(b"", "complete"), [])
        self.assertEqual(model._receipt_prefix(b'{"sequence":1}\n', "complete"), [{"sequence": 1}])
