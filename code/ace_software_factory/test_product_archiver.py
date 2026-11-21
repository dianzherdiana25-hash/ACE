"""Verifier arsip deterministic, replay sandbox, dan bukti yang berubah."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import product_archiver
from ace_software_factory._contracts import ContractError,identity
from ace_software_factory.build_loop import _description
from ace_software_factory.repo_scaffolder import materialize


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))/"source"
        self.files={"tool.py":b"def total(x):\n    return 1+x\n",
                    "tests/test_tool.py":b"import unittest\nfrom tool import total\n"
                                         b"class Cases(unittest.TestCase):\n    def test_a(self):\n"
                                         b"        self.assertEqual(total(4),5)\n"}
        materialize(self.root,self.files)
        self.plan={"schema":"ace.factory-archive-plan.v1","source_ref":"fixture/archive","product_id":"catalog",
                   "version":"1.2.0","test_count":1,"timeout_seconds":5,"files":_description(self.files)}

    def pack(self):
        return product_archiver.archive(self.root,self.plan,identity(self.plan))

    def test_replay_verifies_suite_in_isolation_and_keeps_original_source(self):
        data,report=self.pack()
        self.assertEqual(data,self.pack()[0])
        proof=product_archiver.replay(data,report["archive_sha256"],report["manifest_sha256"],report["recipe_sha256"])
        if proof["verification"]["status"]=="sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(proof["status"],"verified_replay")
        self.assertEqual(proof["verification"]["tests"],1)
        self.assertEqual((self.root/"tool.py").read_bytes(),self.files["tool.py"])

    def test_refuses_different_archive_or_recipe_before_runner(self):
        data,report=self.pack()
        with self.assertRaisesRegex(ContractError,"archive berbeda"):
            product_archiver.replay(data+b"x",report["archive_sha256"],report["manifest_sha256"],report["recipe_sha256"])
        with self.assertRaisesRegex(ContractError,"Resep archive"):
            product_archiver.replay(data,report["archive_sha256"],report["manifest_sha256"],"f"*64,
                                    runner=lambda *args:self.fail("runner harus ditahan"))
