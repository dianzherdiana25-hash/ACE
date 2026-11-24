"""Tests for Anti-Hallucination High-Bar Quality Gate Engine & Outcome Calibration."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.memory_bridge import ConversationalMemoryManager
from ace_operational.outcome_calibrator import calibration_report, record_real_outcome
from ace_operational.quality_gate_engine import (
    check_cross_agent_heterogeneity,
    evaluate_code_quality,
    evaluate_kbm_quality,
    evaluate_reels_quality,
    evaluate_research_grounding,
)
from ace_operational.store import OperationalStore


class QualityGateEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-qge-")
        self.ws = Path(self._tmp.name) / "ws"
        self.store = OperationalStore(self.ws)
        self.memory = ConversationalMemoryManager(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_research_grounding_rejects_ungrounded_and_accepts_cited(self) -> None:
        bad = evaluate_research_grounding(
            claims=["Produk A pasti viral 90%"],
            sources=[],
        )
        self.assertFalse(bad["passed"])
        self.assertEqual(bad["verdict"], "UNGROUNDED_CLAIMS")

        good = evaluate_research_grounding(
            claims=[{"claim": "Format vertikal 9:16 memberi rasio tonton ulang lebih baik", "source_ref": "doc_1"}],
            sources=[{
                "id": "doc_1",
                "observed_at": "2026-11-22T00:00:00Z",
                "content": "Studi internal format video vertikal sembilan banding enam belas menunjukkan peningkatan penyelesaian tontonan pemirsa seluler.",
            }],
        )
        self.assertTrue(good["passed"], good)
        self.assertEqual(good["score_bp"], 10000)

    def test_reels_quality_rejects_weak_script_then_accepts_strong_revision(self) -> None:
        weak = evaluate_reels_quality({
            "title": "Video Biasa",
            "scenes": [
                {"id": "intro_lama", "source_ref": "s1", "narration": "Halo semuanya selamat datang di channel ini hari ini kita santai saja.", "duration_ms": 14000, "has_visual_action": False},
            ],
            "facts": [{"id": "f1", "text": "Fakta belum dicek", "source_ref": "draft", "approved": False}],
        }, min_score_bp=8500)
        self.assertFalse(weak["passed"])
        self.assertEqual(weak["verdict"], "REJECTED_BELOW_BAR")
        self.assertEqual(weak["checks"]["lowest_proxy_scene"], "intro_lama")
        self.assertGreaterEqual(len(weak["revision_feedback"]), 2)

        strong = evaluate_reels_quality({
            "title": "Rahasia Hook 3 Detik Reels",
            "promise_terms": ["hook", "detik", "reels"],
            "action_terms": ["lihat", "coba", "simpan"],
            "cta": "Simpan reels ini dan ikuti update berikutnya!",
            "scenes": [
                {"id": "sc_hook", "source_ref": "res/1", "narration": "Kenapa 3 detik pertama menentukan nasib Reels kamu? Lihat contoh ini!", "duration_ms": 3000, "has_visual_action": True},
                {"id": "sc_isi", "source_ref": "res/2", "narration": "Coba ubah adegan hook ke pertanyaan konkret agar detik berikutnya terus ditonton.", "duration_ms": 5000, "has_visual_action": True},
                {"id": "sc_cta", "source_ref": "res/3", "narration": "Simpan dan ikuti tips Reels berikutnya sekarang!", "duration_ms": 3000, "has_visual_action": True},
            ],
            "facts": [{"id": "f1", "text": "Hook visual 3 detik menekan drop-off awal penonton", "source_ref": "res/1", "approved": True}],
            "tags": ["reels", "kreator"],
        }, min_score_bp=8500)
        self.assertTrue(strong["passed"], strong)
        self.assertGreaterEqual(strong["score_bp"], 8500)

    def test_kbm_quality_rejects_weak_chapters_and_accepts_rich_arc_chapters(self) -> None:
        weak = evaluate_kbm_quality({
            "pack_id": "cerita_lemah",
            "chapters": [{"chapter_id": "b1", "text": "Hari ini cerah. Besok cerah."}],
            "title_config": {"characters": ["Sora"]},
            "min_words": 50,
        }, min_score_bp=8500)
        self.assertFalse(weak["passed"])
        self.assertEqual(weak["verdict"], "REJECTED_BELOW_BAR")

        # Craft high-quality chapters hitting alur (turns+beats+paras), tokoh (dialogue+multi chars), bahasa, daya_tarik (hooks).
        ch1 = (
            "\"Apakah surat rahasia itu masih terkunci di lemari besi, Raka?\" tanya Sora dengan suara gemetar.\n\n"
            "Raka menoleh cepat, namun bayangan asing ternyata sudah melintas di koridor luar. "
            "Walau ancaman penjaga makin dekat, Nadia tetap membuka laci arsip secara mendadak.\n\n"
            "Nadia: \"Kita berpacu dengan waktu sebelum alarm darurat berbunyi!\"\n\n"
            "\"Tetapi sandi cadangannya hilang!\" seru Raka sambil menunjuk jejak tinta biru yang hampir pudar?\n\n"
            "Petunjuk terakhir justru menunjuk tepat ke kamar sebelah yang terkunci rapat..."
        )
        ch2 = (
            "Sora: \"Mengapa peringatan itu baru muncul di layar sekarang?!\"\n\n"
            "Akhirnya Nadia menemukan salinan kunci darurat, sebab Raka sempat meninggalkan petunjuk di bingkai foto. "
            "Meskipun pintu terbuka perlahan, suara langkah berat mendadak berhenti tepat di ambang tangga.\n\n"
            "\"Siapa yang membawa berkas perjanjian kita ke ruang arsip?!\" bisik Raka nyaris tanpa napas.\n\n"
            "Ternyata bahaya terbesar tidak datang dari luar gedung, melainkan ancaman tersembunyi di ruangan itu?"
        )
        strong = evaluate_kbm_quality({
            "pack_id": "misteri_arsip",
            "title_config": {"characters": ["Sora", "Raka", "Nadia"]},
            "min_words": 40,
            "chapters": [
                {"chapter_number": 1, "chapter_id": "b1", "title": "Surat Terkunci", "text": ch1, "beats": ["konflik", "petunjuk"], "open_hooks": True},
                {"chapter_number": 2, "chapter_id": "b2", "title": "Bayangan Tangga", "text": ch2, "beats": ["pembalikan", "cliffhanger"], "open_hooks": True},
            ],
        }, min_score_bp=8500, min_words_per_chapter=40)
        self.assertTrue(strong["passed"], strong)
        self.assertGreaterEqual(strong["score_bp"], 8500)

    def test_code_quality_and_cross_review_and_outcome_calibration(self) -> None:
        frozen_bad = evaluate_code_quality(self.ws, target_files=("docs/UPSTREAM_SOURCES.json",), run_verify_sources=False)
        self.assertFalse(frozen_bad["passed"])

        (self.ws / "mod_ok.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        code_ok = evaluate_code_quality(
            self.ws,
            target_files=("mod_ok.py",),
            test_commands=[["python3", "-c", "import mod_ok; assert mod_ok.add(2, 3) == 5"]],
            run_verify_sources=False,
        )
        self.assertTrue(code_ok["passed"], code_ok)

        self_rev = check_cross_agent_heterogeneity(
            creator_agent="a1", creator_vendor="antigravity",
            reviewer_agent="a1", reviewer_vendor="antigravity",
            approved=True, reviewer_score_bp=9500,
        )
        self.assertFalse(self_rev["passed"])

        cross_ok = check_cross_agent_heterogeneity(
            creator_agent="a1", creator_vendor="antigravity",
            reviewer_agent="g1", reviewer_vendor="gemini",
            approved=True, reviewer_score_bp=9200, require_distinct_vendor=True,
        )
        self.assertTrue(cross_ok["passed"])

        sk = self.store.save_skill(
            name="kbm_serial_arc",
            domain="kbm_apps",
            preconditions=[],
            boundary_limitations=[],
            procedure_steps=["Tambahkan cliffhanger akhir bab"],
            verification_template={},
            source_task_ids=[],
        )
        cal = record_real_outcome(
            self.store,
            self.memory,
            goal_id="goal_demo_kbm",
            domain="kbm_apps",
            predicted_score_bp=8700,
            actual_metrics={"reads": 4500, "omzet_idr": "300000", "rating": 4.8},
            skill_ids=(sk["skill_id"],),
            min_success_score_bp=7000,
        )
        self.assertTrue(cal["success"])
        self.assertEqual(cal["outcome"]["actual_metrics"]["computed"]["pasal7_author_share"]["rate_percent"], "80")
        rep = calibration_report(self.store, domain="kbm_apps")
        self.assertEqual(rep["count"], 1)


if __name__ == "__main__":
    unittest.main()
