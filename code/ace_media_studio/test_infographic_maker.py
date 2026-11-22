from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .infographic_maker import make_infographic


class ChartTests(unittest.TestCase):
    def test_bar_scale_zero_base_csv_lineage_and_pixels(self):
        csv = b"label,value,source_ref\nMalam,3.0,fixture:night\nSiang,6.0,fixture:noon\nKosong,0,fixture:none\n"
        plan = {"schema": "ace.media.infographic-plan.v1", "csv_sha256": sha256(csv).hexdigest(),
                "title": "INTENSITAS CAHAYA", "unit": "LUX", "width": 320, "descending": True}
        data, report = make_infographic(csv, plan, identity(plan))
        bars = report["bars"]
        self.assertEqual([row["csv_line"] for row in bars], [3, 2, 4])
        self.assertEqual(report["scaling"]["minimum"], "0")
        self.assertEqual(report["scaling"]["maximum"], "6.0")
        self.assertEqual([row["bar_pixels"] for row in bars], [report["scaling"]["length_px"],
                         report["scaling"]["length_px"] // 2, 0])
        self.assertEqual(bars[0]["source_ref"], "fixture:noon")
        image = raster(data)
        self.assertEqual(image.at(*bars[0]["rect"][:2]), (45, 113, 155))
        self.assertNotEqual(image.at(*bars[2]["rect"][:2]), (45, 113, 155))
        broken = csv.replace(b"6.0", b"0E+10000")
        plan["csv_sha256"] = sha256(broken).hexdigest()
        with self.assertRaisesRegex(ContractError, "desimal"):
            make_infographic(broken, plan, identity(plan))
