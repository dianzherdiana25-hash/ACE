"""Uji preseden tertanggal dan kondisi analogi dari arsip sintetis."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import precedent_memory as precedent


def case(identifier, *, day="2026-11-19", issue="Mode observasi jembatan", tags=None,
         conditions=None, outcome="adopt"):
    return {"case_id": identifier, "decided_on": day, "issue": issue,
            "tags": tags if tags is not None else ["Bridge"],
            "conditions": conditions if conditions is not None else ["draf"],
            "outcome": outcome, "source_ref": f"fixture/cases/{identifier}",
            "evidence_refs": [f"fixture/evidence/{identifier}"]}


def request(**updates):
    return {"as_of": "2026-11-20", "issue": "Mode observasi jembatan", "tags": ["ＢＲＩＤＧＥ"],
            "conditions": ["Draf"], "proposed_outcome": "adopt", "limit": 3, **updates}


class PrecedentMemoryTests(unittest.TestCase):
    def test_ties_use_recency_then_id_and_ignore_future_or_same_day(self):
        archive = [case("older", day="2026-11-18"), case("b"), case("a"),
                   case("future", day="2026-11-21"), case("unknown_intra_day", day="2026-11-20")]
        result = precedent.PrecedentMemory(archive).search(request())
        self.assertEqual(result["matches_seen"], 3)
        self.assertEqual([match["case_id"] for match in result["matches"]], ["a", "b", "older"])
        self.assertEqual(result, precedent.PrecedentMemory(archive[::-1]).search(request()))
        first = result["matches"][0]
        self.assertEqual(first["match_score"], {"numerator": 3, "denominator": 1})
        self.assertEqual(first["source_ref"], "fixture/cases/a")
        self.assertTrue(first["applicable_conditions"])

    def test_counter_precedent_stays_visible_outside_result_limit(self):
        archive = [case("winner"),
                   case("counter", issue="Observasi stok", conditions=["approval", "DRAF"], outcome="reject")]
        result = precedent.PrecedentMemory(archive).search(request(limit=1))
        self.assertEqual(result["matches_seen"], 2)
        self.assertEqual([match["case_id"] for match in result["matches"]], ["winner"])
        counter = result["best_different_outcome"]
        self.assertEqual(counter["case_id"], "counter")
        self.assertEqual(counter["evidence_refs"], ["fixture/evidence/counter"])
        self.assertEqual(counter["conditions_missing"], ["approval"])
        self.assertFalse(counter["applicable_conditions"])
        self.assertEqual(counter["relation"], "different_outcome")

    def test_no_pseudo_match_from_stop_words_or_unknown_history(self):
        archive = [case("elsewhere", issue="Riset sendiri oleh pemilik", tags=["riset"])]
        result = precedent.PrecedentMemory(archive).search(request(issue="geologi oleh", tags=[]))
        self.assertEqual(result["matches"], [])
        self.assertIsNone(result["best_different_outcome"])

    def test_rejects_invalid_dates_missing_provenance_and_duplicate_ids(self):
        for archive in ([case("x"), case("x")], [case("a", day="20261119")],
                        [{**case("a"), "source_ref": ""}], [{**case("a"), "evidence_refs": []}]):
            with self.subTest(archive=archive), self.assertRaises(precedent.PrecedentError):
                precedent.PrecedentMemory(archive)

    def test_query_without_proposed_outcome_is_explicit(self):
        result = precedent.PrecedentMemory([case("a", outcome="reject")]).search(request(proposed_outcome=None))
        self.assertEqual(result["matches"][0]["relation"], "unset")
        self.assertIsNone(result["best_different_outcome"])

    def test_cli_reads_archive_and_request_from_separate_files(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        archive, query = root / "archive.json", root / "query.json"
        archive.write_text(json.dumps([case("a")]), encoding="utf-8")
        query.write_text(json.dumps(request()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(precedent.main([str(archive), str(query)]), 0)
        self.assertEqual(json.loads(output.getvalue())["matches"][0]["case_id"], "a")

    def test_term_lookup_can_find_precedent_without_matching_tags(self):
        archive = [case("term", tags=["other"]), case("none", issue="Geologi batuan", tags=["riset"])]
        result = precedent.PrecedentMemory(archive).search(request(tags=[]))
        self.assertEqual(result["matches_seen"], 1)
        self.assertEqual(result["matches"][0]["case_id"], "term")
        self.assertEqual(result["matches"][0]["matched_tags"], [])
