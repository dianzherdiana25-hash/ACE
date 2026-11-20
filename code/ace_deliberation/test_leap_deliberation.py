"""Uji gerbang deliberasi lompatan dengan satu workspace fixture."""
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import PropertyMock, patch

from ace_deliberation.test_decision_brief import fixture
from ace_operational import leap_wiring


class DeliberationWiringTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.engine = SimpleNamespace(workspace=self.root, cycle_count=1)
        self.export = self.root / "evo0051_deliberation_input.json"

    def test_flag_default_off_without_workspace_access(self):
        class UnreadableWorkspace:
            workspace = PropertyMock(side_effect=AssertionError("workspace read while disabled"))

        for settings in ({}, {"ACE_EVO0051_DELIBERATION": "true"}, {"ACE_EVO0051_DELIBERATION": "0"}):
            with self.subTest(settings=settings), patch.dict(os.environ, settings, clear=True):
                self.assertEqual(leap_wiring.step_evo0051_deliberation(UnreadableWorkspace()),
                                 {"status": "disabled"})
        self.assertFalse(self.export.exists())

    def test_read_only_receipt_matches_input_digest_and_keeps_dissent(self):
        raw = fixture()
        payload = json.dumps(raw).encode("utf-8")
        self.export.write_bytes(payload)
        with patch.dict(os.environ, {"ACE_EVO0051_DELIBERATION": "1"}):
            report = leap_wiring.step_evo0051_deliberation(self.engine)
        self.assertEqual(report, {"status": "reviewable", "input_sha256": hashlib.sha256(payload).hexdigest(),
                                  "debate_sha256": raw["debate"]["sha256"], "dissent_count": 1,
                                  "precedent_cited": True})
        self.assertEqual(self.export.read_bytes(), payload)
        self.assertEqual(list(self.root.iterdir()), [self.export])

    def test_missing_invalid_and_symlink_inputs_refuse_review(self):
        with patch.dict(os.environ, {"ACE_EVO0051_DELIBERATION": "1"}):
            self.assertEqual(leap_wiring.step_evo0051_deliberation(self.engine),
                             {"status": "idle", "reason": "input_missing"})
            self.export.write_text("{broken", encoding="utf-8")
            self.assertEqual(leap_wiring.step_evo0051_deliberation(self.engine),
                             {"status": "refused", "reason": "invalid_input"})
            self.export.unlink()
            outside = self.root / "elsewhere"
            outside.write_text(json.dumps(fixture()), encoding="utf-8")
            self.export.symlink_to(outside)
            self.assertEqual(leap_wiring.step_evo0051_deliberation(self.engine),
                             {"status": "refused", "reason": "invalid_input"})

    def test_step_self_exposes_receipt_only_with_exact_flag(self):
        self.export.write_text(json.dumps(fixture()), encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            without = leap_wiring.step_self(self.engine)
        with patch.dict(os.environ, {"ACE_EVO0051_DELIBERATION": "1"}, clear=True):
            enabled = leap_wiring.step_self(self.engine)
        self.assertNotIn("evo0051_deliberation", without)
        self.assertEqual(enabled["evo0051_deliberation"]["status"], "reviewable")

    def test_structurally_valid_debate_without_precedent_refuses_review(self):
        self.export.write_text(json.dumps({**fixture(), "archive": []}), encoding="utf-8")
        with patch.dict(os.environ, {"ACE_EVO0051_DELIBERATION": "1"}, clear=True):
            self.assertEqual(leap_wiring.step_evo0051_deliberation(self.engine),
                             {"status": "refused", "reason": "precedent_missing"})

    def test_oversized_input_is_refused_before_json_replay(self):
        self.export.write_bytes(b"[]")
        with patch.dict(os.environ, {"ACE_EVO0051_DELIBERATION": "1"}, clear=True), \
                patch("ace_deliberation.decision_brief.MAX_INPUT_BYTES", 1):
            self.assertEqual(leap_wiring.step_evo0051_deliberation(self.engine),
                             {"status": "refused", "reason": "input_too_large"})
