#!/usr/bin/env python3
"""Unit tests untuk tools/opportunity_register.py (WS-G #19)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import opportunity_register


class TestOpportunityRegisterTool(unittest.TestCase):
    def test_generates_jsonl_proposals_with_origin_and_excludes_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            assets_file = tmp_path / "assets.json"
            assets_file.write_text(
                json.dumps(
                    {
                        "venue_kbm": {"kind": "venue", "name": "KBM App", "status": "active"},
                        "venue_threads": {"kind": "venue", "name": "Threads", "status": "active"},
                        "cap_fiction": {"kind": "capability", "name": "Serial Fiction", "status": "draft"},
                    }
                ),
                encoding="utf-8",
            )
            reg_file = tmp_path / "register.jsonl"
            reg_file.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "combination": ["venue_kbm", "venue_threads"],
                        "origin": "FOUNDER",
                        "status": "design",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            out_jsonl = tmp_path / "proposals.jsonl"
            summary_out = tmp_path / "summary.json"

            rc = opportunity_register.main(
                [
                    "--assets-file",
                    str(assets_file),
                    "--register-file",
                    str(reg_file),
                    "--out-jsonl",
                    str(out_jsonl),
                    "--summary-out",
                    str(summary_out),
                ]
            )
            self.assertEqual(rc, 0)

            rows = [
                json.loads(line)
                for line in out_jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            # (venue_kbm, venue_threads) sudah tercatat sehingga hanya tersisa 2 kombinasi baru
            self.assertEqual(len(rows), 2)
            combos = {tuple(r["combination"]) for r in rows}
            self.assertNotIn(("venue_kbm", "venue_threads"), combos)
            self.assertIn(("cap_fiction", "venue_kbm"), combos)
            self.assertIn(("cap_fiction", "venue_threads"), combos)

            for row in rows:
                self.assertEqual(row["schema"], "ace.opportunity-register.v1")
                self.assertEqual(row["origin_attribution"], "ACE-origin")
                self.assertIs(row["claim_made"], False)
                self.assertIs(row["requires_human_validation"], True)
                self.assertEqual(row["status"], "proposal_only")

            summary = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertEqual(summary["existing_by_origin"], {"ACE-origin": 0, "human-origin": 1})
            self.assertEqual(summary["proposal_by_origin"], {"ACE-origin": 2, "human-origin": 0})
            self.assertIs(summary["claim_made"], False)

    def test_repo_scan_and_invalid_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "tools").mkdir()
            (tmp_path / "tools" / "alpha_tool.py").write_text("print(1)\n", encoding="utf-8")
            (tmp_path / "docs").mkdir()
            (tmp_path / "docs" / "playbook.md").write_text("# guide\n", encoding="utf-8")

            discovered = opportunity_register.scan_repo_underused_assets(tmp_path)
            self.assertIn("tool_alpha_tool", discovered)
            self.assertIn("doc_playbook", discovered)

            props = opportunity_register.generate_proposals(
                discovered,
                origin_attribution="human-origin",
                origin_detail="owner_curation",
            )
            self.assertEqual(len(props), 1)
            self.assertEqual(props[0]["origin_attribution"], "human-origin")

            rc_bad = opportunity_register.main(["--assets-file", str(tmp_path / "missing.json")])
            self.assertEqual(rc_bad, 2)


if __name__ == "__main__":
    unittest.main()
