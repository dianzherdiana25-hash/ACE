"""Verifier scaffold yang dijalankan dari direktori baru."""
import json
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import architecture_designer, repo_scaffolder as model, spec_writer
from ace_software_factory.test_architecture_designer import decisions
from ace_software_factory.test_spec_writer import brief


class ScaffoldTests(unittest.TestCase):
    def test_generated_product_entrypoint_and_generated_tests_run(self):
        spec=spec_writer.write(brief())
        architecture=architecture_designer.design(spec,decisions(spec))
        root=Path(self.enterContext(TemporaryDirectory()))/"product"
        products,receipt=model.build(spec,architecture,architecture_designer.identity(architecture))
        model.materialize(root,products)
        for row in receipt["files"]:
            self.assertEqual(sha256((root/row["path"]).read_bytes()).hexdigest(),row["sha256"])
        env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":"."}
        run=subprocess.run([sys.executable,"-m","fixture_catalog.app"],cwd=root,env=env,capture_output=True,check=True)
        self.assertEqual(json.loads(run.stdout)["interface_count"],1)
        verified=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests"],cwd=root,env=env,
                                check=True,capture_output=True)
        self.assertIn(b"Ran 1 test",verified.stderr)
        with self.assertRaises(FileExistsError):
            model.materialize(root,products)

    def test_path_escape_and_python_package_collision_rejected(self):
        root=Path(self.enterContext(TemporaryDirectory()))/"fixture"
        with self.assertRaisesRegex(model.ContractError,"di luar root"):
            model.materialize(root,{"../escape":b"no"})
        raw={**brief(),"id":"class"}
        spec=spec_writer.write(raw)
        architecture=architecture_designer.design(spec,decisions(spec))
        with self.assertRaisesRegex(model.ContractError,"Python"):
            model.build(spec,architecture,architecture_designer.identity(architecture))
