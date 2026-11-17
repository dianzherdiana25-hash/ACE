"""Uji kasus tepi untuk utilitas dashboard: dashboard_state_build dan ace_mobile_dashboard (>=25 kasus)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from tools import ace_mobile_dashboard as amd
from tools import dashboard_state_build as dsb


class DashboardStateBuildEdgeTests(unittest.TestCase):
    """Kasus tepi untuk tools/dashboard_state_build.py."""

    def test_rp_to_int_parses_formatted_rupiah_and_zero(self) -> None:
        self.assertEqual(dsb.rp_to_int("Rp 1.250.000"), 1250000)
        self.assertEqual(dsb.rp_to_int("0"), 0)

    def test_rp_to_int_rejects_string_without_digits(self) -> None:
        with self.assertRaises(ValueError):
            dsb.rp_to_int("Rp -")

    def test_mtime_stamp_missing_vs_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sample.txt"
            self.assertIsNone(dsb.mtime_stamp(p))
            p.write_text("ok", encoding="utf-8")
            stamp = dsb.mtime_stamp(p)
            self.assertIsNotNone(stamp)
            self.assertTrue(stamp.endswith(" WIB"))

    def test_atomic_write_replaces_existing_file_without_leaving_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            target.write_text("lama", encoding="utf-8")
            dsb._atomic_write(target, '{"ok": true}')
            self.assertEqual(target.read_text(encoding="utf-8"), '{"ok": true}')
            self.assertFalse(target.with_name("state.json.tmp").exists())

    def test_gate_board_missing_add58_vs_verified_phrases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.md"
            with mock.patch.object(dsb, "ROOT", root), mock.patch.object(dsb, "ADD58", missing):
                out_missing = dsb.gate_board()
                self.assertIsNone(out_missing["source_stamp"])
                self.assertEqual(out_missing["add58_phrase_verified"], {})

            present = root / "add58.md"
            present.write_text("G3: MEASURED — SPECIALIZATION\nG5: NOT_ASSESSED\n", encoding="utf-8")
            with mock.patch.object(dsb, "ROOT", root), mock.patch.object(dsb, "ADD58", present):
                out_present = dsb.gate_board()
                self.assertIsNotNone(out_present["source_stamp"])
                self.assertEqual(
                    out_present["add58_phrase_verified"],
                    {"G3": True, "G4": False, "G5": True},
                )

    def test_runs_handles_corrupt_heartbeat_and_missing_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hb = root / "hb" / "heartbeat.json"
            hb.parent.mkdir(parents=True)
            hb.write_text("{corrupt", encoding="utf-8")
            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "HEARTBEAT", hb),
                mock.patch.object(dsb, "V3_EVIDENCE", root / "none.json"),
                mock.patch.object(dsb, "R2_STATE_DIR", root / "r2"),
                mock.patch.object(dsb, "R2_KERNEL_RESULTS", root / "r2k" / "results.jsonl"),
            ):
                res = dsb.runs()
            self.assertEqual(res["abc_v3"]["status"], "NO HEARTBEAT FILE")
            self.assertFalse(res["abc_v3"]["evidence_exists"])
            self.assertIsNone(res["round2_guard"]["kernel_results_bytes"])
            self.assertEqual(res["round2_guard"]["guard_outputs"], [])

    def test_runs_lists_sorted_checkpoints_excluding_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hb_dir = root / "abc-v3-run-state"
            hb_dir.mkdir(parents=True)
            hb = hb_dir / "heartbeat.json"
            hb.write_text(json.dumps({"band": "mid", "phase": "run"}), encoding="utf-8")
            (hb_dir / "ckpt_02.json").write_text("{}", encoding="utf-8")
            (hb_dir / "ckpt_01.json").write_text("{}", encoding="utf-8")
            ev = root / "abc_v3_run.json"
            ev.write_text("{}", encoding="utf-8")
            r2_dir = root / "round2"
            r2_dir.mkdir()
            (r2_dir / "guard_a.txt").write_text("ok", encoding="utf-8")
            r2k = root / "results.jsonl"
            r2k.write_bytes(b"12345")

            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "HEARTBEAT", hb),
                mock.patch.object(dsb, "V3_EVIDENCE", ev),
                mock.patch.object(dsb, "R2_STATE_DIR", r2_dir),
                mock.patch.object(dsb, "R2_KERNEL_RESULTS", r2k),
            ):
                res = dsb.runs()
            self.assertEqual(res["abc_v3"]["checkpoints"], ["ckpt_01.json", "ckpt_02.json"])
            self.assertEqual(res["abc_v3"]["status"], "COMPLETE — evidence written")
            self.assertEqual(res["round2_guard"]["kernel_results_bytes"], 5)
            self.assertEqual(res["round2_guard"]["guard_outputs"], ["guard_a.txt"])

    def test_venues_parses_kbm_and_cron_titles_and_handles_missing_kbm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crons = root / "crons"
            crons.mkdir()
            (crons / "threads-01.md").write_text("---\ntitle: Posting Malam\n---\n", encoding="utf-8")
            (crons / "fb-01.md").write_text("tanpa judul\n", encoding="utf-8")
            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "KBM_STATE", root / "missing_kbm.md"),
                mock.patch.object(dsb, "CRON_DIR", crons),
            ):
                res_missing = dsb.venues()
            self.assertIsNone(res_missing["kbm"]["published_count"])
            self.assertEqual(res_missing["threads"]["scheduled_tonight"], ["Posting Malam"])
            self.assertEqual(res_missing["facebook"]["scheduled_verifications"], ["fb-01"])

            kbm = root / "KBM_SERIALISASI_STATE.md"
            kbm.write_text(
                '## Published\n- Bab 1 "Awal"\n- Bab 2 "Kedua"\n\n'
                '## Queue\n- Bab 3 "Ketiga"\n- Bab 4 "Keempat"\n- Bab 5 "Kelima"\n',
                encoding="utf-8",
            )
            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "KBM_STATE", kbm),
                mock.patch.object(dsb, "CRON_DIR", crons),
            ):
                res_present = dsb.venues()
            self.assertEqual(res_present["kbm"]["published_count"], 2)
            self.assertEqual(res_present["kbm"]["published_titles"], ["Awal", "Kedua"])
            self.assertEqual(res_present["kbm"]["next_in_queue"], ["3", "4"])

    def test_bug_venues_kbm_without_queue_heading_leaks_published_into_queue(self) -> None:
        # Suspected bug: `text.split("## Queue", 1)[-1]` mengembalikan seluruh teks
        # jika heading `## Queue` tidak ada, sehingga bab terbit ikut terbaca di antrean.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kbm = root / "KBM_SERIALISASI_STATE.md"
            kbm.write_text('## Published\n- Bab 1 "Awal"\n', encoding="utf-8")
            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "KBM_STATE", kbm),
                mock.patch.object(dsb, "CRON_DIR", root / "no_crons"),
            ):
                res = dsb.venues()
            self.assertEqual(res["kbm"]["next_in_queue"], [])

    def test_ledger_missing_vs_partial_vs_complete_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            led = root / "LEDGER_PENGHASILAN.md"
            with mock.patch.object(dsb, "ROOT", root), mock.patch.object(dsb, "LEDGER", led):
                self.assertIsNone(dsb.ledger()["income_total_rp"])

                led.write_text("Total keseluruhan TUNAI terverifikasi: Rp 250.000\n", encoding="utf-8")
                partial = dsb.ledger()
                self.assertEqual(partial["income_total_rp"], 250000)
                self.assertIsNone(partial["utang_awal_baseline_rp"])
                self.assertIn("note_utang", partial)

                led.write_text(
                    "Total keseluruhan TUNAI terverifikasi: Rp 1.000.000\n"
                    "| **Total** | **500.000** | — | **100.000** | **400.000** | **20.0%** |\n",
                    encoding="utf-8",
                )
                full = dsb.ledger()
                self.assertEqual(full["income_total_rp"], 1000000)
                self.assertEqual(full["utang_awal_baseline_rp"], 500000)
                self.assertEqual(full["utang_awal_paid_rp"], 100000)
                self.assertEqual(full["utang_awal_remaining_rp"], 400000)
                self.assertAlmostEqual(full["utang_awal_pct"], 20.0)


class AceMobileDashboardEdgeTests(unittest.TestCase):
    """Kasus tepi untuk tools/ace_mobile_dashboard.py."""

    def test_load_json_missing_and_corrupt_return_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "missing.json"
            self.assertEqual(amd.load_json(p), {})
            p.write_text("{bad", encoding="utf-8")
            self.assertEqual(amd.load_json(p), {})

    def test_parse_logs_empty_and_caps_at_ten_reversed(self) -> None:
        self.assertEqual(amd.parse_logs_to_stories([]), [])
        lines = [f"[2026-11-17] [Daemon] Problem: bug-{i}" for i in range(15)]
        stories = amd.parse_logs_to_stories(lines)
        self.assertEqual(len(stories), 10)
        self.assertEqual(stories[0]["title"], "Tantangan: bug-14")
        self.assertEqual(stories[-1]["title"], "Tantangan: bug-5")

    def test_parse_logs_hypothesis_truncation_boundary_120(self) -> None:
        exact_120 = "h" * 120
        over_120 = "h" * 121
        stories = amd.parse_logs_to_stories([f"Hypothesis: {exact_120}", f"Hypothesis: {over_120}"])
        self.assertEqual(stories[1]["desc"], exact_120)
        self.assertEqual(len(stories[0]["desc"]), 123)
        self.assertTrue(stories[0]["desc"].endswith("..."))

    def test_parse_logs_decision_spacing_variants_and_param_defaults(self) -> None:
        stories = amd.parse_logs_to_stories(
            [
                "Decision: ACCEPTED",
                "Decision:   ACCEPTED",
                "(Param): evaluasi umum",
                "(Param): Task=math_1 Gain=+0.25",
                "Host Status: ok",
                "Host Status: RAM: 4096MB",
                "Push successful for Cycle",
            ]
        )
        by_titles = [s["title"] for s in stories]
        self.assertEqual(by_titles.count("Solusi Berhasil Diterima!"), 2)
        self.assertIn("Uji Kemampuan: tugas", by_titles)
        self.assertIn("Uji Kemampuan: math_1", by_titles)
        self.assertEqual(stories[0]["title"], "Hasil Evolusi Siklus  Disimpan")

    def test_get_focus_breakdown_live_false_ignores_active_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
            focus = amd.get_focus_breakdown(
                ["Running external verifier", "Problem: latensi tinggi", "Janitor: 2 file"],
                {"completed_cycles": 7, "history": [{"decision": "ACCEPTED"}]},
                {"last_cycle_id": 12},
                live_status=False,
            )
        self.assertEqual(focus["doing_status"], "TIDAK ADA HEARTBEAT")
        self.assertIn("latensi tinggi", focus["solving"])
        self.assertIn("2 file", focus["removing"])
        self.assertIn("siklus kode terakhir: 7".lower(), focus["adding"].lower())

    def test_get_focus_breakdown_live_branch_priorities(self) -> None:
        cases = [
            (["Running external verifier"], "VERIFIKASI"),
            (["Autonomous Repo Janitor"], "HOUSEKEEPING"),
            (["Pruned old artifacts"], "HOUSEKEEPING"),
            (["Executing Autonomous Software-Development"], "RISET KODE"),
            (["Committing checkpoint"], "SINKRONISASI"),
            (["Pushing to origin"], "SINKRONISASI"),
            (["Sleeping 30s"], "JEDA"),
            (["Active heartbeat"], "JEDA"),
            (["Something else"], "STATUS DIREKAM"),
        ]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
            for lines, expected_status in cases:
                with self.subTest(expected=expected_status):
                    out = amd.get_focus_breakdown(lines, {"completed_cycles": 3}, {"last_cycle_id": 9}, True)
                    self.assertEqual(out["doing_status"], expected_status)

    def test_get_focus_breakdown_reads_latest_problem_and_ai_consultation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ckpt = root / "checkpoints" / "self_dev"
            ckpt.mkdir(parents=True)
            (ckpt / "ai_consultations.json").write_text(
                json.dumps([{"timestamp": "t1", "status": "old"}, {"timestamp": "t2", "status": "ok"}]),
                encoding="utf-8",
            )
            with mock.patch.object(amd, "REPO_ROOT", root):
                focus = amd.get_focus_breakdown(
                    ["Problem: lama", "Problem: terbaru"],
                    {},
                    {},
                    live_status=False,
                )
        self.assertIn("terbaru", focus["solving"])
        self.assertIn("t2", focus["ai_used"])
        self.assertIn("status: ok", focus["ai_used"])

    def test_get_dashboard_data_missing_files_defaults_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
            data = amd.get_dashboard_data()
        self.assertFalse(data["live_status"])
        self.assertEqual(data["completed_cycles"], 0)
        self.assertEqual(data["soft_cycles"], 0)
        self.assertEqual(data["level"], 1)
        self.assertEqual(data["level_progress"], 0)
        self.assertEqual(data["stories"], [])

    def test_get_dashboard_data_heartbeat_freshness_window_90s(self) -> None:
        now = datetime.now(timezone.utc)
        cases = [
            ((now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z"), True),
            ((now - timedelta(seconds=95)).isoformat().replace("+00:00", "Z"), False),
            ((now + timedelta(seconds=30)).isoformat().replace("+00:00", "Z"), False),
            ("bukan-timestamp", False),
        ]
        for ts, expected_live in cases:
            with tempfile.TemporaryDirectory() as tmp, self.subTest(ts=ts):
                ckpt = Path(tmp) / "checkpoints" / "self_dev"
                ckpt.mkdir(parents=True)
                (ckpt / "daemon_heartbeat.json").write_text(
                    json.dumps({"timestamp": ts, "last_cycle_id": 125}),
                    encoding="utf-8",
                )
                with mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
                    data = amd.get_dashboard_data()
                self.assertEqual(data["live_status"], expected_live)
                self.assertEqual(data["level"], 2)
                self.assertEqual(data["level_progress"], 50)

    def test_bug_get_dashboard_data_crashes_when_heartbeat_json_is_list(self) -> None:
        # Suspected bug: load_json() mengembalikan list jika berkas berisi `[]`,
        # lalu get_dashboard_data() memanggil `heartbeat.get(...)` dan melempar AttributeError.
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoints" / "self_dev"
            ckpt.mkdir(parents=True)
            (ckpt / "daemon_heartbeat.json").write_text("[]", encoding="utf-8")
            with mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
                data = amd.get_dashboard_data()
            self.assertFalse(data["live_status"])

    def test_dashboard_http_handler_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
            server = amd.ReusableTCPServer(("127.0.0.1", 0), amd.DashboardHandler)
            port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request("GET", "/index.html")
                r_html = conn.getresponse()
                html_body = r_html.read().decode("utf-8")
                self.assertEqual(r_html.status, 200)
                self.assertIn("ACE", html_body)

                conn.request("GET", "/api/data")
                r_api = conn.getresponse()
                api_body = json.loads(r_api.read().decode("utf-8"))
                self.assertEqual(r_api.status, 200)
                self.assertEqual(r_api.getheader("Access-Control-Allow-Origin"), "*")
                self.assertIn("focus", api_body)

                conn.request("GET", "/tidak-ada")
                r_404 = conn.getresponse()
                r_404.read()
                self.assertEqual(r_404.status, 404)
                conn.close()
            finally:
                server.shutdown()
                server.server_close()

    def test_parse_logs_ignores_blank_and_prefix_only_lines(self) -> None:
        stories = amd.parse_logs_to_stories(["", "   ", "[2026-11-17 00:00] [Daemon]   "])
        self.assertEqual(stories, [])

    def test_parse_logs_janitor_and_shield_mapping(self) -> None:
        stories = amd.parse_logs_to_stories(
            [
                "[2026-11-17] [Daemon] External verifier: ALL CHECKS PASSED",
                "[2026-11-17] [Daemon] Janitor: pruned 3 temp dirs",
            ]
        )
        self.assertEqual(len(stories), 2)
        self.assertEqual(stories[0]["badge"], "Kebersihan")
        self.assertEqual(stories[0]["desc"], "pruned 3 temp dirs")
        self.assertEqual(stories[1]["badge"], "Aman")

    def test_get_dashboard_data_level_boundaries_at_49_50_99_100(self) -> None:
        expected = [(49, 1, 98), (50, 1, 0), (99, 1, 98), (100, 2, 0)]
        for cycles, exp_level, exp_progress in expected:
            with tempfile.TemporaryDirectory() as tmp, self.subTest(cycles=cycles):
                ckpt = Path(tmp) / "checkpoints" / "self_dev"
                ckpt.mkdir(parents=True)
                (ckpt / "daemon_heartbeat.json").write_text(
                    json.dumps({"last_cycle_id": cycles}),
                    encoding="utf-8",
                )
                with mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
                    data = amd.get_dashboard_data()
                self.assertEqual(data["level"], exp_level)
                self.assertEqual(data["level_progress"], exp_progress)

    def test_get_focus_breakdown_handles_empty_consultations_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoints" / "self_dev"
            ckpt.mkdir(parents=True)
            (ckpt / "ai_consultations.json").write_text("[]", encoding="utf-8")
            with mock.patch.object(amd, "REPO_ROOT", Path(tmp)):
                focus = amd.get_focus_breakdown([], {}, {}, live_status=False)
        self.assertIn("Belum ada bukti konsultasi", focus["ai_used"])

    def test_now_wib_and_operators_metadata_shape(self) -> None:
        self.assertTrue(dsb.now_wib().endswith(" WIB"))
        ops = dsb.operators()
        self.assertIn("director", ops)
        self.assertIn("local_model", ops)
        self.assertIn("note", ops)

    def test_main_writes_atomic_dashboard_state_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handover = root / "handover"
            handover.mkdir()
            out = handover / "ace_dashboard_state.json"
            with (
                mock.patch.object(dsb, "ROOT", root),
                mock.patch.object(dsb, "HANDOVER", handover),
                mock.patch.object(dsb, "OUT", out),
                mock.patch.object(dsb, "ADD58", root / "missing.md"),
                mock.patch.object(dsb, "HEARTBEAT", root / "missing_hb.json"),
                mock.patch.object(dsb, "V3_EVIDENCE", root / "missing_ev.json"),
                mock.patch.object(dsb, "R2_STATE_DIR", root / "missing_r2"),
                mock.patch.object(dsb, "R2_KERNEL_RESULTS", root / "missing_r2k.jsonl"),
                mock.patch.object(dsb, "KBM_STATE", root / "missing_kbm.md"),
                mock.patch.object(dsb, "LEDGER", root / "missing_ledger.md"),
                mock.patch.object(dsb, "CRON_DIR", root / "missing_crons"),
            ):
                dsb.main()
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "ace.dashboard_state.v1")
            self.assertIn("gate_board", payload)
            self.assertIn("runs", payload)
            self.assertIn("venues", payload)
            self.assertIn("ledger", payload)


if __name__ == "__main__":
    unittest.main()
