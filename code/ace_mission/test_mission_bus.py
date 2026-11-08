"""Unit tests for ACE Mission Bus (ace.mission.v1).

Tests follow TDD: initially run to verify failure before implementation is wired.
"""
import json
from pathlib import Path
import tempfile
import unittest


class TestMissionBus(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.db_path = self.workspace / "mission_bus.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mission_schema_validation(self):
        """ace.mission.v1 schema must enforce all required fields."""
        from ace_mission.schema import validate_mission, MissionSchemaError

        valid_mission = {
            "schema_version": "ace.mission.v1",
            "id": "mission_test_001",
            "goal": "Expand grammar to solve parity with run-length encoding",
            "hypothesis": "Composite multi-task predicates resolve modular parity bottleneck",
            "task_family_ids": ["parity_runlength", "modular_congruence"],
            "inputs": [{"path": "code/ace_runtime/engine.py", "hash": "sha256:abc"}],
            "budget": {"time_sec": 30, "max_candidates": 5},
            "acceptance": {"metric": "validation_accuracy", "threshold": 0.85, "comparator": "baseline_35_lib"},
            "forbidden": ["code/ace_host_controller/evaluator.py", "tests/sealed_bank.py"],
            "deadline": "2026-11-08T12:00:00Z",
            "status": "PENDING",
        }
        validated = validate_mission(valid_mission)
        self.assertEqual(validated["id"], "mission_test_001")

        # Missing required field must raise MissionSchemaError
        invalid_mission = valid_mission.copy()
        del invalid_mission["hypothesis"]
        with self.assertRaises(MissionSchemaError):
            validate_mission(invalid_mission)

    def test_mission_bus_lifecycle_and_hash_chain(self):
        """Bus supports enqueue, claim (next), submit, status, and verifies cryptographic hash chain."""
        from ace_mission.bus import MissionBus

        bus = MissionBus(self.db_path)
        m_id = bus.create_mission(
            goal="Repair modular remainder admission",
            hypothesis="Modulo-4 residue tracker fixes 4:1 ratio failure",
            task_family_ids=["ratio_4_1"],
            inputs=[],
            budget={"time_sec": 15, "max_candidates": 3},
            acceptance={"metric": "admission_rate", "threshold": 1.0, "comparator": "DFA"},
            forbidden=["code/ace_host_controller/sealed_evaluator_v3.py"],
        )
        self.assertTrue(m_id.startswith("mission_"))

        # Claim mission via next
        claimed = bus.next_mission(agent_id="advisor_01")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], m_id)
        self.assertEqual(claimed["status"], "CLAIMED")

        # Submit artifact
        artifact_file = self.workspace / "candidate_patch.py"
        artifact_file.write_text("# Candidate implementation\ndef candidate(): return True\n", encoding="utf-8")

        receipt = bus.submit_mission(
            mission_id=m_id,
            artifact_path=str(artifact_file),
            agent_id="advisor_01",
            provenance="ADVISOR_AGENT"
        )
        self.assertEqual(receipt["status"], "SUBMITTED")
        self.assertEqual(receipt["provenance"], "ADVISOR_AGENT")

        # Verify hash chain integrity
        self.assertTrue(bus.verify_hash_chain())

    def test_generator_publishes_at_least_5_distinct_missions(self):
        """MissionGenerator generates >= 5 distinct missions derived from failure diagnoses without duplicates."""
        from ace_mission.generator import MissionGenerator
        from ace_mission.bus import MissionBus

        bus = MissionBus(self.db_path)
        generator = MissionGenerator(bus)

        diagnostics = [
            {"type": "INFORMATION_SHORTAGE", "details": "Negative examples lack count-matching, hiding order failures."},
            {"type": "TOOL_SHORTAGE", "details": "Grammar lacks graph traversal operators, causing 50% random score."},
            {"type": "METHOD_SHORTAGE", "details": "Single-clause mutation saturated; composite dispatch needed."},
            {"type": "BUDGET_EXHAUSTION", "details": "Label budget of 16 insufficient without active query allocation."},
            {"type": "ADMISSION_FAILURE", "details": "Single noisy label caused complete task rejection in ratio4."},
            {"type": "DRIFT_VULNERABILITY", "details": "Late-flip semantics accepted without semantic quarantine."},
        ]

        generated_missions = generator.generate_from_diagnostics(diagnostics)
        self.assertGreaterEqual(len(generated_missions), 5)

        # Check all mission IDs and goals are unique
        ids = [m["id"] for m in generated_missions]
        self.assertEqual(len(ids), len(set(ids)))

        goals = [m["goal"] for m in generated_missions]
        self.assertEqual(len(goals), len(set(goals)))

    def test_anti_idle_and_escalation_on_saturation(self):
        """Repeated identical hypothesis submissions (>= 3 times) trigger ESCALATION and write ESCALATION.md."""
        from ace_mission.bus import MissionBus

        bus = MissionBus(self.db_path, escalation_file=self.workspace / "ESCALATION.md")
        m_id = bus.create_mission(
            goal="Break out of local minimum",
            hypothesis="Re-run static template mutation",
            task_family_ids=["boundary"],
            inputs=[],
            budget={"time_sec": 10, "max_candidates": 1},
            acceptance={"metric": "gain", "threshold": 0.15, "comparator": "baseline"},
            forbidden=[]
        )

        dummy_artifact = self.workspace / "stagnant_patch.py"
        dummy_artifact.write_text("# static\n", encoding="utf-8")

        # Submit 3 identical attempts
        for i in range(3):
            # Claim & submit
            bus.next_mission(agent_id=f"agent_{i}")
            bus.submit_mission(
                mission_id=m_id,
                artifact_path=str(dummy_artifact),
                agent_id=f"agent_{i}",
                decision="REJECTED",
                provenance="ADVISOR_AGENT"
            )

        status = bus.check_saturation_and_escalate(
            hypothesis="Re-run static template mutation",
            patch_content="# static\n"
        )
        self.assertTrue(status["escalated"])
        self.assertTrue((self.workspace / "ESCALATION.md").exists())
        escalation_text = (self.workspace / "ESCALATION.md").read_text(encoding="utf-8")
        self.assertIn("Pilihan Keputusan untuk Pemilik", escalation_text)

    def test_forbidden_files_enforced(self):
        """Submitting or accessing forbidden files is strictly blocked."""
        from ace_mission.bus import MissionBus, ForbiddenFileViolationError

        bus = MissionBus(self.db_path)
        m_id = bus.create_mission(
            goal="Test forbidden boundaries",
            hypothesis="Forbidden probe",
            task_family_ids=["security"],
            inputs=[],
            budget={"time_sec": 10, "max_candidates": 1},
            acceptance={"metric": "gain", "threshold": 0.15, "comparator": "none"},
            forbidden=["code/ace_host_controller/evaluator.py", "sealed_bank.json"]
        )
        bus.next_mission(agent_id="adversary")

        forbidden_file = self.workspace / "sealed_bank.json"
        forbidden_file.write_text("{}", encoding="utf-8")

        with self.assertRaises(ForbiddenFileViolationError):
            bus.submit_mission(
                mission_id=m_id,
                artifact_path=str(forbidden_file),
                agent_id="adversary",
                provenance="ADVISOR_AGENT"
            )


    def test_automata_and_evolutionary_proposers(self):
        """AutomataProposer and EvolutionaryProposer generate valid typed solutions."""
        from ace_mission.proposers import AutomataProposer, EvolutionaryProposer

        mission = {
            "id": "mission_test_lstar",
            "goal": "Synthesize minimal DFA for parity",
            "task_family_ids": ["parity_runlength"]
        }
        proposer = AutomataProposer()
        res = proposer.propose(mission, self.workspace)
        self.assertEqual(res["provenance"], "ADVISOR_AGENT")
        self.assertTrue(Path(res["artifact_path"]).exists())
        self.assertIn("states", res)

        mission_evo = {
            "id": "mission_test_evo",
            "goal": "Evolve ratio 4:1 condition",
            "task_family_ids": ["ratio_4_1_noise"]
        }
        evo_proposer = EvolutionaryProposer()
        res_evo = evo_proposer.propose(mission_evo, self.workspace)
        self.assertEqual(res_evo["provenance"], "ADVISOR_AGENT")
        self.assertTrue(Path(res_evo["artifact_path"]).exists())
        self.assertIn("accuracy", res_evo)


if __name__ == "__main__":
    unittest.main()

