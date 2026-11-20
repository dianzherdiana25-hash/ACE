"""Tes penunjuk origin_commit pada --claims successor_inventory (AG9)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.successor_inventory import main


class SuccessorClaimsOriginCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.snapshot = root / "snapshot"
        self.out = root / "out"
        self.claims = root / "claims.json"
        self.repo.mkdir()
        self.snapshot.mkdir()
        self._git("init", "-q")

        self.evidence = self.repo / "s0006-proof.md"
        self.v1_bytes = b"versi-lama-terverifikasi\n"
        self.v1_sha = hashlib.sha256(self.v1_bytes).hexdigest()
        self.evidence.write_bytes(self.v1_bytes)
        self._git("add", self.evidence.name)
        self._git(
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "commit v1",
        )
        self.commit_v1 = self._git_out("rev-parse", "HEAD")

        # Versi 2 menimpa berkas bukti dengan isi baru.
        self.v2_bytes = b"versi-baru-berubah\n"
        self.v2_sha = hashlib.sha256(self.v2_bytes).hexdigest()
        self.evidence.write_bytes(self.v2_bytes)
        self._git("add", self.evidence.name)
        self._git(
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "commit v2",
        )
        self.commit_v2 = self._git_out("rev-parse", "HEAD")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def _git_out(self, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def test_origin_commit_match_vs_older_version_mismatch(self) -> None:
        # Siapkan relokasi dari bukti v1 ke file relocated_v1.md agar v1 juga bisa diuji via relokasi.
        (self.repo / "relocated_v1.md").write_bytes(self.v1_bytes)

        claims = [
            # 1. Klaim sah langsung menunjuk commit_v1 + sha256 v1 -> cocok pada origin_commit.
            {
                "id": "valid-at-v1",
                "evidence": self.evidence.name,
                "status": "teruji",
                "origin_commit": self.commit_v1,
                "sha256": self.v1_sha,
            },
            # 2. Klaim menunjuk origin_commit=commit_v2 padahal sha256 miliknya cocok versi lama (commit_v1)!
            {
                "id": "stale-pointer-claims-v2-matches-v1",
                "evidence": self.evidence.name,
                "status": "teruji",
                "origin_commit": self.commit_v2,
                "sha256": self.v1_sha,
            },
            # 3. Klaim relokasi sah menunjuk origin_commit=commit_v1.
            {
                "id": "relocated-valid-v1",
                "evidence": self.evidence.name,
                "status": "belum",
                "relocated_to": "relocated_v1.md",
                "origin_commit": self.commit_v1,
                "sha256": self.v1_sha,
            },
        ]
        self.claims.write_text(json.dumps(claims), encoding="utf-8")

        rc = main(
            [
                "--repo",
                str(self.repo),
                "--snapshot",
                str(self.snapshot),
                "--output-dir",
                str(self.out),
                "--claims",
                str(self.claims),
            ]
        )
        self.assertEqual(rc, 0)
        claims_report = json.loads((self.out / "inventory.json").read_bytes())["claims"]

        verified_ids = {item["id"]: item for item in claims_report["origin_commit_verified"]}
        self.assertEqual(set(verified_ids), {"valid-at-v1", "relocated-valid-v1"})
        self.assertEqual(verified_ids["valid-at-v1"]["git_origin"]["state"], "match")
        self.assertEqual(verified_ids["valid-at-v1"]["origin_commit"], self.commit_v1)

        unverified = claims_report["origin_commit_unverified"]
        self.assertEqual([item["id"] for item in unverified], ["stale-pointer-claims-v2-matches-v1"])
        mismatch_item = unverified[0]
        self.assertEqual(mismatch_item["reason"], "mismatch_matched_older_version")
        self.assertEqual(mismatch_item["git_origin"]["state"], "mismatch_matched_older_version")
        self.assertEqual(mismatch_item["git_origin"]["commit"], self.commit_v2)
        self.assertEqual(mismatch_item["git_origin"]["sha256"], self.v2_sha)
        self.assertEqual(mismatch_item["git_origin"]["matched_older_commit"], self.commit_v1)
        self.assertEqual(
            [row["id"] for row in claims_report["missing_evidence"]],
            ["stale-pointer-claims-v2-matches-v1"],
        )


if __name__ == "__main__":
    unittest.main()
