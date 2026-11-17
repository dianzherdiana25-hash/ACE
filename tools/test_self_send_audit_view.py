#!/usr/bin/env python3
"""Unit tests untuk tools/self_send_audit_view.py (WS-F #17)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import self_send_audit_view


def _row(
    *,
    ts: str,
    trigger: str,
    branch: str,
    digest: str,
    files: list[str],
    pr_number: int | None,
    outcome: str,
) -> str:
    return json.dumps(
        {
            "ts": ts,
            "trigger": trigger,
            "branch": branch,
            "basis": "abc1234",
            "content_digest": digest,
            "files": files,
            "pr_number": pr_number,
            "outcome": outcome,
        }
    )


class TestSelfSendAuditView(unittest.TestCase):
    def test_clean_audit_chain_summarized_accurately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "self_send_audit.jsonl"
            lines = [
                _row(
                    ts="2026-11-16",
                    trigger="ratification_flush",
                    branch="",
                    digest="d1",
                    files=["evidence/a.json"],
                    pr_number=None,
                    outcome="refused:marker_absent",
                ),
                _row(
                    ts="2026-11-17",
                    trigger="manual_cli",
                    branch="ace-auto/20261117-test",
                    digest="d2",
                    files=["handover/note.md"],
                    pr_number=None,
                    outcome="prepared",
                ),
                _row(
                    ts="2026-11-17",
                    trigger="manual_cli",
                    branch="ace-auto/20261117-test",
                    digest="d2",
                    files=["handover/note.md"],
                    pr_number=242,
                    outcome="sent",
                ),
            ]
            audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            report = self_send_audit_view.inspect_audit_files([audit_path])
            s = report["summary"]
            self.assertEqual(report["schema"], "ace.self-send-audit-view.v1")
            self.assertIs(report["read_only"], True)
            self.assertEqual(s["total_rows"], 3)
            self.assertEqual(s["delivered_count"], 1)
            self.assertEqual(s["prepared_count"], 1)
            self.assertEqual(s["refused_count"], 1)
            self.assertEqual(s["anomaly_count"], 0)
            self.assertEqual(s["unique_prs"], [242])
            self.assertEqual(report["refusal_reasons"], {"marker_absent": 1})

            md = self_send_audit_view.render_markdown(report)
            self.assertIn("PR #242", md)
            self.assertIn("marker_absent", md)

    def test_detects_anomalies_and_strict_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            lines = [
                "{broken json",
                _row(
                    ts="2026-11-18",
                    trigger="manual_cli",
                    branch="main",
                    digest="d3",
                    files=["handover/x.md"],
                    pr_number=None,
                    outcome="prepared",
                ),
                _row(
                    ts="2026-11-17",
                    trigger="manual_cli",
                    branch="ace-auto/20261117-dup",
                    digest="d4",
                    files=["handover/y.md"],
                    pr_number=250,
                    outcome="sent",
                ),
                _row(
                    ts="2026-11-17",
                    trigger="manual_cli",
                    branch="ace-auto/20261117-dup",
                    digest="d4",
                    files=["handover/y.md"],
                    pr_number=250,
                    outcome="sent",
                ),
            ]
            audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            report = self_send_audit_view.inspect_audit_files([audit_path])
            kinds = {a["kind"] for a in report["anomalies"]}
            self.assertIn("malformed_json", kinds)
            self.assertIn("unexpected_branch_namespace", kinds)
            self.assertIn("non_monotonic_timestamp", kinds)
            self.assertIn("unclosed_prepared_row", kinds)
            self.assertIn("duplicate_delivered_send", kinds)

            rc_strict = self_send_audit_view.main(["--audit-file", str(audit_path), "--strict", "--format", "md"])
            self.assertEqual(rc_strict, 1)

            rc_missing = self_send_audit_view.main(["--audit-file", str(Path(tmp) / "nope.jsonl")])
            self.assertEqual(rc_missing, 2)


if __name__ == "__main__":
    unittest.main()
