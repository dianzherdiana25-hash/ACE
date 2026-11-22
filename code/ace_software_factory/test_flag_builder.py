"""Verifier segmentasi, batas masa berlaku dan bucketing yang stabil."""
import unittest

from ace_software_factory import flag_builder
from ace_software_factory._contracts import identity


class FlagTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-flag-plan.v1","product_id":"catalog","source_ref":"fixture/flags",
                   "attributes":[{"id":"tier","values":["green","blue"]}],
                   "flags":[{"id":"new_style","start":"2026-11-20T00:00:00Z","end":"2026-11-21T00:00:00Z",
                             "enabled":True,"salt":"phase_one","rollout_bp":10000,
                             "segments":[{"tier":["green"]}],"source_ref":"fixture/flags/style"}]}
        self.request={"flag":"new_style","subject":"unit_test","at":"2026-11-20T00:00:00Z",
                      "attributes":{"tier":"green"}}

    def evaluate(self,**options):
        return flag_builder.evaluate(self.plan,identity(self.plan),self.request,**options)

    def test_stable_bucket_and_strict_rollout_boundary(self):
        first=self.evaluate()
        self.assertTrue(first["enabled"])
        self.assertEqual(first,self.evaluate())
        self.assertNotIn(self.request["subject"],str(first))
        self.plan["flags"][0]["rollout_bp"]=first["bucket"]
        self.assertFalse(self.evaluate()["enabled"])
        self.plan["flags"][0]["rollout_bp"]+=1
        self.assertTrue(self.evaluate()["enabled"])

    def test_segment_controls_disable_and_unknown_fail_closed(self):
        self.assertEqual(self.evaluate(disabled=["new_style"])["reason"],"disabled")
        self.request["attributes"]["tier"]="blue"
        self.assertEqual(self.evaluate()["reason"],"outside_segment")
        self.request["at"]="2026-11-21T00:00:00Z"
        self.assertEqual(self.evaluate()["reason"],"inactive_window")
        self.request["flag"]="different"
        self.assertEqual(self.evaluate()["reason"],"unknown_flag")
