"""Tes tepi luring untuk tools/repair_v2_probe.py (E3 #10, TESTS ONLY)."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "code"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import repair_v2_probe as probe  # noqa: E402

_OLD = b"frozen-old-bytes"
_REPORT = {
    "arms": ["a", "b"],
    "arm_summaries": {"a": {"nominal_terminal_verified": 3}, "b": {"nominal_terminal_verified": 5}},
    "hypotheses": {"H1": {"passed": True}, "H2": {"passed": False}},
    "evidence_flags": {"SCIENTIFIC_CAPABILITY_VALIDATED": False},
    "final_ace_state": {"runtime_implementation_sha256": "rt-sha"},
}


class TestRepairV2ProbeE3(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "evidence" / "repair").mkdir(parents=True)
        (self.root / "evidence" / "repair" / "ace_repair_v1.json.gz").write_bytes(_OLD)
        self.out = self.root / "out" / "v2.json.gz"

    def tearDown(self):
        self._tmp.cleanup()

    def _patches(self, report=None, old_blob=None, replay_same=False):
        report = report if report is not None else _REPORT
        blob = old_blob or probe.git_blob(_OLD)
        hist = json.loads(json.dumps(report)) if replay_same else {"different": True}
        return [
            mock.patch.object(probe, "ROOT", self.root),
            mock.patch.object(probe, "V1_BLOB", blob),
            mock.patch.object(
                probe, "verify_report_bytes",
                side_effect=lambda data, repo_root=None, replay=False: {
                    "status": "STRUCTURE_OK", "canonical_json_sha256": "old-canon"},
            ),
            mock.patch("ace_research_repair.runner.decompress_gzip", return_value=json.dumps(hist).encode()),
            mock.patch.object(probe, "run_benchmark", return_value=report),
            mock.patch.object(probe, "compress_deterministic_gzip", return_value=b"gz-bytes"),
            mock.patch.object(probe, "_first_difference_paths", return_value=["/x"]),
        ]

    def _run(self, **kw):
        ps = self._patches(**kw)
        for p in ps:
            p.start()
        try:
            return probe.generate(self.out)
        finally:
            for p in reversed(ps):
                p.stop()

    def test_01_git_blob_matches_git_hash_object_format(self):
        self.assertEqual(probe.git_blob(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        data = b"hello\n"
        self.assertEqual(
            probe.git_blob(data),
            hashlib.sha1(b"blob 6\0hello\n").hexdigest(),
        )

    def test_02_git_blob_handles_binary_and_unicode_bytes(self):
        data = bytes(range(256)) + "é".encode("utf-8")
        expected = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        self.assertEqual(probe.git_blob(data), expected)

    def test_03_generate_writes_output_and_fail_closed_flags(self):
        r = self._run()
        self.assertEqual(self.out.read_bytes(), b"gz-bytes")
        self.assertEqual(r["schema"], "ace.repair.v2.public-candidate")
        self.assertEqual(r["release_gate"], "BLOCK_RELEASE")
        self.assertEqual(r["scientific_decision"], "NOT_ASSESSED")
        self.assertFalse(r["candidate_deployed"])
        self.assertTrue(r["public_engineering_receipt_only"])
        self.assertFalse(r["candidate_v2_scientific_validation"])

    def test_04_generate_summarizes_arms_and_hypotheses(self):
        r = self._run()
        self.assertEqual(r["candidate_v2_nominal_verified"], {"a": 3, "b": 5})
        self.assertEqual(r["candidate_v2_hypotheses"], {"H1": True, "H2": False})
        self.assertEqual(r["candidate_v2_runtime_implementation_sha256"], "rt-sha")
        self.assertEqual(r["changed_json_pointers_sample"], ["/x"])

    def test_05_generate_reports_gzip_sizes_and_digests(self):
        r = self._run()
        self.assertEqual(r["candidate_v2_gzip_bytes"], len(b"gz-bytes"))
        self.assertEqual(r["candidate_v2_sha256"], hashlib.sha256(b"gz-bytes").hexdigest())
        self.assertEqual(r["historical_v1_canonical_sha256"], "old-canon")
        self.assertEqual(r["historical_v1_structure_verified"], "STRUCTURE_OK")

    def test_06_generate_replay_flag_true_only_when_reports_equal(self):
        self.assertFalse(self._run(replay_same=False)["historical_v1_replay_matches_current"])
        self.assertTrue(self._run(replay_same=True)["historical_v1_replay_matches_current"])

    def test_07_generate_rejects_changed_frozen_v1_blob_without_writing(self):
        with self.assertRaisesRegex(ValueError, "frozen historical repair v1 blob changed"):
            self._run(old_blob="0" * 40)
        self.assertFalse(self.out.exists())

    def test_08_generate_missing_v1_file_raises_oserror(self):
        (self.root / "evidence" / "repair" / "ace_repair_v1.json.gz").unlink()
        with self.assertRaises(OSError):
            self._run()

    def test_09_generate_missing_report_key_raises_keyerror(self):
        bad = {k: v for k, v in _REPORT.items() if k != "hypotheses"}
        with self.assertRaises(KeyError):
            self._run(report=bad)

    def test_10_generate_creates_nested_output_parent(self):
        self.out = self.root / "a" / "b" / "c" / "v2.json.gz"
        self._run()
        self.assertTrue(self.out.exists())

    def test_11_main_prints_sorted_json_and_returns_zero(self):
        buf = io.StringIO()
        with (
            mock.patch.object(probe, "generate", return_value={"z": 1, "a": 2}),
            mock.patch.object(sys, "argv", ["probe", "--output", str(self.out)]),
            redirect_stdout(buf),
        ):
            rc = probe.main()
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), '{"a": 2, "z": 1}')

    def test_12_main_halts_with_exit_2_on_handled_errors(self):
        for exc in (OSError("io"), ValueError("val"), KeyError("k"), TypeError("t")):
            err = io.StringIO()
            with (
                mock.patch.object(probe, "generate", side_effect=exc),
                mock.patch.object(sys, "argv", ["probe", "--output", str(self.out)]),
                redirect_stderr(err),
                self.assertRaises(SystemExit) as ctx,
            ):
                probe.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("HALT_REPAIR_V2_DIAGNOSTIC:", err.getvalue())

    def test_13_main_does_not_swallow_unexpected_exception_types(self):
        with (
            mock.patch.object(probe, "generate", side_effect=RuntimeError("unexpected")),
            mock.patch.object(sys, "argv", ["probe", "--output", str(self.out)]),
        ):
            with self.assertRaisesRegex(RuntimeError, "unexpected"):
                probe.main()

    def test_14_main_requires_output_argument(self):
        with (
            mock.patch.object(sys, "argv", ["probe"]),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as ctx,
        ):
            probe.main()
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
