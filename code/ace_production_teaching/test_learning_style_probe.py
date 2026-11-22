from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .learning_style_probe import probe
from .test_tabular_engine import save


class FormatTests(unittest.TestCase):
    def test_only_matched_format_pairs_affect_mean_with_missing_visible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = [dict(pair=f"p{pair}", format=mode, score_bp=score, seconds=30, source_ref="fixture:record")
                    for pair, mode, score in ((1, "text", 6000), (1, "audio", 8000), (2, "text", 7000),
                                              (2, "audio", 7500), (3, "audio", 10000))]
            plan = {"schema": "ace.teaching.format-probe-plan.v1",
                    "observations": save(root, "outcomes", b"\n".join(map(canonical, rows))),
                    "formats": ["text", "audio"], "minimum_pairs": 2, "minimum_delta_bp": 1000}
            result = probe(plan, identity(plan), root)
            self.assertEqual((result["pair_count"], result["mean_second_minus_first_bp"]), (2, 1250))
            self.assertEqual(result["held"], [{"pair": "p3", "missing_formats": ["text"]}])
            self.assertEqual(result["status"], "higher_observed_scores_in_audio")
