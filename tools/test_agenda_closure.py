"""Fixture sintetik & verifikasi pointer untuk laporan penutupan kandidat agenda (Garis A2 Tranche 2)."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.agenda_candidates import (
    CLOSURE_SCHEMA,
    build_closure_report,
    prioritize,
    propose_asset_pairs,
    scan_failure_documents,
)


SCRIPT = Path(__file__).with_name("agenda_candidates.py")


class AgendaClosureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "handover").mkdir()
        (self.root / "docs").mkdir()

    def _write_repo_file(self, rel_path: str, content: str) -> tuple[str, str]:
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return rel_path, digest

    def _sample_proposals(self):
        assets = {
            "tool_a": {"kind": "tool", "name": "A"},
            "corpus_a": {"kind": "corpus", "name": "B"},
            "engine_b": {"kind": "engine", "name": "C"},
        }
        asset_props = propose_asset_pairs(
            assets, [], assets_source="handover/assets.json", snapshot_source="handover/known.jsonl"
        )
        verdict_props = scan_failure_documents({
            "handover/VERDICT.md": (
                "# PROGRAM VERDICT — Gate X: NOT_PASSED\n"
                "### Probe 1 (VONIS: INSTRUMEN_TIDAK_CUKUP)\n"
                "### Probe 2: NOL\n"
            ),
        })
        return prioritize(asset_props + verdict_props)

    def test_closure_report_proves_status_per_candidate_and_flags_orphans(self):
        proposals = self._sample_proposals()
        ids = [row["proposal_id"] for row in proposals]
        self.assertGreaterEqual(len(ids), 6)

        reg_path, reg_sha = self._write_repo_file(
            "handover/AGENDA_REGISTER.md",
            "line 1 header\nDECISION: APPROVED batch 1\nDECISION: COMPLETED run 99\nDECISION: REJECTED scope\nDECISION: DEFERRED phase 2\n",
        )

        decisions = [
            {
                "proposal_id": ids[0],
                "decision": "APPROVED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 2, "sha256": reg_sha, "excerpt": "APPROVED batch 1"},
            },
            {
                "candidate_id": ids[1],
                "decision": "COMPLETED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 3, "sha256": reg_sha, "commit": "478848d"},
            },
            {
                "proposal_id": ids[2],
                "decision": "REJECTED",
                "decided_by": "ila",
                "decision_pointer": {"path": reg_path, "line": 4, "sha256": reg_sha},
            },
            {
                "proposal_id": ids[3],
                "decision": "DEFERRED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 5},
            },
            # ids[4] intentionally has no decision -> OPEN_PENDING_DECISION
            # ids[5] gets conflicting decisions -> CONFLICTING_DECISION
            {
                "proposal_id": ids[5],
                "decision": "APPROVED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 2},
            },
            {
                "proposal_id": ids[5],
                "decision": "REJECTED",
                "decided_by": "ila",
                "decision_pointer": {"path": reg_path, "line": 4},
            },
            # Orphan decision
            {
                "proposal_id": "agenda-nonexistent-999",
                "decision": "APPROVED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 2},
            },
        ]

        report = build_closure_report(proposals, decisions, repo_root=self.root)
        self.assertEqual(report["schema"], CLOSURE_SCHEMA)
        by_id = {item["candidate_id"]: item for item in report["items"]}

        self.assertEqual(by_id[ids[0]]["status"], "CLOSED_APPROVED")
        self.assertTrue(by_id[ids[0]]["closed"])
        self.assertEqual(by_id[ids[0]]["verified_pointers"][0]["observed_sha256"], reg_sha)
        self.assertEqual(by_id[ids[1]]["status"], "CLOSED_COMPLETED")
        self.assertTrue(by_id[ids[1]]["closed"])
        self.assertEqual(by_id[ids[2]]["status"], "CLOSED_REJECTED")
        self.assertTrue(by_id[ids[2]]["closed"])
        self.assertEqual(by_id[ids[3]]["status"], "OPEN_DEFERRED")
        self.assertFalse(by_id[ids[3]]["closed"])
        self.assertEqual(by_id[ids[4]]["status"], "OPEN_PENDING_DECISION")
        self.assertFalse(by_id[ids[4]]["closed"])
        self.assertEqual(by_id[ids[5]]["status"], "CONFLICTING_DECISION")
        self.assertFalse(by_id[ids[5]]["closed"])

        self.assertEqual(report["summary"]["total_candidates"], len(proposals))
        self.assertEqual(report["summary"]["closed_count"], 3)
        self.assertEqual(report["summary"]["open_or_invalid_count"], len(proposals) - 3)
        self.assertEqual(report["summary"]["orphan_decision_count"], 1)
        self.assertEqual(report["orphan_decisions"][0]["candidate_id"], "agenda-nonexistent-999")

    def test_pointer_failures_stay_fail_closed(self):
        proposals = self._sample_proposals()[:4]
        ids = [row["proposal_id"] for row in proposals]
        reg_path, reg_sha = self._write_repo_file("handover/REG.md", "baris 1\nbaris 2\n")

        bad_decisions = [
            # Missing pointer
            {"proposal_id": ids[0], "decision": "APPROVED", "decided_by": "Ian"},
            # Wrong SHA-256
            {
                "proposal_id": ids[1],
                "decision": "APPROVED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 1, "sha256": "0" * 64},
            },
            # Line out of range
            {
                "proposal_id": ids[2],
                "decision": "COMPLETED",
                "decided_by": "Ian",
                "decision_pointer": {"path": reg_path, "line": 99},
            },
            # Path traversal outside repo
            {
                "proposal_id": ids[3],
                "decision": "REJECTED",
                "decided_by": "Ian",
                "decision_pointer": {"path": "../outside.md", "line": 1},
            },
        ]
        report = build_closure_report(proposals, bad_decisions, repo_root=self.root)
        self.assertEqual(report["summary"]["closed_count"], 0)
        for item in report["items"]:
            self.assertEqual(item["status"], "INVALID_DECISION_POINTER")
            self.assertFalse(item["closed"])
            self.assertEqual(item["verified_pointers"], [])
            self.assertTrue(item["validation_errors"])

    def test_cli_closure_subcommand_end_to_end(self):
        proposals = self._sample_proposals()[:2]
        reg_path, reg_sha = self._write_repo_file("handover/DECISIONS.md", "APPROVED item 1\n")
        (self.root / "handover/proposals.jsonl").write_text(
            "".join(json.dumps(p) + "\n" for p in proposals), encoding="utf-8"
        )
        (self.root / "handover/decisions.json").write_text(
            json.dumps({
                "decisions": [
                    {
                        "proposal_id": proposals[0]["proposal_id"],
                        "decision": "APPROVED",
                        "decided_by": "Ian",
                        "decision_pointer": {"path": reg_path, "line": 1, "sha256": reg_sha},
                    }
                ]
            }),
            encoding="utf-8",
        )
        res = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(self.root),
                "closure",
                "--proposals",
                "handover/proposals.jsonl",
                "--decisions",
                "handover/decisions.json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["schema"], CLOSURE_SCHEMA)
        self.assertEqual(
            payload["summary"]["counts_by_status"],
            {"CLOSED_APPROVED": 1, "OPEN_PENDING_DECISION": 1},
        )


if __name__ == "__main__":
    unittest.main()
