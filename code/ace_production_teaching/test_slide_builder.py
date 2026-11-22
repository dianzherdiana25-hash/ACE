from importlib.util import find_spec
from io import BytesIO
import unittest

from ._contracts import ProductionError, identity
from .slide_builder import make_slides


@unittest.skipUnless(find_spec("pptx"), "Backend slide lokal diperlukan")
class SlidesTests(unittest.TestCase):
    def test_three_distinct_slide_layouts_can_be_read_back_with_source(self):
        from pptx import Presentation

        plan = {"schema": "ace.production.slide-plan.v1", "title": "Catatan percobaan", "slides": [
            {"id": "start", "title": "Ringkasan", "kind": "bullets", "source_ref": "fixture:summary",
             "content": ["Dua kelompok sebanding", "Tiga pengukuran"]},
            {"id": "compare", "title": "Perbandingan", "kind": "comparison", "source_ref": "fixture:compare",
             "content": {"left": {"heading": "Baseline", "points": ["Kontrol"]}, "right": {"heading": "Target", "points": ["Uji"]}}},
            {"id": "grid", "title": "Data", "kind": "table", "source_ref": "fixture:data",
             "content": {"columns": ["Metrik", "Nilai"], "rows": [["Tinggi", "30"]]}}]}
        data, report = make_slides(plan, identity(plan))
        result = Presentation(BytesIO(data))
        self.assertEqual(len(result.slides), 3)
        self.assertEqual(result.core_properties.title, "Catatan percobaan")
        self.assertTrue(any(shape.has_text_frame and shape.text == "fixture:summary" for shape in result.slides[0].shapes))
        self.assertEqual(next(shape.table for shape in result.slides[2].shapes if shape.has_table).cell(1, 1).text, "30")
        self.assertEqual(report["slides"][1]["kind"], "comparison")
        self.assertEqual(make_slides(plan, identity(plan))[0], data)
        plan["slides"][2]["id"] = "start"
        with self.assertRaisesRegex(ProductionError, "ganda"):
            make_slides(plan, identity(plan))
