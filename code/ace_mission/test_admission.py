"""Integration and negative controls for the actual MissionBus submission path."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ace_cognition.reasoning import SCHEMA, canonical, digest
from ace_mission.admission import ARTIFACT_SCHEMA, evaluate_submission
from ace_mission.bus import MissionBus
from ace_mission.schema import MissionSchemaError

ROOT = Path(__file__).resolve().parents[2]


def problem():
    return {"schema": SCHEMA, "id": "add", "goal": "Infer a rule from examples.",
            "train": [{"inputs": {"x": x, "y": y}, "output": x + y}
                      for x, y in ((1, 2), (3, 1), (-1, 2))],
            "validation": [{"inputs": {"x": x, "y": y}, "output": x + y}
                           for x, y in ((4, 2), (-3, 2))]}


ADD = {"op": "add", "args": [{"var": "x"}, {"var": "y"}]}


class MissionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        self.bus = MissionBus(self.ws / "missions.sqlite3")

    def mission(self, data=None, **kwargs):
        mid = self.bus.create_mission(
            goal="Check provided development observations",
            hypothesis="A typed program fits the supplied data",
            task_family_ids=["arithmetic_xy"], inputs=[], forbidden=[],
            budget=kwargs.get("budget", {"time_sec": 5, "max_candidates": 5000}),
            acceptance=kwargs.get("acceptance", {"metric": "exact_development_fit", "threshold": 1, "comparator": "none"}),
            reasoning_problem=data,
        )
        return self.bus.next_mission("test")

    def artifact(self, data, program=ADD, **changes):
        artifact = {"schema": ARTIFACT_SCHEMA, "problem_digest": digest(data), "program": program}
        artifact.update(changes)
        path = self.ws / "candidate.json"
        path.write_text(canonical(artifact), encoding="utf-8")
        return path

    def submit(self, mission, path, decision="ACCEPTED"):
        return self.bus.submit_mission(mission["id"], str(path), "test", decision=decision)

    def test_honest_ir_staged_with_bound_replay_and_source(self):
        data = problem()
        mission = self.mission(data)
        path = self.artifact(data)
        with patch("ace_component_synthesis.component_synthesizer.ComponentNode.compile_to_callable", side_effect=AssertionError("source execution")):
            result = self.submit(mission, path)
        ev = result["evaluation"]
        self.assertEqual(result["requested_decision"], "ACCEPTED")
        self.assertEqual(result["decision"], "STAGED_EMPIRICAL")
        self.assertEqual(ev["observations_evaluated"], 5)
        self.assertEqual(ev["primitive_operations"], 5)
        self.assertEqual(ev["artifact_sha"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(ev["program_digest"], digest(ADD))
        self.assertEqual(len(ev["evaluator_digest"]), 64)
        self.assertEqual(ev["scientific_status"], "NOT_ASSESSED")
        self.assertFalse(ev["independent_confirmation"])
        self.assertFalse(ev["candidate_python_executed"])
        self.assertTrue(self.bus.verify_hash_chain())

    def test_python_and_success_text_never_authorize_acceptance(self):
        mission = self.mission()
        path = self.ws / "candidate.py"
        marker = self.ws / "executed"
        path.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n# ACCEPTED 100% signed receipt")
        result = self.submit(mission, path)
        self.assertEqual(result["decision"], "PENDING_EVALUATION")
        self.assertEqual(result["evaluation"]["observations_evaluated"], 0)
        self.assertFalse(marker.exists())

    def test_generic_ir_cannot_supply_its_own_problem(self):
        data = problem()
        result = self.submit(self.mission(), self.artifact(data))
        self.assertEqual(result["decision"], "PENDING_EVALUATION")

    def test_actual_wrong_program_counterexample(self):
        data = problem()
        result = self.submit(self.mission(data), self.artifact(data, {"const": 1}))
        self.assertEqual(result["decision"], "REJECTED")
        self.assertEqual(result["evaluation"]["counterexample"]["actual"], 1)

    def test_changed_validation_rejects_previously_fitting_program(self):
        data = problem()
        data["validation"][0]["output"] += 1
        result = self.submit(self.mission(data), self.artifact(data))
        self.assertEqual(result["decision"], "REJECTED")
        self.assertEqual(result["evaluation"]["counterexample"]["split"], "validation")

    def test_problem_digest_tamper_rejected(self):
        data = problem()
        result = self.submit(self.mission(data), self.artifact(data, problem_digest="0" * 64))
        self.assertEqual(result["decision"], "REJECTED")
        self.assertEqual(result["evaluation"]["observations_evaluated"], 0)

    def test_forged_receipt_and_source_payload_rejected(self):
        for payload in ({"receipt": {"passed": True}}, {"source": "import os"}):
            with self.subTest(payload=payload):
                data = problem()
                result = self.submit(self.mission(data), self.artifact(data, **payload))
                self.assertEqual(result["decision"], "REJECTED")

    def test_unknown_operator_and_deep_tree_rejected(self):
        deep = copy.deepcopy(ADD)
        for _ in range(5):
            deep = {"op": "add", "args": [deep, {"const": 1}]}
        for program in ({"op": "exec", "args": []}, deep, {"var": "__builtins__"}):
            with self.subTest(program=program):
                data = problem()
                result = self.submit(self.mission(data), self.artifact(data, program))
                self.assertEqual(result["decision"], "REJECTED")

    def test_boolean_is_not_integer_one(self):
        data = problem()
        for split in ("train", "validation"):
            for row in data[split]:
                row["output"] = 1
        result = self.submit(self.mission(data), self.artifact(data, {"const": True}))
        self.assertEqual(result["decision"], "REJECTED")

    def test_operation_budget_stops_replay(self):
        data = problem()
        mission = self.mission(data, budget={"time_sec": 5, "max_candidates": 1, "max_primitive_operations": 1})
        result = self.submit(mission, self.artifact(data))
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertEqual(result["evaluation"]["primitive_operations"], 1)
        self.assertEqual(result["evaluation"]["observations_evaluated"], 1)

    def test_wall_budget_stops_replay(self):
        data = problem()
        mission = self.mission(data, budget={"time_sec": 1e-300, "max_candidates": 1})
        result = self.submit(mission, self.artifact(data))
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertEqual(result["evaluation"]["reason"], "WALL_BUDGET")

    def test_bad_budgets_cannot_stage(self):
        for seconds, operations, candidates in ((float("inf"), 30, 1), (5, 0, 1), (5, 30, 0), (True, 30, 1)):
            with self.subTest(seconds=seconds, operations=operations, candidates=candidates):
                data = problem()
                with self.assertRaises(MissionSchemaError):
                    self.mission(data, budget={"time_sec": seconds, "max_candidates": candidates,
                                                "max_primitive_operations": operations})

    def test_superiority_criterion_not_satisfied_by_development_fit(self):
        data = problem()
        result = self.submit(self.mission(data, acceptance={"metric": "holdout_gain", "threshold": .1, "comparator": "fresh"}), self.artifact(data))
        self.assertEqual(result["decision"], "PENDING_EVALUATION")

    def test_pending_and_rejected_never_promoted(self):
        data = problem()
        mission = self.mission(data)
        for decision in ("PENDING_EVALUATION", "REJECTED", "STAGNATED"):
            result = self.submit(mission, self.artifact(data), decision)
            self.assertEqual(result["decision"], decision)

    def test_unknown_success_status_rejected_without_submission(self):
        data = problem()
        with self.assertRaises(ValueError):
            self.submit(self.mission(data), self.artifact(data), "SCIENTIFIC_GO")
        self.assertEqual(self.bus.status()["total_submissions"], 0)

    def test_size_limit_rejects_without_reading_entire_artifact(self):
        mission = self.mission()
        path = self.ws / "large.py"
        path.write_bytes(b"x" * 65_537)
        with self.assertRaises(ValueError):
            self.submit(mission, path)
        self.assertEqual(self.bus.status()["total_submissions"], 0)

    def test_terminal_and_overlapping_data_rejected_at_creation(self):
        for mode in ("terminal", "overlap"):
            data = problem()
            if mode == "terminal":
                data["terminal"] = []
            else:
                data["validation"][0] = data["train"][0]
            with self.assertRaises(MissionSchemaError):
                self.mission(data)

    def test_receipt_survives_separate_process_and_artifact_mutation(self):
        data = problem()
        mission = self.mission(data)
        path = self.artifact(data)
        expected = self.submit(mission, path)["evaluation"]
        path.write_text("changed after submission")
        cp = subprocess.run([sys.executable, "-c", "import json,sys; from pathlib import Path; from ace_mission.bus import MissionBus; print(json.dumps(MissionBus(Path(sys.argv[1])).evaluation_history(sys.argv[2])))",
                             str(self.bus.db_path), mission["id"]], capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(cp.stdout), [expected])
        self.assertNotEqual(expected["artifact_sha"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_historical_rows_preserved_and_labelled_unevaluated(self):
        mission = self.mission()
        path = self.ws / "old.py"
        path.write_text("pass")
        self.submit(mission, path)
        with self.bus._get_connection() as conn:
            conn.execute("DELETE FROM mission_evaluations")
            # A historical bus emitted events without new evaluation bindings.
            conn.execute("DELETE FROM hash_chain WHERE event_type = 'MISSION_SUBMITTED'")
            conn.execute("UPDATE submissions SET decision = 'ACCEPTED'")
            before = [tuple(r) for r in conn.execute("SELECT * FROM submissions")]
        reopened = MissionBus(self.bus.db_path)
        with reopened._get_connection() as conn:
            after = [tuple(r) for r in conn.execute("SELECT * FROM submissions")]
        self.assertEqual(before, after)
        self.assertEqual(reopened.status()["historical_unevaluated_submissions"], 1)
        self.assertEqual(reopened.evaluation_history(mission["id"]), [])

    def test_receipt_tamper_is_detected_on_read_and_status(self):
        data = problem()
        mission = self.mission(data)
        self.submit(mission, self.artifact(data))
        with self.bus._get_connection() as conn:
            conn.execute("UPDATE mission_evaluations SET receipt_json = '{}' ")
        self.assertFalse(self.bus.status()["evaluation_receipts_valid"])
        with self.assertRaises(ValueError):
            self.bus.evaluation_history(mission["id"])

    def test_duplicate_json_keys_rejected(self):
        data = problem()
        path = self.artifact(data)
        path.write_text(path.read_text().replace('"program":', '"program":null,"program":'))
        result = self.submit(self.mission(data), path)
        self.assertEqual(result["decision"], "REJECTED")

    def test_worker_legacy_proposal_cannot_claim_label_savings(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mission_worker", ROOT / "tools/ace_mission_worker.py")
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        path, decision, reason = worker.solve_mission({"id": "probe", "goal": "Query", "hypothesis": "Unknown", "task_family_ids": ["active_query_boundary"]}, self.ws)
        self.assertEqual(decision, "PENDING_EVALUATION")
        self.assertNotIn("4x", reason)
        self.assertTrue(path.exists())

    def test_worker_structured_problem_then_bus_replay(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mission_worker", ROOT / "tools/ace_mission_worker.py")
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        data = problem()
        mission = self.mission(data)
        path, decision, _ = worker.solve_mission(mission, self.ws)
        self.assertEqual(decision, "STAGED_EMPIRICAL")
        self.assertEqual(self.submit(mission, path, decision)["decision"], "STAGED_EMPIRICAL")

    def test_worker_small_search_budget_abstains(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mission_worker", ROOT / "tools/ace_mission_worker.py")
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        mission = self.mission(problem(), budget={"time_sec": 5, "max_candidates": 1})
        path, decision, reason = worker.solve_mission(mission, self.ws)
        self.assertEqual(decision, "INCONCLUSIVE")
        self.assertEqual(reason, "INSUFFICIENT_SEARCH_BUDGET")
        self.assertEqual(self.submit(mission, path, decision)["decision"], "INCONCLUSIVE")

    def test_one_shot_cli_synthesizes_and_records_actual_bus_result(self):
        source = self.ws / "problem.json"
        source.write_text(canonical(problem()))
        cp = subprocess.run([sys.executable, str(ROOT / "tools/ace_mission_worker.py"),
                             "--workspace", str(self.ws), "--problem", str(source)],
                            capture_output=True, text=True, timeout=15, check=True)
        self.assertIn("Bus decision: STAGED_EMPIRICAL", cp.stdout)
        status = MissionBus(self.ws / "mission_bus.sqlite3").status()
        self.assertEqual(status["submission_decisions"], {"STAGED_EMPIRICAL": 1})
        self.assertEqual(status["evaluated_submissions"], 1)
        self.assertTrue(status["evaluation_receipts_valid"])


if __name__ == "__main__":
    unittest.main()
