"""Tests for SecretVault, Live Chromium Browser Operator, Facebook Reels Connector, and KBM Operator."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import stat
from threading import Thread
import tempfile
import unittest

from ace_media_studio.reels_pipeline import render_vertical_reels
from ace_operational.connectors import facebook_reels, kbm_operator, live_browser
from ace_operational.connectors.vault import SecretVault, redact_secrets
from ace_operational.store import OperationalStore


def _live_chromium_available() -> bool:
    node, chrome = live_browser.detect_browser_binaries()
    return bool(node and chrome)


class _MockPortalHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/fb/reels/create":
            html = """<!doctype html><html><head><title>Creator Studio Reels</title></head><body>
            <h1>Buat Reels</h1>
            <input type="file" accept="video/*" onchange="document.getElementById('up_status').textContent='VIDEO_READY:' + this.files[0].name" />
            <div id="up_status">WAITING</div>
            <textarea name="description"></textarea>
            <button aria-label="Publish" onclick="document.getElementById('pub_res').textContent='PUBLISHED_OK:' + document.querySelector('textarea').value.slice(0,20)">Publish</button>
            <div id="pub_res" data-testid="reels_published_banner">PENDING</div>
            </body></html>"""
        elif self.path == "/fb/captcha_gate":
            html = """<!doctype html><html><head><title>Security Check</title></head><body>
            <h2>Verify you are human</h2>
            <div class="captcha-box">Please solve captcha to continue</div>
            <input type="password" name="pass" />
            </body></html>"""
        elif self.path == "/kbm/new_chapter":
            html = """<!doctype html><html><head><title>KBM Author Dashboard</title></head><body>
            <input data-testid="kbm_chapter_title" name="title" />
            <textarea data-testid="kbm_chapter_body" name="content"></textarea>
            <button data-testid="kbm_publish_btn" onclick="document.querySelector('[data-testid=kbm_status]').textContent='KBM_OK:' + document.querySelector('[data-testid=kbm_chapter_title]').value">Terbitkan</button>
            <div data-testid="kbm_status">READY</div>
            </body></html>"""
        else:
            self.send_response(404)
            self.end_headers()
            return
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _high_bar_reels_pkg() -> dict:
    return {
        "title": "Trik Hook 3 Detik Reels",
        "promise_terms": ["hook", "detik", "reels"],
        "action_terms": ["lihat", "coba", "simpan"],
        "cta": "Simpan reels ini dan ikuti tips selanjutnya!",
        "source_ref": "riset/reels_01",
        "scenes": [
            {"id": "sc_hook", "source_ref": "riset/1", "narration": "Kenapa 3 detik pertama menentukan Reels? Lihat cara ini!", "duration_ms": 3500, "has_visual_action": True},
            {"id": "sc_body", "source_ref": "riset/2", "narration": "Coba tampilkan visual hook dengan kontras tajam.", "duration_ms": 3500, "has_visual_action": True},
            {"id": "sc_cta", "source_ref": "riset/3", "narration": "Simpan dan ikuti panduan lengkapnya sekarang!", "duration_ms": 3000, "has_visual_action": True},
        ],
        "facts": [{"id": "f1", "text": "Hook visual 3 detik menekan drop-off awal penonton", "source_ref": "riset/1", "approved": True}],
        "tags": ["reels", "tips"],
    }


def _high_bar_kbm_pkg() -> dict:
    ch1 = (
        "\"Apakah surat rahasia itu masih terkunci di lemari besi, Raka?\" tanya Sora dengan suara gemetar.\n\n"
        "Raka menoleh cepat, namun bayangan asing ternyata sudah melintas di koridor luar. "
        "Walau ancaman penjaga makin dekat, Nadia tetap membuka laci arsip secara mendadak.\n\n"
        "Nadia: \"Kita berpacu dengan waktu sebelum alarm darurat berbunyi!\"\n\n"
        "\"Tetapi sandi cadangannya hilang!\" seru Raka sambil menunjuk jejak tinta biru?\n\n"
        "Petunjuk terakhir menunjuk tepat ke ruangan terkunci rapat..."
    )
    ch2 = (
        "Sora: \"Mengapa peringatan itu baru muncul di layar sekarang?!\"\n\n"
        "Akhirnya Nadia menemukan salinan kunci darurat, sebab Raka meninggalkan jejak penting. "
        "Meskipun pintu terbuka perlahan, suara langkah berat mendadak berhenti di tangga.\n\n"
        "\"Siapa yang membawa berkas kita ke ruang arsip?!\" bisik Raka.\n\n"
        "Ternyata bahaya terbesar justru ancaman tersembunyi di ruangan itu?"
    )
    return {
        "pack_id": "misteri_arsip",
        "title_config": {"characters": ["Sora", "Raka", "Nadia"]},
        "min_words": 40,
        "chapters": [
            {"chapter_number": 1, "chapter_id": "b1", "title": "Surat Terkunci", "text": ch1, "beats": ["konflik", "petunjuk"], "open_hooks": True},
            {"chapter_number": 2, "chapter_id": "b2", "title": "Bayangan Tangga", "text": ch2, "beats": ["pembalikan", "cliffhanger"], "open_hooks": True},
        ],
    }


class ConnectorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-conn-")
        self.ws = Path(self._tmp.name) / "ws"
        self.store = OperationalStore(self.ws)

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_vault_isolation_permissions_and_redaction(self) -> None:
        vault = SecretVault(self.ws)
        status = vault.set_venue_credentials("facebook", {"page_id": "12345", "page_access_token": "EAAGSuperSecret999999999"})
        self.assertTrue(status["has_api_credentials"])
        self.assertNotIn("EAAGSuperSecret999999999", json.dumps(vault.all_status()))
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(vault.secrets_file.stat().st_mode), 0o600)

        scrubbed = redact_secrets({"msg": "token=EAAGSuperSecret999999999", "page_access_token": "abc"}, extra_secrets=vault.secret_values())
        self.assertEqual(scrubbed["page_access_token"], "[REDACTED_SECRET]")
        self.assertNotIn("EAAGSuperSecret", json.dumps(scrubbed))

    def test_live_browser_blocks_unlisted_domain_and_halts_on_captcha(self) -> None:
        with self.assertRaises(PermissionError):
            live_browser.run_browser_workflow(
                self.store,
                venue="facebook",
                steps=[{"id": "rogue", "op": "navigate", "url": "https://evil-phishing.example.com/"}],
            )

        if not _live_chromium_available():
            self.skipTest("Chromium atau Node tidak tersedia")

        srv = self.enterContext(ThreadingHTTPServer(("127.0.0.1", 0), _MockPortalHandler))
        th = Thread(target=srv.serve_forever, daemon=True)
        th.start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(th.join, 3)

        res = live_browser.run_browser_workflow(
            self.store,
            venue="facebook",
            allowed_hosts=("127.0.0.1",),
            steps=[{"id": "hit_captcha", "op": "navigate", "url": f"http://127.0.0.1:{srv.server_port}/fb/captcha_gate"}],
            no_sandbox=True,
        )
        self.assertEqual(res["status"], "WAITING_FOR_OWNER_AUTH", res)
        self.assertIn(res["reason"], ("CAPTCHA_DETECTED", "LOGIN_REQUIRED"))

    def test_facebook_reels_real_chromium_upload_and_graph_api_mock(self) -> None:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg / ffprobe tidak tersedia")

        pkg = _high_bar_reels_pkg()
        bundle = render_vertical_reels(pkg, self.ws / "reels_out", width=720, height=1280, fps=24, renderer="ffmpeg")

        # Low quality package strictly refused even with dry_run=False
        weak_pkg = {
            "title": "Lemah",
            "scenes": [{"id": "s1", "source_ref": "x", "narration": "diam saja", "duration_ms": 14000, "has_visual_action": False}],
            "facts": [],
        }
        rej = facebook_reels.publish_reel(
            self.store, package=weak_pkg, video_path=bundle["video_path"], policy_override=True
        )
        self.assertFalse(rej["ok"])
        self.assertEqual(rej["verdict"], "REJECTED_BELOW_BAR")

        # Dry run succeeds with full quality verification
        dry = facebook_reels.publish_reel(self.store, package=pkg, video_path=bundle["video_path"], dry_run=True)
        self.assertTrue(dry["ok"], dry)
        self.assertEqual(dry["verdict"], "PREFLIGHT_DRY_RUN_READY")

        # Graph API 3-phase upload test via mock opener
        vault = SecretVault(self.ws)
        vault.set_venue_credentials("facebook", {"page_id": "999111", "page_access_token": "EAAGMockToken888888888"})
        calls = []

        def mock_opener(req, timeout=30):
            body = json.loads(req.data.decode("utf-8")) if req.headers.get("Content-type") == "application/json" else f"<binary:{len(req.data)}>"
            calls.append((req.full_url, body))
            if isinstance(body, dict) and body.get("upload_phase") == "start":
                return 200, {"video_id": "vid_555", "upload_url": "https://rupload.facebook.com/reels/vid_555"}
            return 200, {"success": True}

        g_res = facebook_reels.publish_reel(
            self.store,
            package=pkg,
            video_path=bundle["video_path"],
            backend="meta_graph_api",
            http_opener=mock_opener,
            policy_override=True,
        )
        self.assertTrue(g_res["published"], g_res)
        self.assertEqual(g_res["video_id"], "vid_555")
        self.assertEqual(len(calls), 3)

        # Real Chromium headless live_browser upload E2E against local Composer mock!
        if not _live_chromium_available():
            self.skipTest("Chromium atau Node tidak tersedia")
        srv = self.enterContext(ThreadingHTTPServer(("127.0.0.1", 0), _MockPortalHandler))
        th = Thread(target=srv.serve_forever, daemon=True)
        th.start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(th.join, 3)

        b_res = facebook_reels.publish_reel(
            self.store,
            package=pkg,
            video_path=bundle["video_path"],
            backend="live_browser",
            publish_mode="auto",
            reels_create_url=f"http://127.0.0.1:{srv.server_port}/fb/reels/create",
            allowed_hosts=("127.0.0.1",),
            policy_override=True,
        )
        self.assertTrue(b_res["published"], b_res)
        self.assertEqual(b_res["verdict"], "PUBLISHED")
        verify_step = next(s for s in b_res["browser"]["steps"] if s["id"] == "verify_result")
        self.assertIn("PUBLISHED_OK:", verify_step["evidence"]["text"])
        shot_step = next(s for s in b_res["browser"]["steps"] if s["id"] == "proof_shot")
        self.assertTrue(Path(shot_step["evidence"]["screenshot_path"]).is_file())

    def test_kbm_operator_catalog_royalty_and_real_chromium_submit(self) -> None:
        cat = self.ws / "kbm_catalog.json"
        cat.write_text(json.dumps({
            "as_of": "2026-11-24",
            "serials": [{
                "id": "ser_arsip",
                "title": "Misteri Arsip Kota",
                "status": "naskah",
                "total_chapters": 4,
                "completed_chapters": 2,
                "total_words": 2400,
                "weekly_target": 2,
            }],
        }), encoding="utf-8")
        cat_rep = kbm_operator.audit_kbm_catalog(cat, as_of_date="2026-11-24")
        self.assertEqual(cat_rep["titles"]["summary"]["total_serials"], 1)

        csv_p = self.ws / "royalti.csv"
        csv_p.write_text("serial,date,amount,currency,units\nser_arsip,2026-11-10,300000,IDR,30\n", encoding="utf-8")
        roy = kbm_operator.summarize_kbm_royalties([csv_p])
        self.assertEqual(roy["totals_by_currency"]["IDR"], "300000")
        self.assertEqual(roy["totals_by_serial"]["ser_arsip"]["tier_summary"]["rate_percent"], "80")

        # Reject weak draft
        weak = kbm_operator.submit_kbm_chapter(
            self.store,
            chapter_package={"chapters": [{"text": "pendek sekali"}], "min_words": 50},
            chapter_title="Lemah",
            chapter_body="pendek",
            policy_override=True,
        )
        self.assertFalse(weak["ok"])
        self.assertEqual(weak["verdict"], "REJECTED_BELOW_BAR")

        if not _live_chromium_available():
            self.skipTest("Chromium atau Node tidak tersedia")
        srv = self.enterContext(ThreadingHTTPServer(("127.0.0.1", 0), _MockPortalHandler))
        th = Thread(target=srv.serve_forever, daemon=True)
        th.start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(th.join, 3)

        ok = kbm_operator.submit_kbm_chapter(
            self.store,
            chapter_package=_high_bar_kbm_pkg(),
            chapter_title="Bab 1: Surat Terkunci",
            chapter_body="Isi bab berkualitas tinggi.",
            publish_mode="auto",
            kbm_url=f"http://127.0.0.1:{srv.server_port}/kbm/new_chapter",
            allowed_hosts=("127.0.0.1",),
            policy_override=True,
        )
        self.assertTrue(ok["submitted"], ok)
        self.assertEqual(ok["verdict"], "PUBLISHED")


if __name__ == "__main__":
    unittest.main()
