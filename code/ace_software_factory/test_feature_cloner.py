"""Verifier replika perilaku eksplisit, input ambigu dan state tak terlihat."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import feature_cloner
from ace_software_factory._contracts import ContractError,canonical,decode,identity
from ace_software_factory.repo_scaffolder import materialize


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-behavior-plan.v1","id":"switch_fixture","source_ref":"fixture/description",
                   "initial":"idle","states":["idle","occupied"],
                   "transitions":[{"from":"idle","event":"open","input":{"key":"a"},"to":"occupied","response":{"open":True},
                                   "source_ref":"fixture/open"},
                                  {"from":"occupied","event":"reset","input":None,"to":"idle","response":{"open":False},
                                   "source_ref":"fixture/close"}]}

    def build(self):
        return feature_cloner.build(self.plan,identity(self.plan))

    def test_generated_cli_matches_described_transitions_only(self):
        files,report=self.build()
        root=Path(self.enterContext(TemporaryDirectory()))/"product"
        materialize(root,files)
        probe=[{"event":"open","input":{"key":"different"}},{"event":"open","input":{"key":"a"}},
               {"event":"reset","input":None}]
        result=subprocess.run([sys.executable,"-B",report["runtime"]["path"]],cwd=root,input=canonical(probe),
                              capture_output=True,timeout=5)
        self.assertEqual(result.returncode,1,result.stderr)
        seen=decode(result.stdout)
        self.assertEqual([row["state"] for row in seen["steps"]],["idle","occupied","idle"])
        self.assertEqual(seen["steps"][1]["source_ref"],"fixture/open")
        self.assertEqual(seen["steps"][2]["response"],{"open":False})

    def test_conflicting_transition_and_unreachable_state_do_not_generate(self):
        self.plan["transitions"].append({**self.plan["transitions"][0],"response":[]})
        with self.assertRaisesRegex(ContractError,"Dua transisi"):
            self.build()
        self.plan["transitions"].pop()
        self.plan["states"].append("orphan")
        with self.assertRaisesRegex(ContractError,"dicapai"):
            self.build()
