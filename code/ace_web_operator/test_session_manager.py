"""Verifier sesi opak, cap, TTL dan kegagalan credential adapter."""
import unittest

from ace_web_operator import session_manager
from ace_web_operator._contracts import identity


class Browser:
    def __init__(self,available=True):
        self.available=available
        self.closed=False

    def authenticated(self):
        return self.available and not self.closed

    def close(self):
        self.closed=True


class Vault:
    def __init__(self):
        self.sessions=[]
        self.calls=[]
        self.available=True

    def open_session(self,account,origin):
        self.calls.append((account,origin))
        item=Browser(self.available)
        self.sessions.append(item)
        return item


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.base="http://127.0.0.1:9100"
        config={"schema":"ace.web.session-policy.v1","source_ref":"fixture/session","ttl_seconds":20,"max_active":1,
                "accounts":[{"ref":name,"origin":self.base,"source_ref":"fixture/"+name} for name in ("first","second")]}
        self.now=10
        self.vault=Vault()
        self.driver=session_manager.SessionManager(config,identity(config),self.vault,lambda:self.now)

    def test_reuses_verified_handle_until_expiry_and_enforces_account_cap(self):
        start=self.driver.start("first",self.base)
        self.assertEqual(start["status"],"active_new")
        reentry=self.driver.start("first",self.base)
        self.assertEqual((reentry["status"],reentry["session_id"]),("active_reused",start["session_id"]))
        self.assertEqual(self.driver.start("second",self.base)["reason"],"session_capacity")
        self.now=30
        other=self.driver.start("second",self.base)
        self.assertEqual(other["status"],"active_new")
        self.assertTrue(self.vault.sessions[0].closed)
        self.assertEqual(self.driver.stop("second")["status"],"closed")

    def test_unregistered_origin_and_failed_verification_hold(self):
        self.assertEqual(self.driver.start("first","http://127.0.0.1:9101")["reason"],"account_or_origin_unregistered")
        self.assertFalse(self.vault.calls)
        self.vault.available=False
        result=self.driver.start("first",self.base)
        self.assertEqual(result["reason"],"vault_session_failed")
        self.assertIsNone(result["session_id"])
        self.assertTrue(self.vault.sessions[0].closed)
