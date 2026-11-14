"""Behavioral integrity tests for curated Indonesian lexicon KB, semantic graph, and POS inference (`ace_indo_nlp.lexicon_kb`)."""
from __future__ import annotations

import unittest

from ace_indo_nlp.lexicon_kb import (
    CORE_INDONESIAN_LEXICON,
    SEMANTIC_RELATIONS,
    STOPWORDS_ID,
    TELEGRAPHIC_PATTERNS,
    VALID_POS_ROLES,
    infer_indonesian_pos,
)
from ace_indo_nlp.phonotactics import syllabify_indonesian


class LexiconKBTests(unittest.TestCase):
    def test_core_lexicon_integrity_and_phonotactic_soundness(self) -> None:
        self.assertGreaterEqual(len(CORE_INDONESIAN_LEXICON), 260)
        seen_words: set[str] = set()
        roles_covered: set[str] = set()
        for word, role, meaning, domains, example, syns, ants in CORE_INDONESIAN_LEXICON:
            self.assertNotIn(word, seen_words, f"Duplicate word: {word}")
            seen_words.add(word)
            self.assertIn(role, VALID_POS_ROLES, word)
            roles_covered.add(role)
            self.assertGreater(len(meaning.strip()), 4, word)
            self.assertGreater(len(example.strip()), 6, word)
            self.assertGreaterEqual(len(domains), 1, word)
            self.assertTrue(syllabify_indonesian(word)["pronounceable"], f"Unpronounceable KB word: {word}")
            self.assertIsInstance(syns, tuple)
            self.assertIsInstance(ants, tuple)

        self.assertEqual(roles_covered, VALID_POS_ROLES)
        # Everyday Indonesian conversation coverage
        for everyday in ("kabar", "hobi", "musik", "warna", "cuaca", "hujan", "capek", "bosan", "lapar", "teh", "biru", "merah"):
            self.assertIn(everyday, seen_words)
        for interj in ("haha", "wkwk", "dong", "sih", "deh", "nih", "kok"):
            self.assertIn(interj, STOPWORDS_ID)

        # Authenticity guard: test discovery words must stay outside core KB
        for holdout_unknown in ("samudra", "lentera", "senja", "nirwana", "kopi", "pahit", "cakrawala", "mentari", "merdu"):
            self.assertNotIn(holdout_unknown, seen_words)
            self.assertNotIn(holdout_unknown, STOPWORDS_ID)

    def test_semantic_relations_pos_inference_and_telegraphic_patterns(self) -> None:
        self.assertIn("damai", SEMANTIC_RELATIONS["tenang"]["synonyms"])
        self.assertIn("gelap", SEMANTIC_RELATIONS["terang"]["antonyms"])
        self.assertIn("segar", SEMANTIC_RELATIONS["capek"]["antonyms"])
        self.assertIn("lelah", SEMANTIC_RELATIONS["capek"]["synonyms"])
        self.assertGreaterEqual(len(TELEGRAPHIC_PATTERNS), 12)

        self.assertEqual(infer_indonesian_pos("merdu", "indah didengar suara", explicit_role="sifat"), "sifat")
        self.assertEqual(infer_indonesian_pos("menyanyi", "melakukan nyanyian suara"), "aksi")
        self.assertEqual(infer_indonesian_pos("bahagia", "perasaan sukacita"), "emosi")
        self.assertEqual(infer_indonesian_pos("dermaga", "tempat kapal bersandar"), "tempat")
        self.assertEqual(infer_indonesian_pos("pahit", "rasa tajam seperti kopi"), "sifat")
        self.assertEqual(infer_indonesian_pos("lentera", "cahaya penuntun"), "objek")


if __name__ == "__main__":
    unittest.main()
