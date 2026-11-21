"""Verifier izin terikat isi dan proyeksi draf tanpa aksi send."""
import unittest

from ace_web_operator import web_messenger
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available,fixture,plan


class MessengerTests(unittest.TestCase):
    def build(self,port):
        base=plan(port)
        content="Sampel draf"
        approval={"schema":"ace.web.message-authorization.v1","task":"local_test","origin":base["origin"],"path":"/",
                  "thread_id":"example","message_sha256":identity(content),"scope":"draft_only","source_ref":"fixture/approval"}
        raw={"schema":"ace.web.message-draft-plan.v1","source_ref":"fixture/message","approval_sha256":identity(approval),
             "browser":{key:base[key] for key in ("origin","allow_paths","timeout_ms","request_limit")},
             "path":"/","thread_id":"example","thread_selector":"out","thread_label":"Awal","message_selector":"name",
             "message":content}
        return raw,approval

    def test_changed_message_or_send_control_never_enters_browser(self):
        plan,approval=self.build(9010)
        plan["message"]="Different"
        with self.assertRaisesRegex(ContractError,"Izin"):
            web_messenger.draft(plan,approval,identity(plan),browser=lambda *args:self.fail("browser called"))
        plan["message"]="Sampel draf"
        plan["message_selector"]="control_send"
        with self.assertRaisesRegex(ContractError,"Kontrol kirim"):
            web_messenger.compile_message(plan,approval,identity(plan))

    def test_real_browser_verifies_draft_without_releasing_message_text(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        server=fixture(self)
        plan,approval=self.build(server.server_port)
        result=web_messenger.draft(plan,approval,identity(plan))
        self.assertEqual(result["status"],"drafted_locally",result)
        self.assertFalse(result["sent"])
        self.assertNotIn(plan["message"],str(result))
