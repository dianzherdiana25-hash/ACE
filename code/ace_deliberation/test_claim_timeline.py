"""Uji peristiwa sebagai versi, cutoff, dan keterlacakan perubahan bukti."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import claim_timeline as timeline


def event(number, operation, statement, refs, claim="x"):
    return {"id": f"{claim}-{number}", "claim": claim, "source_ref": f"fixture/event/{claim}/{number}",
            "at": f"2026-11-20T00:0{number}:00Z", "operation": operation,
            "previous_version": number - 1, "statement": statement,
            "evidence_refs": refs, "reason": "Alasan fixture"}


def fixture():
    return {"as_of": "2026-11-20T00:04:00Z", "events": [
        event(1, "publish", "Awal", ["e1", "e2"]),
        event(2, "revise", "Batas berubah", ["e2", "e3"]),
        event(3, "retract", "Batas berubah", ["e3", "e2"]),
        event(4, "reinstate", "Valid dalam cakupan baru", ["e4"]),
    ]}


class TimelineTests(unittest.TestCase):
    def test_retraction_keeps_same_record_then_reinstatement_is_separate(self):
        row, = timeline.build_timeline(fixture())["claims"]
        initial, second, withdrawn, restored = row["versions"]
        self.assertEqual(initial["statement"], "Awal")
        self.assertEqual(second["evidence_added"], ["e3"])
        self.assertEqual(second["evidence_removed"], ["e1"])
        self.assertEqual(withdrawn["status"], "retracted")
        self.assertFalse(withdrawn["statement_changed"])
        self.assertEqual(restored["previous_event_id"], "x-3")
        self.assertEqual(row["current"], restored)
        self.assertEqual(restored["status"], "asserted")

    def test_cutoff_reports_only_visible_versions_without_making_future_claim(self):
        raw = {**fixture(), "as_of": "2026-11-20T00:03:00Z"}
        raw["events"].append(event(1, "publish", "Belum diketahui", ["q"], "another"))
        raw["events"][-1]["at"] = "2026-11-21T00:00:00Z"
        result = timeline.build_timeline(raw)["claims"]
        claim, = result
        self.assertEqual(claim["current"]["status"], "retracted")
        self.assertEqual(len(claim["versions"]), 3)
        self.assertNotIn("Belum diketahui", json.dumps(result))

    def test_stale_version_cannot_overwrite_existing_evidence(self):
        raw = fixture()
        raw["events"][1]["previous_version"] = 0
        with self.assertRaisesRegex(timeline.TimelineError, "usang"):
            timeline.build_timeline(raw)

    def test_retracted_statement_requires_reinstatement_before_further_revision(self):
        raw = fixture()
        raw["events"][3]["operation"] = "revise"
        with self.assertRaisesRegex(timeline.TimelineError, "reinstate"):
            timeline.build_timeline(raw)

    def test_noop_revision_and_unanchored_retraction_are_rejected(self):
        raw = fixture()
        raw["events"][1].update(statement="Awal", evidence_refs=["e1", "e2"])
        with self.assertRaisesRegex(timeline.TimelineError, "tidak mengubah"):
            timeline.build_timeline(raw)
        raw = fixture()
        raw["events"][2]["evidence_refs"] = ["inserted"]
        with self.assertRaisesRegex(timeline.TimelineError, "tidak boleh"):
            timeline.build_timeline(raw)

    def test_shuffled_ledger_reconstructs_identical_cli_report(self):
        raw = fixture()
        expected = timeline.build_timeline(raw)
        raw["events"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "claim.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(timeline.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_diff_keeps_intermediate_retraction_even_if_endpoint_is_asserted_again(self):
        raw = fixture()
        report = timeline.diff_since(raw, "2026-11-20T00:02:00Z")
        changed, = report["changes"]
        self.assertEqual((changed["before"]["status"], changed["after"]["status"]), ("asserted", "asserted"))
        self.assertEqual([event["kind"] for event in changed["operations"]], ["retract", "reinstate"])
        self.assertEqual(changed["operations"][0]["source_ref"], "fixture/event/x/3")

    def test_diff_rejects_inverted_cutoff_and_empty_when_equal(self):
        raw = fixture()
        self.assertEqual(timeline.diff_since(raw, raw["as_of"])["changes"], [])
        with self.assertRaisesRegex(timeline.TimelineError, "melampaui"):
            timeline.diff_since(raw, "2026-11-20T00:05:00Z")

    def test_cli_diff_reports_initial_claim_with_no_preexisting_snapshot(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        path = root / "claim.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(timeline.main([str(path), "--diff-since", "2026-11-20T00:00:00Z"]), 0)
        changed, = json.loads(output.getvalue())["changes"]
        self.assertIsNone(changed["before"])
        self.assertEqual(changed["after"]["version"], 4)
        self.assertEqual(changed["operations"][0]["kind"], "publish")

    def test_same_instant_overlapping_versions_cannot_be_disambiguated_by_id(self):
        raw = fixture()
        raw["events"][2]["at"] = raw["events"][1]["at"]
        with self.assertRaisesRegex(timeline.TimelineError, "mendahului"):
            timeline.build_timeline(raw)

    def test_publish_cannot_enter_snapshot_without_evidence(self):
        raw = fixture()
        raw["events"][0]["evidence_refs"] = []
        with self.assertRaisesRegex(timeline.TimelineError, "rujukan bukti"):
            timeline.build_timeline(raw)
