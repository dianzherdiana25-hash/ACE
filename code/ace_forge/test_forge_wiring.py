"""Verifier gerbang dossier pada satu-satunya titik integrasi EVO 0052."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_forge._forge_io import canonical, identity
from ace_forge.test_model_dossier import fixture
from ace_operational.leap_wiring import step_evo0052_forge


def read_step(engine, environ):
    with patch.dict(os.environ, environ, clear=True):
        return step_evo0052_forge(engine)


class ForgeWiringTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.engine = SimpleNamespace(workspace=self.root)
        self.path = self.root / "evo0052_dossier.json"

    def test_flag_off_does_not_read_workspace_or_import_fit(self):
        class Untouchable:
            @property
            def workspace(self):
                raise AssertionError("Workspace dibaca saat flag mati.")

        for flags in ({}, {"ACE_EVO0052_FORGE": "0"}, {"ACE_EVO0052_FORGE": "true"}):
            with self.subTest(flags=flags):
                self.assertEqual(read_step(Untouchable(), flags), {"status": "disabled"})

    def test_complete_dossier_reaches_readonly_summary(self):
        raw = fixture()
        payload = canonical(raw)
        self.path.write_bytes(payload)
        report = read_step(self.engine, {"ACE_EVO0052_FORGE": "1", "ACE_EVO0052_DOSSIER_SHA256": identity(raw)})
        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(report["candidate_sha256"], raw["candidate_sha256"])
        self.assertEqual(report["dossier_sha256"], identity(raw))
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(self.path.read_bytes(), payload)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_absent_anchor_missing_dossier_and_wrong_hash_fail_closed(self):
        enabled = {"ACE_EVO0052_FORGE": "1"}
        self.assertEqual(read_step(self.engine, enabled)["reason"], "dossier_anchor_missing_or_invalid")
        raw = fixture()
        enabled["ACE_EVO0052_DOSSIER_SHA256"] = identity(raw)
        self.assertEqual(read_step(self.engine, enabled)["reason"], "dossier_missing")
        raw["minimum_gain_bp"] += 1
        self.path.write_bytes(canonical(raw))
        self.assertEqual(read_step(self.engine, enabled), {"status": "hold", "reason": "dossier_unreadable_or_invalid"})

    def test_anchored_missing_checks_return_hold_without_effect(self):
        raw = fixture()
        raw["registry"] = None
        self.path.write_bytes(canonical(raw))
        report = read_step(self.engine, {"ACE_EVO0052_FORGE": "1", "ACE_EVO0052_DOSSIER_SHA256": identity(raw)})
        self.assertEqual(report["status"], "hold")
        self.assertEqual(report["missing"], ["registry"])
        self.assertEqual(self.path.read_bytes(), canonical(raw))

    def test_reject_symlink_and_fifo(self):
        raw = fixture()
        enabled = {"ACE_EVO0052_FORGE": "1", "ACE_EVO0052_DOSSIER_SHA256": identity(raw)}
        target = self.root / "outside_snapshot.json"
        target.write_bytes(canonical(raw))
        self.path.symlink_to(target)
        self.assertEqual(read_step(self.engine, enabled)["reason"], "dossier_unreadable_or_invalid")
        self.path.unlink()
        os.mkfifo(self.path)
        self.assertEqual(read_step(self.engine, enabled)["reason"], "dossier_type_or_size")
