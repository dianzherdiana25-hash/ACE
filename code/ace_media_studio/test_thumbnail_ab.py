from collections import Counter
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .test_cover_maker import cover_plan
from .thumbnail_ab import draft_comparison


class ThumbnailABTests(unittest.TestCase):
    def test_exactly_one_factor_rendered_and_first_exposure_balanced(self):
        plan = {"schema": "ace.media.thumbnail-ab.v1", "base_cover": cover_plan(), "factor": "accent",
                "levels": ["#204060", "#903040"], "subjects": ["red", "green", "blue", "white"], "seed": 20}
        outputs, report = draft_comparison(plan, identity(plan))
        first = Counter(item["display"][0]["sha256"] for item in report["assignments"])
        self.assertEqual(sorted(first.values()), [2, 2])
        self.assertIsNone(report["result"])
        a, b = map(raster, outputs.values())
        self.assertEqual(a.at(0, 0), b.at(0, 0))
        self.assertNotEqual(a.at(0, 95), b.at(0, 95))
        self.assertEqual(report, draft_comparison(plan, identity(plan))[1])
        plan["subjects"].pop()
        with self.assertRaisesRegex(ContractError, "genap"):
            draft_comparison(plan, identity(plan))
