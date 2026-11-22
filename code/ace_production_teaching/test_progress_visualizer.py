from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree as ET

from ._contracts import canonical, identity
from .chart_builder import NS
from .progress_visualizer import visualize
from .test_tabular_engine import save


class ProgressTests(unittest.TestCase):
    def test_missing_checkpoint_gets_explicit_gap_and_no_joined_line(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            register = {"schema": "ace.teaching.progress-readings.v1", "checkpoints": [
                {"topic": "sketch", "date": f"2025-04-0{i}", "score_bp": score,
                 "source_ref": f"fixture:{i}"} for i, score in enumerate((4000, 6300, None, 6000, 7200), 1)]}
            plan = {"schema": "ace.teaching.progress-plan.v1", "readings": save(root, "points", canonical(register)),
                    "chart_width": 460, "topics": ["sketch"]}
            files, report = visualize(plan, identity(plan), root)
            proof = report["topics"][0]
            self.assertEqual(proof["missing_checkpoints"][0]["date"], "2025-04-03")
            self.assertEqual(set(files), {"sketch_1.svg", "sketch_2.svg"})
            for raw in files.values():
                shapes = ET.fromstring(raw).findall(f".//{{{NS}}}circle")
                self.assertEqual(len(shapes), 2)
