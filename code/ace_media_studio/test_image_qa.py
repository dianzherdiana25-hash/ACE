"""Verifier kontras wilayah, piksel clipping, dan data anotasi hilang."""
from hashlib import sha256
import unittest

from ace_media_studio import image_qa
from ace_media_studio._contracts import identity
from ace_media_studio._raster import Raster,png


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.image=png(Raster(4,2,bytes([0,0,0,0,0,0,255,255,255,255,255,255])*2))
        self.plan={"schema":"ace.media.image-qa-plan.v1","source_ref":"fixture/qa","image_sha256":sha256(self.image).hexdigest(),
                   "minimum_width":4,"minimum_height":2,"max_clipped_bp":10000,"min_range":1000,"min_edge_delta":1,
                   "require_text_regions":True,"text_regions":[{"id":"caption","ink":[0,0,2,2],"background":[2,0,2,2],
                                                                "minimum_ratio_milli":4500,"source_ref":"fixture/caption"}]}

    def assess(self):
        return image_qa.evaluate(self.image,self.plan,identity(self.plan))

    def test_actual_contrast_21_to_1_and_clipping_reported(self):
        report=self.assess()
        self.assertEqual(report["status"],"pass")
        self.assertEqual(report["text_regions"][0]["contrast_milli"],21000)
        self.assertEqual(report["metrics"]["clipped_bp"],10000)
        self.plan["max_clipped_bp"]=9999
        self.assertEqual(self.assess()["status"],"hold")

    def test_required_annotations_cannot_pass_when_absent(self):
        self.plan["text_regions"]=[]
        result=self.assess()
        self.assertIn({"rule":"text_annotations","pass":False},result["checks"])
        self.assertEqual(result["status"],"hold")
