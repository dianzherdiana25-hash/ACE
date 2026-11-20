"""Uji perilaku SchedulePractice dan ArchiveProposal dengan store fixture (AG44)."""

import ast
from pathlib import Path
import unittest

from ace_operational.director_actions_wave2 import (
    ArchiveProposal,
    SchedulePractice,
)


class _FixturePracticeStore:
    def __init__(self) -> None:
        self.status = {"prac-1": "QUEUED"}
        self.refs = {"ev-1", "ev-2"}
        self.writes: list[tuple[str, str]] = []

    def verify_ref(self, ref: str) -> bool:
        return ref in self.refs

    def get_practice_status(self, practice_id: str) -> str | None:
        return self.status.get(practice_id)

    def set_practice_status(self, practice_id: str, status: str) -> None:
        self.writes.append((practice_id, status))
        self.status[practice_id] = status


class _FixtureProposalStore:
    def __init__(self) -> None:
        self.status = {"prop-1": "PENDING_REVIEW"}
        self.refs = {"ev-arch-1"}
        self.writes: list[tuple[str, str]] = []

    def verify_ref(self, ref: str) -> bool:
        return ref in self.refs

    def get_proposal_status(self, proposal_id: str) -> str | None:
        return self.status.get(proposal_id)

    def set_proposal_status(self, proposal_id: str, status: str) -> None:
        self.writes.append((proposal_id, status))
        self.status[proposal_id] = status


class DirectorActionsWave2Tests(unittest.TestCase):
    def test_schedule_practice_execute_and_undo_restores_prior_state(self) -> None:
        store = _FixturePracticeStore()
        action = SchedulePractice(store)
        undo_payload = action.execute(
            {"checkpoint": {"practice_id": "prac-1", "evidence_refs": ["ev-1", "ev-2"]}}
        )
        self.assertEqual(store.status["prac-1"], "SCHEDULED")
        self.assertEqual(
            undo_payload,
            {
                "action": "schedule_practice",
                "practice_id": "prac-1",
                "previous_status": "QUEUED",
            },
        )

        action.undo(undo_payload)
        self.assertEqual(store.status["prac-1"], "QUEUED")
        self.assertEqual(
            store.writes, [("prac-1", "SCHEDULED"), ("prac-1", "QUEUED")]
        )

    def test_archive_proposal_execute_and_undo_restores_prior_state(self) -> None:
        store = _FixtureProposalStore()
        action = ArchiveProposal(store)
        undo_payload = action.execute(
            {"checkpoint": {"proposal_id": "prop-1", "evidence_refs": ["ev-arch-1"]}}
        )
        self.assertEqual(store.status["prop-1"], "ARCHIVED")
        self.assertEqual(
            undo_payload,
            {
                "action": "archive_proposal",
                "proposal_id": "prop-1",
                "previous_status": "PENDING_REVIEW",
            },
        )

        action.undo(undo_payload)
        self.assertEqual(store.status["prop-1"], "PENDING_REVIEW")

    def test_malformed_inputs_and_unverified_refs_fail_closed_without_write(self) -> None:
        p_store = _FixturePracticeStore()
        sched = SchedulePractice(p_store)
        for bad_task in (
            "not-a-mapping",
            {},
            {"checkpoint": "not-a-mapping"},
            {"checkpoint": {"evidence_refs": ["ev-1"]}},
            {"checkpoint": {"practice_id": "   ", "evidence_refs": ["ev-1"]}},
            {"checkpoint": {"practice_id": "prac-1"}},
            {"checkpoint": {"practice_id": "prac-1", "evidence_refs": []}},
            {"checkpoint": {"practice_id": "prac-1", "evidence_refs": ["unverified"]}},
            {"checkpoint": {"practice_id": "missing-id", "evidence_refs": ["ev-1"]}},
        ):
            with self.assertRaises(ValueError):
                sched.execute(bad_task)  # type: ignore[arg-type]
        self.assertEqual(p_store.writes, [])

        a_store = _FixtureProposalStore()
        arch = ArchiveProposal(a_store)
        for bad_task in (
            {},
            {"checkpoint": {"proposal_id": "", "evidence_refs": ["ev-arch-1"]}},
            {"checkpoint": {"proposal_id": "prop-1", "evidence_refs": ["unknown"]}},
            {"checkpoint": {"proposal_id": "missing-prop", "evidence_refs": ["ev-arch-1"]}},
        ):
            with self.assertRaises(ValueError):
                arch.execute(bad_task)
        self.assertEqual(a_store.writes, [])

        for bad_undo in (
            "not-mapping",
            {},
            {"action": "archive_proposal", "practice_id": "prac-1", "previous_status": "QUEUED"},
            {"action": "schedule_practice", "practice_id": "", "previous_status": "QUEUED"},
            {"action": "schedule_practice", "practice_id": "prac-1", "previous_status": ""},
        ):
            with self.assertRaises(ValueError):
                sched.undo(bad_undo)  # type: ignore[arg-type]

        for bad_undo in (
            {},
            {"action": "schedule_practice", "proposal_id": "prop-1", "previous_status": "PENDING_REVIEW"},
            {"action": "archive_proposal", "proposal_id": "prop-1", "previous_status": ""},
        ):
            with self.assertRaises(ValueError):
                arch.undo(bad_undo)

    def test_no_engine_imports_in_module(self) -> None:
        source = (
            Path(__file__).resolve().parent / "director_actions_wave2.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertTrue(
            all("autonomous_engine" not in name and "director_execution" not in name for name in imported),
            f"Import terlarang ke engine terdeteksi: {imported}",
        )


if __name__ == "__main__":
    unittest.main()
