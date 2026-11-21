"""Verifier agregasi mikro, batas UTC, dan bulan tanpa bukti."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import perception_monthly as model
from ace_perception.test_perception_bench import bytes_observations, q, raw_plan


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.protocol=raw_plan()
        self.plan={"schema":"ace.perception-monthly-plan.v1","plan_ref":"fixture/monthly","protocol_sha256":model._sha(self.protocol),
                   "start_month":"2026-09","month_count":3,"minimum_sessions_per_month":1,
                   "as_of":"2026-11-21T00:00:00Z","sessions":[]}

    def put(self,name,when,content):
        (self.root/name).write_bytes(content)
        self.plan["sessions"].append({"id":name,"at":when,"ref":f"fixture/{name}","path":name,
                                      "bytes":len(content),"sha256":sha256(content).hexdigest()})

    def summarize(self):
        return model.summarize(self.root,model._canonical(self.protocol),model._canonical(self.plan),model._sha(self.plan))

    def test_complete_rates_use_denominators_and_missing_month_has_no_delta(self):
        self.put("first","2026-10-01T00:00:00+07:00",bytes_observations(audio="hello the white cat"))
        self.put("second","2026-11-08T00:00:00Z",bytes_observations(doc={"first":"Alpha"},audio="hello cat"))
        a,b,c=self.summarize()["months"]
        self.assertEqual([a["status"],b["status"],c["status"]],["complete","missing","complete"])
        self.assertEqual(a["month"],"2026-09")
        self.assertEqual(c["classes"]["document"]["full_rate"],q(1,3))
        self.assertIsNone(c["classes"]["document"]["delta_from_previous"])
        self.assertIsNone(b["classes"]["asr"]["observed_rate"])
        self.assertIn("TIDAK TAHU",model.markdown(self.summarize()))

    def test_invalid_receipt_keeps_observed_and_holds_complete_rate(self):
        self.put("x","2026-09-05T09:30:00Z",bytes_observations())
        self.put("y","2026-09-05T09:45:00Z",bytes_observations())
        (self.root/"y").write_bytes(b"corrupt")
        a=self.summarize()["months"][0]
        self.assertEqual(a["status"],"incomplete")
        self.assertEqual(a["status_counts"],{"observed":1,"invalid_receipt":1})
        self.assertEqual(a["classes"]["document"]["observed_rate"],q(1))
        self.assertIsNone(a["classes"]["table"]["full_rate"])
