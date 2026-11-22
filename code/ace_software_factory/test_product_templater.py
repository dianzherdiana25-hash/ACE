"""Verifier interpolasi aman, dua penggunaan template dan uji entrypoint."""
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import product_templater
from ace_software_factory._contracts import ContractError,identity
from ace_software_factory.repo_scaffolder import materialize


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.source=b"def announce():\n    print([[label:python]])\n\nannounce()\n"
        materialize(self.root/"source",{"script.template":self.source})
        self.plan={"schema":"ace.factory-product-template.v1","id":"sample","source_ref":"fixture/template",
                   "fields":[{"id":"slug","type":"identifier","encoding":["id"]},
                             {"id":"label","type":"text","encoding":["python"]}],
                   "files":[{"source":"script.template","sha256":sha256(self.source).hexdigest(),
                             "output":"[[slug:id]].py"}]}

    def build(self,slug,label):
        anchor=identity(self.plan)
        return product_templater.build(self.root/"source",self.plan,
            {"schema":"ace.factory-template-bindings.v1","template_sha256":anchor,
             "values":{"slug":slug,"label":label},"source_ref":"fixture/binding"},anchor)

    def test_same_template_creates_two_distinct_runnable_products(self):
        for slug,title in (("first","Say 'here'"),("second",'Teks "literal"')):
            files,report=self.build(slug,title)
            path=self.root/slug
            materialize(path,files)
            result=subprocess.run([sys.executable,"-B",f"{slug}.py"],cwd=path,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.decode().strip(),title)
            self.assertEqual(report["files"][0]["template"],"script.template")

    def test_path_outside_product_or_unknown_field_rejected(self):
        self.plan["files"][0]["output"]="../[[slug:id]].py"
        with self.assertRaises(ContractError):
            self.build("first","sample")
        self.plan["files"][0]["output"]="[[label:python]].py"
        with self.assertRaisesRegex(ContractError,"Encoding"):
            self.build("first","sample")
