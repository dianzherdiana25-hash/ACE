from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational import leap_wiring


class StudioWiringTests(unittest.TestCase):
    def test_default_cycle_contract_unchanged_and_missing_anchor_holds_only_extension(self):
        with TemporaryDirectory() as temporary:
            engine = SimpleNamespace(workspace=Path(temporary))
            with patch.dict("os.environ", {}, clear=True), patch.object(leap_wiring, "step_evo0056_media_studio") as step:
                result = leap_wiring.step_capability_report(engine)
            self.assertEqual(set(result), {"status", "schema", "completeness", "gaps"})
            step.assert_not_called()
            self.assertTrue((engine.workspace / "capability_report.md").is_file())
            with patch.dict("os.environ", {"ACE_EVO0056_MEDIA_STUDIO": "1"}, clear=True):
                self.assertEqual(leap_wiring.step_capability_report(engine)["media_studio"],
                                 {"status": "held", "reason": "workspace_or_anchor_missing"})

    def test_gated_receipt_matches_fixture_and_rejects_tampering_or_symlink(self):
        source = Path(__file__).parent / "fixtures" / "closed_studio_evidence" / "report.json"
        content = source.read_bytes()
        anchor = sha256(content).hexdigest()
        environment = {"ACE_EVO0056_MEDIA_STUDIO": "1", "ACE_EVO0056_REPORT_SHA256": anchor}
        with TemporaryDirectory() as temporary, patch.dict("os.environ", environment, clear=True):
            workspace = Path(temporary)
            root = workspace / "evo0056_media"
            root.mkdir()
            data = root / "bench_report.json"
            engine = SimpleNamespace(workspace=workspace)
            data.write_bytes(content)
            result = leap_wiring.step_capability_report(engine)["media_studio"]
            self.assertEqual((result["scope"], result["qa_passed"], result["qa_total"]), ("closed_fixture", 10, 10))
            self.assertEqual((result["character_passed"], result["character_total"]), (20, 20))
            self.assertEqual(data.read_bytes(), content)
            data.write_bytes(content + b" ")
            self.assertEqual(leap_wiring.step_evo0056_media_studio(engine)["status"], "held")
            data.unlink()
            data.symlink_to(source)
            self.assertEqual(leap_wiring.step_evo0056_media_studio(engine)["status"], "held")
