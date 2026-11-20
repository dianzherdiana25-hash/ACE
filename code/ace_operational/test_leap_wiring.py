"""Tes wiring lompatan EVO 0031–0040 (leap_wiring) pada stub engine
dengan OperationalStore nyata di workspace sementara."""
import json
import tempfile
import unittest
from pathlib import Path

from ace_operational import leap_wiring
from ace_operational.store import OperationalStore


class _StubEngine:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.store = OperationalStore(workspace=workspace)
        self.cycle_count = 10
        self._lang_cursor = 3
        self._tech_cursor = 5
        self._bridge_transport_failures = 2


def _episode(seq: int, rid: str, topic: str, text: str) -> str:
    # Format rantai CognitiveMemory yang sebenarnya: seq/prev/event/hash.
    return json.dumps({"seq": seq, "prev": f"h{seq - 1}", "hash": f"h{seq}",
                       "event": {"type": "record", "record": {
                           "id": rid, "kind": "episodic",
                           "content": {"topic": topic, "text": text},
                           "source_refs": [f"src:{rid}"],
                       }}})


class LeapWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)
        mem_dir = self.ws / "cognitive_memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "memory.jsonl").write_text("\n".join([
            _episode(1, "ep1", "bahasa", "morfologi imbuhan berlari"),
            _episode(2, "ep2", "bahasa", "morfologi imbuhan menulis"),
            _episode(3, "ep3", "teknik", "csv dedup pipeline"),
        ]) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.engine.store.close()
        self._tmp.cleanup()

    def test_checkpoint_chain_grows(self) -> None:
        out = leap_wiring.step_checkpoint(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertGreaterEqual(out["chain_len"], 1)
        self.assertTrue((self.ws / "step_checkpoints.jsonl").is_file())

    def test_recall_consolidates_and_probes(self) -> None:
        out = leap_wiring.step_recall(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertTrue((self.ws / "semantic_memory.json").is_file())
        self.assertTrue((self.ws / "recall_probe.jsonl").is_file())
        self.assertIn("probe", out)

    def _seed_gap(self) -> None:
        self.engine.store.record_gap(
            source_task_id="t-gap", error_type="skill_missing",
            missing_skill_or_tool="morfologi imbuhan",
            description_id="morfologi imbuhan berlari menulis",
            reproduction_ref="probe:morfologi")

    def test_recall_semantic_channel_when_embedder_available(self) -> None:
        self._seed_gap()

        def stub_embedder(text: str):
            return [1.0, 0.1] if "morfologi" in text else [0.0, 1.0]

        orig = leap_wiring._bridge_embedder
        leap_wiring._bridge_embedder = lambda: stub_embedder
        try:
            out = leap_wiring.step_recall(self.engine)
        finally:
            leap_wiring._bridge_embedder = orig
        self.assertEqual(out["status"], "ok")
        self.assertGreaterEqual(out["probe"]["semantic_probes"], 1)

    def test_recall_semantic_failure_fails_closed(self) -> None:
        self._seed_gap()

        def bad_embedder(text: str):
            raise RuntimeError("embedding budget exhausted")

        orig = leap_wiring._bridge_embedder
        leap_wiring._bridge_embedder = lambda: bad_embedder
        try:
            out = leap_wiring.step_recall(self.engine)
        finally:
            leap_wiring._bridge_embedder = orig
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["probe"]["semantic_probes"], 0)

    def test_house_model_and_plan_written(self) -> None:
        out = leap_wiring.step_house(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertTrue((self.ws / "house_model.json").is_file())
        self.assertTrue((self.ws / "cycle_plan.json").is_file())

    def test_director_folds_duplicates_and_queues(self) -> None:
        def _proposal(title: str) -> str:
            task = self.engine.store.create_task(
                kind="director_proposal", title_id=title,
                user_request="rasional uji", normalized_goal=title,
                model_backend="groq/openai/gpt-oss-120b", priority=5,
                checkpoint={"stage": "director_review",
                            "proposal": {"title": title,
                                         "rationale": "rasional uji",
                                         "based_on": ["gap_uji_1"]}},
                hold_for_review=True)
            return task["task_id"]

        keeper = _proposal("Usulan A")
        dup = _proposal("Usulan A lagi")
        out = leap_wiring.step_director(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["folded_duplicates"], 1)
        self.assertEqual(self.engine.store.get_task(dup)["status"], "CANCELLED")
        self.assertEqual(self.engine.store.get_task(keeper)["status"],
                         "WAITING_FOR_DEPENDENCY")
        queue = json.loads((self.ws / "evolution_queue.json").read_text())
        self.assertEqual(len(queue), 1)

    def test_practice_schedule_written(self) -> None:
        out = leap_wiring.step_practice(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertTrue((self.ws / "practice_schedule.json").is_file())
        self.assertTrue((self.ws / "leap_state.json").is_file())

    def test_projects_created(self) -> None:
        out = leap_wiring.step_projects(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertTrue((self.ws / "projects" / "evo0031-recall-repair.json").is_file())

    def test_self_model_and_hypothesis(self) -> None:
        out = leap_wiring.step_self(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertTrue((self.ws / "self_model.json").is_file())
        hyps = json.loads((self.ws / "hypotheses.json").read_text())
        self.assertIn("recall-pool-cleanup", hyps)

    def test_memory_hygiene_audit_writes_artifact_with_duplicates_orphans_stale(self) -> None:
        from tools import memory_hygiene_audit as mha

        log_path = self.ws / "cognitive_memory" / "memory.jsonl"
        before_e1 = mha.compute_entry_hash(
            mha.GENESIS_PREV,
            {
                "type": "record",
                "record": {
                    "id": "ep-clean",
                    "kind": "fact",
                    "content": "fakta bersih tentang spool",
                    "source": {"kind": "verify", "ref": "probe:ok"},
                    "evidence_refs": ["probe:ok"],
                    "confidence": 0.9,
                    "created_at": "2020-01-01T00:00:00Z",
                },
            },
        )
        e1 = {
            "seq": 1,
            "prev": mha.GENESIS_PREV,
            "hash": before_e1,
            "event": {
                "type": "record",
                "record": {
                    "id": "ep-clean",
                    "kind": "fact",
                    "content": "fakta bersih tentang spool",
                    "source": {"kind": "verify", "ref": "probe:ok"},
                    "evidence_refs": ["probe:ok"],
                    "confidence": 0.9,
                    "created_at": "2020-01-01T00:00:00Z",
                },
            },
        }
        e2_ev = {
            "type": "record",
            "record": {
                "id": "ep-dup-orphan",
                "kind": "fact",
                "content": "fakta bersih tentang spool",
                "source": {"kind": "verify", "ref": "missing:ref/file.json"},
                "evidence_refs": ["missing:ref/file.json"],
                "confidence": 0.8,
            },
        }
        e2 = {
            "seq": 2,
            "prev": e1["hash"],
            "hash": mha.compute_entry_hash(e1["hash"], e2_ev),
            "event": e2_ev,
        }
        log_path.write_text(json.dumps(e1) + "\n" + json.dumps(e2) + "\n", encoding="utf-8")
        raw_before = log_path.read_bytes()

        self.engine.cycle_count = 50
        out = leap_wiring.step_memory_hygiene_audit(self.engine)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["duplicate_groups"], 1)
        self.assertEqual(out["orphan_refs"], 2)
        self.assertEqual(out["stale_count"], 1)
        self.assertEqual(log_path.read_bytes(), raw_before)

        artifact = json.loads((self.ws / "memory_hygiene.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact["schema"], mha.SCHEMA)
        self.assertEqual(artifact["stale"]["stale_memory_records"], ["ep-clean"])

        # Verifikasi dispatch Step 3d di autonomous_engine.py saat cycle=50 dan ACE_LEAPS=1.
        src = (Path(__file__).resolve().with_name("autonomous_engine.py")).read_text(encoding="utf-8")
        self.assertIn("step_memory_hygiene_audit", src)

    def test_memory_hygiene_audit_no_log_is_fail_closed(self) -> None:
        (self.ws / "cognitive_memory" / "memory.jsonl").unlink()
        out = leap_wiring.step_memory_hygiene_audit(self.engine)
        self.assertEqual(out["status"], "ok")
        artifact = json.loads((self.ws / "memory_hygiene.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact["status"], "no_memory_log")


if __name__ == "__main__":
    unittest.main()
