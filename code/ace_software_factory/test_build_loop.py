"""Verifier sandbox build, retry repair, dan bukti sumber tak berubah."""
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_software_factory import build_loop as model
from ace_software_factory._contracts import identity
from ace_software_factory.repo_scaffolder import materialize


TEST = b'''import os
from pathlib import Path
import unittest
from fixture_code import result

class Calibration(unittest.TestCase):
    def test_receipt(self):
        self.assertEqual(result(), 2)
        self.assertIsNone(os.getenv("ACE_FACTORY_TEST_CANARY"))
        self.assertFalse(Path("/workspace/ACE-evo0054").exists())
        with self.assertRaises(OSError):
            Path("/work/write-attempt").write_text("fixture")
'''


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))/"source"
        original=b"def result():\n    return 1\n"
        self.files={"fixture_code.py":original,"tests/test_fixture.py":TEST}
        materialize(self.root,self.files)
        base=model._description(self.files)
        self.raw={"schema":"ace.factory-build-loop.v1","source_ref":"fixture/build","maximum_attempts":2,"timeout_seconds":6,
                  "files":base,"editable":["fixture_code.py"],
                  "repairs":[{"based_on_tree":identity(base),"ref":"fixture/fix",
                              "patch":[{"path":"fixture_code.py","before_sha256":sha256(original).hexdigest(),
                                        "replacement":"def result():\n    return 2\n"}]}]}

    def test_real_bubblewrap_keeps_source_readonly_and_repair_matches_verifier(self):
        with patch.dict(os.environ,{"ACE_FACTORY_TEST_CANARY":"fixture-present"}):
            payload,report=model.run(self.root,self.raw,identity(self.raw))
        if report["reason"]=="sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(report["status"],"verified")
        one,two=report["attempts"]
        self.assertEqual([one["test"]["status"],two["test"]["status"]],["failed","passed"])
        self.assertEqual([one["test"]["tests"],two["test"]["tests"]],[1,1])
        self.assertEqual(one["repair"]["source_ref"],"fixture/fix")
        self.assertEqual(report["output_tree_sha256"],identity(model._description(payload)))
        self.assertEqual((self.root/"fixture_code.py").read_bytes(),self.files["fixture_code.py"])
        self.assertFalse((self.root/"write-attempt").exists())

    def test_disabled_dependency_is_held_and_cannot_apply_patch(self):
        with patch.object(model.shutil,"which",return_value=None):
            data,report=model.run(self.root,self.raw,identity(self.raw))
        self.assertIsNone(data)
        self.assertEqual(report["reason"],"sandbox_unavailable")
        self.assertIsNone(report["attempts"][0]["repair"])

    def test_verifier_cannot_be_patched_through_repair_manifest(self):
        self.raw["editable"].append("tests/test_fixture.py")
        with self.assertRaisesRegex(model.ContractError,"izin"):
            model.run(self.root,self.raw,identity(self.raw))
