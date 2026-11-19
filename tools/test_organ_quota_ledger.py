"""Unit & adversarial tests untuk tools/organ_quota_ledger.py (offline, 0 HTTP)."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import organ_quota_ledger as oql


class TestOrganQuotaLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_01_create_ledger_rejects_bool_negative_and_bad_dates(self):
        for kwargs in (
            {"day": "19-11-2026"},
            {"groq_daily_cap": 0},
            {"groq_daily_cap": True},
            {"gonka_monthly_token_cap": -1},
            {"gemini_bucket_caps": {}},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    oql.create_ledger(**kwargs)

    def test_02_front_and_validator_rotate_between_groq_and_gemini_by_ratio(self):
        ledger = oql.create_ledger(
            groq_daily_cap=10,
            gemini_bucket_caps={"custom.gemini": 5, "custom.gemini2": 5},
        )
        # Initially tied 1.0 vs 1.0 -> groq chosen
        sel1 = oql.select_route_for_role(ledger, "front")
        self.assertEqual(sel1["provider"], "groq")
        self.assertEqual(sel1["reason"], "rotation_highest_remaining_ratio")

        # Consume 3 calls on groq -> groq 0.7 vs gemini 1.0 -> rotates to gemini
        for _ in range(3):
            ledger = oql.record_call(ledger, "front", "groq")
        sel2 = oql.select_route_for_role(ledger, "validator")
        self.assertEqual(sel2["provider"], "gemini")
        self.assertEqual(sel2["key_bucket"], "custom.gemini")

    def test_03_coder_stays_sticky_on_groq_until_fully_exhausted(self):
        ledger = oql.create_ledger(
            groq_daily_cap=2,
            gemini_bucket_caps={"custom.gemini": 10},
        )
        ledger = oql.record_call(ledger, "coder", "groq")
        # Groq still has 1 remaining (50%) vs Gemini (100%) -> coder MUST stay on groq
        sel1 = oql.select_route_for_role(ledger, "coder")
        self.assertEqual(sel1["provider"], "groq")
        self.assertEqual(sel1["reason"], "coder_primary_groq")

        # Exhaust last groq call -> now coder moves to named gemini fallback
        ledger = oql.record_call(ledger, "coder", "groq")
        sel2 = oql.select_route_for_role(ledger, "coder")
        self.assertEqual(sel2["provider"], "gemini")
        self.assertEqual(sel2["reason"], "coder_groq_exhausted_named_fallback")

    def test_04_gemini_multi_bucket_drain_and_embedding_lexical_fallback(self):
        ledger = oql.create_ledger(
            gemini_bucket_caps={"custom.gemini": 1, "custom.gemini2": 1},
        )
        ledger = oql.record_call(ledger, "embedding", "gemini", key_bucket="custom.gemini")
        sel_next = oql.select_route_for_role(ledger, "embedding")
        self.assertEqual(sel_next["key_bucket"], "custom.gemini2")

        ledger = oql.record_call(ledger, "embedding", "gemini", key_bucket="custom.gemini2")
        sel_exhausted = oql.select_route_for_role(ledger, "embedding")
        self.assertEqual(sel_exhausted["decision"], "LEXICAL_FALLBACK")
        self.assertEqual(sel_exhausted["reason"], "embedding_quota_exhausted_lexical_fallback")

    def test_05_gonka_monthly_judge_budget_holds_measurement_on_exhaustion(self):
        ledger = oql.create_ledger(gonka_monthly_token_cap=1000, gonka_daily_cap=5)
        ledger = oql.record_call(ledger, "judge", "gonka", tokens_used=950)
        sel_ok = oql.select_route_for_role(ledger, "judge", mode="measurement", estimated_tokens=40)
        self.assertEqual(sel_ok["decision"], "ROUTE")

        # Need 200 tokens > 50 remaining -> MUST hold & amend in measurement mode (never swap)
        sel_hold = oql.select_route_for_role(ledger, "judge", mode="measurement", estimated_tokens=200)
        self.assertEqual(sel_hold["decision"], "HOLD_AND_AMEND")
        self.assertIsNone(sel_hold["route"])
        self.assertIsNone(sel_hold["contingency_candidate"])

        # Same exhaustion in engine mode reports BrainUnavailable cleanly
        sel_eng = oql.select_route_for_role(ledger, "judge", mode="engine", estimated_tokens=200)
        self.assertEqual(sel_eng["decision"], "BRAIN_UNAVAILABLE")

    def test_06_rollover_preserves_monthly_gonka_same_month_and_resets_next_month(self):
        ledger = oql.create_ledger(day="2026-11-29", gonka_monthly_token_cap=10_000)
        ledger = oql.record_call(ledger, "front", "groq")
        ledger = oql.record_call(ledger, "judge", "gonka", tokens_used=4000)

        same_month = oql.rollover_period(ledger, "2026-11-30")
        self.assertEqual(same_month["routes"]["groq"]["calls_used"], 0)
        self.assertEqual(same_month["routes"]["gonka"]["calls_used"], 0)
        self.assertEqual(same_month["routes"]["gonka"]["monthly_tokens_used"], 4000)

        next_month = oql.rollover_period(same_month, "2026-12-01")
        self.assertEqual(next_month["month"], "2026-12")
        self.assertEqual(next_month["routes"]["gonka"]["monthly_tokens_used"], 0)

    def test_07_contingency_chain_enforces_owner_order_and_routes_after_registration(self):
        ledger = oql.create_ledger(groq_daily_cap=1, gemini_bucket_caps={"custom.gemini": 1})
        ledger = oql.record_call(ledger, "front", "groq")
        ledger = oql.record_call(ledger, "front", "gemini")

        need_cont = oql.select_route_for_role(ledger, "coder", mode="engine")
        self.assertEqual(need_cont["decision"], "TRIGGER_CONTINGENCY_REQUIRED")
        self.assertEqual(need_cont["contingency_candidate"], "nvidia")

        # Cannot skip nvidia -> cloudflare
        with self.assertRaises(ValueError):
            oql.activate_contingency(ledger, "cloudflare")

        # Explicitly activate nvidia -> then route selects nvidia
        ledger2 = oql.activate_contingency(ledger, "nvidia", daily_call_cap=50)
        sel = oql.select_route_for_role(ledger2, "coder", mode="engine")
        self.assertEqual(sel["decision"], "ROUTE")
        self.assertEqual(sel["provider"], "nvidia")
        self.assertEqual(sel["reason"], "contingency_active:nvidia")

        # Chain progresses nvidia -> cloudflare -> zai -> cometapi
        ledger2 = oql.activate_contingency(ledger2, "cloudflare", daily_call_cap=40)
        self.assertEqual(oql.route_snapshot(ledger2)["next_contingency_candidate"], "zai")

    def test_08_role_daily_budget_exhaustion_fails_closed(self):
        ledger = oql.create_ledger(role_budgets={"validator": 1})
        ledger = oql.record_call(ledger, "validator", "groq")
        sel = oql.select_route_for_role(ledger, "validator")
        self.assertEqual(sel["decision"], "BRAIN_UNAVAILABLE")
        self.assertEqual(sel["reason"], "role_daily_budget_exhausted:validator")

    def test_09_reconcile_bridge_log_handles_ok_over_budget_error_and_corrupt_lines(self):
        log_path = self.root / "bridge_calls.jsonl"
        log_path.write_text(
            "\n".join(
                [
                    json.dumps({"role": "front", "brain": "groq/openai/gpt-oss-120b", "result": "ok", "tokens": 120}),
                    json.dumps({"role": "front", "brain": "gemini/gemini-3-flash-preview", "result": "ok", "key": "custom.gemini2"}),
                    json.dumps({"role": "judge", "brain": "gonka/deepseek", "result": "ok", "tokens": 500}),
                    json.dumps({"role": "coder", "result": "over_budget"}),
                    json.dumps({"role": "coder", "brain": "groq/qwen", "result": "error: timeout"}),
                    "{malformed json line",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = oql.create_ledger()
        rep = oql.reconcile_bridge_log(ledger, log_path)
        self.assertEqual(rep["parsed_rows"], 5)
        self.assertEqual(rep["applied_ok"], 3)
        self.assertEqual(rep["over_budget_events"], 1)
        self.assertEqual(rep["error_events"], 1)
        self.assertEqual(rep["malformed_line_count"], 1)
        self.assertEqual(rep["ledger"]["routes"]["groq"]["tokens_used"], 120)
        self.assertEqual(rep["ledger"]["routes"]["gemini"]["buckets"]["custom.gemini2"]["used"], 1)
        self.assertEqual(rep["ledger"]["routes"]["gonka"]["monthly_tokens_used"], 500)

    def test_10_cli_markdown_json_and_missing_file_error(self):
        md_out = self.root / "quota.md"
        rc = oql.main(["--day", "2026-11-19", "--format", "markdown", "--output", str(md_out)])
        self.assertEqual(rc, 0)
        text = md_out.read_text(encoding="utf-8")
        self.assertIn("Buku Anggaran Kuota Organ Multi-Rute", text)
        self.assertIn("`coder`", text)

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_err = oql.main(["--reconcile-log", str(self.root / "missing.jsonl")])
        self.assertEqual(rc_err, 1)


if __name__ == "__main__":
    unittest.main()
