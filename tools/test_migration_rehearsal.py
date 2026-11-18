from pathlib import Path
import tempfile
import unittest

from tools.instance_kit import build_instance_config
from tools.migration_rehearsal import rehearse
from tools.portability_pack import pack_bundle


class MigrationRehearsalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = build_instance_config(instance_id="source", base_dir=self.root, port_base=18100)
        self.target = build_instance_config(instance_id="preview", base_dir=self.root, port_base=18200)
        self.original = Path(self.source["directories"]["workspace_dir"])
        self.original.mkdir(parents=True)
        self.destination = Path(self.target["directories"]["workspace_dir"])
        self.destination.mkdir(parents=True)
        (self.destination / "keep.txt").write_text("unrelated")
        (self.original / "notes").mkdir()
        self.note = self.original / "notes" / "manual.txt"
        self.note.write_bytes(b"fixture\x00\n")

    def bundle(self, name="capsule", *, include="notes/manual.txt"):
        path = self.root / name
        report = pack_bundle(source_dir=self.original, out_path=path, include_paths=[include])
        return path, report["manifest_sha256"]

    def run_drill(self, bundle, digest, *, target=None):
        return rehearse(bundle, self.source, self.target if target is None else target,
                        expected_manifest_sha256=digest)

    def assert_no_preview_left(self):
        self.assertEqual([x.name for x in self.destination.iterdir()], ["keep.txt"])
        self.assertEqual((self.destination / "keep.txt").read_text(), "unrelated")

    def test_roundtrip_for_directory_and_archive(self):
        for name in ("capsule", "capsule.tar.gz"):
            with self.subTest(name=name):
                bundle, digest = self.bundle(name)
                report = self.run_drill(bundle, digest)
                self.assertEqual(report["restored_and_rechecked"], 1)
                self.assertEqual(report["manifest_sha256"], digest)
                self.assertIs(report["activation_authorized"], False)
                self.assert_no_preview_left()

    def test_tamper_and_self_consistent_wrong_bundle_are_rejected(self):
        bundle, digest = self.bundle()
        self.note.write_bytes(b"other")
        replacement, _ = self.bundle("replacement")
        with self.assertRaisesRegex(ValueError, "trusted source"):
            self.run_drill(replacement, digest)
        (bundle / "payload" / "notes" / "manual.txt").write_bytes(b"other")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.run_drill(bundle, digest)
        self.assert_no_preview_left()

    def test_active_target_and_port_collision_are_rejected(self):
        bundle, digest = self.bundle()
        for changes in ({"second_instance_active": True}, {"ports": self.source["ports"]}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "isolation"):
                self.run_drill(bundle, digest, target=self.target | changes)
        self.assert_no_preview_left()

    def test_excluded_payload_is_rejected_even_with_matching_pin(self):
        # Synthetic filename and bytes, no credential material.
        (self.original / "test-token.txt").write_text("fixture")
        bundle, digest = self.bundle(include="test-token.txt")
        with self.assertRaisesRegex(ValueError, "policy"):
            self.run_drill(bundle, digest)
        self.assert_no_preview_left()
