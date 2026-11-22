"""Verifier slot hilang dan perbedaan harga yang berdasar dua snapshot."""
import unittest

from ace_web_operator import price_research_runner
from ace_web_operator._contracts import identity


STAMP="2026-01-01T00:0"


class PriceTests(unittest.TestCase):
    def setUp(self):
        self.schedule={"schema":"ace.web.scheduler-plan.v1","source_ref":"fixture/clock","window_start":STAMP+"0:00Z",
                       "window_end":STAMP+"3:00Z","as_of":STAMP+"2:30Z","tasks":[
                           {"id":"price","first_at":STAMP+"0:00Z","every_seconds":60,"until":STAMP+"3:00Z",
                            "missed_slots":"queue_all","workflow_sha256":"a"*64,"source_ref":"fixture/task"}]}
        self.history={"schema":"ace.web.scheduler-history.v1","receipts":[]}
        self.feeds={"schema":"ace.web.price-feeds.v1","source_ref":"fixture/data","snapshots":[]}
        for stamp,amount in ((STAMP+"0:00Z",10),(STAMP+"2:00Z",12)):
            feed={"schema":"ace.web.comparison-feed.v1","source_ref":"fixture/feed","observations":[
                {"site":name,"sku":name+"1","at":stamp,"currency":"IDR","price":price,"shipping":0,"in_stock":True,
                 "source_ref":"fixture/"+name} for name,price in (("one",amount),("two",20))]}
            self.feeds["snapshots"].append({"scheduled_at":stamp,"feed_sha256":identity(feed),"feed":feed,
                                            "source_ref":"fixture/at/"+stamp})
        self.plan={"schema":"ace.web.price-research-plan.v1","source_ref":"fixture/plan","schedule_sha256":identity(self.schedule),
                   "history_sha256":identity(self.history),"feeds_sha256":identity(self.feeds),"task":"price",
                   "workflow_sha256":"a"*64,"comparison":{"source_ref":"fixture/comparator","currency":"IDR",
                   "max_age_seconds":300,"sites":["one","two"],"products":[{"id":"box","skus":{"one":"one1","two":"two1"},
                                                                        "source_ref":"fixture/map"}]}}

    def test_records_missing_feed_and_uses_two_observed_periods_for_delta(self):
        result=price_research_runner.run(self.plan,identity(self.plan),self.schedule,self.history,self.feeds)
        self.assertEqual((result["status"],result["due"],result["missing_feeds"]),("partial",3,1))
        rows=result["slots"]
        self.assertIsNone(rows[1]["comparison"])
        self.assertEqual(rows[2]["changes"][0]["delta_minor_units"],2)
        self.assertEqual(rows[2]["changes"][0]["from"],STAMP+"0:00Z")
