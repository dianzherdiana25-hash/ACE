"""Verifier HTML semantik, quoting, navigasi dan aksi form lokal."""
from hashlib import sha256
from html.parser import HTMLParser
import unittest

from ace_software_factory import ui_builder as model
from ace_software_factory._contracts import identity


def fixture():
    return {"schema":"ace.factory-ui-plan.v1","screen_ref":"fixture/screen","locale":"id",
            "title":"Katalog <fixture>","api_endpoints":["/items"],"navigation":[{"target":"details","label":"Rincian"}],
            "sections":[{"id":"details","heading":"Rincian item","source_ref":"fixture/rincian","blocks":[
                {"type":"table","data":{"columns":[{"id":"code","label":"Kode"}],"rows":[{"code":"<item>"}],"caption":"Daftar item"}},
                {"type":"form","data":{"id":"add","endpoint":"/items",
                   "fields":[{"name":"label","label":"Nama item","input_type":"text","required":True,"max_length":50}],
                   "submit":"Tambah","wait":"Menyimpan","success":"Tersimpan","error":"Gagal menyimpan"}},
            ]}]}


class Tags(HTMLParser):
    def __init__(self,data):
        super().__init__()
        self.rows=[]
        self.feed(data.decode())

    def handle_starttag(self,tag,attrs):
        self.rows.append((tag,dict(attrs)))


class UITests(unittest.TestCase):
    def test_structure_and_contract_host_path_have_no_dynamic_html_insertion(self):
        plan=fixture()
        files,report=model.build(plan,identity(plan))
        output=files["index.html"]
        self.assertEqual(report["html_sha256"],sha256(output).hexdigest())
        self.assertIn(b"Katalog &lt;fixture&gt;",output)
        self.assertIn(b"&lt;item&gt;",output)
        rows=Tags(output).rows
        self.assertIn(("th",{"scope":"col"}),rows)
        self.assertIn(("label",{"for":"add-label"}),rows)
        self.assertIn(("a",{"href":"#details"}),rows)
        self.assertIn(("form",{"data-endpoint":"/items","data-wait":"Menyimpan","data-success":"Tersimpan","data-error":"Gagal menyimpan"}),rows)
        self.assertIn(b"status.textContent",output)

    def test_unregistered_or_schema_skewed_inputs_refused(self):
        plan=fixture()
        plan["sections"][0]["blocks"][1]["data"]["endpoint"]="https://fixture.invalid/items"
        with self.assertRaisesRegex(model.ContractError,"belum terdaftar"):
            model.build(plan,identity(plan))
        plan=fixture()
        plan["navigation"][0]["target"]="missing"
        with self.assertRaisesRegex(model.ContractError,"tidak dikenal"):
            model.build(plan,identity(plan))
