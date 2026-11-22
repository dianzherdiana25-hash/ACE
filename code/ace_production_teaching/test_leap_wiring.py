from hashlib import sha256
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational import leap_wiring


class TeachingWiringTests(unittest.TestCase):
    def test_dashboard_default_skips_new_hook_and_enabled_without_anchor_holds(self):
        with TemporaryDirectory() as temporary:
            engine = SimpleNamespace(workspace=Path(temporary))
            with patch("tools.repo_status_dashboard_v3.collect_v3_status", return_value={"summary": {"tool_count": 2}}), patch(
                    "tools.repo_status_dashboard_v3.render_v3_html", return_value="<p>fixture</p>"):
                with patch.dict("os.environ", {}, clear=True), patch.object(leap_wiring, "step_evo0058_teaching") as hook:
                    baseline = leap_wiring.step_dashboard_v3(engine)
                hook.assert_not_called()
                self.assertNotIn("production_teaching", baseline)
                with patch.dict("os.environ", {"ACE_EVO0058_TEACHING": "1"}, clear=True):
                    enabled = leap_wiring.step_dashboard_v3(engine)
                self.assertEqual(enabled.pop("production_teaching"), {"status": "held", "reason": "workspace_or_anchor_missing"})
                self.assertEqual(baseline, enabled)

    def test_evidence_requires_matching_artifact_byte_hashes_and_keeps_files_unchanged(self):
        source = Path(__file__).parent / "fixtures" / "teaching_bench_evidence"
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            bench = workspace / "evo0058_teaching"
            copytree(source, bench)
            digest = sha256((bench / "run.json").read_bytes()).hexdigest()
            engine = SimpleNamespace(workspace=workspace)
            opt_in = {"ACE_EVO0058_TEACHING": "1", "ACE_EVO0058_REPORT_SHA256": digest}
            old = {p.name: p.read_bytes() for p in bench.iterdir()}
            with patch.dict("os.environ", opt_in, clear=True):
                valid = leap_wiring.step_evo0058_teaching(engine)
                self.assertEqual(valid["fixture_status"], "fixture_pass")
                self.assertEqual(valid["details"]["artifact_passed"], 5)
                self.assertEqual({p.name: p.read_bytes() for p in bench.iterdir()}, old)
                (bench / "workbook.xlsx").write_bytes(b"tampered")
                self.assertEqual(leap_wiring.step_evo0058_teaching(engine)["status"], "held")
