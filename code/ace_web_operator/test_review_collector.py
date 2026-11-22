"""Verifier rating lintas skala, dedup, dan konflik yang tak dirata-rata."""
import unittest

from ace_web_operator import review_collector
from ace_web_operator._contracts import ContractError,identity


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.source={"schema":"ace.web.review-snapshot.v1","source_ref":"fixture/reviews","rows":[
            {"id":"entry","site":site,"product":"x","rating":rating,"observed_at":"2026-01-01T00:00:00Z",
             "review":body,"source_ref":"fixture/"+site,"snapshot_sha256":stamp*64}
            for site,rating,body,stamp in (("two","9","Dasar  tahan.", "a"),("one","4.5","Dasar tahan.","b"))]}
        self.plan={"schema":"ace.web.review-plan.v1","source_ref":"fixture/ratings","products":["x","y"],
                   "sites":[{"id":"one","scale":5,"source_ref":"fixture/five"},
                            {"id":"two","scale":10,"source_ref":"fixture/ten"}]}

    def collect(self):
        self.plan["data_sha256"]=identity(self.source)
        return review_collector.collect(self.plan,identity(self.plan),self.source)

    def test_same_text_and_equivalent_scale_get_one_review(self):
        report=self.collect()
        self.assertEqual((report["source_rows"],report["unique_reviews"]),(2,1))
        self.assertEqual(report["reviews"][0]["rating_bp"],9000)
        self.assertIsNone(report["by_product"]["y"]["mean_bp"])

    def test_conflicting_rating_remains_visible(self):
        self.source["rows"][0]["rating"]="8"
        result=self.collect()
        self.assertEqual(result["reviews"][0]["rating_status"],"conflicting")
        self.assertIsNone(result["by_product"]["x"]["mean_bp"])
        self.source["rows"][0]["rating"]="11"
        with self.assertRaisesRegex(ContractError,"skala"):
            self.collect()
