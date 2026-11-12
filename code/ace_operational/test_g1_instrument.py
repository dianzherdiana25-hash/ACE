"""Stage H evidence: the G1 instrument passes complete dossiers
and names exactly what is missing from incomplete ones."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.g1_instrument import assess_g1

REPORT = {"experiment": "pilot-x", "protocol_hash": "abc123",
          "audit": {"status": "CLEAN", "chain_break_at": None,
                    "results_verified": 4,
                    "ledger_entries_verified": 4, "problems": []}}
PROBE = {"package": "OMEGA-04", "subject": "store",
         "method": "three separate OS processes: create -> restart",
         "task_status": "ACTIVE",
         "checkpoint": {"stage": "implemented", "step": 2},
         "event_phases": ["A", "B"], "verdict": "PASS"}


class G1InstrumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-g1-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data))
        return path

    def test_complete_dossier_demonstrates_g1(self):
        result = assess_g1(
            experiment_report=self._write("report.json", REPORT),
            resume_probe=self._write("probe.json", PROBE))
        self.assertEqual(result["overall"], "DEMONSTRATED")
        for clause in result["clauses"].values():
            self.assertEqual(clause["verdict"], "PASS")

    def test_missing_preregistration_fails_c1_by_name(self):
        broken = dict(REPORT)
        del broken["protocol_hash"]
        result = assess_g1(
            experiment_report=self._write("report.json", broken),
            resume_probe=self._write("probe.json", PROBE))
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertIn("protocol_hash",
                      result["clauses"]["C1_task_to_report"]
                      ["missing"][0])

    def test_dirty_audit_fails_c2(self):
        broken = json.loads(json.dumps(REPORT))
        broken["audit"]["status"] = "DIRTY"
        broken["audit"]["chain_break_at"] = 3
        result = assess_g1(
            experiment_report=self._write("report.json", broken),
            resume_probe=self._write("probe.json", PROBE))
        self.assertEqual(result["clauses"]["C2_complete_records"]
                         ["verdict"], "FAIL")

    def test_single_process_probe_fails_c3(self):
        broken = dict(PROBE)
        broken["method"] = "in-memory only"
        broken["event_phases"] = ["A"]
        result = assess_g1(
            experiment_report=self._write("report.json", REPORT),
            resume_probe=self._write("probe.json", broken))
        self.assertEqual(
            result["clauses"]["C3_resume_after_interruption"]
            ["verdict"], "FAIL")

    def test_probe_species_keeps_the_qualification(self):
        result = assess_g1(
            experiment_report=self._write("report.json", REPORT),
            resume_probe=self._write("probe.json", PROBE))
        self.assertEqual(result["criteria_version"], 2)
        self.assertIn("substrate",
                      result["qualification"])

    def test_flagship_drill_lifts_the_qualification(self):
        drill = {"experiment": "resume-drill-flagship",
                 "verdict": "RESUME_DRILL_PASS",
                 "interruption": {
                     "killed_mid_work": True,
                     "state_integrity_after": True,
                     "resumed_by_separate_process": True,
                     "final_report_reached": True,
                     "record_continuity": True}}
        result = assess_g1(
            experiment_report=self._write("report.json", REPORT),
            resume_probe=self._write("drill.json", drill))
        self.assertEqual(result["overall"], "DEMONSTRATED")
        self.assertEqual(
            result["clauses"]["C3_resume_after_interruption"]
            ["evidence"]["species"], "flagship_interruption")
        self.assertTrue(result["qualification"].startswith("none"))

    def test_incomplete_drill_record_fails_c3_by_name(self):
        drill = {"experiment": "resume-drill-flagship",
                 "verdict": "RESUME_DRILL_PASS",
                 "interruption": {"killed_mid_work": True,
                                  "record_continuity": True}}
        result = assess_g1(
            experiment_report=self._write("report.json", REPORT),
            resume_probe=self._write("drill.json", drill))
        clause = result["clauses"]["C3_resume_after_interruption"]
        self.assertEqual(clause["verdict"], "FAIL")
        self.assertTrue(any("state_integrity_after" in item
                            for item in clause["missing"]))

    def test_missing_files_fail_closed(self):
        result = assess_g1(experiment_report=None, resume_probe=None)
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        for clause in result["clauses"].values():
            self.assertEqual(clause["verdict"], "FAIL")
            self.assertTrue(clause["missing"])


if __name__ == "__main__":
    unittest.main()
