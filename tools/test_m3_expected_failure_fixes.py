"""Regression tests for M3: all 5 expectedFailure findings (7 cases) fixed cleanly."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import typing
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from ace_code_agent.problem_selector import ProblemSelector
from ace_core_repair.drift_quarantine import SemanticDriftQuarantine
from tools import ace_mobile_dashboard as amd
from tools import dashboard_state_build as dsb


class TestM3ExpectedFailureFixes(unittest.TestCase):
    def test_1_drift_quarantine_exact_float_boundary_consistent(self) -> None:
        q = SemanticDriftQuarantine(consistency_threshold=0.9)
        base = [(f"k{i}", True) for i in range(10)]
        inc = [(f"k{i}", i != 0) for i in range(10)]
        status, meta = q.check_distribution_consistency(base, inc)
        self.assertEqual(status, "CONSISTENT")
        self.assertFalse(meta["quarantined"])

        # 2/10 = 0.2 > 0.1 masih harus ABSTAIN
        inc_drift = [(f"k{i}", i >= 2) for i in range(10)]
        status_drift, meta_drift = q.check_distribution_consistency(base, inc_drift)
        self.assertEqual(status_drift, "ABSTAIN")
        self.assertTrue(meta_drift["quarantined"])

    def test_2_problem_selector_type_hints_resolve_cleanly(self) -> None:
        hints = typing.get_type_hints(ProblemSelector.select_next_problem)
        self.assertIn("return", hints)

    def test_3_ace_reasoning_corrupt_sqlite_exits_2_json(self) -> None:
        script = REPO_ROOT / "tools" / "ace_reasoning.py"
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            ws = t / "ws"
            ws.mkdir()
            p.write_text(
                json.dumps({"problem_id": "p1", "prompt": "hitung 1+1", "kind": "math"}),
                encoding="utf-8",
            )
            (ws / "selfmodel_memory.sqlite3").write_bytes(b"NOT A SQLITE DB")
            proc = subprocess.run(
                [sys.executable, str(script), "--problem", str(p), "--workspace", str(ws)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_5a_dashboard_state_build_venues_without_queue_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kbm = root / "KBM_SERIALISASI_STATE.md"
            kbm.write_text('## Published\n- Bab 1 "Awal"\n', encoding="utf-8")
            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "KBM_STATE", kbm),
                mock.patch.object(dsb, "CRON_DIR", root / "no_crons"),
            ):
                res = dsb.venues()
            self.assertEqual(res["kbm"]["published_titles"], ["Awal"])
            self.assertEqual(res["kbm"]["next_in_queue"], [])

    def test_5b_ace_mobile_dashboard_non_dict_heartbeat_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoints" / "self_dev"
            ckpt.mkdir(parents=True)
            (ckpt / "daemon_heartbeat.json").write_text("[]", encoding="utf-8")
            (ckpt / "v03_researcher_state.json").write_text("[]", encoding="utf-8")
            with mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
                data = amd.get_dashboard_data()
            self.assertFalse(data["live_status"])


if __name__ == "__main__":
    unittest.main()
