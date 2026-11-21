"""Verifier lineage, seal head, dan klasifikasi perubahan per file."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import perception_evidence as model


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.raw = {"schema": "ace.perception-evidence-request.v1", "bundle_ref": "fixture/bundle", "entries": []}
        for key, parents, role in (("report", ["raster"], "report"), ("input", [], "source"),
                                   ("raster", ["input"], "transform")):
            payload = f"{key} bytes".encode()
            (self.root/key).write_bytes(payload)
            self.raw["entries"].append({"id": key, "path": key, "role": role, "parents": parents,
                                        "sha256": None, "declared_bytes": len(payload)})

    def test_seal_topologically_then_show_missing_and_mismatch_separately(self):
        result = model.seal(self.root, model._canonical(self.raw))
        self.assertEqual([row["id"] for row in result["entries"]], ["input", "raster", "report"])
        head = result["head_sha256"]
        self.assertTrue(model.verify(self.root, model._canonical(result), head)["verified"])
        (self.root/"raster").write_bytes(b"garbage!!!!!")
        (self.root/"report").unlink()
        patched = model.verify(self.root, model._canonical(result), head)
        self.assertFalse(patched["verified"])
        self.assertEqual([row["status"] for row in patched["entries"]], ["verified", "mismatch", "missing"])

    def test_cycle_path_escape_and_bad_head_rejected(self):
        result = model.seal(self.root, model._canonical(self.raw))
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.verify(self.root, model._canonical(result), "0"*64)
        self.raw["entries"][2]["parents"] = ["report"]
        with self.assertRaisesRegex(ValueError, "Siklus"):
            model.seal(self.root, model._canonical(self.raw))
        self.raw["entries"][2]["path"] = "../raster"
        with self.assertRaisesRegex(ValueError, "dalam root"):
            model.seal(self.root, model._canonical(self.raw))
