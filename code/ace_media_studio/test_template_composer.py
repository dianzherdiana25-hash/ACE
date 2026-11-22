from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from ._raster import blank, png, raster
from .template_composer import compose_template


class TemplateTests(unittest.TestCase):
    def test_local_template_preserved_outside_caption_and_low_contrast_held(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            src = blank(100, 78, (200, 130, 70))
            raw = png(src)
            (root / "base.png").write_bytes(raw)
            slot = {"id": "bottom", "x": 5, "y": 48, "width": 90, "height": 26,
                    "ink": "#F0F0E0", "fill": "#141421"}
            plan = {"schema": "ace.media.reaction-plan.v1", "template":
                    {"id": "fixture", "path": "base.png", "sha256": sha256(raw).hexdigest(),
                     "license_ref": "fixture:authored", "slots": [slot]},
                    "captions": [{"id": "bottom", "text": "SIAP", "source_ref": "fixture:label"}]}
            result, report = compose_template(plan, identity(plan), root)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["layout"][0]["lines"], ["SIAP"])
            self.assertEqual(raster(result).at(50, 22), src.at(50, 22))
            self.assertEqual(raster(result).at(5, 48), (20, 20, 33))
            slot["ink"] = slot["fill"]
            result, report = compose_template(plan, identity(plan), root)
            self.assertIsNone(result)
            self.assertEqual(report["status"], "hold")
            plan["template"]["slots"].append(slot | {"id": "overlap"})
            with self.assertRaisesRegex(ContractError, "tumpang tindih"):
                compose_template(plan, identity(plan), root)
