"""Verifier resume baca, idempotensi dan kegagalan assertion checkpoint."""
import unittest

from ace_web_operator import session_recoverer
from ace_web_operator._contracts import identity
from ace_web_operator.test_browser_engine import browser_available,fixture,plan


class RecoveryTests(unittest.TestCase):
    def configure(self,port,maybe_effect=False):
        base=plan(port)
        checkpoint={"schema":"ace.web.session-checkpoint.v1","workflow_sha256":"a"*64,"source_ref":"fixture/last-good",
                    "current_path":"/","assertion":{"test_id":"out","expected":"Awal"},
                    "confirmed_steps":["already"],"unconfirmed_effect":maybe_effect}
        recipe={"schema":"ace.web.resume-plan.v1","source_ref":"fixture/follow-up","workflow_sha256":"a"*64,
                "checkpoint_sha256":identity(checkpoint),
                "browser":{key:base[key] for key in ("origin","allow_paths","timeout_ms","request_limit")},
                "steps":[{"id":"already","op":"click","test_id":"mark"},{"id":"continue","op":"read_text","test_id":"out"}]}
        return recipe,checkpoint

    def test_holds_pending_effect_and_new_write_steps_before_browser_start(self):
        recipe,snapshot=self.configure(9010,True)
        result=session_recoverer.recover(recipe,snapshot,identity(recipe),
                                         browser=lambda *args:self.fail("Browser called"))
        self.assertEqual(result["reason"],"effect_requires_operator")
        recipe,snapshot=self.configure(9010)
        recipe["steps"][1]["op"]="click"
        self.assertEqual(session_recoverer.recover(recipe,snapshot,identity(recipe))["status"],"held")

    def test_actual_resume_rechecks_state_and_never_repeats_confirmed_click(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        host=fixture(self)
        recipe,snapshot=self.configure(host.server_port)
        result=session_recoverer.recover(recipe,snapshot,identity(recipe))
        self.assertEqual(result["status"],"resumed",result)
        self.assertEqual([row["id"] for row in result["resumed_steps"]],["continue"])
        self.assertTrue(result["checkpoint_reverified"])
        snapshot["assertion"]["expected"]="Selesai"
        recipe["checkpoint_sha256"]=identity(snapshot)
        withheld=session_recoverer.recover(recipe,snapshot,identity(recipe))
        self.assertEqual(withheld["reason"],"assertion_failed")
        self.assertEqual(withheld["resumed_steps"],[])
