"""Behavioral tests for Indonesian discourse parser, anaphora, revisions, and Q&A realization (`ace_indo_nlp.discourse`)."""
from __future__ import annotations

import unittest

from ace_indo_nlp.discourse import (
    analyze_discourse_cues,
    extract_meaning_query,
    extract_query_target,
    format_lexicon_qa_clauses,
    parse_teaching_or_correction,
    realize_indonesian_clauses,
)


class DiscourseTests(unittest.TestCase):
    def test_teaching_anaphora_and_correction_parsing(self) -> None:
        direct = parse_teaching_or_correction("ajarkan kata lentera artinya cahaya penuntun (objek)")
        self.assertIsNotNone(direct)
        self.assertEqual(direct["word"], "lentera")
        self.assertEqual(direct["role"], "objek")
        self.assertFalse(direct["is_correction"])
        self.assertFalse(direct["is_anaphora"])

        anaphora = parse_teaching_or_correction("oh, itu artinya lautan luas di bumi", pending_word="samudra")
        self.assertIsNotNone(anaphora)
        self.assertEqual(anaphora["word"], "samudra")
        self.assertEqual(anaphora["meaning_id"], "lautan luas di bumi")
        self.assertTrue(anaphora["is_anaphora"])

        anaphora_q = parse_teaching_or_correction("itu artinya apa ya?", pending_word="samudra")
        self.assertIsNone(anaphora_q)

        corr = parse_teaching_or_correction("ralat kata samudra jadi hamparan laut sangat luas")
        self.assertIsNotNone(corr)
        self.assertEqual(corr["word"], "samudra")
        self.assertEqual(corr["meaning_id"], "hamparan laut sangat luas")
        self.assertTrue(corr["is_correction"])

        self.assertIsNone(parse_teaching_or_correction("buatkan aplikasi catatan pengeluaran"))

    def test_query_extraction_discourse_cues_and_realization(self) -> None:
        self.assertEqual(extract_meaning_query("Apa arti kata senja?"), "senja")
        self.assertEqual(extract_query_target("Apa sinonim kata tenang?"), {"word": "tenang", "query_kind": "synonym"})
        self.assertEqual(extract_query_target("lawan kata gelap apa?"), {"word": "gelap", "query_kind": "antonym"})
        self.assertEqual(extract_query_target("kata dasar memperbaiki apa?"), {"word": "memperbaiki", "query_kind": "morphology"})

        cues = analyze_discourse_cues("gmn kbr lu skrg? ak masih bingung")
        self.assertTrue(cues["asks_wellbeing"])
        self.assertTrue(cues["is_question"])
        self.assertTrue(cues["is_confused_or_negative"])
        self.assertIn("gmn", cues["slang_rewrites"])

        qa_syn = format_lexicon_qa_clauses(
            query_target={"word": "tenang", "query_kind": "synonym"},
            entry={
                "word": "tenang",
                "syllables": ["te", "nang"],
                "role": "emosi",
                "meaning_id": "sikap sabar dan damai",
                "examples": ["Mari urai kendala dengan tenang."],
                "source": "curriculum",
                "synonyms": ["damai", "sabar"],
                "antonyms": ["panik"],
            },
            grounded=[],
            mode_label="Offline Lokal",
        )
        self.assertIn("damai", qa_syn[0])

        clauses = realize_indonesian_clauses(
            user_text="Aku masih bingung memahami samudra",
            cues=cues,
            grounded=[{"word": "samudra", "syllables": ["sa", "mu", "dra"], "meaning_id": "lautan luas", "source": "user_taught", "examples": ["Samudra biru."]}],
            profile={"vocab_count": 210, "user_taught_count": 1},
            mode_label="Offline Lokal",
            latest_task=None,
            recent_assistant_texts=[],
            history_turns=2,
            curious_word={"word": "lentera", "syllables": ["len", "te", "ra"]},
        )
        joined = "\n\n".join(clauses)
        self.assertIn("samudra", joined)
        self.assertIn("lentera", joined)


if __name__ == "__main__":
    unittest.main()
