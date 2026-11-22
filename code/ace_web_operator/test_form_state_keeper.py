"""Verifier checkpoint, versi form, dan larangan field sensitif."""
import unittest

from ace_web_operator import form_state_keeper
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator import test_form_filler


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.form,self.values=test_form_filler.FormTests().form(9010)
        self.policy={"schema":"ace.web.form-checkpoint-policy.v1","source_ref":"fixture/snapshot","form_sha256":identity(self.form),
                     "fields":["full_name"],"expires_at":"2026-01-02T00:00:00Z"}

    def save(self):
        return form_state_keeper.save(self.policy,identity(self.policy),self.form,self.values,"2026-01-01T00:00:00Z")

    def test_restores_selected_control_with_rehashed_receipt(self):
        snapshot=self.save()
        def controlled(plan,anchor):
            self.assertEqual([item["op"] for item in plan["steps"]],["navigate","fill"])
            return {"plan_sha256":anchor,"status":"completed","reason":None,
                    "steps":[{"id":item["id"],"status":"ok"} for item in plan["steps"]]}
        result=form_state_keeper.restore(self.policy,identity(self.policy),self.form,snapshot,identity(snapshot),
                                        "2026-01-01T01:00:00Z",browser=controlled)
        self.assertEqual(result["status"],"restored_locally")
        self.assertFalse(result["submitted"])

    def test_expired_snapshot_and_sensitive_field_are_held(self):
        snapshot=self.save()
        with self.assertRaisesRegex(ContractError,"tidak berlaku"):
            form_state_keeper.restore(self.policy,identity(self.policy),self.form,snapshot,identity(snapshot),
                                      self.policy["expires_at"],browser=lambda *args:self.fail("unexpected"))
        self.policy["fields"].append("password")
        with self.assertRaisesRegex(ContractError,"sensitif"):
            self.save()
