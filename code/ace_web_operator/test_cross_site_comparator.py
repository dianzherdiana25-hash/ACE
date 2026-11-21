"""Verifier total per situs, seri, mata uang salah dan data absen."""
import unittest

from ace_web_operator import cross_site_comparator
from ace_web_operator._contracts import identity


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.feed={"schema":"ace.web.comparison-feed.v1","source_ref":"fixture/offers","observations":[
            {"site":site,"sku":site+"1","source_ref":"fixture/"+site,"currency":currency,"at":when,
             "price":price,"shipping":fee,"in_stock":True}
            for site,currency,when,price,fee in (
                ("one","IDR","2026-01-02T00:00:00Z",15,10),("two","IDR","2026-01-02T00:00:00Z",20,5),
                ("four","USD","2026-01-02T00:00:00Z",2,0),("five","IDR","2026-01-01T00:00:00Z",1,0))]}
        sites=["one","two","three","four","five"]
        self.raw={"schema":"ace.web.compare-plan.v1","source_ref":"fixture/sku-map","feed_sha256":identity(self.feed),
                  "currency":"IDR","as_of":"2026-01-02T02:00:00Z","max_age_seconds":9000,"sites":sites,
                  "products":[{"id":"box","skus":{site:site+"1" for site in sites},"source_ref":"fixture/box"}]}

    def compare(self):
        self.raw["feed_sha256"]=identity(self.feed)
        return cross_site_comparator.compare(self.raw,identity(self.raw),self.feed)["products"][0]

    def test_only_comparable_prices_tie_and_unavailable_have_reasons(self):
        result=self.compare()
        self.assertEqual(result["lowest_sites"],["one","two"])
        self.assertEqual(result["spread_minor_units"],0)
        self.assertEqual({row["site"]:row["reason"] for row in result["offers"]},{
            "one":None,"two":None,"three":"missing","four":"currency_mismatch","five":"stale"})

    def test_single_known_site_does_not_support_comparison(self):
        self.feed["observations"][1]["shipping"]=None
        result=self.compare()
        self.assertEqual(result["comparable_count"],1)
        self.assertIsNone(result["spread_minor_units"])
        self.assertEqual(result["lowest_sites"],[])
