"""Verifier panduan produk, rujukan lintas spesifikasi, dan contoh absen."""
import unittest

from ace_software_factory import architecture_designer, docs_writer, spec_writer
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.test_spec_writer import brief


class DocsTests(unittest.TestCase):
    def setUp(self):
        self.spec = spec_writer.write(brief())
        self.arch = architecture_designer.design(self.spec, {
            "spec_sha256": identity(self.spec), "data_retention": "none", "storage_ref": "fixture/storage",
            "interfaces": [{"id": "show_items", "requirement": "show", "input_shape": "JSON <items>",
                            "output_shape": "Daftar barang", "persist": False, "source_ref": "fixture/interface/1"}],
        })
        self.data = {"schema": "ace.factory-doc-examples.v1", "spec_sha256": identity(self.spec),
                     "architecture_sha256": identity(self.arch), "examples": []}

    def test_attaches_observed_output_and_escapes_html(self):
        self.data["examples"].append({"id": "normal", "interface": "show_items", "acceptance_ref": "fixture/brief/1",
                                      "command": "python3 -m sample", "observed_output": "<items> dua",
                                      "receipt": {"status": "passed", "path": "receipts/test.json", "sha256": "0" * 64}})
        guide, report = docs_writer.build(self.spec, self.arch, self.data, identity(self.data))
        self.assertIn("JSON &lt;items&gt;", guide)
        self.assertIn("&lt;items&gt; dua", guide)
        self.assertIn("receipts/test.json", guide)
        self.assertIn("fixture/brief/1", guide)
        self.assertEqual(report["status"], "documented")

    def test_uncovered_surface_is_explicit(self):
        guide, report = docs_writer.build(self.spec, self.arch, self.data, identity(self.data))
        self.assertEqual(report["missing_examples"], ["show_items"])
        self.assertIn("menunggu receipt", guide)

    def test_does_not_render_examples_with_wrong_acceptance(self):
        self.data["examples"].append({"id": "normal", "interface": "show_items", "acceptance_ref": "fixture/unknown",
                                      "command": "sample", "observed_output": "dua",
                                      "receipt": {"status": "passed", "path": "receipt.json", "sha256": "0" * 64}})
        with self.assertRaisesRegex(ContractError, "berbeda"):
            docs_writer.build(self.spec, self.arch, self.data, identity(self.data))
