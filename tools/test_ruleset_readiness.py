#!/usr/bin/env python3
"""Unit tests untuk tools/ruleset_readiness.py (WS-F #18)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import ruleset_readiness


class TestRulesetReadiness(unittest.TestCase):
    def test_ready_classic_protection_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "ready.json"
            snap.write_text(
                json.dumps(
                    {
                        "repo": {"default_branch": "main"},
                        "protection": {
                            "required_pull_request_reviews": {
                                "required_approving_review_count": 1
                            },
                            "allow_force_pushes": {"enabled": False},
                            "allow_deletions": {"enabled": False},
                            "enforce_admins": {"enabled": True},
                            "required_status_checks": {"contexts": ["unit-tests"]},
                        },
                    }
                ),
                encoding="utf-8",
            )
            report = ruleset_readiness.check_repo_readiness(
                repo="dianzherdiana25-hash/ACE",
                branch="main",
                snapshot_path=snap,
            )
            self.assertEqual(report["schema"], "ace.ruleset-readiness.v1")
            self.assertIs(report["read_only"], True)
            self.assertIs(report["mutated_github_settings"], False)
            self.assertTrue(report["ready"])
            self.assertEqual(report["summary"]["required_passed"], report["summary"]["required_total"])

            md = ruleset_readiness.render_markdown(report)
            self.assertIn("**SIAP**", md)

    def test_unprotected_branch_and_mocked_gh_api_runner(self) -> None:
        def fake_runner(argv: list[str] | tuple[str, ...]) -> tuple[int, str, str]:
            endpoint = argv[-1]
            if endpoint.endswith("/protection"):
                return 1, "", "HTTP 404: Branch not protected"
            if endpoint.startswith("repos/owner/repo/rules/branches/"):
                return (
                    0,
                    json.dumps(
                        [
                            {"type": "deletion"},
                            {"type": "non_fast_forward"},
                            {
                                "type": "pull_request",
                                "parameters": {"required_approving_review_count": 0},
                            },
                        ]
                    ),
                    "",
                )
            return 0, json.dumps({"default_branch": "main"}), ""

        report = ruleset_readiness.check_repo_readiness(
            repo="owner/repo",
            branch="main",
            runner=fake_runner,
        )
        self.assertFalse(report["ready"])
        checks = {c["id"]: c for c in report["checks"]}
        self.assertTrue(checks["disallow_force_pushes"]["passed"])
        self.assertTrue(checks["pull_request_required"]["passed"])
        self.assertFalse(checks["approving_review_minimum"]["passed"])

        with tempfile.TemporaryDirectory() as tmp:
            bad_snap = Path(tmp) / "unready.json"
            bad_snap.write_text(json.dumps({"protection": None, "branch_rules": []}), encoding="utf-8")
            rc = ruleset_readiness.main(
                ["--snapshot", str(bad_snap), "--fail-if-unready", "--format", "md"]
            )
            self.assertEqual(rc, 1)

            rc_missing = ruleset_readiness.main(["--snapshot", str(Path(tmp) / "missing.json")])
            self.assertEqual(rc_missing, 2)


if __name__ == "__main__":
    unittest.main()
