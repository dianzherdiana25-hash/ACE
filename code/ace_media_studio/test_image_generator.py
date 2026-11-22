"""Verifier geometri, alpha, determinisme, dan round trip format raster."""
from hashlib import sha256
import unittest

from ace_media_studio import image_generator
from ace_media_studio._contracts import ContractError,identity
from ace_media_studio._raster import raster


def plan(instructions=None):
    return {"schema":"ace.media.image-plan.v1","id":"fixture_scene","source_ref":"fixture/design","format":"png",
            "instructions":instructions or "CANVAS 12 10 #111111\nGRADIENT x #000000 #ffffff\nRECT 2 2 4 4 #ff000080\n"
                                           "ELLIPSE 7 2 4 4 #00ff00\nLINE 2 8 8 8 2 #0000ff\nPOLYGON #ff9e2c 1,0 3,0 2,2"}


class GeneratorTests(unittest.TestCase):
    def test_rendered_pixels_confirm_gradient_alpha_and_line(self):
        raw=plan()
        data,report=image_generator.render(raw,identity(raw))
        image=raster(data)
        self.assertEqual(image.at(0,9),(0,0,0))
        self.assertEqual(image.at(11,9),(255,255,255))
        self.assertEqual(image.at(8,3),(0,255,0))
        self.assertEqual(image.at(4,8),(0,0,255))
        self.assertGreater(image.at(3,3)[0],image.at(3,3)[1])
        self.assertEqual(report["image_sha256"],sha256(data).hexdigest())
        self.assertEqual(image_generator.render(raw,identity(raw)),(data,report))
        raw["format"]="ppm"
        output,_=image_generator.render(raw,identity(raw))
        self.assertEqual(raster(output),image)

    def test_invalid_source_has_no_partial_image(self):
        for instruction in ("CANVAS 5 5 #aaaaaa\nRECT 30 0 1 1 #000000",
                            "CANVAS 4 4 #aaaaaaaa\nRECT 0 0 2 2 #000000",
                            "CANVAS 5 5 #aaaaaa\nPOLYGON #123456 0,0 1,1 2,2"):
            raw=plan(instruction)
            with self.subTest(value=instruction),self.assertRaises(ContractError):
                image_generator.render(raw,identity(raw))
