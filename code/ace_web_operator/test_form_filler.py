"""Verifier validasi field dan receipt tanpa isi form."""
import unittest

from ace_web_operator import form_filler
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available,fixture,plan


class FormTests(unittest.TestCase):
    def form(self,port):
        base=plan(port)
        data={"schema":"ace.web.form-plan.v1","source_ref":"fixture/form","path":"/",
              "browser":{key:base[key] for key in ("origin","allow_paths","timeout_ms","request_limit")},
              "fields":[{"id":"full_name","test_id":"name","kind":"text","required":True,"max_chars":50,
                         "choices":[],"source_ref":"fixture/label"}]}
        assignment={"schema":"ace.web.form-assignment.v1","form_sha256":identity(data),
                    "source_ref":"fixture/record","values":{"full_name":"Nama sintetis"}}
        return data,assignment

    def test_invalid_values_forbid_browser_start(self):
        raw,values=self.form(9010)
        values["values"]["full_name"]=""
        with self.assertRaisesRegex(ContractError,"teks"):
            form_filler.fill(raw,values,identity(raw),browser=lambda *args:self.fail("browser tidak boleh dipanggil"))
        values["values"]["full_name"]="Test"
        values["values"]["unapproved"]="Test"
        with self.assertRaisesRegex(ContractError,"terdaftar"):
            form_filler.compile_form(raw,values,identity(raw))

    def test_real_form_receipt_leaves_submission_untriggered(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        http=fixture(self)
        raw,values=self.form(http.server_port)
        report=form_filler.fill(raw,values,identity(raw))
        self.assertEqual(report["status"],"filled_locally",report)
        self.assertEqual(report["fields"],[{"id":"full_name","source_ref":"fixture/label","status":"filled"}])
        self.assertFalse(report["submitted"])
        self.assertNotIn("Nama sintetis",str(report))
        self.assertTrue(set(http.visited)<={"/","/favicon.ico"})
