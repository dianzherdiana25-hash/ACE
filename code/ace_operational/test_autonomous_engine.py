"""Tests for mixed technical+language autonomous engine, loopback auth, and honest story projection."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from ace_operational.autonomous_engine import (
    LANGUAGE_CURRICULUM,
    TECHNICAL_CURRICULUM,
    ContinuousAutonomousEngine,
)
from ace_operational.models_backend import ModelRouter, _local_json, _resolve_local_api_key
from ace_operational.speech_acquisition import SpeechDevelopmentEngine
from ace_operational.store import OperationalStore
from ace_operational.story_projector import project_event_to_story


class AutonomousEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-auto-eng-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)

    def test_loopback_bearer_auth_and_remote_block(self) -> None:
        captured_auth: list[str] = []

        class _AuthHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                captured_auth.append(self.headers.get("Authorization", ""))
                body = (
                    b'{"status":"ok"}'
                    if self.path == "/health"
                    else b'{"data":[{"id":"qwen3-4b-instruct-2507"}]}'
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), _AuthHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)

        key_file = Path(self.tmp.name) / "llm.key"
        key_file.write_text("# comment\nsecret-loopback-fixture-123\n", encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "ACE_LLAMA_SERVER_URL": f"http://127.0.0.1:{port}",
                "ACE_LLAMA_API_KEY": "",
                "ACE_LLAMA_API_KEY_FILE": str(key_file),
            },
            clear=False,
        ):
            self.assertEqual(_resolve_local_api_key(), "secret-loopback-fixture-123")
            router = ModelRouter(self.store)
            disc = router.discover_local_gguf(candidate_dirs=[self.ws / "models"])
            self.assertTrue(disc["server_healthy"])
            self.assertEqual(disc["server_models"][0]["id"], "qwen3-4b-instruct-2507")
            self.assertEqual(captured_auth, ["Bearer secret-loopback-fixture-123", "Bearer secret-loopback-fixture-123"])

            with self.assertRaises(ValueError):
                _local_json("https://api.example.com/v1/models")

    def test_persistent_cycle_count_and_mixed_curriculum_interleaving(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        c1 = eng.execute_cycle()
        self.assertEqual(c1["cycle"], 1)
        self.assertEqual(c1["track"], "language_speech")

        c2 = eng.execute_cycle()
        c3 = eng.execute_cycle()
        self.assertEqual(c2["cycle"], 2)
        self.assertEqual(c2["track"], "language")
        self.assertEqual(c3["cycle"], 3)
        self.assertEqual(c3["track"], "technical")

        # Restart simulation: cycle counter and learned skills survive reopen
        self.store.close()
        reopened = OperationalStore(self.ws)
        self.addCleanup(reopened.close)
        eng2 = ContinuousAutonomousEngine(store=reopened, workspace=self.ws)
        self.assertEqual(eng2.cycle_count, 3)

        c4 = eng2.execute_cycle()
        self.assertEqual(c4["cycle"], 4)
        self.assertEqual(c4["track"], "language")

        skills = {s["name"] for s in reopened.list_skills()}
        self.assertIn("keterampilan_berbicara_bertahap_id", skills)
        self.assertIn(TECHNICAL_CURRICULUM[0]["skill_name"], skills)
        self.assertIn(LANGUAGE_CURRICULUM[0]["skill_name"], skills)

    def test_all_technical_curriculum_modules_verify_and_promote_frontier(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        for idx, expected in enumerate(TECHNICAL_CURRICULUM):
            res = eng.execute_continuous_technical_learning()
            self.assertIsNotNone(res, f"curriculum step {idx} returned None")
            self.assertTrue(res["passed"])
            self.assertEqual(res["skill"], expected["skill_name"])
            self.assertTrue((self.ws / expected["target_file"]).is_file())

        frontier = {f["capability_id"]: f for f in self.store.list_frontier()}
        for item in TECHNICAL_CURRICULUM:
            self.assertEqual(frontier[item["capability_id"]]["status"], "KNOWN_AND_TESTED")
            self.assertTrue(bool(frontier[item["capability_id"]]["evidence_ref"]))

    def test_dynamic_technical_practice_repair_and_fail_closed_gap(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        for _ in TECHNICAL_CURRICULUM:
            eng.execute_continuous_technical_learning()

        healthy_hc = {
            "mode": "local",
            "offline_mode": False,
            "active_backend": "local-gguf-server:http://127.0.0.1:8000",
            "local_gguf": {"server_healthy": True, "ready": True, "valid_models": [], "corrupted_models": []},
        }

        # 1. Failing script triggers repair attempt and passes on attempt 2
        responses = iter([
            {"text": "Deteksi siklus graf dengan DFS dan uji assert pada graf valid serta siklik."},
            {"text": "```python\ndef cek_nol(x):\n    return 10 / x\nif __name__ == '__main__':\n    assert cek_nol(0) is None\n```"},
            {"text": "```python\ndef cek_nol(x: float) -> float | None:\n    if x == 0:\n        return None\n    return 10.0 / x\nif __name__ == '__main__':\n    assert cek_nol(2) == 5.0\n    assert cek_nol(0) is None\n    print('TECH_PRACTICE_VERIFIED_OK')\n```"},
        ])
        with patch.object(eng.models, "health_check", return_value=healthy_hc), patch.object(
            eng.models, "generate_text", side_effect=lambda *_args, **_kwargs: next(responses)
        ):
            ok_res = eng._generate_dynamic_technical_practice()
        self.assertIsNotNone(ok_res)
        self.assertTrue(ok_res["passed"])
        self.assertTrue(Path(ok_res["script"]).is_file())
        self.assertTrue(eng.tech_corpus_file.is_file())

        # 2. Unsafe AST (eval) fails closed and records real gap
        bad_responses = iter([
            {"text": "Buat fungsi evaluator aman tanpa eval dengan uji assert."},
            {"text": "```python\ndef unsafe(s):\n    return eval(s)\nif __name__ == '__main__':\n    assert unsafe('1+1') == 2\n```"},
            {"text": "```python\ndef unsafe(s):\n    return eval(s)\nif __name__ == '__main__':\n    assert unsafe('1+1') == 2\n```"},
        ])
        with patch.object(eng.models, "health_check", return_value=healthy_hc), patch.object(
            eng.models, "generate_text", side_effect=lambda *_args, **_kwargs: next(bad_responses)
        ):
            bad_res = eng._generate_dynamic_technical_practice()
        self.assertIsNotNone(bad_res)
        self.assertFalse(bad_res["passed"])
        gaps = self.store.list_gaps()
        self.assertTrue(any(g["error_type"] == "DYNAMIC_TECH_PRACTICE_FAILED" for g in gaps))

    def test_consolidated_vocab_batch_and_honest_story_projection(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        healthy_hc = {
            "mode": "local",
            "offline_mode": False,
            "active_backend": "local-gguf-server:http://127.0.0.1:8000",
            "local_gguf": {"server_healthy": True, "ready": True, "valid_models": [], "corrupted_models": []},
        }
        vocab_output = (
            "embun: titik air di pagi hari\n"
            "pelita: lampu kecil penerang malam\n"
            "rimba: hutan belantara yang lebat\n"
            "samudra: lautan yang sangat luas\n"
        )
        with patch.object(eng.models, "health_check", return_value=healthy_hc), patch.object(
            eng.models, "generate_text", return_value={"text": vocab_output}
        ):
            learned = eng._explore_vocabulary_batch(batch_size=10)
        self.assertEqual(len(learned), 4)

        skill_events = [e for e in self.store.list_events(limit=50) if e["kind"] == "skill_learned"]
        self.assertEqual(len(skill_events), 1)
        story = project_event_to_story(skill_events[0])
        self.assertIn("4 kosakata bahasa Indonesia", story["story_text"])
        self.assertNotIn("dua kasus uji", story["story_text"])

        tech_story = project_event_to_story({
            "kind": "skill_learned",
            "status": "COMPLETED",
            "verification_passed": True,
            "technical_detail": {
                "skill_name": "algoritma_dijkstra_rute_terpendek",
                "title_id": "Algoritma Dijkstra",
                "learning_kind": "technical_curriculum",
            },
        })
        self.assertIn("Algoritma Dijkstra", tech_story["story_text"])
        self.assertNotIn("dua kasus uji", tech_story["story_text"])

    def test_stage4_word_bound_accepts_complete_gguf_answers(self) -> None:
        speech = SpeechDevelopmentEngine(self.store)
        long_valid = " ".join(["kalimat"] * 170) + " ace"
        res = speech.verify_utterance(
            utterance=long_valid,
            user_text="Jelaskan bagaimana kalimat ini disusun dengan baik?",
            stage_id=4,
            latest_task=None,
            offline_mode=True,
            recent_assistant_texts=[],
        )
        self.assertTrue(res["bounds_ok"])
        self.assertTrue(res["passed"])

    def test_cli_ace_engine_once_with_env_workspace(self) -> None:
        env_ws = Path(self.tmp.name) / "cli_env_ws"
        repo_root = Path(__file__).resolve().parents[2]
        env = {**os.environ, "ACE_WORKSPACE": str(env_ws), "PYTHONPATH": str(repo_root / "code")}
        proc = subprocess.run(
            [sys.executable, str(repo_root / "ace.py"), "engine", "--once", "--interval", "0.2"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        out = json.loads(proc.stdout)
        self.assertEqual(out["cycle"], 1)
        self.assertTrue((env_ws / "autonomous_engine.status.json").is_file())


if __name__ == "__main__":
    unittest.main()
