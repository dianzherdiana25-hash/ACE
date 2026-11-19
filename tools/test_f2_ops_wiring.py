"""Tes integrasi wiring F2: daily_digest & repo_status_dashboard <-> 7+ perkakas aman."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import daily_digest, repo_status_dashboard as rsd


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _seed_git_repo(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "handover").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Tester")
    _git(root, "config", "user.email", "tester@example.com")
    (root / "docs" / "EVO_0007_NOTE.md").write_text("# Evo 0007 Uji\nG0: PASS\n", encoding="utf-8")
    (root / "tools" / "sample_mod.py").write_text('"""Sampel."""\nX = 1\n', encoding="utf-8")
    _git(root, "add", "docs/EVO_0007_NOTE.md", "tools/sample_mod.py")
    _git(root, "commit", "-m", "init repo")
    # File untracked agar storage_debt terbaca dinamis (1 berkas)
    (root / "draft.txt").write_text("hello-debt", encoding="utf-8")


def _seed_fixtures(base: Path) -> dict[str, Path]:
    stage_dir = base / "stage_box"
    stage_dir.mkdir(parents=True, exist_ok=True)
    artifact = stage_dir / "artifact.txt"
    payload = b"staged-ok"
    artifact.write_bytes(payload)
    manifest = stage_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "artifact.txt",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    csv_path = base / "royalty.csv"
    csv_path.write_text(
        "serial,date,amount,currency,units\n"
        "seria,2026-11-10,12500.50,IDR,3\n"
        "seria,2026-11-12,2499.50,IDR,1\n",
        encoding="utf-8",
    )

    catalog = base / "schedule.json"
    catalog.write_text(
        json.dumps(
            {
                "default_start_date": "2026-11-01",
                "as_of": "2026-11-17",
                "serials": [
                    {
                        "id": "seria",
                        "title": "Seri Uji <A>",
                        "total_chapters": 5,
                        "weekly_target": 2,
                        "completed_chapters": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    ruleset_snap = base / "ruleset.json"
    ruleset_snap.write_text(
        json.dumps(
            {
                "repo_full_name": "dianzherdiana25-hash/ACE",
                "branch": "main",
                "repo": {"default_branch": "main"},
                "protection": {
                    "required_pull_request_reviews": {"required_approving_review_count": 1},
                    "allow_force_pushes": {"enabled": False},
                    "allow_deletions": {"enabled": False},
                    "enforce_admins": {"enabled": True},
                    "required_status_checks": {"contexts": ["test"]},
                },
            }
        ),
        encoding="utf-8",
    )

    audit_log = base / "self_send_audit.jsonl"
    audit_log.write_text(
        json.dumps({"ts": "2026-11-18T10:00:00Z", "trigger": "auto", "branch": "ace-auto/demo", "outcome": "sent", "content_digest": "abc123"}) + "\n",
        encoding="utf-8",
    )

    return {
        "stage_dir": stage_dir,
        "manifest": manifest,
        "csv": csv_path,
        "catalog": catalog,
        "ruleset": ruleset_snap,
        "audit": audit_log,
    }


class TestF2OpsWiring(unittest.TestCase):
    def test_daily_digest_auto_all_and_live_tool_wiring_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            _seed_git_repo(repo)
            fx = _seed_fixtures(base)
            out_json = base / "digest.json"
            out_md = base / "digest.md"

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("No network allowed")):
                rc = daily_digest.main(
                    [
                        "--repo-dir",
                        str(repo),
                        "--date",
                        "2026-11-19",
                        "--auto-all",
                        "--stage-dir",
                        str(fx["stage_dir"]),
                        "--stage-manifest",
                        str(fx["manifest"]),
                        "--royalty-csv",
                        str(fx["csv"]),
                        "--schedule-catalog",
                        str(fx["catalog"]),
                        "--ruleset-snapshot",
                        str(fx["ruleset"]),
                        "--audit-file",
                        str(fx["audit"]),
                        "--out-json",
                        str(out_json),
                        "--out-md",
                        str(out_md),
                    ]
                )
            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            sig = payload["signals"]
            self.assertEqual(sig["storage_debt"]["total_debt_files"], 1)
            self.assertEqual(sig["dashboard"]["gate_count"], 1)
            self.assertEqual(sig["repo_index"]["module_count"], 1)
            self.assertTrue(sig["stage"]["ok"])
            self.assertEqual(sig["royalty"]["totals_by_currency"]["IDR"], "15000.00")
            self.assertEqual(sig["schedule"]["completed"], 2)
            self.assertTrue(sig["ruleset_readiness"]["ready"])
            self.assertEqual(sig["self_send_audit"]["delivered_count"], 1)

            md = out_md.read_text(encoding="utf-8")
            self.assertIn("repo_index", md)
            self.assertIn("ruleset_readiness", md)
            self.assertIn("self_send_audit", md)

    def test_repo_status_dashboard_live_wiring_and_conflict_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            _seed_git_repo(repo)
            fx = _seed_fixtures(base)
            out_html = base / "dash.html"

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("No network allowed")):
                rc = rsd.main(
                    [
                        "--root",
                        str(repo),
                        "--auto-storage-debt",
                        "--auto-repo-index",
                        "--stage-dir",
                        str(fx["stage_dir"]),
                        "--stage-manifest",
                        str(fx["manifest"]),
                        "--royalty-csv",
                        str(fx["csv"]),
                        "--schedule-catalog",
                        str(fx["catalog"]),
                        "--ruleset-snapshot",
                        str(fx["ruleset"]),
                        "--audit-file",
                        str(fx["audit"]),
                        "--output",
                        str(out_html),
                    ]
                )
            self.assertEqual(rc, 0)
            html_text = out_html.read_text(encoding="utf-8")
            self.assertIn("15000.00", html_text)
            self.assertIn("Seri Uji &lt;A&gt;", html_text)
            self.assertIn("sec-ruleset", html_text)
            self.assertIn("sec-repo-index", html_text)
            self.assertIn("sec-self-send-audit", html_text)
            self.assertIn('<div class="v" id="stat-storage-debt">1</div>', html_text)
            self.assertNotIn("https://", html_text)
            self.assertNotIn("http://", html_text)

            # Konflik flag --stage-file + --stage-dir ditolak fail-closed
            with self.assertRaises(ValueError):
                rsd.collect_repo_status(repo, stage_file=fx["manifest"], stage_dir=fx["stage_dir"])

            # Missing ruleset snapshot gagal rapi dengan exit code 2
            rc_bad = rsd.main(["--root", str(repo), "--ruleset-snapshot", str(base / "missing.json")])
            self.assertEqual(rc_bad, 2)

            rc_bad_digest = daily_digest.main(["--repo-dir", str(repo), "--ruleset-snapshot", str(base / "missing.json")])
            self.assertEqual(rc_bad_digest, 2)


if __name__ == "__main__":
    unittest.main()
