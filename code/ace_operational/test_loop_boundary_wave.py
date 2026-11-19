"""Offline edge cases for cycle orchestration and ratification custody."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.memory_writeback import recall_context, record_event_outcomes, record_verified_event
from ace_operational.ratification_loop import parse_judge_score, run_ratification_episode
from ace_operational.test_ratification_loop import CODE_EP, LANG_EP, fake_pair, make_chat, sealed_records
from ace_self_dev.agenda_engine import AgendaEngine
from ace_self_dev.models import PersistentResearchState


class CycleBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.engine = ContinuousAutonomousEngine(workspace=self.workspace)

    def cycle(self, *, gate, agenda=0, previous=0):
        self.engine.cycle_count = previous
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"ACE_RATIFICATION_LOOP": gate}))
            mocks = {}
            for name, value in {
                "verify_and_promote_local_gguf": False,
                "check_and_advance_agenda": agenda,
                "execute_continuous_mixed_learning": {"track": "technical"},
                "_auto_teach_heard_words": [],
                "execute_ratification_step": {"status": "no_source"},
                "_run_periodic_self_evolution_audit": {"findings": []},
            }.items():
                mocks[name] = stack.enter_context(patch.object(self.engine, name, return_value=value))
            return self.engine.execute_cycle(), mocks

    def test_gate_must_be_exact_opt_in(self):
        for gate in ("", "true", "01"):
            with self.subTest(gate=gate):
                summary, mocks = self.cycle(gate=gate)
                self.assertIsNone(summary["ratification"])
                mocks["execute_ratification_step"].assert_not_called()

    def test_agenda_owns_cycle_and_ratification_remains_independent(self):
        summary, mocks = self.cycle(gate="1", agenda=2)
        mocks["execute_continuous_mixed_learning"].assert_not_called()
        mocks["execute_ratification_step"].assert_called_once_with()
        self.assertEqual(summary["track"], "agenda")
        self.assertEqual(summary["ratification"]["status"], "no_source")

    def test_periodic_audit_runs_at_boundary(self):
        before, mocks = self.cycle(gate="0", previous=8)
        mocks["_run_periodic_self_evolution_audit"].assert_not_called()
        self.assertIsNone(before["self_audit"])
        at, mocks = self.cycle(gate="0", previous=9)
        mocks["_run_periodic_self_evolution_audit"].assert_called_once_with()
        self.assertEqual(at["cycle"], 10)
        self.assertEqual(at["self_audit"], {"findings": []})

    def test_cursor_survives_engine_recreation(self):
        source = self.workspace / "episodes.jsonl"
        source.write_text("\n".join(map(json.dumps, [CODE_EP, LANG_EP])), encoding="utf-8")
        options = dict(episodes_path=source, chat_fn=make_chat(), pair_fn=fake_pair)
        self.assertEqual(self.engine.execute_ratification_step(**options)["episode_id"], CODE_EP["id"])
        reopened = ContinuousAutonomousEngine(workspace=self.workspace)
        self.assertEqual(reopened.execute_ratification_step(**options)["episode_id"], LANG_EP["id"])
        self.assertEqual(reopened.execute_ratification_step(**options)["status"], "exhausted")

    def test_malformed_source_fails_before_organ_or_cursor(self):
        source = self.workspace / "episodes.jsonl"
        source.write_text("{bad", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.engine.execute_ratification_step(episodes_path=source, chat_fn=self.fail)
        self.assertEqual(self.engine._load_int_meta("autonomous_ratification_cursor"), 0)


class RatificationCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "memory"

    def test_boolean_and_nonfinite_scores_rejected(self):
        for value in (True, False, float("inf"), float("nan"), 0.5, -1):
            with self.subTest(value=value):
                self.assertIsNone(parse_judge_score({"score": value}))
        self.assertEqual(parse_judge_score({"score": 0}), 0)
        self.assertEqual(parse_judge_score({"score": 100.0}), 100)

    def test_truthy_nonboolean_accept_never_writes(self):
        for claim in ('"true"', "1", "[]"):
            with self.subTest(claim=claim):
                result = run_ratification_episode(
                    CODE_EP, memory_root=self.root, pair_fn=fake_pair, scored=True,
                    chat_fn=make_chat(judge_raw='{"accept": ' + claim + ', "score": 100}'),
                )
                self.assertFalse(result["ratified"])
                self.assertIsNone(result["writeback_id"])
        self.assertEqual(sealed_records(self.root), [])

    def test_writeback_failure_preserves_ratification(self):
        self.root.write_text("not a directory", encoding="utf-8")
        with self.assertLogs("ace_operational.memory_writeback", level="WARNING"):
            result = run_ratification_episode(
                CODE_EP, memory_root=self.root, pair_fn=fake_pair, chat_fn=make_chat(),
            )
        self.assertTrue(result["ratified"])
        self.assertIsNone(result["writeback_id"])

    def test_recall_failure_does_not_erase_existing_file(self):
        self.root.write_bytes(b"fixture")
        with self.assertLogs("ace_operational.memory_writeback", level="WARNING"):
            self.assertEqual(recall_context(self.root, "query"), [])
        self.assertEqual(self.root.read_bytes(), b"fixture")

    def test_outcome_batch_continues_after_missing_record(self):
        record_id = record_verified_event(
            self.root, event="skill_verified", summary="fixture token pulse", evidence_bytes=b"receipt"
        )
        valid, = recall_context(self.root, "fixture token pulse")
        self.assertEqual(valid["id"], record_id)
        with self.assertLogs("ace_operational.memory_writeback", level="WARNING"):
            count = record_event_outcomes(
                self.root, [{"kind": "procedural", "id": "missing"}, valid],
                context="retry", success=False,
            )
        self.assertEqual(count, 1)


class AgendaBoundaryTests(unittest.TestCase):
    def test_empty_agenda_reports_terminal_and_replays_seed(self):
        engine = AgendaEngine()
        state = PersistentResearchState(
            schema_version="2.0", active_generation_id="G0_root", cycle_count=3
        )
        diagnosis = SimpleNamespace(diagnostic_details={})
        first = engine.select_cycle_strategy(state, diagnosis, {})
        self.assertEqual(first, engine.select_cycle_strategy(state, diagnosis, {}))
        self.assertEqual((first[0], first[2]), ("SEARCH_SPACE_EXHAUSTED", 0))
        self.assertTrue(1000 <= first[1] <= 9999)
        hypothesis = engine.formulate_hypothesis(4, first[0], None, first[2], state)
        self.assertEqual(hypothesis.target_task_id, "NONE")

    def test_accepted_task_hands_agenda_to_next_task(self):
        engine = AgendaEngine()
        tasks = {"old": SimpleNamespace(family="A"), "next": SimpleNamespace(family="B")}
        state = PersistentResearchState(
            schema_version="2.0", active_generation_id="G0_root", cycle_count=3
        )
        priority = engine.formulate_next_goal(4, "old", 2, "ACCEPTED", 0.25, tasks, state)
        self.assertEqual(priority.priority_task_id, "next")
        self.assertEqual(priority.priority_family, "B")
        self.assertEqual(priority.suggested_ordinal, 1)
