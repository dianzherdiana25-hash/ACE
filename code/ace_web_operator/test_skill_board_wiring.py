"""Verifier gerbang mati, source baca-saja, dan kontrak skill board."""
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational import leap_wiring
from ace_web_operator._contracts import canonical,identity


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.engine=SimpleNamespace(workspace=self.root)
        registry={"schema":"ace.web.skill-registry.v1","revision":0,"source_ref":"fixture/empty-registry","entries":[]}
        roadmap={"schema":"ace.web.skill-roadmap.v1","source_ref":"fixture/roadmap",
                 "clusters":[{"id":"k01","title":"Fixture","domain":"software","source_ref":"fixture/cluster",
                              "skills":[{"id":"list","title":"Daftar","source_ref":"fixture/list"}]}]}
        plan={"schema":"ace.web.skill-board-plan.v1","source_ref":"fixture/board","roadmap_sha256":identity(roadmap),
              "registry_sha256":identity(registry),"staleness_sha256":None}
        self.payload=canonical({"schema":"ace.web.skill-board-bundle.v1","plan":plan,"roadmap":roadmap,
                                "registry":registry,"staleness":None})
        self.file=self.root/"evo0055_skills"/"board.json"
        self.file.parent.mkdir()
        self.file.write_bytes(self.payload)

    def test_disabled_hook_does_not_read_private_plan_and_legacy_shape_stays(self):
        with patch.dict(os.environ,{"ACE_EVO0055_SKILL_BOARD":"0"}), patch(
                "ace_web_operator._artifact.read_relative",side_effect=AssertionError("tidak boleh membaca")):
            missing=SimpleNamespace(workspace=None)
            self.assertEqual(leap_wiring.step_capability_report(missing),{"status":"skipped","reason":"no_workspace"})
            self.assertEqual(leap_wiring.step_evo0055_skill_board(self.engine),{"status":"disabled"})

    def test_passes_only_when_exact_artifact_is_verified_and_never_writes_workspace(self):
        anchor=sha256(self.payload).hexdigest()
        with patch.dict(os.environ,{"ACE_EVO0055_SKILL_BOARD":"1","ACE_EVO0055_BOARD_SHA256":anchor}):
            report=leap_wiring.step_capability_report(self.engine)
            self.assertEqual(report["status"],"ok")
            board=report["skill_board"]
            self.assertEqual(board["status"],"ok")
            self.assertEqual(board["skills_requested"],1)
            self.assertEqual(board["counts"],{"ACQUIRED":0,"FRAGILE":0,"MISSING":1})
            self.assertEqual(self.file.read_bytes(),self.payload)
            self.assertTrue((self.root/"capability_report.md").exists())
            self.file.write_bytes(self.payload+b" ")
            held=leap_wiring.step_capability_report(self.engine)
            self.assertEqual(held["status"],"ok")
            self.assertEqual(held["skill_board"]["reason"],"skill_board_evidence_unavailable")

    def test_skill_board_coexists_with_media_studio_evidence(self):
        anchor=sha256(self.payload).hexdigest()
        env={"ACE_EVO0055_SKILL_BOARD":"1","ACE_EVO0055_BOARD_SHA256":anchor,
             "ACE_EVO0056_MEDIA_STUDIO":"1"}
        with patch.dict(os.environ,env):
            report=leap_wiring.step_capability_report(self.engine)
            self.assertEqual(report["status"],"ok")
            self.assertEqual(report["skill_board"]["status"],"ok")
            self.assertIn("media_studio",report)
            self.assertTrue((self.root/"capability_report.md").exists())

    def test_absent_anchor_and_indirected_evidence_are_held(self):
        with patch.dict(os.environ,{"ACE_EVO0055_SKILL_BOARD":"1","ACE_EVO0055_BOARD_SHA256":""}):
            self.assertEqual(leap_wiring.step_capability_report(self.engine)["skill_board"]["reason"],"workspace_or_anchor_missing")
        moved=self.root/"other-data"
        self.file.rename(moved)
        self.file.symlink_to(moved)
        with patch.dict(os.environ,{"ACE_EVO0055_SKILL_BOARD":"1","ACE_EVO0055_BOARD_SHA256":sha256(self.payload).hexdigest()}):
            self.assertEqual(leap_wiring.step_capability_report(self.engine)["skill_board"]["reason"],"skill_board_evidence_unavailable")
