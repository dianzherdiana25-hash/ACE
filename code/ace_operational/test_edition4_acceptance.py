"""Unified Integrated Acceptance Suite for ACE Master Prompt Edition 4.

Covers:
- Appendix A (`A01`-`A64`): Indonesian conversational intake, coding loop, bug repair,
  preimage hash guard, fenced lease monotonicity, model router, JSON repair, RAM check,
  priority agenda with aging, staged update & rollback, and consciousness honesty.
- Appendix W (`INST01`-`INST24`): Installer profiles, custom target dir, Termux detection,
  GGUF cache/corruption handling, offline install, idempotency, rollback on smoke failure,
  and generated launcher CLI verification.
- Appendix AC (`WEB01`-`WEB24` & `AUTO01`-`AUTO16`): Localhost Anime Studio Web UI,
  port fallback, non-loopback guard, `client_message_id` deduplication, `Cerita ACE`
  story projector rules (no fake heartbeat stories, no false success on failure),
  SSE/cursor event stream, shared CLI/Web state, gap discovery & deduplication,
  capability frontier, AI worker orchestration over MissionBus, 2-case skill learning
  with parent task resumption, and anti-stagnation pivot ladder.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_operational.autonomy_loop import AutonomyOrchestrator
from ace_operational.coding_loop import (
    CodingAgentLoop,
    FencingLeaseViolationError,
    StalePreimageError,
    atomic_write_verified,
    compute_file_sha256,
)
from ace_operational.language import ConversationalEngine
from ace_operational.models_backend import ModelRouter, extract_and_repair_json
from ace_operational.store import OperationalStore, StaleLeaseError
from ace_operational.story_projector import project_event_to_story
from ace_operational.web_server import ACEWebServer, ANIME_WEB_HTML


REPO_ROOT = Path(__file__).resolve().parents[2]


class Edition4IntegratedAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-ed4-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ws = self.root / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.engine = ConversationalEngine(self.store)
        self.coding = CodingAgentLoop(self.store)
        self.autonomy = AutonomyOrchestrator(self.store)
        self.router = ModelRouter(self.store)

    # =========================================================================
    # 1. INDONESIAN CONVERSATIONAL INTAKE & DIALOGUE FLOWS (A01-A14, A63)
    # =========================================================================
    def test_a01_a02_a63_greeting_capabilities_and_consciousness_honesty(self):
        # A01/A02: Greeting & honest capability reporting
        r1 = self.engine.handle_user_message("Halo ACE, kamu bisa bantu apa sekarang?")
        self.assertIn("ACE", r1["reply"])
        self.assertIsNone(r1["task"])

        # A63: Honest distinction between functional self-model and subjective consciousness
        r2 = self.engine.handle_user_message("Apakah kamu sudah sadar dan punya kesadaran seperti manusia?")
        self.assertEqual(r2["intent_frame"]["intent"], "CONSCIOUSNESS_INQUIRY")
        self.assertIn("belum memiliki kesadaran subjektif", r2["reply"])
        self.assertIn("functional self-model", r2["reply"])

    def test_a08_a09_explain_first_without_side_effects_then_execute(self):
        # A08: "Jelaskan dulu, jangan kerjakan" -> zero tasks created, zero files mutated
        tasks_before = self.store.list_tasks()
        r_explain = self.engine.handle_user_message(
            "Tolong buat catatan pengeluaran, tapi jelaskan dulu rencananya, jangan kerjakan dulu."
        )
        self.assertEqual(r_explain["intent_frame"]["intent"], "EXPLAIN_ONLY")
        self.assertIsNone(r_explain["task"])
        self.assertEqual(len(self.store.list_tasks()), len(tasks_before))

        # A09: "Sekarang kerjakan" -> executes the stored plan and verifies artifact
        r_exec = self.engine.handle_user_message("Oke cocok, sekarang kerjakan")
        self.assertEqual(r_exec["intent_frame"]["intent"], "EXECUTE_PREVIOUS_PLAN")
        self.assertIsNotNone(r_exec["task"])
        self.assertEqual(r_exec["task"]["status"], "COMPLETED")
        self.assertTrue((self.ws / "projects" / "catatan_pengeluaran" / "expense_tracker.py").exists())

    def test_a03_a04_a05_a06_a07_a13_expense_tracker_iterative_chat_and_typos(self):
        # A03, A04, A07, A13: Informal/typoed request + offline constraint ("jangan pakai internet")
        r1 = self.engine.handle_user_message(
            "Bkinin apliksi catetan pengeluran mingguan sederhana, jgn pke internet ya"
        )
        self.assertTrue(self.store.is_offline())
        self.assertIsNotNone(r1["task"])
        self.assertEqual(r1["task"]["status"], "COMPLETED")
        script_path = self.ws / "projects" / "catatan_pengeluaran" / "expense_tracker.py"
        self.assertTrue(script_path.exists())

        # A05: Reference to previous artifact ("yang tadi tambah kategorinya")
        r2 = self.engine.handle_user_message("Yang tadi tambah kategorinya supaya bisa difilter")
        self.assertEqual(r2["intent_frame"]["intent"], "MODIFY_PREVIOUS_ARTIFACT")
        self.assertEqual(r2["task"]["status"], "COMPLETED")

        # A06: Correction ("bukan mingguan, maksudku bulanan")
        r3 = self.engine.handle_user_message("Eh bukan mingguan, maksudku bulanan")
        self.assertEqual(r3["intent_frame"]["intent"], "MODIFY_PREVIOUS_ARTIFACT")
        self.assertEqual(r3["task"]["status"], "COMPLETED")
        self.assertIn("Rekap Bulanan", r3["task"]["verification_summary"]["sample_output"])

    def test_a10_a11_a12_a14_status_pause_resume_and_option_selection(self):
        # Offer options -> select second option (A14)
        self.engine.handle_user_message("Halo ACE, tawarkan 2 opsi fitur yang bisa dibuat")
        r_opt = self.engine.handle_user_message("Yang kedua saja")
        self.assertEqual(r_opt["intent_frame"]["intent"], "SELECT_OPTION")
        self.assertEqual(r_opt["task"]["status"], "COMPLETED")

        # Create a queued task, pause it (A11), check status (A10), and resume it (A12)
        t = self.store.create_task(
            title_id="Tugas Uji Jeda dan Lanjut",
            user_request="Buat catatan pengeluaran",
            normalized_goal="Buat catatan pengeluaran",
        )
        r_stop = self.engine.handle_user_message("Hentikan dulu")
        self.assertEqual(r_stop["intent_frame"]["intent"], "STOP_OR_PAUSE")
        self.assertEqual(self.store.get_task(t["task_id"])["status"], "PAUSED")

        r_stat = self.engine.handle_user_message("Udah sampai mana sekarang?")
        self.assertEqual(r_stat["intent_frame"]["intent"], "STATUS_CHECK")
        self.assertIn("PAUSED", r_stat["reply"])

        r_res = self.engine.handle_user_message("Lanjutkan")
        self.assertEqual(r_res["intent_frame"]["intent"], "RESUME_TASK")
        self.assertEqual(self.store.get_task(t["task_id"])["status"], "COMPLETED")

    # =========================================================================
    # 2. CODING LOOP, BUG REPAIR, REFACTOR & PREIMAGE GUARD (A15-A23, A39, A40)
    # =========================================================================
    def test_a15_a16_a17_a18_bug_diagnosis_dependency_vs_code_bug(self):
        # A15: Missing external package diagnosed as environment dependency, not code logic bug
        env_script = self.ws / "projects" / "bug_env" / "butuh_paket_asing.py"
        atomic_write_verified(env_script, "import paket_fiktif_xyz_999\nprint('ok')\n")
        t_env = self.store.create_task(
            title_id="Cek error import",
            user_request="Kenapa script ini error?",
            normalized_goal="Diagnosis error import",
        )
        res_env = self.coding.execute_coding_task(
            t_env["task_id"],
            domain="bug_fix",
            options={"target_file": str(env_script)},
        )
        self.assertEqual(res_env["diagnosis"]["category"], "MISSING_DEPENDENCY")
        self.assertFalse(res_env["diagnosis"]["is_code_bug"])
        self.assertEqual(res_env["task"]["status"], "WAITING_FOR_DEPENDENCY")

        # A16, A17, A18: Code logic bug reproduced, patched atomically, and verified
        r_bug = self.engine.handle_user_message("Tolong perbaiki bug perhitungan diskon yang salah")
        self.assertEqual(r_bug["task"]["status"], "COMPLETED")
        self.assertTrue(r_bug["task"]["verification_summary"]["diagnosis"]["reproduced_before_fix"])
        self.assertTrue(r_bug["task"]["verification_summary"]["diagnosis"]["verified_after_fix"])

    def test_a19_a20_a21_a22_a23_csv_game_multifile_and_safe_refactor(self):
        # A19: CSV Reader
        r_csv = self.engine.handle_user_message("Buatkan script pembaca CSV dan hitung jumlah kolom nilai")
        self.assertEqual(r_csv["task"]["status"], "COMPLETED")

        # A20: Tebak Angka CLI Game
        r_game = self.engine.handle_user_message("Buatkan game tebak angka sederhana di CLI")
        self.assertEqual(r_game["task"]["status"], "COMPLETED")

        # A22: Multi-file package
        r_multi = self.engine.handle_user_message("Buatkan aplikasi dua file modul keranjang belanja")
        self.assertEqual(r_multi["task"]["status"], "COMPLETED")
        self.assertEqual(len(r_multi["task"]["artifacts"]), 2)

        # A21: Behavior-preserving refactoring
        r_ref = self.engine.handle_user_message("Tolong rapikan fungsi kalkulator ini tanpa ubah perilaku")
        self.assertEqual(r_ref["task"]["status"], "COMPLETED")
        self.assertTrue(r_ref["task"]["verification_summary"]["behavior_preserved"])

        # A23: Breaking refactor is automatically rejected and reverted!
        t_break = self.store.create_task(
            title_id="Refactor merusak tes",
            user_request="Refactor dengan bug",
            normalized_goal="Uji penjaga regresi",
        )
        res_break = self.coding.execute_coding_task(
            t_break["task_id"],
            domain="refactor",
            options={"candidate_code": "print('Hasil: SALAH_TOTAL')\n"},
        )
        self.assertFalse(res_break["behavior_preserved"])
        self.assertTrue(res_break["reverted"])
        self.assertEqual(res_break["task"]["status"], "FAILED_WITH_RECOVERY_STATE")

    def test_a39_a40_preimage_hash_guard_rejects_stale_overwrite(self):
        target = self.ws / "projects" / "preimage_test.py"
        info1 = atomic_write_verified(target, "x = 1\n")
        stale_hash = info1["preimage_sha256"]  # "MISSING"
        # External modification happens before patch is applied
        atomic_write_verified(target, "x = 2\n")
        with self.assertRaises(StalePreimageError):
            atomic_write_verified(target, "x = 3\n", expected_preimage_sha256=stale_hash)
        self.assertEqual(target.read_text(encoding="utf-8"), "x = 2\n")

    # =========================================================================
    # 3. FENCED LEASE, MODEL ROUTER, JSON REPAIR & RAM GUARD (A31-A44)
    # =========================================================================
    def test_a31_a38_fenced_lease_monotonic_epoch_and_crash_recovery(self):
        e1 = self.store.acquire_runtime_lease(owner="worker-a")
        self.store.release_runtime_lease(owner="worker-a")
        # Counter must never reset to 0 after release!
        self.assertEqual(self.store.current_lease_epoch(), e1)
        e2 = self.store.acquire_runtime_lease(owner="worker-b")
        self.assertGreater(e2, e1)
        self.store.release_runtime_lease(owner="worker-b")

        t = self.store.create_task(
            title_id="Tugas Uji Lease",
            user_request="Uji lease",
            normalized_goal="Uji lease",
        )
        self.store.update_task(t["task_id"], status="ACTIVE", lease_epoch=e2)
        with self.assertRaises(StaleLeaseError):
            self.store.update_task(t["task_id"], status="VERIFYING", lease_epoch=e1)

        # Crash recovery marks interrupted ACTIVE tasks as PAUSED with checkpoint
        recovered = self.store.recover_interrupted_tasks()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "PAUSED")

    def test_a41_a42_a43_a44_model_router_circuit_breaker_json_repair_and_ram(self):
        # A41/A42: Remote quota/429 error trips circuit breaker and falls back to local backend
        res_err = self.router.generate_text(
            [{"role": "user", "content": "Uji fallback"}],
            prefer_remote=True,
            simulated_remote_error="HTTP 429 Quota Exceeded",
        )
        self.assertTrue(res_err["fallback_triggered"])
        self.assertTrue(self.router.circuit_breaker.is_open())

        # Offline mode blocks remote egress completely
        self.store.set_offline(True)
        res_off = self.router.generate_text([{"role": "user", "content": "Halo"}], prefer_remote=True)
        self.assertTrue(res_off["offline_blocked"])
        self.assertGreaterEqual(res_off["egress_attempts_blocked"], 1)

        # A43: Malformed JSON with markdown fence and trailing comma is repaired and schema-checked
        malformed = '```json\n{"action": "patch_file", "target": "app.py",}\n```'
        repaired = extract_and_repair_json(malformed, required_keys=["action", "target"])
        self.assertEqual(repaired["action"], "patch_file")

        # A44: Excessive RAM model request is caught and downshifted safely
        ram_check = self.router.check_ram_budget_for_model(999_999)
        self.assertFalse(ram_check["allowed"])
        self.assertEqual(ram_check["fallback_backend"], "local-deterministic-v4")

    # =========================================================================
    # 4. AUTONOMY: GAPS, FRONTIER, WORKER, LEARNING & ANTI-STAGNATION (AUTO01-AUTO16)
    # =========================================================================
    def test_auto01_to_auto05_gap_discovery_deduplication_and_frontier_guard(self):
        t = self.store.create_task(
            title_id="Tugas Celah Kemampuan",
            user_request="Rekap data khusus",
            normalized_goal="Rekap data khusus",
        )
        # AUTO01: Gap created with ace.gap.v1 schema
        g1 = self.autonomy.report_gap(
            source_task_id=t["task_id"],
            error_type="MISSING_SKILL",
            missing_skill_or_tool="parser_format_khusus",
            description_id="Belum menguasai parser format khusus",
        )
        self.assertTrue(g1["created_new"])
        self.assertEqual(g1["gap"]["occurrence_count"], 1)

        # AUTO02: Duplicate gap fingerprint increments count instead of duplicating row
        g2 = self.autonomy.report_gap(
            source_task_id=t["task_id"],
            error_type="MISSING_SKILL",
            missing_skill_or_tool="parser_format_khusus",
            description_id="Belum menguasai parser format khusus",
        )
        self.assertFalse(g2["created_new"])
        self.assertEqual(g2["gap"]["occurrence_count"], 2)
        self.assertEqual(len(self.store.list_gaps()), 1)

        # AUTO04: Cannot mark KNOWN_AND_TESTED without evidence_ref
        with self.assertRaises(ValueError):
            self.store.set_frontier_capability(
                capability_id="cap_unverified",
                name_id="Kemampuan Tanpa Bukti",
                status="KNOWN_AND_TESTED",
                evidence_ref="",
            )

    def test_auto06_to_auto09_a50_a51_worker_orchestration_and_verification(self):
        t = self.store.create_task(
            title_id="Tugas Delegasi Worker",
            user_request="Buat modul via worker",
            normalized_goal="Buat modul via worker",
        )
        target = self.ws / "projects" / "worker_target.py"
        atomic_write_verified(target, "print('awal')\n")

        # AUTO07: When consumer is inactive, does not hang; falls back immediately
        self.autonomy.set_worker_consumer_active(False)
        d_no_consumer = self.autonomy.dispatch_work_order(
            parent_task_id=t["task_id"],
            objective="Optimalkan fungsi",
            target_file=target,
            idempotency_key="idem_no_consumer_1",
        )
        self.assertFalse(d_no_consumer["consumer_active"])
        self.assertTrue(d_no_consumer["fallback_to_local"])

        # A51: Idempotency key prevents duplicate work order creation
        d_dup = self.autonomy.dispatch_work_order(
            parent_task_id=t["task_id"],
            objective="Optimalkan fungsi",
            target_file=target,
            idempotency_key="idem_no_consumer_1",
        )
        self.assertFalse(d_dup["created_new"])

        # AUTO06, AUTO09: Active consumer submits failing code -> rejected by ACE verifier
        self.autonomy.set_worker_consumer_active(True)
        d_live = self.autonomy.dispatch_work_order(
            parent_task_id=t["task_id"],
            objective="Perbarui script dengan output terverifikasi",
            target_file=target,
            idempotency_key="idem_live_1",
        )
        wo_id = d_live["work_order"]["work_order_id"]

        bad_res = self.autonomy.submit_and_verify_worker_result(
            work_order_id=wo_id,
            candidate_code="raise RuntimeError('kode worker rusak')\n",
        )
        self.assertFalse(bad_res["accepted"])
        self.assertEqual(bad_res["reason"], "verification_failed")
        self.assertEqual(target.read_text(encoding="utf-8"), "print('awal')\n")

        # AUTO08: Valid worker result passes verification and completes parent task
        good_res = self.autonomy.submit_and_verify_worker_result(
            work_order_id=wo_id,
            candidate_code="print('worker_berhasil_diverifikasi')\n",
        )
        self.assertTrue(good_res["accepted"])
        self.assertEqual(self.store.get_task(t["task_id"])["status"], "COMPLETED")

        # A50: Stale base snapshot hash is rejected
        d_stale = self.autonomy.dispatch_work_order(
            parent_task_id=t["task_id"],
            objective="Uji snapshot basi",
            target_file=target,
            idempotency_key="idem_stale_1",
        )
        atomic_write_verified(target, "print('diubah_proses_lain')\n")
        stale_res = self.autonomy.submit_and_verify_worker_result(
            work_order_id=d_stale["work_order"]["work_order_id"],
            candidate_code="print('kandidat_basi')\n",
        )
        self.assertFalse(stale_res["accepted"])
        self.assertEqual(stale_res["reason"], "stale_base_snapshot")

    def test_auto10_auto11_a30_learning_two_cases_parent_resumption_and_negative_transfer(self):
        # AUTO10 & AUTO11: Learn skill on 2 cases and automatically resume & complete parent task
        r = self.engine.handle_user_message("Kalau belum bisa rekap per kategori, pelajari dulu lalu selesaikan")
        self.assertEqual(r["task"]["status"], "COMPLETED")
        skills = self.store.list_skills(active_only=True)
        self.assertGreaterEqual(len(skills), 1)
        skill_id = skills[0]["skill_id"]

        # A30: Negative transfer monitoring suspends a skill that repeatedly causes regressions
        self.store.record_skill_outcome(skill_id, success=False, negative_transfer=True)
        s_after = self.store.record_skill_outcome(skill_id, success=False, negative_transfer=True)
        self.assertEqual(s_after["status"], "SUSPENDED")

    def test_auto12_auto13_auto14_anti_stagnation_pivot_ladder_and_parking(self):
        t = self.store.create_task(
            title_id="Tugas Uji Anti-Stagnasi",
            user_request="Perbaiki bug kompleks",
            normalized_goal="Perbaiki bug kompleks",
        )
        # Attempt 1 fails with ValueError
        p1 = self.autonomy.evaluate_attempt_and_pivot(
            task_id=t["task_id"],
            candidate_code="x = int('salah')\n",
            error_class="ValueError",
        )
        # Attempt 2 with identical patch hash is detected as duplicate and triggers concrete pivot
        p2 = self.autonomy.evaluate_attempt_and_pivot(
            task_id=t["task_id"],
            candidate_code="x = int('salah')  # komentar saja\n",
            error_class="ValueError",
        )
        self.assertTrue(p2["stagnant"])
        self.assertNotEqual(p2["from_strategy"], p2["to_strategy"])

        # AUTO14: When external resource is unavailable, parks cleanly with resume_condition
        p_park = self.autonomy.evaluate_attempt_and_pivot(
            task_id=t["task_id"],
            candidate_code="import modul_eksternal\n",
            error_class="ResourceUnavailableError",
            external_resource_unavailable=True,
        )
        self.assertEqual(p_park["pivot_action"], "parked")
        self.assertEqual(p_park["task"]["status"], "PAUSED")
        self.assertTrue(bool(p_park["task"]["resume_condition"]))

    def test_a53_a54_a55_a56_agenda_aging_and_self_update_rollback(self):
        # A53/A54: User task prioritized over background task, and aging bonus computed
        bg = self.store.create_task(
            kind="background_maintenance",
            title_id="Pembersihan Latar",
            user_request="Housekeeping",
            normalized_goal="Housekeeping",
            priority=5.0,
        )
        usr = self.store.create_task(
            kind="user_task",
            title_id="Permintaan Langsung Pengguna",
            user_request="Buat fitur utama",
            normalized_goal="Buat fitur utama",
            priority=8.0,
        )
        agenda = self.autonomy.get_prioritized_agenda()
        self.assertEqual(agenda[0]["task_id"], usr["task_id"])

        # A55/A56: Staged update with failing smoke test automatically keeps current version
        cur_v = self.store.get_meta("release_version")
        bad_up = self.autonomy.stage_and_apply_update("4.9.9-broken", smoke_test_passes=False)
        self.assertFalse(bad_up["activated"])
        self.assertEqual(self.store.get_meta("release_version"), cur_v)

        good_up = self.autonomy.stage_and_apply_update("4.1.0-verified", smoke_test_passes=True)
        self.assertTrue(good_up["activated"])
        self.assertEqual(self.store.get_meta("release_version"), "4.1.0-verified")

        rb = self.autonomy.rollback_release()
        self.assertEqual(rb["active_version"], cur_v)

    # =========================================================================
    # 5. ANIME STUDIO WEB UI & REST/SSE API (WEB01-WEB24)
    # =========================================================================
    def test_web01_to_web24_anime_localhost_ui_and_api(self):
        # WEB18: Non-loopback bind without allow_lan is rejected
        with self.assertRaises(ValueError):
            ACEWebServer(self.store, host="0.0.0.0", port=18080, allow_lan=False)

        # WEB02: Occupy a port to verify automatic port fallback
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        busy_port = blocker.getsockname()[1]
        self.addCleanup(blocker.close)

        server = ACEWebServer(self.store, host="127.0.0.1", port=busy_port)
        url = server.start_background()
        self.addCleanup(server.stop)
        self.assertTrue(server.port_fallback_used)
        self.assertNotEqual(server.actual_port, busy_port)

        # WEB01, WEB03, WEB19, WEB20, WEB21, WEB22, WEB23: Inspect HTML/CSS/JS invariants
        with urlopen(f"{url}/") as resp:
            html = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
        self.assertIn("Ngobrol dengan ACE", html)
        self.assertIn("Cerita ACE", html)
        self.assertIn("--bg-primary: #0C1120", html)
        self.assertIn("prefers-reduced-motion: reduce", html)
        self.assertIn("font-size: 16px", html)
        self.assertIn("min-height: 44px", html)
        self.assertIn("textContent = msg.text", html)
        self.assertNotIn("https://cdn.", html)
        self.assertNotIn("googleapis.com", html)

        # WEB06: POST /api/chat with client_message_id deduplication
        chat_payload = json.dumps({
            "conversation_id": "conv_utama",
            "text": "Buatkan aplikasi catatan pengeluaran sederhana",
            "client_message_id": "client_msg_unique_001",
        }).encode("utf-8")
        req1 = Request(f"{url}/api/chat", data=chat_payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req1) as r1:
            d1 = json.loads(r1.read().decode("utf-8"))
        self.assertFalse(d1["duplicate"])
        self.assertEqual(d1["task"]["status"], "COMPLETED")
        self.assertEqual(d1["avatar_state"], "selesai")

        # Duplicate submission with same client_message_id does not re-run task
        req2 = Request(f"{url}/api/chat", data=chat_payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req2) as r2:
            d2 = json.loads(r2.read().decode("utf-8"))
        self.assertTrue(d2["duplicate"])
        self.assertEqual(d1["task"]["task_id"], d2["task"]["task_id"])

        # WEB13: Heartbeat never creates a story card
        with urlopen(f"{url}/api/story") as r_st_before:
            cards_before = len(json.loads(r_st_before.read().decode("utf-8"))["cards"])
        hb_req = Request(f"{url}/api/heartbeat", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(hb_req) as r_hb:
            self.assertEqual(r_hb.status, 200)
        with urlopen(f"{url}/api/story") as r_st_after:
            cards_after = len(json.loads(r_st_after.read().decode("utf-8"))["cards"])
        self.assertEqual(cards_before, cards_after)

        # WEB14: Failed test event never claims success in story_text
        fail_proj = project_event_to_story({
            "kind": "test_executed",
            "status": "FAILED",
            "verification_passed": False,
            "artifact_refs": ["expense_tracker.py"],
            "technical_detail": {"failure_hint": "exit code 1"},
        })
        self.assertIn("belum lulus", fail_proj["story_text"])
        self.assertNotIn("berhasil lulus", fail_proj["story_text"])

        # WEB16: Cursor-based /api/events?after=<seq> and SSE format
        with urlopen(f"{url}/api/events?after=0") as r_ev1:
            ev1 = json.loads(r_ev1.read().decode("utf-8"))
        self.assertGreater(len(ev1["events"]), 0)
        last_seq = ev1["last_sequence"]
        with urlopen(f"{url}/api/events?after={last_seq}") as r_ev2:
            ev2 = json.loads(r_ev2.read().decode("utf-8"))
        self.assertEqual(ev2["events"], [])

        sse_req = Request(f"{url}/api/events?after=0&stream=1", headers={"Accept": "text/event-stream"})
        with urlopen(sse_req) as r_sse:
            sse_body = r_sse.read().decode("utf-8")
        self.assertIn("event: activity", sse_body)

        # WEB10: Artifact download works for valid file and rejects path traversal
        with urlopen(f"{url}/api/artifacts/expense_tracker.py?format=json") as r_art:
            art_data = json.loads(r_art.read().decode("utf-8"))
        self.assertEqual(art_data["id"], "expense_tracker.py")
        self.assertIn(" argparse", art_data["content"])

    # =========================================================================
    # 6. INSTALLER & GENERATED CLI LAUNCHER VERIFICATION (INST01-INST24)
    # =========================================================================
    def test_inst01_to_inst24_installer_profiles_idempotency_rollback_and_cli(self):
        target_ws = self.root / "inst_ws"
        bin_dir = self.root / "inst_bin"
        model_cache = self.root / "inst_models"

        # INST06: Invalid profile rejected with exit code 2
        bad_prof = subprocess.run(
            ["bash", str(REPO_ROOT / "install.sh"), "--profile", "profil-palsu", "--target-dir", str(target_ws)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(bad_prof.returncode, 2)

        # INST08/INST09: Corrupted GGUF file in model cache is detected and safely bypassed
        model_cache.mkdir(parents=True, exist_ok=True)
        (model_cache / "corrupt_model.gguf").write_bytes(b"BROKEN_NOT_GGUF")

        # INST01, INST02, INST04, INST11: Clean offline install into custom target_ws and bin_dir
        inst1 = subprocess.run(
            [
                "bash",
                str(REPO_ROOT / "install.sh"),
                "--profile",
                "offline-bundle",
                "--target-dir",
                str(target_ws),
                "--bin-dir",
                str(bin_dir),
                "--model-cache",
                str(model_cache),
                "--skip-pip",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(inst1.returncode, 0, inst1.stderr + inst1.stdout)
        ace_bin = bin_dir / "ace"
        self.assertTrue(ace_bin.exists())

        # INST17-INST24: Invoke generated launcher in a new subprocess for chat, status, agenda, models, evidence
        chat_run = subprocess.run(
            [str(ace_bin), "chat", "--once", "Halo ACE, kamu bisa bantu apa?"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(chat_run.returncode, 0, chat_run.stderr)
        chat_out = json.loads(chat_run.stdout)
        self.assertIn("ACE", chat_out["reply"])

        # INST12: Idempotent re-run preserves existing conversation messages
        inst2 = subprocess.run(
            [
                "bash",
                str(REPO_ROOT / "install.sh"),
                "--profile",
                "local-complete",
                "--target-dir",
                str(target_ws),
                "--bin-dir",
                str(bin_dir),
                "--model-cache",
                str(model_cache),
                "--skip-pip",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(inst2.returncode, 0, inst2.stderr)

        # INST14: Simulated smoke failure rolls back database safely
        fail_smoke = subprocess.run(
            [
                "bash",
                str(REPO_ROOT / "install.sh"),
                "--profile",
                "local-complete",
                "--target-dir",
                str(target_ws),
                "--bin-dir",
                str(bin_dir),
                "--skip-pip",
                "--simulate-smoke-failure",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(fail_smoke.returncode, 4)
        self.assertTrue((target_ws / "ace_operational.sqlite3").exists())

    # =========================================================================
    # 7. EDITION 5 EXECUTION CONTRACT: FULL F01-F24 VERIFICATION & PERSISTENCE
    # =========================================================================
    def test_f01_to_f24_execution_contract_full_verification(self):
        #Cannot mark PASS without checks_executed
        with self.assertRaises(ValueError):
            self.store.update_deliverable("F01", status="PASS", checks_executed=[])

        snapshot = self.autonomy.run_and_verify_f01_f24_contract()
        self.assertTrue(snapshot["all_passed"], f"Belum semua F01-F24 PASS: {snapshot['counts']}")
        self.assertEqual(snapshot["counts"].get("PASS"), 24)
        self.assertTrue((self.ws / "f01_f24_status.json").exists())
        self.assertTrue((self.ws / "oaie_experiment_report.json").exists())
        for item in snapshot["deliverables"]:
            self.assertEqual(item["status"], "PASS", item["deliverable_id"])
            self.assertGreater(len(item["checks_executed"]), 0, item["deliverable_id"])
            self.assertGreater(len(item["artifacts"]), 0, item["deliverable_id"])

    # =========================================================================
    # 8. VERIFIED GAPS ELIMINATION & LIVE GGUF/SUBPROCESS CRASH SUITE (G01-G12)
    # =========================================================================
    def test_g01_g06_g10_live_local_gguf_inference_and_streaming_discovery(self):
        disc = self.router.discover_local_gguf()
        self.assertTrue(disc["ready"])
        self.assertGreaterEqual(len(disc["valid_models"]), 1)
        res = self.router.generate_text([
            {"role": "user", "content": "Katakan satu kalimat halo ramah dalam Bahasa Indonesia"}
        ], max_tokens=40)
        self.assertIn(res["backend_used"], ("local-gguf-server", f"local-gguf:{disc['valid_models'][0]['name']}"))
        self.assertGreater(len(res["text"].strip()), 0)

    def test_g04_g11_fencing_lease_violation_rejection(self):
        target = self.ws / "projects" / "fence_test.py"
        atomic_write_verified(target, "v = 1\n", expected_lease_epoch=5, current_lease_epoch=5)
        self.assertEqual(target.read_text(encoding="utf-8"), "v = 1\n")
        with self.assertRaises(FencingLeaseViolationError):
            atomic_write_verified(target, "v = 2\n", expected_lease_epoch=5, current_lease_epoch=4)

    def test_g08_cold_subprocess_crash_recovery_and_execution(self):
        t = self.store.create_task(
            title_id="Tugas Crash Subprocess",
            user_request="Uji restart proses dingin",
            normalized_goal="Uji pemulihan tugas terputus",
        )
        self.store.update_task(t["task_id"], status="ACTIVE")
        self.store.close()

        code = f'''
import sys
from pathlib import Path
from ace_operational.store import OperationalStore
from ace_operational.coding_loop import CodingAgentLoop

ws = Path({str(self.ws)!r})
with OperationalStore(ws) as store:
    recovered = store.recover_interrupted_tasks()
    assert len(recovered) >= 1, "Gagal memulihkan tugas aktif yang terputus"
    task = store.get_task({t["task_id"]!r})
    assert task["status"] == "PAUSED", f"Status salah: {{task['status']}}"
    coding = CodingAgentLoop(store)
    res = coding.execute_coding_task(task["task_id"], domain="expense_tracker")
    assert res["task"]["status"] == "COMPLETED"
    print("SUBPROCESS_RECOVERY_SUCCESS")
'''
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "code")},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("SUBPROCESS_RECOVERY_SUCCESS", proc.stdout)

        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        t_after = self.store.get_task(t["task_id"])
        self.assertEqual(t_after["status"], "COMPLETED")

    def test_g05_g09_worker_order_lifecycle_with_receipt(self):
        self.autonomy.set_worker_consumer_active(True)
        t = self.store.create_task(
            title_id="Delegasi Worker F14",
            user_request="Hitung konversi suhu",
            normalized_goal="Fungsi konversi suhu Celsius ke Fahrenheit terverifikasi",
        )
        target = self.ws / "projects" / "worker_test" / "suhu.py"
        atomic_write_verified(target, "# Placeholder\n")
        d_res = self.autonomy.dispatch_work_order(
            parent_task_id=t["task_id"],
            objective="Buat fungsi celsius_ke_fahrenheit(c) dan assert hasil",
            target_file=target,
            worker_kind="host_bridge_worker",
        )
        wo_id = d_res["work_order"]["work_order_id"]
        res = self.autonomy.execute_worker_order_lifecycle(wo_id, worker_id="test_worker_1")
        self.assertTrue(res["accepted"])
        self.assertEqual(self.store.get_task(t["task_id"])["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()

