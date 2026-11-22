"""Verifier filter, provenance dan nilai yang absen pada tabel DOM."""
from base64 import b64encode
from hashlib import sha256
import unittest

from ace_web_operator import analytics_operator
from ace_web_operator._contracts import identity


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.web.analytics-plan.v1","source_ref":"fixture/query","permission_ref":"fixture/read","path":"/chart",
                   "browser":{"origin":"http://127.0.0.1:9010","allow_paths":["/chart"],"timeout_ms":500,"request_limit":4},
                   "filter":{"target":"period","value":"week","ready_target":"ready","ready_text":"Siap"},
                   "date_from":"2026-01-01","date_until":"2026-01-08","metric":"count","groups":["new","old"],
                   "container":"chart","row_class":"event"}

    def run_fixture(self,when="2026-01-03"):
        body=(f'<tr class="event"><td data-field="id">one</td><td data-field="date">{when}</td>'
              '<td data-field="group">old</td><td data-field="value">3</td></tr>').encode()
        def browser(job,anchor):
            self.assertEqual([step["op"] for step in job["steps"]][:3],["navigate","select","expect_value"])
            return {"plan_sha256":anchor,"status":"completed","reason":None,"steps":[{"evidence":{
                "html_base64":b64encode(body).decode(),"bytes":len(body),"sha256":sha256(body).hexdigest()}}]}
        return analytics_operator.run(self.plan,identity(self.plan),browser=browser)

    def test_counts_only_observed_groups_with_capture_locator(self):
        files,proof=self.run_fixture()
        self.assertEqual(proof["status"],"measured_fixture")
        self.assertIsNone(proof["groups"][0]["total"])
        self.assertEqual(proof["groups"][1]["total"],3)
        self.assertIn(proof["extraction"]["html_ref"],files)

    def test_rejects_outside_filter_even_with_verified_picture(self):
        _,proof=self.run_fixture("2026-01-08")
        self.assertEqual(proof["reason"],"row_outside_filter")
        self.assertEqual(proof["groups"],[])
