"""Uji struktur mobile, mutasi storage dan sekat antar-tab."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import mobile_builder
from ace_software_factory._contracts import ContractError, decode, identity
from ace_software_factory.repo_scaffolder import materialize


NODE_FIXTURE = """
const assert = require("node:assert/strict");
const { mutate, load } = require("./mobile.js");
const data = new Map();
const store = { getItem: key => data.get(key) ?? null, setItem: (key, val) => data.set(key,val) };
assert.deepEqual(mutate(store,"today","add","  Meter  "), [{key:1,title:"Meter"}]);
assert.deepEqual(load(store,"archive"), []);
assert.deepEqual(mutate(store,"archive","add","Tali"), [{key:1,title:"Tali"}]);
assert.throws(() => mutate(store,"today","add","extra"), /storage_limit/);
assert.deepEqual(mutate(store,"today","remove",1), []);
assert.deepEqual(load(store,"archive"), [{key:1,title:"Tali"}]);
assert.throws(() => mutate(store,"unknown","add","Never"), /unknown_view/);
"""


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"schema": "ace.factory-mobile-plan.v1", "id": "gear_log", "name": "Catatan alat",
                     "summary": "Daftar perlengkapan.", "theme": "#15334c", "source_ref": "fixture/mobile",
                     "max_records": 1, "tabs": [{"id": key, "title": title, "input": "Nama alat",
                                                 "source_ref": "fixture/" + key}
                                                for key, title in [("today", "Hari ini"), ("archive", "Arsip")]]}

    def build(self):
        return mobile_builder.build(self.plan, identity(self.plan))

    def test_outputs_mobile_manifest_and_escaped_controls(self):
        self.plan["tabs"][0]["title"] = "<Hari ini>"
        files, report = self.build()
        self.assertIn(b"&lt;Hari ini&gt;", files["index.html"])
        self.assertIn(b"width=device-width", files["index.html"])
        self.assertEqual(decode(files["manifest.webmanifest"])["display"], "standalone")
        self.assertEqual(report["runtime"], "mobile_web")

    def test_runs_generated_storage_policy_with_real_javascript(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node lokal tidak tersedia")
        root = Path(self.enterContext(TemporaryDirectory())) / "mobile"
        files, _ = self.build()
        materialize(root, {**files, "fixture.cjs": NODE_FIXTURE.encode()})
        result = subprocess.run([node, "fixture.cjs"], cwd=root, capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_two_tabs_with_same_state_key(self):
        self.plan["tabs"][1]["id"] = "today"
        with self.assertRaisesRegex(ContractError, "ganda"):
            self.build()
