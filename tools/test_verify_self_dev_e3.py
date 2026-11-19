"""Tes tepi luring untuk tools/verify_self_dev.py (E3 #6, TESTS ONLY)."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import verify_self_dev as vsd  # noqa: E402


def _valid_evidence(**overrides):
    data = {
        "benchmark_id": "ACE_AUTONOMOUS_CONTINUITY_V02",
        "governance_result": {
            "release_gate": "BLOCK_RELEASE",
            "scientific_status": "NOT_ASSESSED",
            "oaie_established": False,
            "is_promoted": False,
            "active_head_id": "head_0",
        },
        "diagnosis": {"summary": "ok"},
        "hypothesis": {"statement": "h"},
        "candidate": {"author_type": "ACE_AUTONOMOUS_V02"},
        "evaluation_receipt": {
            "gain_over_parent": 0.05,
            "decision": "REJECTED",
            "candidate_id": "cand_1",
            "cost_usd": 0.0,
        },
        "proposal": {"action": "none"},
    }
    data.update(overrides)
    return data


class TestVerifySelfDevE3(unittest.TestCase):
    """Uji unit tepi untuk 4 simbol publik tools/verify_self_dev.py."""

    def test_01_compute_sha256_empty_and_binary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p_empty = Path(tmp) / "empty.bin"
            p_empty.write_bytes(b"")
            self.assertEqual(vsd.compute_sha256(p_empty), hashlib.sha256(b"").hexdigest())

            p_bin = Path(tmp) / "data.bin"
            payload = bytes(range(256))
            p_bin.write_bytes(payload)
            self.assertEqual(vsd.compute_sha256(p_bin), hashlib.sha256(payload).hexdigest())

    def test_02_verify_evidence_rejects_invalid_benchmark_and_missing_sections(self):
        ok, msg = vsd.verify_self_dev_evidence(_valid_evidence(benchmark_id="UNKNOWN_BENCH"))
        self.assertFalse(ok)
        self.assertIn("Invalid benchmark_id", msg)

        for section in ("diagnosis", "hypothesis", "candidate", "evaluation_receipt", "proposal"):
            ev = _valid_evidence()
            del ev[section]
            ok, msg = vsd.verify_self_dev_evidence(ev)
            self.assertFalse(ok)
            self.assertIn(f"Missing section '{section}'", msg)

    def test_03_verify_evidence_enforces_fail_closed_governance_flags(self):
        for field, bad_val, snippet in (
            ("release_gate", "ALLOW_RELEASE", "release_gate must be BLOCK_RELEASE"),
            ("scientific_status", "ESTABLISHED", "scientific_status must be NOT_ASSESSED"),
            ("oaie_established", 0, "oaie_established must strictly be False"),
            ("oaie_established", True, "oaie_established must strictly be False"),
            ("oaie_established", None, "oaie_established must strictly be False"),
        ):
            ev = _valid_evidence()
            ev["governance_result"][field] = bad_val
            ok, msg = vsd.verify_self_dev_evidence(ev)
            self.assertFalse(ok)
            self.assertIn(snippet, msg)

    def test_04_verify_evidence_low_gain_enforces_rejection_non_promotion_and_lineage(self):
        ev_bad_dec = _valid_evidence()
        ev_bad_dec["evaluation_receipt"]["decision"] = "PROMOTED"
        ok, msg = vsd.verify_self_dev_evidence(ev_bad_dec)
        self.assertFalse(ok)
        self.assertIn("was not REJECTED, STAGNATED, or ABSTAINED", msg)

        ev_promoted = _valid_evidence()
        ev_promoted["governance_result"]["is_promoted"] = True
        ok, msg = vsd.verify_self_dev_evidence(ev_promoted)
        self.assertFalse(ok)
        self.assertIn("marked promoted", msg)

        # Empty active_head_id + candidate_id triggers lineage collision even when REJECTED.
        ev_empty_ids = _valid_evidence()
        ev_empty_ids["governance_result"]["active_head_id"] = ""
        ev_empty_ids["evaluation_receipt"]["candidate_id"] = ""
        ok, msg = vsd.verify_self_dev_evidence(ev_empty_ids)
        self.assertFalse(ok)
        self.assertIn("Lineage corruption", msg)

    def test_05_verify_evidence_exact_gain_threshold_allows_promotion_at_015(self):
        ev = _valid_evidence()
        ev["evaluation_receipt"]["gain_over_parent"] = 0.1500
        ev["evaluation_receipt"]["decision"] = "PROMOTED"
        ev["evaluation_receipt"]["candidate_id"] = "head_1"
        ev["governance_result"]["is_promoted"] = True
        ev["governance_result"]["active_head_id"] = "head_1"
        ok, msg = vsd.verify_self_dev_evidence(ev)
        self.assertTrue(ok)
        self.assertEqual(msg, "ACE Evidence: ALL CHECKS PASSED")

    def test_06_verify_evidence_rejects_invalid_author_and_nonzero_cost(self):
        ev_author = _valid_evidence()
        ev_author["candidate"]["author_type"] = "EXTERNAL_BOT"
        ok, msg = vsd.verify_self_dev_evidence(ev_author)
        self.assertFalse(ok)
        self.assertIn("Invalid author_type", msg)

        ev_cost = _valid_evidence()
        ev_cost["evaluation_receipt"]["cost_usd"] = 0.0001
        ok, msg = vsd.verify_self_dev_evidence(ev_cost)
        self.assertFalse(ok)
        self.assertIn("Nonzero cost detected", msg)

    def test_07_verify_evidence_accepts_all_valid_benchmarks_and_authors(self):
        for bench in (
            "ACE_AUTONOMOUS_SELF_DEV_LOOP_V01",
            "ACE_AUTONOMOUS_CONTINUITY_V02",
            "ACE_AUTONOMOUS_SELF_DEV_BOOTSTRAP_V03",
        ):
            for author in ("ACE_AUTONOMOUS_V01", "ACE_AUTONOMOUS_V02", "ACE_AUTONOMOUS_V03", "GEMINI", "CODEX", "HUMAN"):
                ev = _valid_evidence(benchmark_id=bench)
                ev["candidate"]["author_type"] = author
                ok, _ = vsd.verify_self_dev_evidence(ev)
                self.assertTrue(ok)

    def test_08_continuity_missing_file_and_too_few_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "missing.json"
            ok, msg = vsd.verify_multi_cycle_continuity(Path(tmp), p)
            self.assertFalse(ok)
            self.assertIn("Research state file not found", msg)

            p.write_text(json.dumps({"completed_cycles": [{"cycle_id": 1}, {"cycle_id": 2}]}), encoding="utf-8")
            ok, msg = vsd.verify_multi_cycle_continuity(Path(tmp), p)
            self.assertFalse(ok)
            self.assertIn("Expected at least 3 completed cycles, found 2", msg)

    def test_09_continuity_detects_gap_in_cycle_sequence_and_digest_break(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(
                json.dumps(
                    {
                        "completed_cycles": [
                            {"cycle_id": 1, "state_digest": "d1"},
                            {"cycle_id": 3, "prior_digest": "d1", "state_digest": "d3"},
                            {"cycle_id": 4, "prior_digest": "d3", "state_digest": "d4"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ok, msg = vsd.verify_multi_cycle_continuity(Path(tmp), p)
            self.assertFalse(ok)
            self.assertIn("Broken cycle sequence between 1 and 3", msg)

            p.write_text(
                json.dumps(
                    {
                        "completed_cycles": [
                            {"cycle_id": 1, "state_digest": "d1"},
                            {"cycle_id": 2, "prior_digest": "TAMPERED", "state_digest": "d2"},
                            {"cycle_id": 3, "prior_digest": "d2", "state_digest": "d3"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ok, msg = vsd.verify_multi_cycle_continuity(Path(tmp), p)
            self.assertFalse(ok)
            self.assertIn("Broken state digest chaining between cycle 1 and 2", msg)

    def test_10_continuity_passes_on_valid_chained_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(
                json.dumps(
                    {
                        "completed_cycles": [
                            {"cycle_id": 1, "state_digest": "a1"},
                            {"cycle_id": 2, "prior_digest": "a1", "state_digest": "a2"},
                            {"cycle_id": 3, "prior_digest": "a2", "state_digest": "a3"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ok, msg = vsd.verify_multi_cycle_continuity(Path(tmp), p)
            self.assertTrue(ok)
            self.assertIn("confirmed across 3 cycles", msg)

    def test_11_main_fails_when_v02_prescore_missing_or_hash_mismatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            err = io.StringIO()
            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(sys, "argv", ["verify_self_dev.py"]),
                redirect_stdout(io.StringIO()),
                redirect_stderr(err),
            ):
                rc = vsd.main()
            self.assertEqual(rc, 1)
            self.assertIn("Preregistration file not found", err.getvalue())

            v02 = root / vsd.V02_PRESCORE_FILE
            v02.parent.mkdir(parents=True, exist_ok=True)
            v02.write_text("tampered content", encoding="utf-8")
            err2 = io.StringIO()
            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(sys, "argv", ["verify_self_dev.py"]),
                redirect_stdout(io.StringIO()),
                redirect_stderr(err2),
            ):
                rc2 = vsd.main()
            self.assertEqual(rc2, 1)
            self.assertIn("Pre-score hash mismatch", err2.getvalue())

    def test_12_main_fails_when_unit_tests_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v02 = root / vsd.V02_PRESCORE_FILE
            v02.parent.mkdir(parents=True, exist_ok=True)
            v02.write_bytes(b"v02")
            err = io.StringIO()
            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(vsd, "EXPECTED_V02_PRESCORE_HASH", hashlib.sha256(b"v02").hexdigest()),
                mock.patch.object(vsd.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)),
                mock.patch.object(sys, "argv", ["verify_self_dev.py"]),
                redirect_stdout(io.StringIO()),
                redirect_stderr(err),
            ):
                rc = vsd.main()
            self.assertEqual(rc, 1)
            self.assertIn("Unit tests failed", err.getvalue())

    def test_13_main_verifies_explicit_gzip_artifact_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v02 = root / vsd.V02_PRESCORE_FILE
            v02.parent.mkdir(parents=True, exist_ok=True)
            v02.write_bytes(b"v02")

            good_gz = root / "good.json.gz"
            with gzip.open(good_gz, "wt", encoding="utf-8") as gz:
                json.dump(_valid_evidence(), gz)

            bad_gz = root / "bad.json.gz"
            with gzip.open(bad_gz, "wt", encoding="utf-8") as gz:
                json.dump(_valid_evidence(benchmark_id="BAD"), gz)

            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(vsd, "EXPECTED_V02_PRESCORE_HASH", hashlib.sha256(b"v02").hexdigest()),
                mock.patch.object(vsd.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
                mock.patch.object(sys, "argv", ["verify_self_dev.py", str(good_gz)]),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(vsd.main(), 0)

            err = io.StringIO()
            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(vsd, "EXPECTED_V02_PRESCORE_HASH", hashlib.sha256(b"v02").hexdigest()),
                mock.patch.object(vsd.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
                mock.patch.object(sys, "argv", ["verify_self_dev.py", str(bad_gz)]),
                redirect_stdout(io.StringIO()),
                redirect_stderr(err),
            ):
                self.assertEqual(vsd.main(), 1)
            self.assertIn("Invalid benchmark_id", err.getvalue())

    def test_14_main_checks_v01_hash_and_passes_with_chained_state_and_no_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v01 = root / vsd.V01_PRESCORE_FILE
            v02 = root / vsd.V02_PRESCORE_FILE
            v01.parent.mkdir(parents=True, exist_ok=True)
            v01.write_bytes(b"v01")
            v02.write_bytes(b"v02")

            state = root / "checkpoints" / "self_dev" / "research_state.json"
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(
                json.dumps(
                    {
                        "completed_cycles": [
                            {"cycle_id": 1, "state_digest": "s1"},
                            {"cycle_id": 2, "prior_digest": "s1", "state_digest": "s2"},
                            {"cycle_id": 3, "prior_digest": "s2", "state_digest": "s3"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out = io.StringIO()
            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(vsd, "EXPECTED_V01_PRESCORE_HASH", hashlib.sha256(b"v01").hexdigest()),
                mock.patch.object(vsd, "EXPECTED_V02_PRESCORE_HASH", hashlib.sha256(b"v02").hexdigest()),
                mock.patch.object(vsd.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
                mock.patch.object(sys, "argv", ["verify_self_dev.py"]),
                redirect_stdout(out),
            ):
                rc = vsd.main()
            self.assertEqual(rc, 0)
            self.assertIn("Multi-cycle continuity confirmed across 3 cycles", out.getvalue())

    def test_15_main_fails_on_broken_continuity_state(self):
        # Perilaku yang dikunci sejak perbaikan F7 (2026-11-20): kontinuitas
        # yang rusak adalah kegagalan verifikasi — main() keluar non-nol,
        # bukan lagi sekadar catatan NOTE/FAIL dengan exit 0.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v02 = root / vsd.V02_PRESCORE_FILE
            v02.parent.mkdir(parents=True, exist_ok=True)
            v02.write_bytes(b"v02")
            state = root / "checkpoints" / "self_dev" / "research_state.json"
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(json.dumps({"completed_cycles": [{"cycle_id": 1}]}), encoding="utf-8")

            out, err = io.StringIO(), io.StringIO()
            with (
                mock.patch.object(vsd, "REPO_ROOT", root),
                mock.patch.object(vsd, "EXPECTED_V02_PRESCORE_HASH", hashlib.sha256(b"v02").hexdigest()),
                mock.patch.object(vsd.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
                mock.patch.object(sys, "argv", ["verify_self_dev.py"]),
                redirect_stdout(out),
                redirect_stderr(err),
            ):
                rc = vsd.main()
            self.assertEqual(rc, 1)
            self.assertIn("FAIL: Expected at least 3 completed cycles", err.getvalue())

    def test_16_live_repo_prescore_files_match_committed_sha256(self):
        v01 = ROOT / vsd.V01_PRESCORE_FILE
        v02 = ROOT / vsd.V02_PRESCORE_FILE
        self.assertTrue(v02.exists())
        self.assertEqual(vsd.compute_sha256(v02), vsd.EXPECTED_V02_PRESCORE_HASH)
        if v01.exists():
            self.assertEqual(vsd.compute_sha256(v01), vsd.EXPECTED_V01_PRESCORE_HASH)


if __name__ == "__main__":
    unittest.main()
