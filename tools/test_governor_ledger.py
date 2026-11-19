"""Tes unit buku anggaran governor per rute/peran (D7 — tes saja, offline).

Mencakup governor runtime (`ace_operational.brain_bridge`) dan buku anggaran
multi-rute (`tools.organ_quota_ledger`): akuntansi panggilan per hari,
rollover hari/bulan, penolakan saat budget habis, dan ketahanan state rusak.
Dugaan bug pada modul yang diuji didokumentasikan sebagai `@unittest.expectedFailure`
berkomentar tanpa mengubah logika modul produksi.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CODE_DIR = _REPO_ROOT / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_operational import brain_bridge as bridge
from tools import organ_quota_ledger as oql


DAY_1 = "2026-11-18"
DAY_2 = "2026-11-19"
MONTH_NEXT = "2026-12-01"


class _FakeHeaders:
    def __init__(self, body_len: int) -> None:
        self._body_len = body_len

    def get(self, key: str, default: str = "0") -> str:
        if key.lower() == "content-length":
            return str(self._body_len)
        return default


class BrainBridgeGovernorLedgerTests(unittest.TestCase):
    """Tes unit governor `ace_operational.brain_bridge`."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "bridge_state.json"
        self.log = self.root / "bridge_calls.jsonl"
        self.day = DAY_1

        p_state = mock.patch.object(bridge, "STATE", self.state)
        p_log = mock.patch.object(bridge, "LOG", self.log)
        p_today = mock.patch.object(bridge, "_today", side_effect=lambda: self.day)
        for p in (p_state, p_log, p_today):
            p.start()
            self.addCleanup(p.stop)

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        raw = json.dumps(payload).encode("utf-8")
        handler = bridge.Handler.__new__(bridge.Handler)
        handler.path = path
        handler.headers = _FakeHeaders(len(raw))
        handler.rfile = io.BytesIO(raw)
        handler._send = mock.Mock()
        handler.do_POST()
        handler._send.assert_called_once()
        return handler._send.call_args.args

    def test_01_all_governor_roles_present_and_per_day_accounting_persists(self) -> None:
        expected_roles = {"front", "coder", "validator", "embedding", "judge"}
        self.assertTrue(expected_roles.issubset(set(bridge.BUDGETS.keys())))

        for role in sorted(expected_roles):
            ok, used = bridge._budget_check(role)
            self.assertTrue(ok)
            self.assertEqual(used, 1)

        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved["day"], DAY_1)
        for role in expected_roles:
            self.assertEqual(saved["counts"][role], 1)

        status, snap = bridge.budget_response()
        self.assertEqual(status, 200)
        self.assertTrue(snap["initialized"])
        for role in expected_roles:
            self.assertEqual(snap["roles"][role]["used_today"], 1)
            self.assertEqual(snap["roles"][role]["remaining"], bridge.BUDGETS[role] - 1)

    def test_02_exact_cap_exhaustion_blocks_only_exhausted_role(self) -> None:
        limit_judge = bridge.BUDGETS["judge"]
        self.state.write_text(
            json.dumps({"day": DAY_1, "counts": {"judge": limit_judge - 1, "front": 2}}),
            encoding="utf-8",
        )

        ok_last, used_last = bridge._budget_check("judge")
        self.assertTrue(ok_last)
        self.assertEqual(used_last, limit_judge)

        ok_over, used_over = bridge._budget_check("judge")
        self.assertFalse(ok_over)
        self.assertEqual(used_over, limit_judge)

        # Counter must not keep climbing beyond cap when rejected.
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved["counts"]["judge"], limit_judge)

        # Other roles keep their independent remaining budget on the same day.
        ok_front, used_front = bridge._budget_check("front")
        self.assertTrue(ok_front)
        self.assertEqual(used_front, 3)

    def test_03_day_rollover_resets_all_daily_counters(self) -> None:
        self.state.write_text(
            json.dumps({
                "day": DAY_1,
                "counts": {role: cap for role, cap in bridge.BUDGETS.items()},
            }),
            encoding="utf-8",
        )
        ok_day1, _ = bridge._budget_check("judge")
        self.assertFalse(ok_day1)

        # Advance calendar day.
        self.day = DAY_2
        status_before, snap_before = bridge.budget_response()
        self.assertEqual(status_before, 200)
        self.assertFalse(snap_before["initialized"])
        self.assertEqual(snap_before["roles"]["judge"]["used_today"], 0)

        ok_day2, used_day2 = bridge._budget_check("judge")
        self.assertTrue(ok_day2)
        self.assertEqual(used_day2, 1)

        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved["day"], DAY_2)
        self.assertEqual(saved["counts"], {"judge": 1})

    def test_04_http_post_rejects_exhausted_role_with_429_and_logs_over_budget(self) -> None:
        self.state.write_text(
            json.dumps({"day": DAY_1, "counts": {"coder": bridge.BUDGETS["coder"]}}),
            encoding="utf-8",
        )
        with mock.patch.object(bridge, "serve_chat") as chat_mock:
            status, body = self._post(
                "/v1/chat/completions",
                {"role": "coder", "messages": [{"role": "user", "content": "ping"}]},
            )
        chat_mock.assert_not_called()
        self.assertEqual(status, 429)
        self.assertIn("error", body)

        log_lines = [json.loads(ln) for ln in self.log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(log_lines), 1)
        self.assertEqual(log_lines[0]["role"], "coder")
        self.assertEqual(log_lines[0]["result"], "over_budget")

    def test_05_budget_response_fails_closed_on_all_corrupt_states_without_mutation(self) -> None:
        bad_payloads = [
            b"",
            b"{truncated",
            b"\xff\xfe\xfd",
            b"[]",
            b"null",
            b"42",
            json.dumps({"day": DAY_1, "counts": "not-a-dict"}).encode("utf-8"),
            json.dumps({"day": DAY_1, "counts": {"front": True}}).encode("utf-8"),
            json.dumps({"day": DAY_1, "counts": {"front": -5}}).encode("utf-8"),
            json.dumps({"day": DAY_1, "counts": {"front": "10"}}).encode("utf-8"),
        ]
        for raw in bad_payloads:
            with self.subTest(raw=raw):
                self.state.write_bytes(raw)
                status, body = bridge.budget_response()
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["type"], "budget_state_unavailable")
                self.assertEqual(self.state.read_bytes(), raw)

    # Dugaan bug brain_bridge._budget_check:
    # `budget_response()` menolak JSON rusak/non-dict dengan 503 secara aman,
    # tetapi `_budget_check()` memanggil `json.loads(STATE.read_text())` langsung
    # tanpa try/except sehingga meledak `JSONDecodeError`.
    @unittest.expectedFailure
    def test_06_bug_budget_check_crashes_on_corrupt_state_json(self) -> None:
        self.state.write_bytes(b"{corrupt-json")
        ok, rem = bridge._budget_check("front")
        self.assertFalse(ok)
        self.assertEqual(rem, 0)

    # Dugaan bug brain_bridge._budget_check:
    # Akar JSON berupa list/null/skalar atau `counts["front"]` berupa `bool`/`str`
    # menyebabkan `AttributeError`/`TypeError` atau menghitung `True` sebagai `1`
    # alih-alih fail-closed atau memulihkan state harian.
    @unittest.expectedFailure
    def test_07_bug_budget_check_crashes_on_non_dict_or_bool_counts(self) -> None:
        self.state.write_text(json.dumps({"day": DAY_1, "counts": {"front": "bad"}}), encoding="utf-8")
        ok, _ = bridge._budget_check("front")
        self.assertFalse(ok)


class OrganQuotaLedgerGovernorTests(unittest.TestCase):
    """Tes unit buku anggaran multi-rute `tools.organ_quota_ledger`."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_08_daily_role_accounting_across_all_five_roles_and_exact_boundary(self) -> None:
        ledger = oql.create_ledger(
            day=DAY_1,
            role_budgets={"front": 3, "coder": 2, "validator": 2, "embedding": 2, "judge": 2},
            groq_daily_cap=20,
            gemini_bucket_caps={"b1": 10},
            gonka_daily_cap=5,
            gonka_monthly_token_cap=5000,
        )
        ledger = oql.record_call(ledger, "front", "groq")
        ledger = oql.record_call(ledger, "front", "gemini", key_bucket="b1")
        self.assertEqual(ledger["role_used"]["front"], 2)
        self.assertEqual(oql.select_route_for_role(ledger, "front")["decision"], "ROUTE")

        # Exact 3rd call reaches cap=3 -> 4th call blocked by role_daily_budget_exhausted:front.
        ledger = oql.record_call(ledger, "front", "groq")
        sel_exhausted = oql.select_route_for_role(ledger, "front")
        self.assertEqual(sel_exhausted["decision"], "BRAIN_UNAVAILABLE")
        self.assertEqual(sel_exhausted["reason"], "role_daily_budget_exhausted:front")

        # Coder still has its own budget untouched.
        sel_coder = oql.select_route_for_role(ledger, "coder")
        self.assertEqual(sel_coder["decision"], "ROUTE")
        self.assertEqual(sel_coder["provider"], "groq")

    def test_09_daily_and_monthly_rollover_clears_role_and_provider_counters(self) -> None:
        ledger = oql.create_ledger(
            day=DAY_1,
            role_budgets={"front": 2, "judge": 5},
            groq_daily_cap=2,
            gemini_bucket_caps={"b1": 2},
            gonka_monthly_token_cap=1000,
        )
        ledger = oql.record_call(ledger, "front", "groq")
        ledger = oql.record_call(ledger, "front", "groq")
        ledger = oql.record_call(ledger, "judge", "gonka", tokens_used=600)
        self.assertEqual(oql.select_route_for_role(ledger, "front")["decision"], "BRAIN_UNAVAILABLE")

        day2 = oql.rollover_period(ledger, DAY_2)
        self.assertEqual(day2["day"], DAY_2)
        self.assertEqual(day2["role_used"]["front"], 0)
        self.assertEqual(day2["routes"]["groq"]["calls_used"], 0)
        self.assertEqual(day2["routes"]["gonka"]["calls_used"], 0)
        # Same month preserves monthly Gonka token cumulative counter.
        self.assertEqual(day2["routes"]["gonka"]["monthly_tokens_used"], 600)
        self.assertEqual(oql.select_route_for_role(day2, "front")["decision"], "ROUTE")

        # New month resets monthly Gonka token counter too.
        dec = oql.rollover_period(day2, MONTH_NEXT)
        self.assertEqual(dec["month"], "2026-12")
        self.assertEqual(dec["routes"]["gonka"]["monthly_tokens_used"], 0)

    def test_10_role_exhaustion_takes_precedence_over_active_contingency(self) -> None:
        ledger = oql.create_ledger(
            day=DAY_1,
            role_budgets={"coder": 1},
            groq_daily_cap=5,
            gemini_bucket_caps={"b1": 5},
        )
        ledger = oql.activate_contingency(ledger, "nvidia", daily_call_cap=10)
        ledger = oql.record_call(ledger, "coder", "nvidia")

        # Even though nvidia/groq/gemini all have provider quota remaining,
        # role daily budget exhaustion MUST block the role cleanly.
        sel = oql.select_route_for_role(ledger, "coder", mode="engine")
        self.assertEqual(sel["decision"], "BRAIN_UNAVAILABLE")
        self.assertEqual(sel["reason"], "role_daily_budget_exhausted:coder")

    def test_11_record_call_and_rollover_reject_corrupt_types_and_bad_values(self) -> None:
        ledger = oql.create_ledger(day=DAY_1)

        with self.assertRaises(ValueError):
            oql.record_call(ledger, "unknown_role", "groq")
        with self.assertRaises(ValueError):
            oql.record_call(ledger, "front", "unknown_provider")
        with self.assertRaises(ValueError):
            oql.record_call(ledger, "front", "groq", tokens_used=True)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            oql.record_call(ledger, "front", "groq", tokens_used=-1)
        with self.assertRaises(ValueError):
            oql.rollover_period(ledger, "invalid-date")

    def test_12_reconcile_corrupt_bridge_log_resilience_and_cli_bad_json(self) -> None:
        log_path = self.root / "bridge_calls.jsonl"
        log_path.write_text(
            "\n".join(
                [
                    "",
                    "[]",
                    "null",
                    "123",
                    "{broken-json",
                    json.dumps({"role": "unknown_role", "brain": "groq/x", "result": "ok"}),
                    json.dumps({"role": "front", "brain": "groq/openai/gpt-oss-120b", "result": "ok", "tokens": True}),
                    json.dumps({"role": "coder", "brain": "groq/qwen", "result": "error: 500"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = oql.create_ledger(day=DAY_1)
        rep = oql.reconcile_bridge_log(ledger, log_path)
        self.assertGreaterEqual(rep["malformed_line_count"], 1)
        self.assertEqual(rep["error_events"], 1)
        # Ensure boolean tokens in log line did not corrupt integer token accounting.
        self.assertNotIsInstance(rep["ledger"]["routes"]["groq"]["tokens_used"], bool)

        # CLI fails cleanly (exit code 1, no unhandled traceback) when passed corrupt base ledger JSON.
        bad_ledger = self.root / "bad_ledger.json"
        bad_ledger.write_text("{corrupt", encoding="utf-8")
        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc = oql.main(["--ledger", str(bad_ledger)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
