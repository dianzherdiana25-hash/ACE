"""Verifier izin efektif, byte tersimpan dan pembacaan tanpa symlink."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _vision, media_intake as model


ASSET = _vision.encode(3, 2, [2, 25, 40, 56, 80, 100])


def request(**changes):
    return model._canonical({"schema": "ace.perception-intake-request.v1", "source_path": "input.pgm",
                             "source_ref": "fixture/media", "source_sha256": sha256(ASSET).hexdigest(),
                             "bytes": len(ASSET), "kind": "pgm", "purpose": "fixture_ocr", "as_of": "2026-11-21T00:00:00Z",
                             "permission": {"ref": "fixture/permission", "purposes": ["fixture_ocr"],
                                            "start": "2026-11-20T23:00:00Z", "expires": "2026-11-21T01:00:00Z"}, **changes})


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        (self.root/"input.pgm").write_bytes(ASSET)

    def test_permission_rejection_happens_before_reading_media(self):
        for args, status in (({"permission": None}, "permission_missing"),
                             ({"purpose": "different"}, "purpose_not_allowed"),
                             ({"as_of": "2026-11-21T08:00:00+07:00"}, "outside_permission_window")):
            with self.subTest(args=args), patch.object(model._perception_io, "read_relative") as read:
                payload, receipt = model.inspect(self.root, request(**args))
                read.assert_not_called()
                self.assertIsNone(payload)
                self.assertIsNone(receipt["observed_sha256"])
                self.assertEqual(receipt["status"], "held")
                self.assertEqual(receipt["reason"], status)

    def test_ingests_decoded_fixture_and_archives_by_content_without_mutation(self):
        req = request(as_of="2026-11-20T23:00:00Z")
        payload, receipt = model.inspect(self.root, req)
        self.assertEqual(payload, ASSET)
        self.assertEqual(receipt["request_sha256"], sha256(req).hexdigest())
        self.assertEqual(receipt["observed_sha256"], sha256(ASSET).hexdigest())
        self.assertEqual(receipt["permission_ref"], "fixture/permission")
        self.assertEqual(receipt["format"], {"check": "decoded", "width": 3, "height": 2, "gray_max": 255})
        out = self.root/"incoming"
        model._archive(out, payload, receipt)
        self.assertEqual(json.loads((out/"receipt.json").read_bytes()), receipt)
        self.assertEqual((out/receipt["artifact"]).read_bytes(), ASSET)
        with self.assertRaises(FileExistsError):
            model._archive(out, payload, receipt)
        self.assertEqual((self.root/"input.pgm").read_bytes(), ASSET)

    def test_mismatch_path_and_kind_do_not_publish_artifact(self):
        with self.assertRaisesRegex(ValueError, "Hash byte"):
            model.inspect(self.root, request(source_sha256="a"*64))
        with self.assertRaisesRegex(ValueError, "dalam root"):
            model.inspect(self.root, request(source_path="../input.pgm"))
        with self.assertRaisesRegex(ValueError, "format"):
            model.inspect(self.root, request(kind="pdf"))
        (self.root/"link.pgm").symlink_to(self.root/"input.pgm")
        with self.assertRaises(OSError):
            model.inspect(self.root, request(source_path="link.pgm"))
        self.assertFalse((self.root/"incoming").exists())

    def test_container_check_is_labeled_header_only(self):
        payload = b"%PDF-1.7\nfixture\n%%EOF\n"
        (self.root/"doc.pdf").write_bytes(payload)
        _, result = model.inspect(self.root, request(source_path="doc.pdf", kind="pdf", bytes=len(payload),
                                                      source_sha256=sha256(payload).hexdigest()))
        self.assertEqual(result["format"], {"check": "header_only"})
        self.assertEqual(result["kind"], "pdf")
