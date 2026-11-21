"""Verifier pilihan rollback, hash artefak, dan pembacaan jalur fixture."""
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import model_rollback as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_model_registry_v2 import event, records, review


ACTIVE = "a" * 64
OLDER = b"fixture weights for base"
NEARER = b"fixture weights for newer version"
OLD_SHA, NEW_SHA = (hashlib.sha256(value).hexdigest() for value in (OLDER, NEARER))


def fixture(root, *, path="weights/new.bin", near_status="qualified", near_domain="fixture/domain"):
    old, new = event(OLD_SHA), event(NEW_SHA, "adapter", [OLD_SHA])
    old["values"]["artifact_ref"], new["values"]["artifact_ref"] = "weights/base.bin", path
    new["values"]["domain"] = near_domain
    log, head = records(old, new, review(OLD_SHA), review(NEW_SHA, near_status))
    root = root / "artifacts"
    (root / "weights").mkdir(parents=True)
    (root / "weights/base.bin").write_bytes(OLDER)
    (root / "weights/new.bin").write_bytes(NEARER)
    selector = {"selector_ref": "fixture/selector", "domain": "fixture/domain", "generation": 3,
                "active_sha256": ACTIVE, "history": [
                    {"generation": index, "artifact_sha256": key, "activation_ref": f"fixture/on/{index}"}
                    for index, key in enumerate((OLD_SHA, NEW_SHA, ACTIVE), 1)
                ]}
    request = {"request_ref": "fixture/rollback", "reason_ref": "fixture/diagnosis", "from_artifact_sha256": ACTIVE}
    return selector, identity(selector), log, head, request, root


class RollbackTests(unittest.TestCase):
    def test_nearest_qualified_version_with_matching_bytes_is_selected(self):
        inputs = fixture(Path(self.enterContext(TemporaryDirectory())))
        result = model.plan(*inputs)
        picked = result["selected"]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(picked["artifact_sha256"], NEW_SHA)
        self.assertEqual(picked["artifact_ref"], "weights/new.bin")
        self.assertEqual(picked["review_ref"], f"fixture/result/{NEW_SHA[:4]}")
        self.assertEqual(result["proposed_selector"]["generation"], 4)
        self.assertEqual(result["proposed_selector"]["active_sha256"], NEW_SHA)
        self.assertEqual(result["proposed_selector_sha256"], identity(result["proposed_selector"]))
        self.assertEqual(inputs[0]["active_sha256"], ACTIVE)
        self.assertEqual(len(result["candidates_checked"]), 1)

    def test_tampered_or_absent_recent_version_falls_back_with_named_blocker(self):
        for tampered in (True, False):
            inp = fixture(Path(self.enterContext(TemporaryDirectory())))
            path = inp[-1] / "weights/new.bin"
            if tampered:
                path.write_bytes(b"fixture corruption")
            else:
                path.unlink()
            result = model.plan(*inp)
            self.assertEqual(result["selected"]["artifact_sha256"], OLD_SHA)
            expected = "artifact_sha256_mismatch" if tampered else "artifact_missing"
            self.assertEqual(result["candidates_checked"][0]["blocker"], expected)

    def test_unknown_rejected_or_wrong_domain_version_does_not_win(self):
        args = fixture(Path(self.enterContext(TemporaryDirectory())), near_status="rejected")
        self.assertEqual(model.plan(*args)["candidates_checked"][0]["blocker"], "not_qualified")
        args = fixture(Path(self.enterContext(TemporaryDirectory())), near_domain="fixture/elsewhere")
        self.assertEqual(model.plan(*args)["candidates_checked"][0]["blocker"], "wrong_domain")
        selector, _, log, head, request, root = fixture(Path(self.enterContext(TemporaryDirectory())))
        selector["history"][1]["artifact_sha256"] = "f" * 64
        self.assertEqual(model.plan(selector, identity(selector), log, head, request, root)
                         ["candidates_checked"][0]["blocker"], "not_registered")

    def test_symlinks_traversal_and_nonregular_inputs_fail_closed(self):
        for pointer in ("../leak.bin", "/abs/leak.bin", "weights/link.bin", "weights/linked_dir/new.bin", "weights", "weights/fifo"):
            with self.subTest(pointer=pointer):
                args = fixture(Path(self.enterContext(TemporaryDirectory())), path=pointer)
                root = args[-1]
                path = root / "weights/link.bin"
                path.symlink_to(root / "weights/new.bin")
                (root / "weights/linked_dir").symlink_to(root / "weights", target_is_directory=True)
                os.mkfifo(root / "weights/fifo")
                result = model.plan(*args)
                self.assertEqual(result["selected"]["artifact_sha256"], OLD_SHA)
                self.assertTrue(result["candidates_checked"][0]["blocker"])

    def test_no_qualified_intact_version_keeps_explicit_hold(self):
        args = fixture(Path(self.enterContext(TemporaryDirectory())), near_status="rejected")
        (args[-1] / "weights/base.bin").unlink()
        value = model.plan(*args)
        self.assertEqual(value["status"], "hold")
        self.assertIsNone(value["proposed_selector"])
        self.assertIsNone(value["selected"])
        self.assertEqual([item["blocker"] for item in value["candidates_checked"]], ["not_qualified", "artifact_missing"])

    def test_stale_request_and_selector_anchor_and_registry_head_are_rejected(self):
        selector, anchor, log, head, request, root = fixture(Path(self.enterContext(TemporaryDirectory())))
        with self.assertRaisesRegex(model.InputError, "Selector.*anchor"):
            model.plan(selector, "0" * 64, log, head, request, root)
        with self.assertRaisesRegex(model.InputError, "Head.*anchor"):
            model.plan(selector, anchor, log[:-1], head, request, root)
        with self.assertRaisesRegex(model.InputError, "aktif.*berbeda"):
            model.plan(selector, anchor, log, head, {**request, "from_artifact_sha256": OLD_SHA}, root)
        selector["history"][-1]["artifact_sha256"] = NEW_SHA
        with self.assertRaisesRegex(model.InputError, "Aktivasi"):
            model.plan(selector, identity(selector), log, head, request, root)

    def test_cli_returns_selector_proposal_and_keeps_original_bytes(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        selector, anchor, log, head, request, artifacts = fixture(root)
        s, r, q = root / "selector.json", root / "registry.jsonl", root / "request.json"
        s.write_bytes(canonical(selector))
        r.write_bytes(b"".join(canonical(entry) + b"\n" for entry in log))
        q.write_bytes(canonical(request))
        args = [str(s), str(r), str(q), str(artifacts), "--expect-selector-sha256", anchor,
                "--expect-registry-head", head]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(output.getvalue()), model.plan(selector, anchor, log, head, request, artifacts))
        self.assertEqual(s.read_bytes(), canonical(selector))
        self.assertEqual((artifacts / "weights/new.bin").read_bytes(), NEARER)

    def test_repeated_unusable_version_is_probed_at_its_latest_occurrence_once(self):
        selector, _, log, head, request, root = fixture(Path(self.enterContext(TemporaryDirectory())))
        latest = selector["history"][-1]
        selector["history"] = [*selector["history"][:-1],
                               {"generation": 3, "artifact_sha256": NEW_SHA, "activation_ref": "fixture/on/new-retry"},
                               {**latest, "generation": 4}]
        selector["generation"] = 4
        (root / "weights/new.bin").unlink()
        report = model.plan(selector, identity(selector), log, head, request, root)
        self.assertEqual([item["generation"] for item in report["candidates_checked"]], [3, 1])
        self.assertEqual(report["selected"]["artifact_sha256"], OLD_SHA)

    def test_matching_file_pointed_through_symlinked_root_is_not_accepted(self):
        args = fixture(Path(self.enterContext(TemporaryDirectory())))
        link = args[-1].parent / "alias"
        link.symlink_to(args[-1], target_is_directory=True)
        report = model.plan(*args[:-1], link)
        self.assertEqual(report["status"], "hold")
        self.assertTrue(all(item["blocker"] == "artifact_unreadable_or_unsafe" for item in report["candidates_checked"]))
