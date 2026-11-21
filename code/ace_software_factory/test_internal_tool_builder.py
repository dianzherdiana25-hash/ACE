"""Verifier state triase, alur yang dibatasi dan ekspor rencana lokal."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import internal_tool_builder
from ace_software_factory._contracts import ContractError,identity
from ace_software_factory.repo_scaffolder import materialize


class InternalTests(unittest.TestCase):
    def setUp(self):
        self.source={"schema":"ace.factory-internal-snapshot.v1","source_ref":"fixture/records","records":[
            {"id":"first","title":"Periksa unit","state":"open","source_ref":"fixture/id1"}]}
        self.plan={"schema":"ace.factory-internal-plan.v1","id":"fixture_tool","title":"Triase <lokal>",
                   "source_ref":"fixture/tool","snapshot_sha256":identity(self.source),"states":["open","done"],
                   "transitions":[{"from":"open","to":"done","source_ref":"fixture/edge"}]}

    def build(self):
        return internal_tool_builder.build(self.plan,self.source,identity(self.plan))

    def test_generated_runtime_plans_without_mutating_snapshot(self):
        node=shutil.which("node")
        if node is None:
            self.skipTest("Node lokal tidak tersedia")
        files,report=self.build()
        code=b'''
const assert=require("node:assert/strict");
const {make,prepare,propose}=require("./triage.js");
const initial=make(), next=propose(initial,"first","done");
assert.deepEqual(initial.changes,[]);
assert.deepEqual(next.changes,[{id:"first",from:"open",to:"done"}]);
assert.equal(prepare(next).first,"done");
assert.throws(()=>propose(next,"first","open"));
assert.throws(()=>prepare({...next,snapshot_sha256:"invalid"}));
'''
        root=Path(self.enterContext(TemporaryDirectory()))/"out"
        materialize(root,{**files,"fixture.cjs":code})
        result=subprocess.run([node,"fixture.cjs"],cwd=root,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b"Triase &lt;lokal&gt;",files["index.html"])
        self.assertEqual(report["records"],1)

    def test_unregistered_state_rule_is_refused(self):
        self.plan["transitions"][0]["to"]="never"
        with self.assertRaisesRegex(ContractError,"tak dikenal"):
            self.build()
