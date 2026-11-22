from hashlib import sha256
import unittest

from ._contracts import ResearchError
from .paper_reader import extract
from .test_source_collector import HEADER


class PaperTests(unittest.TestCase):
    def test_measured_rows_only_results_fences_ignored_and_bad_interval_held(self):
        good = "| point | group | cahaya | lab | 25 | pct | 20 | 18 | 30 |"
        bad = "| wrong | group | cahaya | lab | 25 | pct | 20 | 31 | 34 |"
        raw = f"## Metode\n{HEADER}{good}\n\n## Hasil\n```\n{HEADER}{bad}\n```\n{HEADER}{good}\n{bad}\n".encode()
        run = extract(raw, "Fixture", "paper.md", "cohort", sha256(raw).hexdigest())
        self.assertEqual(len(run["claims"]), 1)
        claim = run["claims"][0]
        self.assertEqual(claim["estimate"], "0.25")
        self.assertEqual(claim["source"]["line"], 14)
        self.assertEqual(claim["interval"], {"lower": "0.18", "upper": "0.3"})
        self.assertIn("tidak mengapit", run["held"][0]["reason"])
        with self.assertRaisesRegex(ResearchError, "anchor"):
            extract(raw, "Fixture", "paper.md", "cohort", "0" * 64)
