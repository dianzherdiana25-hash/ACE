"""Behavioral tests for Indonesian morphology, Nazief-Adriani stemming, and colloquial normalization (`ace_indo_nlp.morphology`)."""
from __future__ import annotations

import unittest

from ace_indo_nlp.morphology import (
    analyze_morphology,
    bounded_edit_distance,
    is_laughter_token,
    normalize_colloquial,
    stem_candidates,
    stem_word,
)


class MorphologyTests(unittest.TestCase):
    def test_nazief_adriani_nasalization_clitics_and_multi_prefix(self) -> None:
        known = {"tulis", "sapu", "pukul", "kirim", "baik", "jelas", "hati", "sayang", "ajar", "cari", "cerita"}
        cases = {
            "menulis": "tulis",
            "menyapu": "sapu",
            "memukulnya": "pukul",
            "mengirimkan": "kirim",
            "memperbaiki": "baik",
            "diperjelas": "jelas",
            "memperhatikan": "hati",
            "menyayangiku": "sayang",
            "pelajarannya": "ajar",
            "nyari": "cari",
            "nulis": "tulis",
            "ceritain": "cerita",
        }
        for surface, expected_root in cases.items():
            info = analyze_morphology(surface, known_roots=known)
            self.assertEqual(info["root"], expected_root, surface)
            self.assertIn(expected_root, stem_candidates(surface))
            self.assertEqual(stem_word(surface, known_roots=known), expected_root)

        dup = analyze_morphology("kata-katanya", known_roots={"kata"})
        self.assertTrue(dup["is_reduplicated"])
        self.assertEqual(dup["root"], "kata")

        kupu = analyze_morphology("kupu-kupu", known_roots={"kupu"})
        self.assertFalse(kupu["is_reduplicated"])

    def test_colloquial_normalization_and_edit_distance(self) -> None:
        norm, rewrites = normalize_colloquial("gmn kbr lu skrg, udh blm ngomong sm gw?")
        self.assertEqual(norm, "bagaimana kabar kamu sekarang sudah belum bicara sama aku")
        self.assertEqual(rewrites["gmn"], "bagaimana")
        self.assertEqual(rewrites["ngomong"], "bicara")

        self.assertTrue(is_laughter_token("wkwkwk"))
        self.assertTrue(is_laughter_token("hahahaha"))
        self.assertFalse(is_laughter_token("bahasa"))
        laugh_norm, laugh_rw = normalize_colloquial("wkwkwk bosen bgt laper nih")
        self.assertEqual(laugh_norm, "haha bosan sangat lapar nih")
        self.assertEqual(laugh_rw["wkwkwk"], "haha")

        # Keep imperative coding verb "buat" untouched
        norm_code, rw_code = normalize_colloquial("Tolong buat catatan pengeluaran sederhana")
        self.assertIn("buat catatan", norm_code)
        self.assertNotIn("buat", rw_code)

        self.assertEqual(bounded_edit_distance("belajar", "belajr"), 1)
        self.assertEqual(bounded_edit_distance("kata", "katanya"), 3)
        self.assertEqual(bounded_edit_distance("a", "abcdef"), 99)


if __name__ == "__main__":
    unittest.main()
