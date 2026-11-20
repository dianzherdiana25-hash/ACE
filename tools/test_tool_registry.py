"""Tes manifes registry tiga perkakas dengan nasib berbeda (AG82)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import tool_registry


class ToolRegistryTest(unittest.TestCase):
    def test_three_tools_with_contrasting_fates(self) -> None:
        registry = {
            "tools": [
                {
                    "name": "tool_healthy_ok",
                    "version": "1.2.0",
                    "origin_gap": "gap-csv-01",
                    "status": "adopted",
                    "registered_at": "2026-11-01T00:00:00Z",
                },
                {
                    "name": "tool_dormant_unused",
                    "version": "1.0.0",
                    "origin_gap": "gap-old-02",
                    "status": "adopted",
                    "registered_at": "2026-09-01T00:00:00Z",
                },
                {
                    "name": "tool_failing_often",
                    "version": "0.9.0",
                    "origin_gap": "gap-parse-03",
                    "status": "adopted",
                    "registered_at": "2026-11-15T00:00:00Z",
                },
            ]
        }
        usage_events = [
            {"tool": "tool_healthy_ok", "ts": "2026-11-19T10:00:00Z", "success": True},
            {"tool": "tool_healthy_ok", "ts": "2026-11-19T12:00:00Z", "success": True},
            {"tool": "tool_healthy_ok", "ts": "2026-11-20T08:00:00Z", "success": True},
            # Dormant: terakhir dipakai 50 hari lalu (> 30 hari).
            {"tool": "tool_dormant_unused", "ts": "2026-10-01T00:00:00Z", "success": True},
            # Gagal berulang: 3 dari 4 panggilan gagal (75% >= 50%).
            {"tool": "tool_failing_often", "ts": "2026-11-19T01:00:00Z", "success": False},
            {"tool": "tool_failing_often", "ts": "2026-11-19T02:00:00Z", "success": False},
            {"tool": "tool_failing_often", "ts": "2026-11-19T03:00:00Z", "success": True},
            {"tool": "tool_failing_often", "ts": "2026-11-20T01:00:00Z", "success": False},
        ]

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg_path = root / "registry.json"
            log_path = root / "usage.jsonl"
            out_path = root / "eval.json"
            reg_path.write_text(json.dumps(registry), encoding="utf-8")
            log_path.write_text(
                "\n".join(json.dumps(e) for e in usage_events) + "\n", encoding="utf-8"
            )

            rc = tool_registry.main(
                [
                    "--registry",
                    str(reg_path),
                    "--usage-log",
                    str(log_path),
                    "--as-of",
                    "2026-11-20T12:00:00Z",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], tool_registry.SCHEMA)
        self.assertEqual(rep["summary"]["keep_active"], ["tool_healthy_ok"])
        self.assertEqual(
            rep["summary"]["retire_candidates"],
            ["tool_dormant_unused", "tool_failing_often"],
        )

        by_name = {t["name"]: t for t in rep["tools"]}
        self.assertEqual(by_name["tool_healthy_ok"]["recommendation"], "keep_active")
        self.assertEqual(by_name["tool_dormant_unused"]["recommendation"], "retire_candidate")
        self.assertTrue(any("unused_past_threshold" in r for r in by_name["tool_dormant_unused"]["reasons"]))
        self.assertEqual(by_name["tool_failing_often"]["recommendation"], "retire_candidate")
        self.assertTrue(any("repeated_failures" in r for r in by_name["tool_failing_often"]["reasons"]))


if __name__ == "__main__":
    unittest.main()
