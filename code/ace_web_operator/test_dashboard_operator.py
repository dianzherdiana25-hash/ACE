"""Verifier ACL tampilan dan perubahan tab lokal dengan bukti hash."""
import unittest

from ace_web_operator import dashboard_operator
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available,fixture,plan


class DashboardTests(unittest.TestCase):
    def inputs(self,port):
        base=plan(port)
        panel={"schema":"ace.web.dashboard-panel.v1","source_ref":"fixture/panel","origin":base["origin"],
               "views":[{"id":"main_view","path":"/","title":"Unit lokal","source_ref":"fixture/overview",
                         "controls":[{"id":"finished","kind":"tab","test_id":"mark"}],
                         "verify_test_id":"out","verify_text":"Selesai"}]}
        profile={"schema":"ace.web.dashboard-plan.v1","source_ref":"fixture/read","panel_sha256":identity(panel),
                 "permission_ref":"fixture/read-scope","view":"main_view","actions":["finished"],
                 "browser":{key:base[key] for key in ("origin","allow_paths","timeout_ms","request_limit")}}
        return profile,panel

    def test_unknown_or_mutation_control_does_not_start_browser(self):
        raw,panel=self.inputs(9010)
        panel["views"][0]["controls"][0]["test_id"]="save_now"
        raw["panel_sha256"]=identity(panel)
        with self.assertRaisesRegex(ContractError,"mutasi"):
            dashboard_operator.inspect(raw,identity(raw),panel,browser=lambda *args:self.fail("browser called"))

    def test_real_browser_follows_approved_tab_and_verifies_witness(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        server=fixture(self)
        raw,panel=self.inputs(server.server_port)
        report=dashboard_operator.inspect(raw,identity(raw),panel)
        self.assertEqual(report["status"],"verified_read",report)
        self.assertIsNotNone(report["proof"]["text_sha256"])
