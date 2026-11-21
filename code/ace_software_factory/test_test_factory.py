"""Verifier tes acceptance yang menjalankan entry point fixture sungguhan."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import spec_writer, test_factory as model
from ace_software_factory._contracts import identity
from ace_software_factory.repo_scaffolder import materialize
from ace_software_factory.test_spec_writer import brief, utterance


def examples(spec,output):
    return {"schema":"ace.factory-acceptance-examples.v1","spec_sha256":identity(spec),"module":"sample",
            "timeout_seconds":5,"example_ref":"fixture/examples",
            "cases":[{"id":"round_trip","acceptance_ref":"fixture/brief/1","arguments":[],
                      "stdin":{"items":["a","b"]},"exit_code":0,"stdout":{"format":"json","value":output}}]}


class AcceptanceGeneratorTests(unittest.TestCase):
    def test_actual_generated_test_fails_with_wrong_expected_value(self):
        spec=spec_writer.write(brief())
        root=Path(self.enterContext(TemporaryDirectory()))
        for index, (expected, exit_code) in enumerate((({"items":["a","b"]},0),({"items":["missing"]},1))):
            config=examples(spec,expected)
            files,report=model.build(spec,config,identity(config))
            self.assertEqual(report["status"],"ready")
            self.assertEqual(report["trace"][0]["acceptance_ref"],"fixture/brief/1")
            directory=root/str(index)
            materialize(directory,{**files,"sample.py":b"import json,sys\nprint(json.dumps(json.load(sys.stdin)))\n"})
            env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":"."}
            result=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests"],
                                  cwd=directory,env=env,capture_output=True)
            self.assertEqual(result.returncode,exit_code,result.stderr)
            self.assertIn(b"Ran 1 test",result.stderr)

    def test_missing_criteria_held_and_wrong_links_rejected(self):
        raw=brief()
        raw["utterances"].append(utterance(5,"uji show: Sertakan total."))
        spec=spec_writer.write(raw)
        settings=examples(spec,0)
        _,report=model.build(spec,settings,identity(settings))
        self.assertEqual(report["status"],"partial")
        self.assertEqual(report["missing_acceptance"],["fixture/brief/5"])
        settings["cases"][0]["acceptance_ref"]="fixture/other"
        with self.assertRaisesRegex(model.ContractError,"di luar"):
            model.build(spec,settings,identity(settings))
