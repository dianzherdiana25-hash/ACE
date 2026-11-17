"""Edge-case unit tests for ace_host_exchange (diagnostic.py and contracts.py)."""
from __future__ import annotations

import hashlib
import subprocess
from unittest.mock import patch
import unittest

from ace_host_exchange import contracts, diagnostic

HEAD_SHA = "a" * 40
OTHER_SHA = "b" * 40


def _make_pair() -> tuple[dict, dict]:
    req = contracts.make_request(
        HEAD_SHA,
        "Repair boundary check",
        "Regression observed on empty payload",
        "All edge tests pass cleanly",
    )
    cand = contracts.make_candidate(
        req,
        "Append guard helper at end of strategy_repair.py",
        "# benign patch comment",
        "local-host",
        "test-model",
    )
    return req, cand


def _valid_receipt(baseline_bytes: bytes, patch_text: str, *, base_commit: str = HEAD_SHA) -> dict:
    combined = baseline_bytes + b"\n" + patch_text.encode("utf-8")
    return {
        "base_commit": base_commit,
        "target": contracts.TARGET,
        "patch_sha256": hashlib.sha256(patch_text.encode("utf-8")).hexdigest(),
        "base_file_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "candidate_file_sha256": hashlib.sha256(combined).hexdigest(),
        "promotion_authorized": False,
    }


class TestHostExchangeDiagnosticEdgeCases(unittest.TestCase):
    def test_01_make_request_rejects_short_or_uppercase_or_non_hex_sha(self) -> None:
        for bad_sha in ("abc123", "A" * 40, "g" * 40, 123, None):
            with self.assertRaises(ValueError):
                contracts.make_request(bad_sha, "p", "e", "s")  # type: ignore[arg-type]

    def test_02_make_request_rejects_empty_whitespace_or_oversized_fields(self) -> None:
        with self.assertRaises(ValueError):
            contracts.make_request(HEAD_SHA, "   ", "e", "s")
        with self.assertRaises(ValueError):
            contracts.make_request(HEAD_SHA, "x" * 2049, "e", "s")
        with self.assertRaises(ValueError):
            contracts.make_request(HEAD_SHA, "p", "e" * 8193, "s")

    def test_03_make_request_rejects_non_string_and_oversized_utf8_bytes(self) -> None:
        with self.assertRaises(ValueError):
            contracts.make_request(HEAD_SHA, 123, "e", "s")  # type: ignore[arg-type]
        # 1024 emoji (4 byte each) exceeds 2048 bytes even though char count < 2048.
        with self.assertRaises(ValueError):
            contracts.make_request(HEAD_SHA, "😀" * 1024, "e", "s")

    def test_04_verify_request_detects_tampered_request_id_or_constraints(self) -> None:
        req, _ = _make_pair()
        self.assertTrue(contracts.verify_request(req))
        tampered = dict(req)
        tampered["request_id"] = "0" * 64
        self.assertFalse(contracts.verify_request(tampered))

        tampered2 = dict(req)
        tampered2["constraints"] = dict(req["constraints"], promotion_authorized=True)
        self.assertFalse(contracts.verify_request(tampered2))

    def test_05_verify_request_rejects_non_dict_or_missing_keys(self) -> None:
        self.assertFalse(contracts.verify_request(["not_dict"]))
        self.assertFalse(contracts.verify_request({"schema": "ace.host-request.v1"}))

    def test_06_make_candidate_rejects_tampered_request(self) -> None:
        req, _ = _make_pair()
        req["problem"] = "silently altered"
        with self.assertRaises(ValueError):
            contracts.make_candidate(req, "hyp", "patch", "host", "model")

    def test_07_make_candidate_rejects_oversized_patch_or_empty_host(self) -> None:
        req, _ = _make_pair()
        with self.assertRaises(ValueError):
            contracts.make_candidate(req, "hyp", "a" * (contracts.MAX_SNIPPET + 1), "host", "model")
        with self.assertRaises(ValueError):
            contracts.make_candidate(req, "hyp", "ok", "  ", "model")

    def test_08_verify_candidate_rejects_tampered_patch_or_candidate_id(self) -> None:
        req, cand = _make_pair()
        self.assertTrue(contracts.verify_candidate(req, cand))
        bad_patch = dict(cand)
        bad_patch["patch"] += "\n# extra"
        self.assertFalse(contracts.verify_candidate(req, bad_patch))
        bad_status = dict(cand)
        bad_status["promotion_authorized"] = True
        self.assertFalse(contracts.verify_candidate(req, bad_status))

    def test_09_evaluate_rejects_invalid_or_mismatched_candidate(self) -> None:
        req, cand = _make_pair()
        other_req = contracts.make_request(OTHER_SHA, "p2", "e2", "s2")
        with self.assertRaises(ValueError):
            diagnostic.evaluate_host_candidate(".", other_req, cand)

    def test_10_evaluate_blocked_if_git_rev_parse_fails(self) -> None:
        req, cand = _make_pair()
        with patch(
            "ace_host_exchange.diagnostic.subprocess.check_output",
            side_effect=subprocess.SubprocessError("git unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot inspect base commit"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_11_evaluate_blocked_if_git_rev_parse_oserror(self) -> None:
        req, cand = _make_pair()
        with patch(
            "ace_host_exchange.diagnostic.subprocess.check_output",
            side_effect=OSError("no git"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot inspect base commit"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_12_evaluate_rejects_head_mismatch(self) -> None:
        req, cand = _make_pair()
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=OTHER_SHA + "\n"):
            with self.assertRaisesRegex(ValueError, "does not match current HEAD"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_13_evaluate_blocked_when_evaluate_patch_raises(self) -> None:
        req, cand = _make_pair()
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=HEAD_SHA + "\n"), \
                patch("ace_host_exchange.diagnostic.evaluate_patch", side_effect=OSError("snap failed")):
            with self.assertRaisesRegex(RuntimeError, "cannot construct committed snapshot"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_14_evaluate_blocked_when_verify_receipt_returns_false(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"])
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=HEAD_SHA + "\n"), \
                patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "evaluated snapshot or patch differs"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_15_evaluate_blocked_on_receipt_base_commit_mismatch(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"], base_commit=OTHER_SHA)
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=HEAD_SHA + "\n"), \
                patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "evaluated snapshot or patch differs"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_16_evaluate_blocked_on_receipt_target_or_patch_hash_mismatch(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"])
        rec["target"] = "other/file.py"
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=HEAD_SHA + "\n"), \
                patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "evaluated snapshot or patch differs"):
                diagnostic.evaluate_host_candidate(".", req, cand)

        rec2 = _valid_receipt(b"orig", cand["patch"])
        rec2["patch_sha256"] = "0" * 64
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=HEAD_SHA + "\n"), \
                patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec2), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "evaluated snapshot or patch differs"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_17_evaluate_blocked_if_receipt_promotion_authorized_not_false(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"])
        rec["promotion_authorized"] = True
        with patch("ace_host_exchange.diagnostic.subprocess.check_output", return_value=HEAD_SHA + "\n"), \
                patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "evaluated snapshot or patch differs"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_18_evaluate_blocked_when_git_show_baseline_fails(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"])
        with patch(
            "ace_host_exchange.diagnostic.subprocess.check_output",
            side_effect=[HEAD_SHA + "\n", subprocess.CalledProcessError(128, "git show")],
        ), patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "cannot read committed target"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_19_evaluate_blocked_on_base_file_sha256_mismatch(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"])
        with patch(
            "ace_host_exchange.diagnostic.subprocess.check_output",
            side_effect=[HEAD_SHA + "\n", b"DIFFERENT_BASELINE"],
        ), patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "evaluated target bytes differ"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_20_evaluate_blocked_on_candidate_file_sha256_mismatch(self) -> None:
        req, cand = _make_pair()
        rec = _valid_receipt(b"orig", cand["patch"])
        rec["candidate_file_sha256"] = "f" * 64
        with patch(
            "ace_host_exchange.diagnostic.subprocess.check_output",
            side_effect=[HEAD_SHA + "\n", b"orig"],
        ), patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "evaluated target bytes differ"):
                diagnostic.evaluate_host_candidate(".", req, cand)

    def test_21_evaluate_success_returns_diagnostic_only_envelope(self) -> None:
        req, cand = _make_pair()
        baseline = b"def helper():\n    return 1\n"
        rec = _valid_receipt(baseline, cand["patch"])
        with patch(
            "ace_host_exchange.diagnostic.subprocess.check_output",
            side_effect=[HEAD_SHA + "\n", baseline],
        ), patch("ace_host_exchange.diagnostic.evaluate_patch", return_value=rec), \
                patch("ace_host_exchange.diagnostic.verify_receipt", return_value=True):
            out = diagnostic.evaluate_host_candidate(".", req, cand)
        self.assertEqual(out["schema"], "ace.host-evaluation.v1")
        self.assertEqual(out["status"], "DIAGNOSTIC_ONLY")
        self.assertFalse(out["promotion_authorized"])
        self.assertEqual(out["request_id"], req["request_id"])
        self.assertEqual(out["candidate_id"], cand["candidate_id"])

    def test_22_verify_candidate_rejects_non_dict_input(self) -> None:
        req, _ = _make_pair()
        self.assertFalse(contracts.verify_candidate(req, None))
        self.assertFalse(contracts.verify_candidate(req, "candidate_str"))


if __name__ == "__main__":
    unittest.main()
