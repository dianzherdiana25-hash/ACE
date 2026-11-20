"""Tes siklus hidup proyek dua tonggak & penolakan transisi tanpa bukti gerbang (AG80)."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from ace_operational.project_layer import (
    ProjectGateError,
    complete_project,
    create_project,
    register_artifact,
    start_milestone,
    verify_milestone_gate,
)


class _FixtureProjectStore:
    def __init__(self, verified_refs: set[str]) -> None:
        self._projects: dict[str, dict] = {}
        self._refs = set(verified_refs)

    def get_project(self, project_id: str):
        val = self._projects.get(project_id)
        return deepcopy(val) if val is not None else None

    def save_project(self, project_id: str, data) -> None:
        self._projects[project_id] = deepcopy(dict(data))

    def verify_ref(self, ref: str) -> bool:
        return ref in self._refs


class ProjectLayerTests(unittest.TestCase):
    def test_two_milestone_lifecycle_enforces_gate_evidence_and_order(self) -> None:
        store = _FixtureProjectStore(
            {"art-m1", "ev-m1-gate", "art-m2", "ev-m2-gate"}
        )
        create_project(
            store,
            project_id="proj-pilot",
            title="Proyek Perdana Mainan",
            milestones=[
                {"milestone_id": "m1", "title": "Desain & Artefak", "required_gates": ["design_gate"]},
                {"milestone_id": "m2", "title": "Implementasi & Uji", "required_gates": ["test_gate"]},
            ],
        )

        # Tidak boleh lompat ke m2 sebelum m1 VERIFIED.
        with self.assertRaises(ProjectGateError):
            start_milestone(store, project_id="proj-pilot", milestone_id="m2")

        start_milestone(store, project_id="proj-pilot", milestone_id="m1")

        # Transisi tonggak tanpa bukti gerbang atau tanpa artefak atau ref tak terverifikasi wajib ditolak!
        with self.assertRaises(ProjectGateError):
            verify_milestone_gate(store, project_id="proj-pilot", milestone_id="m1", gate_evidence={})
        with self.assertRaises(ProjectGateError):
            verify_milestone_gate(
                store,
                project_id="proj-pilot",
                milestone_id="m1",
                gate_evidence={"design_gate": ["ev-unverified-fake"]},
            )
        # Masih belum boleh sebelum artefak terdaftar walaupun bukti gate valid.
        with self.assertRaises(ProjectGateError):
            verify_milestone_gate(
                store,
                project_id="proj-pilot",
                milestone_id="m1",
                gate_evidence={"design_gate": ["ev-m1-gate"]},
            )

        register_artifact(
            store,
            project_id="proj-pilot",
            milestone_id="m1",
            artifact_id="spec-doc",
            ref="art-m1",
        )
        p1 = verify_milestone_gate(
            store,
            project_id="proj-pilot",
            milestone_id="m1",
            gate_evidence={"design_gate": ["ev-m1-gate"]},
        )
        self.assertEqual(p1["milestones"][0]["status"], "VERIFIED")

        # Tidak boleh menutup proyek saat m2 belum VERIFIED.
        with self.assertRaises(ProjectGateError):
            complete_project(store, project_id="proj-pilot")

        start_milestone(store, project_id="proj-pilot", milestone_id="m2")
        register_artifact(
            store,
            project_id="proj-pilot",
            milestone_id="m2",
            artifact_id="module-pkg",
            ref="art-m2",
        )
        verify_milestone_gate(
            store,
            project_id="proj-pilot",
            milestone_id="m2",
            gate_evidence={"test_gate": ["ev-m2-gate"]},
        )
        final_proj = complete_project(store, project_id="proj-pilot")
        self.assertEqual(final_proj["status"], "COMPLETED")
        self.assertEqual(
            [m["status"] for m in final_proj["milestones"]],
            ["VERIFIED", "VERIFIED"],
        )

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "project_layer.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
