"""Verifier rilis deterministik, inventaris, byte yang berbeda dan anggaran."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from ace_software_factory import release_packager as model
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())) / "product"
        self.source = {"app/main.py": b"pass\n", "README.md": b"Sample\n", "docs/panduan.txt": "Syarat uji".encode()}
        materialize(self.root, self.source)
        self.plan = {"schema": "ace.factory-release-plan.v1", "product_id": "example_product", "version": "1.2.3",
                     "source_ref": "fixture/release", "files": [
                         {"path": name, "sha256": sha256(data).hexdigest(), "bytes": len(data)}
                         for name, data in self.source.items()]}

    def test_reproducible_same_contract_ignores_mtime(self):
        key = identity(self.plan)
        first, report = model.build(self.root, self.plan, key)
        (self.root / "README.md").touch()
        second, other = model.build(self.root, self.plan, key)
        self.assertEqual(first, second)
        self.assertEqual(report, other)
        verified = model.verify(first, report["manifest_sha256"])
        self.assertEqual(verified["verified_files"], 3)
        self.assertEqual(verified["zip_sha256"], report["zip_sha256"])
        with ZipFile(BytesIO(first)) as archive:
            self.assertEqual(archive.read("README.md"), self.source["README.md"])

    def test_same_manifest_rejects_tampered_content_and_extra_path(self):
        valid, report = model.build(self.root, self.plan, identity(self.plan))
        for change in ("README.md", "item.txt"):
            with self.subTest(change=change):
                stream = BytesIO()
                with ZipFile(BytesIO(valid)) as good, ZipFile(stream, "w") as bad:
                    for name in sorted(set(good.namelist()) | {change}):
                        data = b"Struck\n" if name == change else good.read(name)
                        bad.writestr(model._zip_entry(name), data)
                with self.assertRaises(ContractError):
                    model.verify(stream.getvalue(), report["manifest_sha256"])

    def test_rejects_paths_and_zip_variants_that_were_not_authorized(self):
        raw = self.plan["files"][0]
        raw["path"] = "app/../main.py"
        with self.assertRaises(ContractError):
            model.build(self.root, self.plan, identity(self.plan))
        stream = BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED) as extra:
            extra.writestr("app/main.py", b"pass\n")
            extra.writestr(model.MANIFEST, b"{}")
        with self.assertRaisesRegex(ContractError, "Metadata"):
            model.verify(stream.getvalue(), "a" * 64)
