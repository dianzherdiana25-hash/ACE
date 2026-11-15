"""End-to-end verification tests for ACE Mission 0002 Long-Term Cognitive Memory Bridge.

Covers:
- Explicit & passive Indonesian memory capture, hearsay/coding/self-identity guards,
  and persistence across OperationalStore restart.
- Semantic conflict resolution (supersede) with honest history retrieval and Story Projector cards.
- Sensitivity privacy bounds (internal vs private) and audited tombstone forgetting.
- Evidence-anchored episodic & procedural task recording, frontier promotion, and
  negative-transfer risk surfacing.
- Non-private GGUF prompt conditioning and ACE Web Studio REST endpoints & UI invariants.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_operational.language import ConversationalEngine
from ace_operational.memory_bridge import ConversationalMemoryManager
from ace_operational.store import OperationalStore
from ace_operational.story_projector import project_event_to_story
from ace_operational.web_server import ACEWebServer


def _http_json(url: str, *, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8"))


class MemoryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-mem-bridge-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.engine = ConversationalEngine(self.store)

    def tearDown(self):
        self.store.close()

    def test_explicit_store_passive_capture_guards_and_restart(self):
        r_store = self.engine.handle_user_message("Ingat bahwa warna favoritku adalah biru laut")
        self.assertEqual(r_store["intent_frame"]["intent"], "MEMORY_STORE")
        self.assertIn("biru laut", r_store["reply"])

        r_name = self.engine.handle_user_message("Namaku Dian")
        self.assertEqual(r_name["intent_frame"]["intent"], "GENERAL_CONVERSATION")
        r_city = self.engine.handle_user_message("Aku tinggal di Bandung")
        self.assertEqual(r_city["intent_frame"]["intent"], "GENERAL_CONVERSATION")

        # Guards: assistant identity, hearsay, and slang "lupa" must never misroute
        r_id = self.engine.handle_user_message("Siapa namamu?")
        self.assertNotEqual(r_id["intent_frame"]["intent"], "MEMORY_RECALL")
        self.assertIn("ACE", r_id["reply"])

        self.engine.handle_user_message("Kata teman aku tinggal di Mars")
        self.assertEqual(self.engine.memory.recall_memories("Mars")["returned"], 0)

        r_slang = self.engine.handle_user_message("gmn kbr lu skrg, blm lupa kan?")
        self.assertEqual(r_slang["intent_frame"]["intent"], "GENERAL_CONVERSATION")

        # Close and reopen store + engine to prove persistence across process restart
        self.store.close()
        self.store = OperationalStore(self.ws)
        reopened = ConversationalEngine(self.store)

        q_name = reopened.handle_user_message("Siapa namaku?")
        self.assertEqual(q_name["intent_frame"]["intent"], "MEMORY_RECALL")
        self.assertIn("Dian", q_name["reply"])

        q_city = reopened.handle_user_message("Di mana aku tinggal?")
        self.assertIn("Bandung", q_city["reply"])

        q_color = reopened.handle_user_message("Apa warna favoritku?")
        self.assertIn("biru laut", q_color["reply"])

        q_self = reopened.handle_user_message("Apa yang kamu ingat tentang aku?")
        self.assertIn("Dian", q_self["reply"])
        self.assertIn("Bandung", q_self["reply"])

    def test_conflict_superseding_and_story_cards(self):
        r1 = self.engine.handle_user_message("Jadwal belanjaku tiap Minggu")
        self.assertEqual(r1["intent_frame"]["intent"], "GENERAL_CONVERSATION")
        self.assertIsNone(r1["task"])

        r2 = self.engine.handle_user_message("Sekarang jadwal belanjaku pindah ke Sabtu")
        self.assertEqual(r2["intent_frame"]["intent"], "GENERAL_CONVERSATION")
        self.assertIsNone(r2["task"])

        r_now = self.engine.handle_user_message("Kapan jadwal belanjaku?")
        self.assertEqual(r_now["intent_frame"]["intent"], "MEMORY_RECALL")
        self.assertIn("Sabtu", r_now["reply"])
        self.assertNotIn("Minggu", r_now["reply"])

        r_hist = self.engine.handle_user_message("Apa yang kamu ingat riwayat jadwal belanja?")
        self.assertIn("Sabtu", r_hist["reply"])
        self.assertIn("Minggu", r_hist["reply"])
        self.assertIn("digantikan", r_hist["reply"])

        r_aud = self.engine.handle_user_message("Cek status memori")
        self.assertEqual(r_aud["intent_frame"]["intent"], "MEMORY_AUDIT")
        self.assertIn("VALID", r_aud["reply"])
        self.assertIn("**1**", r_aud["reply"])

        ev_kinds = [e["kind"] for e in self.store.list_events(include_heartbeats=False)]
        self.assertIn("memory_saved", ev_kinds)
        self.assertIn("memory_superseded", ev_kinds)

        sup_proj = project_event_to_story({
            "kind": "memory_superseded",
            "status": "COMPLETED",
            "technical_detail": {"label": "jadwal belanja waktu: Sabtu"},
        })
        self.assertIn("superseded", sup_proj["story_text"])
        self.assertTrue(sup_proj["is_story_card"])

    def test_privacy_bounds_and_audited_tombstone_forgetting(self):
        r_priv = self.engine.handle_user_message("Ingat bahwa pin brankas rahasiaku adalah 9182")
        self.assertEqual(r_priv["intent_frame"]["intent"], "MEMORY_STORE")
        self.assertIn("privat", r_priv["reply"].lower())

        # Private facts never leak to default recall or prompt conditioning
        self.assertEqual(self.engine.memory.recall_memories("pin brankas")["returned"], 0)
        self.assertNotIn("9182", self.engine.memory.build_prompt_context("pin brankas"))

        r_priv_ok = self.engine.handle_user_message("Apa yang kamu ingat tentang rahasia pin brankas?")
        self.assertIn("9182", r_priv_ok["reply"])

        self.engine.handle_user_message("Ingat jadwal rapat adalah Senin pagi")
        self.engine.handle_user_message("Ingat jadwal olahraga adalah Rabu sore")

        r_forget = self.engine.handle_user_message("Lupakan jadwal olahraga")
        self.assertEqual(r_forget["intent_frame"]["intent"], "MEMORY_FORGET")
        self.assertIn("tombstone", r_forget["reply"].lower())

        # Unrelated schedules & private secrets remain intact
        self.assertEqual(self.engine.memory.recall_memories("jadwal rapat")["returned"], 1)
        self.assertEqual(self.engine.memory.recall_memories("pin brankas", include_private=True)["returned"], 1)

        # Forgotten content is destroyed from raw JSONL and honest on recall
        raw_log = (self.ws / "cognitive_memory" / "memory.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("Rabu sore", raw_log)
        r_gone = self.engine.handle_user_message("Apa yang kamu ingat soal jadwal olahraga?")
        self.assertIn("belum punya ingatan aktif", r_gone["reply"].lower())
        self.assertIn("tombstone", r_gone["reply"].lower())
        self.assertTrue(self.engine.memory.audit_report()["chain_ok"])

    def test_task_episode_evidence_procedural_and_negative_transfer(self):
        r_code = self.engine.handle_user_message("Buatkan aplikasi catatan pengeluaran sederhana")
        self.assertEqual(r_code["task"]["status"], "COMPLETED")

        frontier = {f["capability_id"]: f for f in self.store.list_frontier()}
        self.assertIn("cap_memori_jangka_panjang", frontier)
        self.assertEqual(frontier["cap_memori_jangka_panjang"]["status"], "KNOWN_AND_TESTED")

        audit = self.engine.memory.audit_report()
        self.assertTrue(audit["chain_ok"])
        self.assertGreaterEqual(audit["anchored_evidence"], 1)

        ep = self.engine.memory.recall_memories("pengeluaran", kinds=["episodic"])
        self.assertGreaterEqual(ep["returned"], 1)
        self.assertEqual(ep["results"][0]["source"]["kind"], "evidence")

        proc_ok = self.engine.memory.recall_memories("expense_tracker", kinds=["procedural"], context="expense_tracker")
        self.assertEqual(proc_ok["returned"], 1)
        self.assertFalse(proc_ok["results"][0]["negative_transfer_risk"])

        proc_cross = self.engine.memory.recall_memories("expense_tracker", kinds=["procedural"], context="domain_baru")
        self.assertTrue(proc_cross["results"][0]["negative_transfer_risk"])

        # Repeated failure in refactor domain triggers negative_transfer_risk in same context
        for idx in range(2):
            self.engine.memory.record_task_episode(
                {"task_id": f"tsk_fail_{idx}", "title_id": "Refactor gagal", "status": "FAILED_WITH_RECOVERY_STATE", "artifacts": []},
                domain="refactor",
            )
        proc_risk = self.engine.memory.recall_memories("refactor", kinds=["procedural"], context="refactor")
        self.assertEqual(proc_risk["returned"], 1)
        self.assertTrue(proc_risk["results"][0]["negative_transfer_risk"])

    def test_gguf_prompt_conditioning_excludes_private_memory(self):
        self.assertIsInstance(self.engine.memory, ConversationalMemoryManager)
        grad = self.engine.speech.train_and_graduate()
        self.assertTrue(grad["passed"])
        self.engine.memory.remember_statement("Namaku Budi", source_kind="operator")
        self.engine.memory.remember_statement("pin rahasiaku adalah 4321", source_kind="operator", sensitivity="private")

        captured: list[list[dict[str, str]]] = []
        orig_hc = self.engine.router.health_check

        def fake_hc():
            hc = dict(orig_hc())
            hc["local_gguf"] = {"server_healthy": True, "ready": True}
            return hc

        def fake_gen(messages, **kwargs):
            captured.append(messages)
            return {"text": "Halo Budi! Aku ACE, senang melanjutkan obrolan tentang perjalanan akhir pekan.", "backend_used": "local-gguf-test", "success": True}

        self.engine.router.health_check = fake_hc  # type: ignore[method-assign]
        self.engine.router.generate_text = fake_gen  # type: ignore[method-assign]

        r = self.engine.handle_user_message("Ceritakan kesanmu soal perjalanan akhir pekan ini dong")
        self.assertIn("Budi", r["reply"])
        self.assertGreaterEqual(len(captured), 1)
        sys_prompt = captured[0][0]["content"]
        self.assertIn("Memori jangka panjang relevan:", sys_prompt)
        self.assertIn("Budi", sys_prompt)
        self.assertNotIn("4321", sys_prompt)

    def test_web_studio_memory_rest_api_and_ui(self):
        server = ACEWebServer(self.store, host="127.0.0.1", port=0)
        url = server.start_background()
        self.addCleanup(server.stop)

        with urlopen(f"{url}/", timeout=10) as resp:
            html = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
        for token in ("badge-memory", "memory-drawer", "toggleMemoryDrawer", "refreshMemoryDrawer", "/api/memory"):
            self.assertIn(token, html)

        # Validation guards
        st_bad, _ = _http_json(f"{url}/api/memory", method="POST", payload={"text": "   "})
        self.assertEqual(st_bad, 400)
        st_sens, _ = _http_json(f"{url}/api/memory", method="POST", payload={"text": "Fakta uji", "sensitivity": "bogus"})
        self.assertEqual(st_sens, 400)

        # Create public & private memory items
        st1, d1 = _http_json(f"{url}/api/memory", method="POST", payload={"text": "Kota favoritku adalah Yogyakarta"})
        self.assertEqual(st1, 200)
        self.assertTrue(d1["stored"])
        rec_id = d1["record_id"]

        st2, d2 = _http_json(f"{url}/api/memory", method="POST", payload={"text": "Kode pintu rahasia 7788", "sensitivity": "private"})
        self.assertEqual(st2, 200)
        self.assertEqual(d2["sensitivity"], "private")

        st_stat, d_stat = _http_json(f"{url}/api/status")
        self.assertEqual(st_stat, 200)
        self.assertEqual(d_stat["memory_summary"]["active_records"], 2)
        self.assertTrue(d_stat["memory_summary"]["chain_ok"])

        # Default snapshot & recall hide private; include_private reveals it
        _, snap_def = _http_json(f"{url}/api/memory")
        self.assertEqual(len(snap_def["active_records"]), 1)
        _, snap_priv = _http_json(f"{url}/api/memory?include_private=1")
        self.assertEqual(len(snap_priv["active_records"]), 2)

        _, rec_def = _http_json(f"{url}/api/memory/recall", method="POST", payload={"query": "7788"})
        self.assertEqual(rec_def["returned"], 0)
        _, rec_priv = _http_json(f"{url}/api/memory/recall", method="POST", payload={"query": "7788", "include_private": True})
        self.assertEqual(rec_priv["returned"], 1)

        st_lim, _ = _http_json(f"{url}/api/memory/recall", method="POST", payload={"query": "kota", "limit": "bukan-angka"})
        self.assertEqual(st_lim, 400)

        # Audited tombstone forget + 404 guard
        st_404, _ = _http_json(f"{url}/api/memory/forget", method="POST", payload={"record_id": "mem_tidak_ada"})
        self.assertEqual(st_404, 404)

        st_f, d_f = _http_json(f"{url}/api/memory/forget", method="POST", payload={"record_id": rec_id})
        self.assertEqual(st_f, 200)
        self.assertEqual(d_f["tombstone"]["record_id"], rec_id)
        self.assertTrue(d_f["audit"]["chain_ok"])

        _, aud_res = _http_json(f"{url}/api/memory/audit")
        self.assertTrue(aud_res["chain_ok"])
        self.assertEqual(aud_res["active_records"], 1)
        self.assertEqual(len(aud_res["tombstones"]), 1)


if __name__ == "__main__":
    unittest.main()
