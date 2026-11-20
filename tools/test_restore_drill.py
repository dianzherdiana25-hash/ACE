"""Tes alat latihan pemulihan rumah ACE mode fixture dan kunci mode live (AG36)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.restore_drill import SCHEMA, main, run_fixture_restore_drill


SCRIPT = Path(__file__).with_name("restore_drill.py")


def _canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class RestoreDrillTests(unittest.TestCase):
    def _seed_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        repo_src = root / "src_repo"
        repo_src.mkdir()
        subprocess.run(["git", "-C", str(repo_src), "init", "-q"], check=True, capture_output=True)
        (repo_src / "README.md").write_text("# Fixture Repo\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo_src), "add", "README.md"], check=True, capture_output=True)
        subprocess.run(
            [
                "git", "-C", str(repo_src),
                "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false",
                "commit", "-q", "-m", "init",
            ],
            check=True,
            capture_output=True,
        )

        custody = root / "src_custody"
        (custody / "memory").mkdir(parents=True)
        # Rantai hash memory valid 2 baris
        prev = "GENESIS"
        mem_lines = []
        for seq, ev in enumerate(
            [
                {"type": "anchor", "digest": "a" * 64},
                {"type": "record", "record": {"id": "mem_1", "kind": "semantic", "content": {"k": "v"}}},
            ],
            1,
        ):
            h = hashlib.sha256(_canon({"prev": prev, "event": ev}).encode("utf-8")).hexdigest()
            mem_lines.append(_canon({"seq": seq, "prev": prev, "event": ev, "hash": h}))
            prev = h
        mem_file = custody / "memory" / "memory.jsonl"
        mem_file.write_text("\n".join(mem_lines) + "\n", encoding="utf-8")
        cfg_file = custody / "house_state.json"
        cfg_file.write_text('{"home":"fixture"}\n', encoding="utf-8")

        manifest = root / "custody_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "path": "memory/memory.jsonl",
                            "sha256": hashlib.sha256(mem_file.read_bytes()).hexdigest(),
                        },
                        {
                            "path": "house_state.json",
                            "sha256": hashlib.sha256(cfg_file.read_bytes()).hexdigest(),
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        return repo_src, custody, manifest

    def test_fixture_drill_restores_verifies_custody_hashes_and_memory_chain(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_src, custody, manifest = self._seed_fixture(root)
            target = root / "restored_home"

            report = run_fixture_restore_drill(
                repo_source=repo_src,
                custody_dir=custody,
                manifest_path=manifest,
                target_dir=target,
            )
            self.assertEqual(report["schema"], SCHEMA)
            self.assertTrue(report["all_passed"], report)
            self.assertEqual(
                [p["phase"] for p in report["phases"]],
                ["clone_repo", "restore_custody", "verify_custody_hashes", "verify_memory_chain"],
            )
            for phase in report["phases"]:
                self.assertTrue(phase["ok"])
                self.assertIsInstance(phase["elapsed_ms"], float)
            self.assertEqual(report["phases"][3]["detail"]["events_verified"], 2)
            self.assertTrue((target / "repo" / "README.md").is_file())
            self.assertTrue((target / "custody" / "house_state.json").is_file())

    def test_live_mode_without_execute_does_nothing_and_returns_zero(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "should_not_exist"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--mode", "live", "--target", str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertFalse(out["executed"])
            self.assertEqual(out["status"], "dry_run_no_execute")
            self.assertFalse(target.exists())

    def test_tampered_custody_chain_detected_in_drill(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_src, custody, manifest = self._seed_fixture(root)
            # Rusak isi baris memory setelah manifest dibuat -> hash & chain gagal
            (custody / "memory" / "memory.jsonl").write_text('{"seq":1,"prev":"GENESIS","hash":"bad"}\n', encoding="utf-8")
            target = root / "restored_tampered"
            code = main([
                "--mode", "fixture",
                "--repo", str(repo_src),
                "--custody", str(custody),
                "--manifest", str(manifest),
                "--target", str(target),
            ])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
