from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .series_cover_system import make_series


class SeriesCoverTests(unittest.TestCase):
    def test_same_title_episodes_have_distinct_marks_with_same_band(self):
        style = {"background": "#202038", "accent": "#3060A0", "foreground": "#F0E0C0",
                 "width": 160, "height": 96, "minimum_contrast_milli": 4500}
        plan = {"schema": "ace.media.series-cover.v1", "series": "test", "season": 2, "style": style,
                "source_ref": "fixture:identity", "episodes": [
                    {"episode": 2, "id": "two", "title": "CAHAYA", "source_ref": "fixture:episode-2"},
                    {"episode": 1, "id": "one", "title": "CAHAYA", "source_ref": "fixture:episode-1"}]}
        files, report = make_series(plan, identity(plan))
        self.assertEqual([item["episode"] for item in report["covers"]], [1, 2])
        self.assertEqual(len({item["series_band_sha256"] for item in report["covers"]}), 1)
        first, second = files["s002_e001_one.png"], files["s002_e002_two.png"]
        self.assertNotEqual(first, second)
        self.assertEqual(raster(first).at(5, 92), (18, 21, 26))
        self.assertEqual(raster(second).at(5, 92), (48, 96, 160))
        self.assertEqual(report["covers"][0]["cover_sha256"], sha256(first).hexdigest())
        style["foreground"] = style["background"]
        with self.assertRaisesRegex(ContractError, "Kontras sampul"):
            make_series(plan, identity(plan))
