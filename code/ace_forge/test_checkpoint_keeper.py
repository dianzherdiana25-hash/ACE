"""Verifier manifest lokal, anchor eksternal, dan artefak checkpoint."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import checkpoint_keeper as model, train_runner
from ace_forge._forge_io import canonical, identity
from ace_forge.test_train_runner import fixture as runner_fixture


def make(root):
    (root / "one").mkdir()
    (root / "two").mkdir()
    (root / "one" / "state.json").write_bytes(b'{"fixture":1}\n')
    (root / "two" / "state.json").write_bytes(b'{"fixture":2}\n')
    (root / "shared.bin").write_bytes(b"fixture file")
    return {"plan_ref": "fixture/checkpoint", "run_id": "fixture/run", "checkpoints": [
        {"id": "one", "receipt_sha256": "a" * 64, "receipt_ref": "fixture/receipt/one",
         "files": ["shared.bin", "one/state.json"]},
        {"id": "two", "receipt_sha256": "b" * 64, "receipt_ref": "fixture/receipt/two",
         "files": ["two/state.json", "shared.bin"]},
    ]}


class CustodyTests(unittest.TestCase):
    def test_seal_binds_file_bytes_receipt_refs_and_predecessor(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        raw = make(root)
        observed = model.seal(raw, identity(raw), root)
        first, last = observed["checkpoints"]
        self.assertEqual(first["receipt_ref"], "fixture/receipt/one")
        self.assertEqual(first["previous_sha256"], observed["genesis_sha256"])
        self.assertEqual(last["previous_sha256"], first["sha256"])
        self.assertEqual(last["sha256"], observed["head_sha256"])
        expected = hashlib.sha256((root / "one/state.json").read_bytes()).hexdigest()
        self.assertEqual(first["files"][0], {"path": "one/state.json", "bytes": 14, "sha256": expected})
        verified = model.verify(raw, identity(raw), root, observed, last["sha256"])
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["findings"], [])

    def test_changed_bytes_are_located_by_checkpoint_and_file(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        raw = make(root)
        manifest = model.seal(raw, identity(raw), root)
        (root / "two/state.json").write_bytes(b'{"fixture":3}\n')
        probe = model.verify(raw, identity(raw), root, manifest, manifest["head_sha256"])
        self.assertFalse(probe["valid"])
        self.assertIn("current_head_mismatch", probe["reasons"])
        self.assertEqual(probe["findings"], [
            {"checkpoint": "two", "path": "two/state.json", "reason": "manifest_or_bytes_changed"},
        ])

    def test_reseal_of_different_bytes_cannot_reuse_external_head(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        raw = make(root)
        first = model.seal(raw, identity(raw), root)
        (root / "shared.bin").write_bytes(b"edited")
        refreshed = model.seal(raw, identity(raw), root)
        rejected = model.verify(raw, identity(raw), root, refreshed, first["head_sha256"])
        self.assertFalse(rejected["valid"])
        self.assertEqual(rejected["reasons"], ["recorded_head_mismatch", "current_head_mismatch"])
        self.assertEqual(rejected["findings"], [])

    def test_missing_file_blocks_seal_and_is_located_in_verify(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        raw = make(root)
        manifest = model.seal(raw, identity(raw), root)
        (root / "shared.bin").unlink()
        with self.assertRaisesRegex(model.InputError, "shared.bin"):
            model.seal(raw, identity(raw), root)
        result = model.verify(raw, identity(raw), root, manifest, manifest["head_sha256"])
        self.assertEqual(result["reasons"], ["artifact_read_failed"])
        self.assertEqual(result["findings"], [
            {"checkpoint": "one", "path": "shared.bin", "reason": "artifact_missing"},
            {"checkpoint": "two", "path": "shared.bin", "reason": "artifact_missing"},
        ])

    def test_moved_header_or_truncated_or_reordered_manifest_fails(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        raw = make(root)
        original = model.seal(raw, identity(raw), root)
        for mutate, reason in (
            (lambda item: item.update(run_id="untrusted"), "manifest_header_changed"),
            (lambda item: item["checkpoints"].pop(), "checkpoint_count_mismatch"),
            (lambda item: item["checkpoints"].reverse(), "checkpoint_order_or_id_mismatch"),
            (lambda item: item["checkpoints"][0]["files"].append(item["checkpoints"][0]["files"][0]),
             "duplicate_manifest_path"),
        ):
            case = deepcopy(original)
            mutate(case)
            with self.subTest(reason=reason):
                result = model.verify(raw, identity(raw), root, case, original["head_sha256"])
                self.assertFalse(result["valid"])
                self.assertIn(reason, [row["reason"] for row in result["findings"]])

    def test_untrusted_paths_are_never_followed_or_listed_in_sealed_artifact(self):
        parent = Path(self.enterContext(TemporaryDirectory()))
        root = parent / "read-root"
        root.mkdir()
        raw = make(root)
        outside = parent / "outside.bin"
        outside.write_bytes(b"fixture outside")
        (root / "alias").symlink_to(outside)
        for path in ("../outside.bin", str(outside), "alias", "one//state.json", "one/./state.json"):
            raw["checkpoints"][0]["files"] = [path]
            with self.subTest(path=path), self.assertRaisesRegex(model.InputError, "Checkpoint"):
                model.seal(raw, identity(raw), root)

    def test_custody_consumes_actual_numeric_runner_checkpoint_receipts(self):
        p, inputs, key = runner_fixture()
        checkpoints = list(train_runner.run(p, inputs, key))
        root = Path(self.enterContext(TemporaryDirectory()))
        registered = []
        for record in checkpoints:
            name = f"{record['id']}.json"
            content = canonical(record)
            (root / name).write_bytes(content)
            registered.append({"id": record["id"], "receipt_sha256": record["sha256"],
                               "receipt_ref": f"fixture/training/{record['id']}", "files": [name]})
        raw = {"plan_ref": "fixture/run-seal", "run_id": "fixture/pair", "checkpoints": registered}
        manifest = model.seal(raw, identity(raw), root)
        self.assertEqual([row["receipt_sha256"] for row in manifest["checkpoints"]],
                         [row["sha256"] for row in checkpoints])
        self.assertTrue(model.verify(raw, identity(raw), root, manifest, manifest["head_sha256"])["valid"])

    def test_cli_seal_then_verify_keeps_original_files_and_checks_anchors(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        raw = make(root)
        plan, path = root / "plan.json", root / "manifest.json"
        plan.write_bytes(canonical(raw))
        args = [str(plan), str(root), "--expect-plan-sha256", identity(raw)]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(args), 0)
        path.write_text(output.getvalue(), encoding="utf-8")
        sealed = json.loads(output.getvalue())
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([*args, "--verify", str(path), "--expect-head", sealed["head_sha256"]]), 0)
        self.assertTrue(json.loads(output.getvalue())["valid"])
        self.assertEqual(plan.read_bytes(), canonical(raw))
        self.assertEqual((root / "one/state.json").read_bytes(), b'{"fixture":1}\n')
