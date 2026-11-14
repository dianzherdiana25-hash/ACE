"""Behavioral tests for Indonesian phonotactics, syllabification, prosody, and babbling (`ace_indo_nlp.phonotactics`)."""
from __future__ import annotations

import unittest

from ace_indo_nlp.phonotactics import (
    echo_input_syllables,
    syllabify_indonesian,
    synthesize_babble,
    tokenize_phonemes,
)


class PhonotacticsTests(unittest.TestCase):
    def test_digraph_tokenization_and_syllabification(self) -> None:
        self.assertEqual(tokenize_phonemes("menyayangi"), ["m", "e", "ny", "a", "y", "a", "ng", "i"])
        self.assertEqual(tokenize_phonemes("khusus"), ["kh", "u", "s", "u", "s"])
        cases = {
            "bernyanyi": (["ber", "nya", "nyi"], "ber·NYA·nyi"),
            "menyayangi": (["me", "nya", "ya", "ngi"], "me·nya·YA·ngi"),
            "kebersamaan": (["ke", "ber", "sa", "ma", "an"], "ke·ber·sa·MA·an"),
            "syukur": (["syu", "kur"], "SYU·kur"),
            "struktur": (["struk", "tur"], "STRUK·tur"),
            "kompleks": (["kom", "pleks"], "KOM·pleks"),
        }
        for word, (expected_syls, expected_prosody) in cases.items():
            res = syllabify_indonesian(word)
            self.assertTrue(res["pronounceable"], word)
            self.assertEqual(res["syllables"], expected_syls, word)
            self.assertEqual(res["prosody_cue"], expected_prosody, word)
            self.assertEqual(res["hyphenated"], "-".join(expected_syls))

    def test_invalid_phonotactics_and_babble_synthesis(self) -> None:
        for invalid in ("", "123!", "bcdfg", "strkkk", "xztpq"):
            res = syllabify_indonesian(invalid)
            self.assertFalse(res["pronounceable"], invalid)
            self.assertEqual(res["syllables"], [])

        b1 = synthesize_babble(consonants=["d", "l", "r"], vowels=["e", "o"], count=4, seed=2)
        b2 = synthesize_babble(consonants=["b", "m", "n"], vowels=["a", "u"], count=4, seed=5)
        self.assertEqual(len(b1), 4)
        self.assertEqual(len(b2), 4)
        self.assertTrue(all(x["pronounceable"] and set(x["word"]).issubset({"d", "l", "r", "e", "o"}) for x in b1))
        self.assertNotEqual([x["word"] for x in b1], [x["word"] for x in b2])
        self.assertEqual(synthesize_babble(consonants=[], vowels=["a"], count=3), [])

    def test_echo_input_syllables(self) -> None:
        echoed = echo_input_syllables("Halo dunia indah sekali!", max_words=3)
        self.assertEqual(echoed, ["ha-lo", "du-ni-a", "in-dah"])


if __name__ == "__main__":
    unittest.main()
