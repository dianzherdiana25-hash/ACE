"""Verifier rantai edit, orientasi, filter dan penolakan cover transparan."""
from hashlib import sha256
import unittest

from ace_media_studio import image_editor
from ace_media_studio._contracts import ContractError,identity
from ace_media_studio._raster import Raster,blank,png,raster


class EditorTests(unittest.TestCase):
    def run_edit(self,image,operations):
        source=png(image)
        raw={"schema":"ace.media.image-edit-plan.v1","source_ref":"fixture/edit","format":"png",
             "input_sha256":sha256(source).hexdigest(),"operations":operations}
        payload,receipt=image_editor.edit(source,raw,identity(raw))
        return raster(payload),receipt

    def test_rotate_then_crop_and_cover_exactly(self):
        original=Raster(2,3,bytes(channel for n in range(6) for channel in (n*20,0,0)))
        result,proof=self.run_edit(original,[{"op":"rotate","quarter_turns":1},{"op":"crop","box":[0,0,2,2]},
                                            {"op":"cover","color":"#ffffff","box":[1,1,1,1]}])
        self.assertEqual(result.at(0,0),(80,0,0))
        self.assertEqual(result.at(1,0),(40,0,0))
        self.assertEqual(result.at(0,1),(100,0,0))
        self.assertEqual(result.at(1,1),(255,255,255))
        self.assertEqual(proof["steps"][1]["before"],proof["steps"][0]["after"])

    def test_resize_and_blur_preserve_constant_color(self):
        result,_=self.run_edit(blank(3,2,(100,160,20)),[
            {"op":"resize","width":9,"height":7,"filter":"bilinear"},{"op":"box_blur","radius":2},
            {"op":"exposure","gain_milli":2000,"offset":-1}])
        self.assertEqual(result.at(6,3),(199,255,39))
        self.assertEqual(result.at(0,0),(199,255,39))

    def test_transparent_cover_and_outside_crop_rejected(self):
        with self.assertRaisesRegex(ContractError,"opak"):
            self.run_edit(blank(3,2,(1,2,3)),[{"op":"cover","color":"#ffffff80","box":[1,1,1,1]}])
        with self.assertRaises(ContractError):
            self.run_edit(blank(3,2,(1,2,3)),[{"op":"crop","box":[1,1,6,1]}])
