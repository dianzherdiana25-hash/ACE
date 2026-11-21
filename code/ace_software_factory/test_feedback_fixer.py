"""Verifier feedback preimage dan perilaku produk hasil rebuild."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import feedback_fixer
from ace_software_factory._contracts import ContractError, decode, identity
from ace_software_factory.repo_scaffolder import materialize
from ace_software_factory.test_cli_builder import config


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.current=config()
        self.report={"schema":"ace.factory-feedback-campaign.v1","product_sha256":identity(self.current),
                     "source_ref":"fixture/triage","issues":[{"id":"more_bytes","source_ref":"fixture/customer",
                     "evidence_sha256":"d"*64,"change":{"item":None,"field":"max_input_bytes","before":128,"after":256}}]}

    def fix(self):
        return feedback_fixer.fix(self.current,self.report,identity(self.report))

    def test_rebuilt_cli_accepts_larger_input_and_preserves_rollback_artifact(self):
        files,result=self.fix()
        root=Path(self.enterContext(TemporaryDirectory()))/"fixture"
        materialize(root,files)
        payload=b'[{"name":"'+b"x"*120+b'","units":4}]'
        self.assertGreater(len(payload),128)
        invocation=subprocess.run([sys.executable,"-B","-m",self.current["id"],"total"],cwd=root/"product",
                                  input=payload,capture_output=True,timeout=5)
        self.assertEqual(invocation.returncode,0,invocation.stderr)
        self.assertEqual(decode(invocation.stdout),{"records":1,"total":4})
        self.assertEqual(decode(files["prior_product.json"]),self.current)
        self.assertEqual(result["after_sha256"],identity(decode(files["updated_product.json"])))

    def test_wrong_preimage_forbids_edit_and_policy_invalidates_out_of_range_rebuild(self):
        row=self.report["issues"][0]["change"]
        row["before"]=100
        with self.assertRaisesRegex(ContractError,"Preimage"):
            self.fix()
        row["before"]=128
        row["after"]=10
        with self.assertRaises(ContractError):
            self.fix()
