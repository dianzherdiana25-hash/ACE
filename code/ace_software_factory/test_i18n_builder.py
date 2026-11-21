"""Verifier runtime dwibahasa dan validasi katalog sebelum emisi."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import i18n_builder
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


JS='''
const assert=require("node:assert/strict");
const {translate}=require("./product_locale.js");
assert.equal(translate("en","items",{count:1}),"1 item ready");
assert.equal(translate("en","items",{count:1200}),"1,200 items ready");
assert.equal(translate("id","items",{count:1200}),"1.200 barang siap");
assert.equal(translate("unknown","items",{count:1}),"1 barang siap");
assert.throws(()=>translate("id","items",{count:"1"}),/field_type_invalid/);
'''


class I18nTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-i18n-plan.v1","id":"fixture_ui","source_ref":"fixture/catalog",
                   "default_locale":"id","messages":[{"id":"items","fields":[{"id":"count","type":"integer"}],
                   "plural":"count","source_ref":"fixture/catalog/items","translations":{
                       "en":{"one":"{count} item ready","other":"{count} items ready"},
                       "id":{"other":"{count} barang siap"}}}]}

    def build(self):
        return i18n_builder.build(self.plan,identity(self.plan))

    def test_runtime_handles_locale_and_plural_rules(self):
        node=shutil.which("node")
        if node is None:
            self.skipTest("Node lokal tidak tersedia")
        files,report=self.build()
        root=Path(self.enterContext(TemporaryDirectory()))/"generated"
        materialize(root,{**files,"fixture.cjs":JS.encode()})
        result=subprocess.run([node,"fixture.cjs"],cwd=root,capture_output=True,timeout=6)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(report["available_locales"],["en","id"])

    def test_missing_plural_or_missing_placeholder_blocks_build(self):
        item=self.plan["messages"][0]["translations"]
        original=item["en"].pop("one")
        with self.assertRaises(ContractError):
            self.build()
        item["en"]["one"]=original
        item["id"]["other"]="Tidak mencantumkan nilai"
        with self.assertRaisesRegex(ContractError,"menghilangkan"):
            self.build()
