"""Fixture kecil memeriksa audit dan memastikan workspace tidak berubah."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.writeback_diagnose import diagnose

from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.memory_writeback import record_verified_event
from ace_operational.store import OperationalStore


def _hash_tree(root: Path) -> dict[str, str | None]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        if path.is_file() else None
        for path in root.rglob("*")
    }


class WritebackDiagnoseTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="ace-diagnose-tests-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / "workspace"
        self.script = Path(__file__).with_name("writeback_diagnose.py")

    def _run_cli(self, workspace: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), "--workspace", str(workspace), *extra],
            env={**os.environ, "TMPDIR": str(workspace)},
            capture_output=True, text=True, timeout=15,
        )

    def test_report_matches_workspace_and_leaves_wal_snapshot_byte_identical(self):
        with OperationalStore(self.workspace) as store:
            for kind, passed in (("compile", True), ("compile", False), ("check", True)):
                store.record_receipt(
                    task_id="task-fixture", action_kind=kind, input_data=b"", output_data=b"",
                    command_or_operation="fixture", exit_code=0 if passed else 1, passed=passed,
                )
            for tool, error in (
                ("parser", "syntax"), ("parser", "syntax"), ("parser", "runtime"),
                ("format", "style"), ("closed-gap", "other"),
            ):
                gap, _ = store.record_gap(
                    source_task_id="task-fixture", error_type=error, missing_skill_or_tool=tool,
                    description_id="fixture",
                )
                if tool == "closed-gap":
                    store.update_gap(gap["gap_id"], status="RESOLVED")
            store.save_skill(
                name="fixture-skill", domain="fixture", preconditions=[],
                boundary_limitations=[], procedure_steps=[], verification_template={},
                source_task_ids=["task-fixture"],
            )
            store.set_frontier_capability(
                capability_id="fixture-cap", name_id="Fixture", status="RETEST_REQUIRED",
            )

            memory_root = self.workspace / "cognitive_memory"
            self.assertIsNotNone(record_verified_event(
                memory_root, event="skill_verified", summary="Fixture",
                evidence_bytes=b"fixture verified",
            ))
            CognitiveMemory(memory_root).remember(
                kind="semantic", content={"note": "Fixture tanpa kelas"},
                source_kind="operator",
            )

            # Simulate a snapshot containing committed WAL pages but no SHM.
            snapshot = self.root / "snapshot dengan spasi"
            (snapshot / "cognitive_memory").mkdir(parents=True)
            for name in ("ace_operational.sqlite3", "ace_operational.sqlite3-wal",
                         "cognitive_memory/memory.jsonl"):
                shutil.copyfile(self.workspace / name, snapshot / name)
            before = _hash_tree(snapshot)
            proc = self._run_cli(snapshot, "--gap-limit", "1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(_hash_tree(snapshot), before)

        report = json.loads(proc.stdout)
        self.assertEqual(report["cognitive_memory"], {
            "available": True, "chain_ok": True, "events": 3, "anchored_evidence": 1,
            "records_by_class": {"skill_verified": 1, "unclassified": 1},
            "records_by_source_kind": {"evidence": 1, "operator": 1},
        })
        self.assertEqual(report["receipts_by_action_kind"], {
            "check": {"passed": 1, "failed": 0}, "compile": {"passed": 1, "failed": 1},
        })
        self.assertEqual(report["top_open_gaps"], [
            {"missing_skill_or_tool": "parser", "occurrence_count": 3},
        ])
        self.assertEqual(report["skills"], {"total": 1, "by_status": {"ACTIVE": 1}})
        self.assertEqual(report["frontier"]["by_status"]["RETEST_REQUIRED"], 1)

    def test_absent_memory_is_explicit_and_does_not_initialize(self):
        with OperationalStore(self.workspace):
            pass
        before = _hash_tree(self.workspace)
        proc = self._run_cli(self.workspace)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)["cognitive_memory"]
        self.assertFalse(report["available"])
        self.assertIsNone(report["chain_ok"])
        self.assertEqual(_hash_tree(self.workspace), before)

    def test_tampered_hash_is_reported_without_repairing_log(self):
        with OperationalStore(self.workspace):
            pass
        memory = CognitiveMemory(self.workspace / "cognitive_memory")
        memory.anchor_evidence(b"fixture")
        entry = json.loads(memory.log_path.read_text(encoding="utf-8"))
        entry["hash"] = "0" * 64
        memory.log_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        before = _hash_tree(self.workspace)
        proc = self._run_cli(self.workspace)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertFalse(json.loads(proc.stdout)["cognitive_memory"]["chain_ok"])
        self.assertEqual(_hash_tree(self.workspace), before)

    def test_changes_during_snapshot_are_rejected(self):
        with OperationalStore(self.workspace):
            pass
        memory = CognitiveMemory(self.workspace / "cognitive_memory")
        real_copy = shutil.copyfile

        def change_source(src: Path, dst: Path):
            result = real_copy(src, dst)
            if src == memory.log_path:
                memory.anchor_evidence(b"synthetic writer appended during copy")
            return result

        with patch("tools.writeback_diagnose.shutil.copyfile", side_effect=change_source):
            with self.assertRaisesRegex(ValueError, "sumber berubah"):
                diagnose(self.workspace)

    def test_missing_database_does_not_create_a_database(self):
        self.workspace.mkdir()
        proc = self._run_cli(self.workspace)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("Database ace_operational.sqlite3 tidak ditemukan", proc.stderr)
        self.assertEqual(_hash_tree(self.workspace), {})


if __name__ == "__main__":
    unittest.main()
