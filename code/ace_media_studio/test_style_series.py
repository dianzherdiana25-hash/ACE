"""Verifier motif, palet aktual, dan variasi yang byte-identik antar-run."""
from hashlib import sha256
import unittest

from ace_media_studio import style_series
from ace_media_studio._contracts import ContractError,identity
from ace_media_studio._raster import raster


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.media.style-series-plan.v1","id":"local_series","source_ref":"fixture/style",
                   "width":80,"height":64,"margin":9,
                   "palette":{"background":"#1b1d29","shadow":"#3b5121","accent":"#ecaa35","highlight":"#def152"},
                   "motif":"diamond","seed":42,"rows":2,"columns":2,
                   "panels":[{"id":name,"source_ref":"fixture/"+name} for name in ("first","second","third")]}

    def render(self):
        return style_series.build(self.plan,identity(self.plan))

    def test_constant_style_and_distinct_layouts_with_reproducible_bytes(self):
        files,report=self.render()
        self.assertEqual((files,report),self.render())
        self.assertEqual(report["distinct_panels"],3)
        for panel in report["panels"]:
            data=files[panel["path"]]
            image=raster(data)
            self.assertEqual(panel["image_sha256"],sha256(data).hexdigest())
            self.assertEqual(image.at(40,0),(236,170,53))
            self.assertEqual(panel["style_sha256"],report["style_sha256"])

    def test_palette_and_overlap_budget_fail_before_file_generation(self):
        self.plan["palette"]["accent"]=self.plan["palette"]["highlight"]
        with self.assertRaisesRegex(ContractError,"warna"):
            self.render()
        self.plan["palette"]["accent"]="#ecaa35"
        self.plan["columns"]=7
        with self.assertRaisesRegex(ContractError,"motif"):
            self.render()
