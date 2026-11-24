"""End-to-end tests for Git Portable Dispatch, CLI Agent Bridge, Work-Order Verifier, and Goal DAG Tick Loops."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
from threading import Thread
import tempfile
import unittest

from ace_operational.agent_cli_bridge import discover_installed_cli_agents, run_local_cli_agent
from ace_operational.memory_bridge import ConversationalMemoryManager
from ace_operational.orchestrator_playbook import create_goal, tick_goal
from ace_operational.portable_dispatch import export_dispatch_bundle, ingest_return_envelope
from ace_operational.store import OperationalStore


class _MockFbHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        html = """<!doctype html><html><head><title>Reels Composer</title></head><body>
        <input type="file" accept="video/*" />
        <textarea name="description"></textarea>
        <button aria-label="Publish" onclick="document.querySelector('[data-testid=reels_published_banner]').textContent='PUBLISHED_OK'">Publish</button>
        <div data-testid="reels_published_banner">WAIT</div>
        </body></html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PortableDispatchAndDagTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-v3-dag-")
        self.ws = Path(self._tmp.name) / "ws"
        self.store = OperationalStore(self.ws)
        self.memory = ConversationalMemoryManager(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_video_reels_full_multi_stage_dag_via_portable_dispatch_and_verifier(self) -> None:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg / ffprobe tidak tersedia")

        self.store.register_agent(agent_id="gemini-res", vendor="gemini", roles=["researcher"], transport="git_handover")
        self.store.register_agent(agent_id="muse-dir", vendor="muse.ai", roles=["creator"], transport="web_relay")

        goal = create_goal(
            self.store,
            title="Reels Promo Otomatis",
            user_request="Buat video Reels 9:16 hook kuat dan siapkan upload Facebook",
            domain="video_reels",
            publish_mode="auto",
            min_quality_score_bp=8500,
            stage_configs={
                "PUBLISH_REELS": {"dry_run": True},
            },
        )
        gid = goal["goal_id"]
        wo0_id = goal["stages"][0]["work_order_id"]

        # 1. Export portable dispatch bundle for stage 0 (TREND_RESEARCH)
        exp = export_dispatch_bundle(
            self.store,
            self.memory,
            work_order_id=wo0_id,
            agent_id="gemini-res",
            vendor="gemini",
        )
        self.assertTrue(Path(exp["json_path"]).is_file())
        self.assertTrue(Path(exp["md_path"]).is_file())

        # 2. Simulate bad return with ungrounded claim -> verifier rejects & records REVISION_NEEDED
        ret_dir = self.ws / "handover" / "returns"
        ret_dir.mkdir(parents=True, exist_ok=True)
        bad_ret = ret_dir / f"{wo0_id}_bad.json"
        bad_ret.write_text(json.dumps({
            "schema": "ace.return_envelope.v1",
            "work_order_id": wo0_id,
            "agent": "gemini-res",
            "vendor": "gemini",
            "result": {"claims": ["Tanpa sumber"], "sources": []},
        }), encoding="utf-8")
        ing_bad = ingest_return_envelope(self.store, self.memory, return_path=bad_ret)
        self.assertFalse(ing_bad["verification"]["passed"])
        self.assertEqual(ing_bad["verification"]["work_order"]["status"], "REVISION_NEEDED")

        # 3. Good grounded research return -> advances to stage 1 (STRATEGY_AND_SCRIPT)
        good_ret = ret_dir / f"{wo0_id}.json"
        good_ret.write_text(json.dumps({
            "schema": "ace.return_envelope.v1",
            "work_order_id": wo0_id,
            "agent": "gemini-res",
            "vendor": "gemini",
            "result": {
                "claims": [{"claim": "Hook pertanyaan 3 detik meningkatkan retensi", "source_ref": "src_yt_2026"}],
                "sources": [{
                    "id": "src_yt_2026",
                    "observed_at": "2026-11-21T00:00:00Z",
                    "content": "Laporan benchmark video vertikal membuktikan pertanyaan pembuka tiga detik menekan penonton kabur di awal.",
                }],
            },
            "new_memories": ["Tren hook 3 detik sangat efektif untuk Reels edukasi"],
        }), encoding="utf-8")
        ing_good = ingest_return_envelope(self.store, self.memory, return_path=good_ret)
        self.assertTrue(ing_good["verification"]["passed"], ing_good)
        g_after_0 = self.store.get_goal(gid)
        self.assertEqual(g_after_0["current_stage_index"], 1)

        # 4. Stage 1 (STRATEGY_AND_SCRIPT): Submit strong Reels script via local CLI bridge mock!
        wo1_id = g_after_0["stages"][1]["work_order_id"]

        def fake_cli_runner(cmd, *, cwd, timeout=120):
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="```json\n" + json.dumps({
                    "schema": "ace.cli_submission.v1",
                    "work_order_id": wo1_id,
                    "result": {
                        "title": "Rahasia Hook 3 Detik Reels",
                        "promise_terms": ["hook", "detik", "reels"],
                        "action_terms": ["lihat", "coba", "simpan"],
                        "cta": "Simpan dan ikuti sekarang!",
                        "source_ref": "src_yt_2026",
                        "scenes": [
                            {"id": "sc_hook", "source_ref": "src_yt_2026", "narration": "Kenapa 3 detik pertama menentukan Reels? Lihat cara ini!", "duration_ms": 3500, "has_visual_action": True},
                            {"id": "sc_isi", "source_ref": "src_yt_2026", "narration": "Coba tampilkan hook visual cepat.", "duration_ms": 3500, "has_visual_action": True},
                            {"id": "sc_cta", "source_ref": "src_yt_2026", "narration": "Simpan dan ikuti tips selanjutnya!", "duration_ms": 3000, "has_visual_action": True},
                        ],
                        "facts": [{"id": "f1", "text": "Hook 3 detik menaikkan retensi awal", "source_ref": "src_yt_2026", "approved": True}],
                        "tags": ["reels", "kreator"],
                    },
                }) + "\n```",
                stderr="",
            )

        cli_res = run_local_cli_agent(
            self.store,
            self.memory,
            cli_name="gemini",
            work_order_id=wo1_id,
            custom_cmd=["mock-gemini", "{prompt}"],
            runner=fake_cli_runner,
        )
        self.assertTrue(cli_res["ok"], cli_res)

        # Tick Goal DAG sequentially through:
        # tick 1 -> advances stage 1 (COMPLETED wo1) -> stage 2 (RENDER_9_16_MP4)
        # tick 2 -> runs ffmpeg render 9:16 MP4 -> stage 3 (FINAL_MEDIA_QA)
        # tick 3 -> runs evaluate_reels_quality (with ffprobe) -> stage 4 (PUBLISH_REELS dry_run)
        # tick 4 -> completes Goal!
        for _ in range(4):
            t_res = tick_goal(self.store, self.memory, goal_id=gid, workspace=self.ws)
        final_goal = self.store.get_goal(gid)
        self.assertEqual(final_goal["status"], "COMPLETED", t_res)
        self.assertTrue(Path(final_goal["metadata"]["rendered_bundle"]["video_path"]).is_file())

    def test_discover_cli_agents_does_not_fail_when_missing(self) -> None:
        clis = discover_installed_cli_agents()
        self.assertEqual({c["name"] for c in clis}, {"gemini", "claude", "codex"})
        missing = run_local_cli_agent(
            self.store,
            cli_name="nonexistent_ai_cli_bin_xyz",
            work_order_id=create_goal(self.store, title="t", user_request="u")["stages"][0]["work_order_id"],
        )
        self.assertEqual(missing["verdict"], "CLI_NOT_INSTALLED")


if __name__ == "__main__":
    unittest.main()
