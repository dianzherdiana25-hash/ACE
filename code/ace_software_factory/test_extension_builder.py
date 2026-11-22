"""Verifier izin manifest dan persistensi popup melalui storage fixture."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import extension_builder
from ace_software_factory._contracts import ContractError, decode, identity
from ace_software_factory.repo_scaffolder import materialize


SCRIPT = """
const assert = require("node:assert/strict");
const {openPreferences} = require("./popup.js");
let state = {};
let pending = Promise.resolve();
const lock = (id, operation) => {
    pending = pending.then(operation);
    return pending;
};
const local = {
    get: async id => state,
    set: async value => { state = value; }
};
(async () => {
    const popup = openPreferences(local);
    assert.deepEqual({...await popup.read()}, {edited:false, reviewed:true});
    await Promise.all([popup.update("edited", true, lock), popup.update("reviewed", false, lock)]);
    const reopened = openPreferences(local);
    assert.deepEqual({...await reopened.read()}, {edited:true, reviewed:false});
    await assert.rejects(() => popup.update("absent", true, lock), /change_invalid/);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"schema": "ace.factory-extension-plan.v1", "id": "review_local", "name": "Cek lokal",
                     "summary": "Checklist perangkat.", "version": "1.4", "source_ref": "fixture/popup",
                     "checklist": [{"id": "edited", "label": "<Disunting>", "default": False, "source_ref": "fixture/1"},
                                   {"id": "reviewed", "label": "Diperiksa", "default": True, "source_ref": "fixture/2"}]}

    def build(self):
        return extension_builder.build(self.plan, identity(self.plan))

    def test_manifest_requests_storage_only_and_popup_escapes_label(self):
        files, report = self.build()
        manifest = decode(files["manifest.json"])
        self.assertEqual(manifest["permissions"], ["storage"])
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("content_scripts", manifest)
        self.assertIn(b"&lt;Disunting&gt;", files["popup.html"])
        self.assertEqual(report["checklist"][0]["source_ref"], "fixture/1")

    def test_generated_popup_updates_storage_and_preserves_queued_updates(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node lokal tidak tersedia")
        target = Path(self.enterContext(TemporaryDirectory())) / "extension"
        files, _ = self.build()
        materialize(target, {**files, "fixture.cjs": SCRIPT.encode()})
        result = subprocess.run([node, "fixture.cjs"], cwd=target, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manifest_rejects_version_outside_chromium_range(self):
        self.plan["version"] = "65536.0"
        with self.assertRaisesRegex(ContractError, "Versi"):
            self.build()
