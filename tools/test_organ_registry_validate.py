"""Unit & adversarial tests untuk tools/organ_registry_validate.py (offline, 0 HTTP)."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.brain_registry import BrainRegistry
from tools import organ_registry_validate as orv


class TestOrganRegistryValidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_01_default_evo0009_slate_passes_validation(self):
        slate = orv.default_evo0009_slate()
        res = orv.validate_config_data(slate)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["error_count"], 0)
        self.assertEqual(res["detected_config_schema"], orv.SLATE_SCHEMA)
        self.assertEqual(res["role_count"], 5)

    def test_02_rejects_missing_required_role_or_unknown_primary(self):
        slate = orv.default_evo0009_slate()
        del slate["roles"]["judge"]
        res = orv.validate_config_data(slate)
        self.assertFalse(res["valid"])
        codes = {e["code"] for e in res["errors"]}
        self.assertIn("missing_required_role", codes)

        slate2 = orv.default_evo0009_slate()
        slate2["roles"]["coder"]["primary"] = "nonexistent_organ"
        res2 = orv.validate_config_data(slate2)
        self.assertFalse(res2["valid"])
        self.assertIn("unknown_primary_organ", {e["code"] for e in res2["errors"]})

    def test_03_rejects_dismissed_or_unavailable_primary_organ(self):
        slate = orv.default_evo0009_slate()
        slate["organs"]["groq_qwen3_coder"]["status"] = "dismissed"
        res = orv.validate_config_data(slate)
        self.assertFalse(res["valid"])
        self.assertIn("inactive_primary_organ", {e["code"] for e in res["errors"]})

    def test_04_enforces_proposer_validator_heterogeneity(self):
        slate = orv.default_evo0009_slate()
        slate["roles"]["coder"]["primary"] = "groq_gpt_oss_120b"
        res = orv.validate_config_data(slate)
        self.assertFalse(res["valid"])
        self.assertIn("heterogeneity_violation_code_pair", {e["code"] for e in res["errors"]})

    def test_05_rejects_secret_api_key_or_bearer_token_in_config(self):
        for fake_secret in (
            "sk-proj-1234567890abcdef1234567890",
            "gsk_abcdefghijklmnop123456",
            "AIzaSyDaBcdEfGhIjKlMnOpQrStUvWxYz",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        ):
            with self.subTest(secret=fake_secret[:8]):
                slate = orv.default_evo0009_slate()
                slate["organs"]["groq_qwen3_coder"]["note"] = fake_secret
                res = orv.validate_config_data(slate)
                self.assertFalse(res["valid"])
                self.assertIn("secret_leak_detected", {e["code"] for e in res["errors"]})

    def test_06_enforces_contingency_order_and_forbids_silent_activation(self):
        slate_bad_order = orv.default_evo0009_slate()
        slate_bad_order["contingency_chain"][0]["provider"] = "cloudflare"
        slate_bad_order["contingency_chain"][1]["provider"] = "nvidia"
        res = orv.validate_config_data(slate_bad_order)
        self.assertFalse(res["valid"])
        self.assertIn("contingency_order_mismatch", {e["code"] for e in res["errors"]})

        slate_silent = orv.default_evo0009_slate()
        slate_silent["contingency_chain"][0]["status"] = "active"
        res2 = orv.validate_config_data(slate_silent)
        self.assertFalse(res2["valid"])
        self.assertIn("silent_contingency_activation", {e["code"] for e in res2["errors"]})

    def test_07_enforces_judge_hold_and_strict_integer_budgets(self):
        slate = orv.default_evo0009_slate()
        slate["roles"]["judge"]["hold_on_exhaustion_in_measurement"] = False
        slate["roles"]["front"]["daily_budget"] = True
        res = orv.validate_config_data(slate)
        self.assertFalse(res["valid"])
        codes = {e["code"] for e in res["errors"]}
        self.assertIn("judge_must_hold_on_exhaustion", codes)
        self.assertIn("invalid_daily_budget", codes)

    def test_08_validates_brain_registry_v1_and_catches_blank_descriptor(self):
        reg_path = self.root / "registry.json"
        reg = BrainRegistry(reg_path)
        reg.register("front-local", kind="local", descriptor="Qwen3.5-4B.gguf", status="active")
        reg.register("cloud-claude", kind="api", descriptor="claude-sonnet", status="declared-unavailable")
        res = orv.validate_config_file(reg_path)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["detected_config_schema"], orv.BRAIN_REGISTRY_SCHEMA)

        # Tambah descriptor kosong (bug wildcard match D2 #360) -> harus ditolak fail-closed
        reg.register("blank-id", kind="local", descriptor="  ", status="active")
        res_bad = orv.validate_config_file(reg_path)
        self.assertFalse(res_bad["valid"])
        self.assertIn("blank_descriptor_wildcard_risk", {e["code"] for e in res_bad["errors"]})

    def test_09_handles_corrupt_json_and_non_dict_root(self):
        bad_file = self.root / "corrupt.json"
        bad_file.write_text("{broken json", encoding="utf-8")
        res = orv.validate_config_file(bad_file)
        self.assertFalse(res["valid"])
        self.assertEqual(res["errors"][0]["code"], "malformed_json")

        res_list = orv.validate_config_data([1, 2, 3])
        self.assertFalse(res_list["valid"])
        self.assertEqual(res_list["errors"][0]["code"], "non_object_root")

    def test_10_cli_check_default_print_template_markdown_and_exit_codes(self):
        tpl_path = self.root / "slate.json"
        md_path = self.root / "report.md"

        rc_tpl = orv.main(["--print-template", "--output", str(tpl_path)])
        self.assertEqual(rc_tpl, 0)
        self.assertEqual(json.loads(tpl_path.read_text(encoding="utf-8"))["schema"], orv.SLATE_SCHEMA)

        rc_cfg = orv.main(["--config", str(tpl_path), "--format", "markdown", "--output", str(md_path)])
        self.assertEqual(rc_cfg, 0)
        md = md_path.read_text(encoding="utf-8")
        self.assertIn("Status: `VALID`", md)

        bad_slate = copy.deepcopy(orv.default_evo0009_slate())
        del bad_slate["roles"]["judge"]
        bad_path = self.root / "bad.json"
        bad_path.write_text(json.dumps(bad_slate), encoding="utf-8")
        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf):
            rc_invalid = orv.main(["--config", str(bad_path)])
        self.assertEqual(rc_invalid, 2)
        self.assertFalse(json.loads(out_buf.getvalue())["valid"])

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_err = orv.main([])
        self.assertEqual(rc_err, 1)


if __name__ == "__main__":
    unittest.main()
