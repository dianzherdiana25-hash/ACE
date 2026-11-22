from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, canonical, decode, identity
from .studio_season_report import summarize


class SeasonReportTests(unittest.TestCase):
    def test_season_rollup_weighted_over_checks_dedup_and_open_evidence(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = Path(__file__).parent / "fixtures" / "closed_studio_evidence" / "report.json"
            proof = decode(source.read_bytes())

            def link(name, data):
                raw = canonical(data)
                (root / name).write_bytes(raw)
                return {"path": name, "sha256": sha256(raw).hexdigest()}

            first = link("first.json", proof)
            proof["qa"]["checks"][0]["pass"] = False
            proof["qa"].update(passed=9, score_bp=9000)
            next_check = link("second.json", proof)
            plan = {"schema": "ace.media.season-report-plan.v1", "roster": [
                {"series": "fixture", "season": 1, "episode": 1, "source_ref": "fixture:first", "receipt": first},
                {"series": "fixture", "season": 1, "episode": 2, "source_ref": "fixture:missing", "receipt": None},
                {"series": "fixture", "season": 2, "episode": 1, "source_ref": "fixture:second", "receipt": next_check}]}
            report = summarize(plan, identity(plan), root)
            initial, after = report["seasons"]
            self.assertEqual((initial["episode_count"], initial["measured_episodes"]), (2, 1))
            self.assertEqual(initial["evidence_gaps"][0]["source_ref"], "fixture:missing")
            self.assertEqual(after["qa_change_bp"], -1000)
            self.assertEqual(after["qa"]["failed_criteria"], {"video_decodes": 1})
            self.assertEqual(after["character"]["total"], 20)
            plan["roster"][1]["receipt"] = first
            with self.assertRaisesRegex(ContractError, "beberapa episode"):
                summarize(plan, identity(plan), root)
