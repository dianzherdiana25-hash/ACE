"""Verifier dialog lokal, persetujuan eksplisit dan kontrol yang tersedia."""
from hashlib import sha256
import unittest

from ace_web_operator import consent_handler
from ace_web_operator._contracts import identity


BASE=b'''<dialog data-consent="preferences" data-kind="cookie_preferences" open>
<button type="button" data-consent-choice="deny_optional" data-testid="deny">Tolak opsional</button>
</dialog>'''


class ConsentTests(unittest.TestCase):
    def run_fixture(self,html,decision="deny_optional",approval="fixture/operator-choice"):
        raw={"schema":"ace.web.consent-plan.v1","source_ref":"fixture/settings","snapshot_ref":"fixture/page.html",
             "snapshot_sha256":sha256(html).hexdigest(),"origin":"http://127.0.0.1:9010","path":"/",
             "dialog_id":"preferences","decision":decision,"approval_ref":approval}
        return consent_handler.plan_action(html,raw,identity(raw))

    def test_approved_rejection_uses_button_in_existing_dialog(self):
        result=self.run_fixture(BASE)
        self.assertEqual(result["status"],"action_planned")
        self.assertEqual(result["steps"][1],{"id":"approved_consent","op":"click","test_id":"deny"})

    def test_without_approval_or_control_it_holds_no_click(self):
        absent=self.run_fixture(BASE,approval=None)
        self.assertEqual(absent["reason"],"decision_without_approval")
        self.assertEqual(absent["steps"],[])
        unavailable=self.run_fixture(BASE,decision="allow_declared")
        self.assertEqual(unavailable["reason"],"approved_control_unavailable")
        self.assertEqual(unavailable["steps"],[])
        nonsupported=self.run_fixture(BASE.replace(b"cookie_preferences",b"login"))
        self.assertEqual(nonsupported["reason"],"not_optional_cookie_banner")
