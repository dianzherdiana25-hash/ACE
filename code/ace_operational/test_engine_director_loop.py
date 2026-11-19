"""Regresi gerbang director, supaya usulan dapat ditelaah dari agenda engine."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_operational import brain_endpoints, director_loop
from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.store import OperationalStore


class EngineDirectorTests(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        root = Path(stack.enter_context(TemporaryDirectory()))
        self.store = stack.enter_context(OperationalStore(root))
        stack.enter_context(patch("ace_operational.memory_snapshot.import_snapshot_if_needed",
                                  return_value={}))
        self.engine = ContinuousAutonomousEngine(store=self.store)
        for method, value in {
            "verify_and_promote_local_gguf": False,
            "execute_continuous_mixed_learning": {},
            "_auto_teach_heard_words": [],
            "_run_periodic_self_evolution_audit": {"fixture": True},
        }.items():
            stack.enter_context(patch.object(self.engine, method, return_value=value))
        stack.enter_context(patch.dict(os.environ, {
            "ACE_RATIFICATION_LOOP": "0", "ACE_BRAIN_BRIDGE_URL": "http://fixture.invalid",
        }))
        self.request = stack.enter_context(patch.object(
            director_loop, "request_direction", wraps=director_loop.request_direction,
        ))
        self.chat = stack.enter_context(patch.object(brain_endpoints, "chat_structured"))

    def run_cycle(self, gate):
        with patch.dict(os.environ, {"ACE_DIRECTOR_LOOP": gate}):
            return self.engine.execute_cycle()

    def set_reply(self, content, origin="groq/fixture-model"):
        self.chat.return_value = brain_endpoints.ChatResult(
            content, "", None, None, None, brain_of_origin=origin,
        )

    def test_gate_off_preserves_summary_and_tasks(self):
        before = self.store.list_tasks()
        summary = self.run_cycle("0")
        self.assertEqual(set(summary), {"cycle", "track", "advanced_agenda", "learning_result",
                                       "vocab_added", "heard_grounded", "ratification", "self_audit"})
        self.request.assert_not_called()
        self.chat.assert_not_called()
        self.assertEqual(self.store.list_tasks(), before)

    def test_enabled_records_one_proposal_with_transport_origin(self):
        fact = self.store.list_deliverables()[0]["deliverable_id"]
        self.set_reply(json.dumps({"proposals": [{
            "title": "Periksa bukti fixture",
            "category": "measurement",
            "rationale": "Tinjau bukti yang sudah tercatat.",
            "value": 4, "effort": 2, "based_on": [fact],
            "brain_of_origin": "untrusted/written-in-answer",
        }]}))
        before = {task["task_id"] for task in self.store.list_tasks()}
        summary = self.run_cycle("1")
        self.request.assert_called_once()
        self.chat.assert_called_once()
        proposal, = [task for task in self.store.list_tasks() if task["task_id"] not in before]
        self.assertEqual(proposal["kind"], "director_proposal")
        self.assertEqual(proposal["status"], "WAITING_FOR_DEPENDENCY")
        self.assertEqual(proposal["checkpoint"]["brain_of_origin"], "groq/fixture-model")
        self.assertEqual(proposal["checkpoint"]["cycle"], summary["cycle"])
        self.assertEqual(summary["director"], {
            "status": "proposed", "task_id": proposal["task_id"],
            "title": "Periksa bukti fixture", "brain_of_origin": "groq/fixture-model",
        })
        self.assertIn(proposal["task_id"], {
            task["task_id"] for task in self.engine.orchestrator.get_prioritized_agenda()
        })
        self.assertEqual(self.engine.check_and_advance_agenda(), 0)

    def test_director_exception_leaves_cycle_running(self):
        self.engine.cycle_count = 9
        self.request.side_effect = RuntimeError("fixture transport detail")
        before = self.store.list_tasks()
        summary = self.run_cycle("1")
        self.assertEqual(summary["director"], {"status": "error", "error": "RuntimeError"})
        self.assertEqual(summary["self_audit"], {"fixture": True})
        self.assertEqual(self.store.list_tasks(), before)

    def test_malformed_response_stays_out_of_agenda(self):
        self.set_reply("bukan JSON")
        before = self.store.list_tasks()
        summary = self.run_cycle("1")
        self.assertEqual(summary["director"]["error"], "ProposalRejected")
        self.assertEqual(self.store.list_tasks(), before)

    def test_missing_origin_is_not_guessed(self):
        self.set_reply('{"proposals":[]}', origin="")
        before = self.store.list_tasks()
        summary = self.run_cycle("1")
        self.assertEqual(summary["director"]["status"], "error")
        self.assertEqual(self.store.list_tasks(), before)

    def _reply_for(self, fact):
        self.set_reply(json.dumps({"proposals": [{
            "title": "Periksa bukti fixture",
            "category": "measurement",
            "rationale": "Tinjau bukti yang sudah tercatat.",
            "value": 4, "effort": 2, "based_on": [fact],
        }]}))

    def test_second_cycle_same_fact_is_duplicate_skipped(self):
        fact = self.store.list_deliverables()[0]["deliverable_id"]
        self._reply_for(fact)
        first = self.run_cycle("1")
        self.assertEqual(first["director"]["status"], "proposed")
        second = self.run_cycle("1")
        self.assertEqual(second["director"]["status"], "duplicate_skipped")
        self.assertEqual(second["director"]["task_id"],
                         first["director"]["task_id"])
        proposals = [t for t in self.store.list_tasks()
                     if t["kind"] == "director_proposal"]
        self.assertEqual(len(proposals), 1)

    def test_different_fact_still_proposes(self):
        fact = self.store.list_deliverables()[0]["deliverable_id"]
        self._reply_for(fact)
        self.run_cycle("1")
        gap, _ = self.store.record_gap(
            source_task_id="fixture", error_type="MissingTool",
            missing_skill_or_tool="fixture_tool",
            description_id="celah fixture kedua")
        self._reply_for(gap["gap_id"])
        summary = self.run_cycle("1")
        self.assertEqual(summary["director"]["status"], "proposed")
        proposals = [t for t in self.store.list_tasks()
                     if t["kind"] == "director_proposal"]
        self.assertEqual(len(proposals), 2)


if __name__ == "__main__":
    unittest.main()
