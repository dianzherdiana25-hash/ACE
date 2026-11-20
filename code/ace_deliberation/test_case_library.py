"""Verifier isolasi partisi, versi kasus, dan snapshot bertanggal."""
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import case_library as model


CUTOFF = "2026-11-15T00:00:00Z"


def entry(key, day=10, *, tags=None, partition="training", origin="historical"):
    return {
        "case_id": key, "event_id": f"event/{key}", "title": f"Fixture {key}",
        "question_ref": f"q/{key}", "resolution_ref": f"r/{key}",
        "available_at": f"2026-11-{day:02}T00:00:00Z", "outcome": 1,
        "tags": tags if tags is not None else ["infra", "durasi"], "partition": partition,
        "origin": origin, "lesson": {"text": "Sumber resolusi menentukan tanggal.",
                                     "ref": f"lesson/{key}", "available_at": "2026-11-19T00:00:00Z"},
    }


def fixture():
    return {
        "library_ref": "fixture/library", "query": {"tags": ["infra"], "partition": "training",
                                                    "origin": "any", "as_of": CUTOFF, "limit": 10},
        "cases": [
            entry("older", 1), entry("z", tags=["durasi", "infra"]), entry("a"),
            entry("impact", 12, tags=["riset", "survei"]),
            entry("held", partition="held_out"), entry("scenario", 11, origin="synthetic"),
            entry("later", 19),
        ],
    }


class LibraryTests(unittest.TestCase):
    def test_lookup_matches_all_tags_and_orders_newest_then_id(self):
        payload = fixture()
        payload["query"]["tags"] = ["infra", "durasi"]
        result = model.lookup(payload)
        self.assertEqual([row["case_id"] for row in result["results"]], ["scenario", "a", "z", "older"])
        self.assertEqual(result["available_count"], 5)
        self.assertEqual(result["matched_count"], 4)
        self.assertEqual(result["query"]["tags"], ["durasi", "infra"])
        self.assertEqual(result["results"][0]["origin"], "synthetic")
        self.assertEqual(result["results"][0]["resolution_ref"], "r/scenario")

    def test_held_out_and_synthetic_filters_preserve_explicit_partitions(self):
        data = fixture()
        data["query"].update(partition="held_out", origin="historical")
        result = model.lookup(data)
        self.assertEqual([x["case_id"] for x in result["results"]], ["held"])
        self.assertEqual(result["available_count"], 1)
        data["query"]["origin"] = "synthetic"
        result = model.lookup(data)
        self.assertFalse(result["results"])
        self.assertEqual(result["available_count"], 0)

    def test_future_lessons_are_excluded_from_digest_and_results(self):
        left = fixture()
        right = fixture()
        right["cases"][0]["lesson"]["text"] = "Versi pelajaran yang berbeda."
        before = model.lookup(left)
        self.assertEqual(before, model.lookup(right))
        self.assertTrue(all(row["lesson"] is None for row in before["results"]))
        for data in (left, right):
            data["query"]["as_of"] = "2026-11-19T07:00:00+07:00"
        after = model.lookup(left)
        self.assertNotEqual(after["snapshot_sha256"], model.lookup(right)["snapshot_sha256"])
        self.assertEqual(after["results"][-1]["lesson"]["ref"], "lesson/older")
        self.assertEqual(after["results"][0]["case_id"], "later")

    def test_training_snapshot_is_independent_of_held_out_entries(self):
        original = fixture()
        alternate = fixture()
        alternate["cases"][4]["lesson"]["text"] = "Materi held-out direvisi."
        alternate["cases"][4]["outcome"] = 0
        self.assertEqual(model.lookup(original), model.lookup(alternate))

    def test_snapshot_digest_is_reproducible_with_canonical_utf8(self):
        data = fixture()
        data["query"].update(tags=[], limit=100)
        data["cases"][0]["title"] = "Perubahan Δ dalam bukti"
        result = model.lookup(data)
        entries = sorted(result["results"], key=lambda row: row["case_id"])
        payload = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(hashlib.sha256(payload.encode("utf-8")).hexdigest(), result["snapshot_sha256"])

    def test_matching_is_exact_and_output_limit_does_not_change_snapshot(self):
        data = fixture()
        full = model.lookup(data)
        data["query"]["limit"] = 2
        limited = model.lookup(data)
        self.assertEqual(limited["matched_count"], 4)
        self.assertEqual(limited["truncated_count"], 2)
        self.assertEqual(limited["results"], full["results"][:2])
        self.assertEqual(limited["snapshot_sha256"], full["snapshot_sha256"])
        data["query"]["tags"] = ["infr"]
        self.assertFalse(model.lookup(data)["results"])

    def test_identical_duplicates_are_recorded_but_do_not_change_snapshot(self):
        data = fixture()
        baseline = model.lookup(data)
        data["cases"].append(entry("a", tags=["durasi", "infra"]))
        report = model.lookup(data)
        self.assertEqual(report["duplicate_records"], [{"case_id": "a", "extra_copies": 1}])
        self.assertEqual(report["snapshot_sha256"], baseline["snapshot_sha256"])

    def test_conflicting_id_and_cross_partition_event_are_invalid(self):
        original = fixture()
        collisions = ({**entry("a"), "outcome": 0},
                      {**entry("copy", partition="held_out"), "event_id": "event/a"},
                      {**entry("third"), "question_ref": "r/a"})
        for row in collisions:
            with self.subTest(row=row), self.assertRaises(model.InputError):
                model.lookup({**original, "cases": [*original["cases"], row]})

    def test_malformed_lesson_and_partition_are_rejected(self):
        for update in ({"partition": "both"}, {"origin": "fabricated"}, {"tags": ["infra", "infra"]},
                       {"lesson": {"text": "", "ref": "fixture/empty", "available_at": CUTOFF}},
                       {"lesson": {"text": "bukti", "ref": "fixture/early",
                                   "available_at": "2026-11-01T00:00:00Z"}}):
            raw = fixture()
            raw["cases"][1].update(update)
            with self.subTest(update=update), self.assertRaises(model.InputError):
                model.lookup(raw)

    def test_cli_prints_same_bytes_after_reordering(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "case.json"
        outputs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as stream:
                self.assertEqual(model.main([str(path)]), 0)
            outputs.append(stream.getvalue())
            raw["cases"].reverse()
        self.assertEqual(outputs[0], outputs[1])

    def test_unresolvable_catalog_query_fails_closed(self):
        for change in ({"limit": 0}, {"limit": True}, {"partition": "any"}, {"as_of": "2026-11-15"}):
            raw = fixture()
            raw["query"].update(change)
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.lookup(raw)

    def test_missing_lesson_kept_as_absent_and_zero_outcome_is_preserved(self):
        raw = fixture()
        raw["cases"][0].update(lesson=None, outcome=0)
        result = model.lookup(raw)
        self.assertIsNone(result["results"][-1]["lesson"])
        self.assertEqual(result["results"][-1]["outcome"], 0)

    def test_empty_library_exports_digest_of_empty_canonical_array(self):
        raw = {**fixture(), "cases": []}
        result = model.lookup(raw)
        self.assertEqual(result["snapshot_sha256"], hashlib.sha256(b"[]").hexdigest())
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["results"], [])

    def test_snapshot_excludes_an_event_until_exact_available_time(self):
        raw = {**fixture(), "cases": [entry("when", 15)]}
        self.assertEqual(model.lookup(raw)["matched_count"], 1)
        raw["query"]["as_of"] = "2026-11-14T23:59:59.999999Z"
        self.assertEqual(model.lookup(raw)["matched_count"], 0)
