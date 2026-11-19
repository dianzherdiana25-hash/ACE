"""Pastikan status dapat melokalisasi latensi dan transport gagal pada siklus offline."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from ace_operational import autonomous_engine, brain_endpoints
from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.store import OperationalStore


class EngineStatusTelemetryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.store = OperationalStore(self.workspace)
        self.addCleanup(self.store.close)
        self.enterContext(mock.patch(
            "ace_operational.memory_snapshot.import_snapshot_if_needed", return_value={}
        ))
        self.enterContext(mock.patch.dict(os.environ, {"ACE_DIRECTOR_LOOP": "0"}))
        self.engine = ContinuousAutonomousEngine(store=self.store)
        self.clock = 100.0

    def status(self):
        return json.loads(self.engine.status_file.read_text(encoding="utf-8"))

    def timed(self, duration, result):
        def step():
            self.clock += duration
            return result

        return step

    def test_completed_cycle_updates_telemetry_and_keeps_legacy_fields(self):
        def mixed_learning():
            for _ in range(2):
                self.assertIsNone(self.engine._gen_text(
                    [{"role": "user", "content": "fixture"}],
                    max_tokens=8, temperature=0.0, organ="coder",
                ))
            self.clock += 3
            return {"track": "technical"}

        self.engine.cycle_count = 9
        steps = {
            "verify_and_promote_local_gguf": self.timed(2, False),
            "check_and_advance_agenda": self.timed(1, 0),
            "execute_continuous_mixed_learning": mixed_learning,
            "_auto_teach_heard_words": self.timed(1, []),
            "execute_ratification_step": self.timed(4, {"status": "fixture"}),
            "_run_periodic_self_evolution_audit": self.timed(2, {"findings": []}),
        }
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {"ACE_RATIFICATION_LOOP": "1"}))
            stack.enter_context(mock.patch.object(brain_endpoints, "bridge_mode", return_value=True))
            chat = stack.enter_context(mock.patch.object(
                brain_endpoints, "chat", side_effect=brain_endpoints.BrainUnavailable("fixture"),
            ))
            clock = stack.enter_context(mock.patch.object(
                autonomous_engine, "time", wraps=autonomous_engine.time,
            ))
            clock.monotonic.side_effect = lambda: self.clock
            for name, step in steps.items():
                stack.enter_context(mock.patch.object(self.engine, name, side_effect=step))
            self.engine.execute_cycle()

        status = self.status()
        self.assertEqual(status.pop("last_cycle_duration_seconds"), 13.0)
        self.assertEqual(status.pop("slowest_step"), {"name": "ratification_loop", "seconds": 4.0})
        self.assertEqual(status.pop("bridge_transport_failures"), 2)
        self.assertEqual(chat.call_count, 2)
        self.assertRegex(status.pop("updated_at"), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(status, {
            "schema": "ace.autonomous_engine.status.v1",
            "running": False,
            "cycle_count": 10,
            "lang_cursor": 0,
            "tech_cursor": 0,
            "current_action": "idle_waiting_next_cycle",
            "pid": os.getpid(),
            "details": {
                "last_cycle_completed": 10,
                "track": "technical",
                "vocab_added": 0,
                "next_cycle_in_seconds": self.engine.tick_interval_seconds,
            },
        })
        self.engine.update_status_file("running")
        self.assertEqual(self.status()["bridge_transport_failures"], 2)

    def test_startup_has_no_completed_cycle_timings_and_resets_transport_counter(self):
        self.engine.update_status_file("running")
        status = self.status()
        self.assertIsNone(status["last_cycle_duration_seconds"])
        self.assertEqual(status["slowest_step"], {"name": None, "seconds": None})
        self.assertEqual(status["bridge_transport_failures"], 0)

        with (mock.patch.object(brain_endpoints, "bridge_mode", return_value=True),
              mock.patch.object(brain_endpoints, "chat",
                                side_effect=brain_endpoints.BrainUnavailable("fixture"))):
            self.assertIsNone(self.engine._gen_text([], max_tokens=8, temperature=0.0, organ="coder"))
        self.engine.update_status_file("running")
        self.assertEqual(self.status()["bridge_transport_failures"], 1)

        self.engine = ContinuousAutonomousEngine(store=self.store)
        self.engine.update_status_file("running")
        self.assertEqual(self.status()["bridge_transport_failures"], 0)

    def test_failed_cycle_leaves_previous_completed_timings(self):
        with (mock.patch.dict(os.environ, {"ACE_RATIFICATION_LOOP": "0"}),
              mock.patch.object(self.engine, "verify_and_promote_local_gguf", return_value=False),
              mock.patch.object(self.engine, "check_and_advance_agenda", side_effect=[
                  1, RuntimeError("fixture failure"),
              ]),
              mock.patch.object(self.engine, "_auto_teach_heard_words", return_value=[])):
            self.engine.execute_cycle()
            completed = self.status()
            self.assertEqual(completed["slowest_step"]["name"], "advancing_agenda")
            self.assertGreaterEqual(completed["last_cycle_duration_seconds"],
                                    completed["slowest_step"]["seconds"])
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                self.engine.execute_cycle()

        current = self.status()
        self.assertEqual(current["last_cycle_duration_seconds"],
                         completed["last_cycle_duration_seconds"])
        self.assertEqual(current["slowest_step"], completed["slowest_step"])
