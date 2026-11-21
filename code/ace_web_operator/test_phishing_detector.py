"""Verifier indikator defensif dan redaksi dari HTML fixture."""
from hashlib import sha256
import unittest

from ace_web_operator import phishing_detector
from ace_web_operator._contracts import identity


class Signals(unittest.TestCase):
    def scan(self,data):
        plan={"schema":"ace.web.phishing-plan.v1","source_ref":"fixture/registry","html_ref":"fixture/phish.html",
              "page_url":"https://local.invalid/inbox","html_sha256":sha256(data).hexdigest(),"trusted_hosts":[]}
        return phishing_detector.inspect(data,plan,identity(plan))

    def test_flags_external_password_target_and_spoofed_visible_host_without_echo(self):
        html=b'''<a href="https://elsewhere.invalid/help">https://local.invalid/help</a>
<form action="http://elsewhere.invalid/login"><input type="password"></form>
<a href="https://canary:user_value@elsewhere.invalid/page?fixture=hidden">Open</a>'''
        result=self.scan(html)
        self.assertEqual({row["rule"] for row in result["findings"]},{
            "label_host_mismatch","password_form_untrusted_target","password_form_cleartext",
            "password_form_query_submission","userinfo_in_link"})
        self.assertNotIn("user_value",str(result))
        self.assertNotIn("fixture=hidden",str(result))

    def test_same_site_https_post_has_no_static_indicator(self):
        result=self.scan(b'<form method="post" action="/login"><input type="password"></form>')
        self.assertEqual(result["status"],"no_indicator_detected")
