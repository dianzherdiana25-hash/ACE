"""Verifier prioritas rules robots dan kuota melarang jaringan."""
from hashlib import sha256
import unittest

from ace_web_operator import politeness_guard
from ace_web_operator._contracts import identity


ROBOTS=b"""User-agent: *
Disallow: /
User-agent: AceFixture
Disallow: /data
Allow: /data/public$
Crawl-delay: 2
"""


class PoliteTests(unittest.TestCase):
    def setUp(self):
        self.history={"schema":"ace.web.politeness-history.v1","requests":[]}
        self.plan={"schema":"ace.web.politeness-plan.v1","source_ref":"fixture/robots","origin":"http://127.0.0.1:9010",
                   "path":"/data/public","agent":"AceFixture/1","now":"2026-01-01T00:00:30Z",
                   "robots_sha256":sha256(ROBOTS).hexdigest(),"history_sha256":identity(self.history),
                   "interval_seconds":1,"hourly_cap":1}

    def run_guard(self,**options):
        self.plan["history_sha256"]=identity(self.history)
        return politeness_guard.fetch_if_allowed(self.plan,identity(self.plan),ROBOTS,self.history,**options)

    def test_longest_agent_and_exact_allow_vs_disallow(self):
        item,report=self.run_guard(transport=lambda base,path:"observed")
        self.assertEqual((item,report["robots"]["rule_line"]),("observed",5))
        self.plan["path"]="/data/private"
        item,report=self.run_guard(transport=lambda *args:self.fail("request terlarang"))
        self.assertIsNone(item)
        self.assertEqual(report["reason"],"robots_denied")

    def test_backoff_and_hourly_window_cannot_be_bypassed(self):
        self.history["requests"]=[{"origin":self.plan["origin"],"at":"2026-01-01T00:00:01Z","status":429,
                                   "retry_after_seconds":9000,"source_ref":"fixture/429"}]
        item,report=self.run_guard(transport=lambda *args:self.fail("request quota"))
        self.assertIsNone(item)
        self.assertEqual(report["reason"],"retry_after")
        self.assertEqual(report["next_allowed_at"],"2026-01-01T02:30:01Z")
        self.history["requests"][0].update(status=200,retry_after_seconds=None)
        self.assertEqual(self.run_guard()[1]["reason"],"hourly_cap")
