"""Verifier challenge HTML dengan handoff tanpa sitekey."""
from hashlib import sha256
import unittest

from ace_web_operator import captcha_escalator
from ace_web_operator._contracts import identity


def config(page):
    return {"schema":"ace.web.challenge-assessment-plan.v1","task":"local_checkout","source_ref":"fixture/policy",
            "html_ref":"fixture/page","html_sha256":sha256(page).hexdigest()}


class ChallengeTests(unittest.TestCase):
    def test_handoff_uses_locations_and_families_without_values(self):
        html=(b'<div class="h-captcha" data-sitekey="fixture-key-body"></div>\n'
              b'<div data-challenge="human_check"></div>')
        plan=config(html)
        result=captcha_escalator.observe(html,plan,identity(plan))
        self.assertEqual(result["handoff"]["families"],["declared_challenge","hcaptcha"])
        self.assertEqual([row["line"] for row in result["markers"]],[1,2])
        self.assertNotIn("fixture-key-body",str(result))

    def test_website_text_about_captcha_does_not_count_as_challenge(self):
        html=b"<p>This FAQ discusses captcha.</p>"
        plan=config(html)
        result=captcha_escalator.observe(html,plan,identity(plan))
        self.assertEqual(result["status"],"not_detected")
        self.assertIsNone(result["handoff"])
