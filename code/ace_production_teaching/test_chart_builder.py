from hashlib import sha256
from xml.etree import ElementTree as ET
import unittest

from ._contracts import ProductionError, identity
from .chart_builder import NS, make_chart


class ChartTests(unittest.TestCase):
    def test_values_proportional_from_zero_and_text_escaped(self):
        plan = {"schema": "ace.production.chart-plan.v1", "title": "Pengukuran <data>", "kind": "bar",
                "width": 400, "height": 300, "y_label": "Lux", "y_axis": {"min": "-10", "max": "10"},
                "points": [{"label": "A", "value": "-5", "source_ref": "fixture:a"},
                           {"label": "B", "value": "5", "source_ref": "fixture:b"}]}
        data, report = make_chart(plan, identity(plan))
        svg = ET.fromstring(data)
        self.assertEqual(svg.find(f"{{{NS}}}title").text, "Pengukuran <data>")
        self.assertEqual(report["chart_sha256"], sha256(data).hexdigest())
        coords = report["points"]
        self.assertGreater(coords[0]["y"], coords[1]["y"])
        bars = svg.findall(f".//{{{NS}}}g/{{{NS}}}rect")
        self.assertLessEqual(abs(int(bars[0].get("height")) - int(bars[1].get("height"))), 1)
        plan["y_axis"] = {"min": "-8", "max": "-2"}
        with self.assertRaisesRegex(ProductionError, "baseline nol"):
            make_chart(plan, identity(plan))
