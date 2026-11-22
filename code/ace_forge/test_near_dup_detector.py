"""Uji Jaccard eksak, cluster, irisan partisi, dan batas kerja."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
from itertools import combinations
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import near_dup_detector as model
from ace_forge._forge_io import canonical


def record(key, prompt, split="train"):
    return {"id": key, "prompt": prompt, "split": split, "source_ref": f"fixture/ref/{key}"}


def dataset(name, *items):
    return {"name": name, "source_ref": f"fixture/dataset/{name}", "rows": list(items)}


def fixture():
    return {"protocol_ref": "fixture/dedup", "minimum_similarity_bp": 5000, "shingle_width": 1,
            "datasets": [
                dataset("a", record("left", "a b c"), record("inside", "different")),
                dataset("b", record("middle", "b c d", "held_out")),
                dataset("c", record("right", "c d e", "candidate"), record("isolated", "x y z")),
            ]}


class DuplicateTests(unittest.TestCase):
    def test_exact_threshold_with_connected_but_nonadjacent_examples(self):
        value = model.scan(fixture())
        self.assertEqual(value["pairs_checked"], 3)
        self.assertEqual(value["cross_partition_pairs"], 1)
        pairs = [(row["left"]["id"], row["right"]["id"]) for row in value["matches"]]
        self.assertEqual(pairs, [("left", "middle"), ("middle", "right")])
        self.assertTrue(all(row["similarity"] == {"numerator": 1, "denominator": 2} for row in value["matches"]))
        self.assertEqual([[row["id"] for row in cluster] for cluster in value["connected_components"]],
                         [["left", "middle", "right"]])
        self.assertEqual(value["matches"][0]["right"]["source_ref"], "fixture/ref/middle")

    def test_increasing_threshold_excludes_equal_and_lower_pairs(self):
        options = {**fixture(), "minimum_similarity_bp": 5001}
        self.assertEqual(model.scan(options)["matches"], [])
        self.assertEqual(model.scan(options)["connected_components"], [])

    def test_unicode_nfkc_casefold_and_punctuation_normalization(self):
        options = {**fixture(), "minimum_similarity_bp": 10_000, "shingle_width": 2,
                   "datasets": [dataset("a", record("new", "ＣＡＦÉ zusammen")),
                                dataset("b", record("old", "cafe\u0301, ZUSAMMEN!", "held_out"))]}
        matched, = model.scan(options)["matches"]
        self.assertEqual((matched["shared_shingles"], matched["union_shingles"]), (1, 1))
        self.assertTrue(matched["crosses_train_held_out"])

    def test_small_prompt_uses_one_short_shingle_and_same_dataset_is_excluded(self):
        raw = {**fixture(), "shingle_width": 4, "minimum_similarity_bp": 1,
               "datasets": [dataset("a", record("one", "x"), record("two", "x")), dataset("b", record("three", "x"))]}
        result = model.scan(raw)
        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(result["pairs_checked"], 2)
        self.assertEqual(len(result["connected_components"][0]), 3)

    def test_match_is_exact_against_independent_small_pair_enumeration(self):
        rng = Random(52)
        for _ in range(25):
            groups = [dataset(f"d{j}", *(record(f"{j}-{i}", " ".join(rng.choices("abcdef", k=8)))
                                         for i in range(3))) for j in range(3)]
            cutoff = rng.randrange(1, 10_001)
            options = {**fixture(), "datasets": groups, "minimum_similarity_bp": cutoff}
            expected = set()
            for first, second in combinations(groups, 2):
                for x in first["rows"]:
                    for y in second["rows"]:
                        left, right = set(x["prompt"].split()), set(y["prompt"].split())
                        if Fraction(len(left & right), len(left | right)) >= Fraction(cutoff, 10_000):
                            expected.add((x["id"], y["id"]))
            actual = {(row["left"]["id"], row["right"]["id"]) for row in model.scan(options)["matches"]}
            self.assertEqual(actual, expected)

    def test_repeated_tokens_are_sets_without_inflating_similarity(self):
        raw = {**fixture(), "datasets": [dataset("a", record("one", "x x x x x")),
                                        dataset("b", record("two", "x y"))]}
        row, = model.scan(raw)["matches"]
        self.assertEqual((row["shared_shingles"], row["union_shingles"]), (1, 2))

    def test_limit_on_postings_and_on_unique_candidate_pairs_fails_closed(self):
        with patch.object(model, "MAX_POSTING_COMPARISONS", 1):
            with self.assertRaisesRegex(model.InputError, "indeks"):
                model.scan(fixture())
        with patch.object(model, "MAX_CANDIDATE_PAIRS", 2):
            with self.assertRaisesRegex(model.InputError, "Pasangan"):
                model.scan(fixture())

    def test_invalid_prompt_and_reused_ids_are_rejected_before_counting(self):
        raw = fixture()
        for items in (dataset("a"), dataset("unique", record("q", "---")),
                      dataset("unique", record("q", "word"), record("q", "other")),
                      dataset("unique", record("q", "word", "unknown"))):
            with self.subTest(items=items), self.assertRaises(model.InputError):
                model.scan({**raw, "datasets": [*raw["datasets"], items]})

    def test_merely_repeated_candidate_prompts_do_not_count_as_heldout_leak(self):
        raw = fixture()
        raw["datasets"][1]["rows"][0]["split"] = "candidate"
        self.assertEqual(model.scan(raw)["cross_partition_pairs"], 0)

    def test_disjoint_empty_and_single_dataset_are_valid_reports_without_matches(self):
        for groups in ([], [dataset("one", record("a", "anvil"))],
                       [dataset("first", record("a", "anvil")), dataset("second", record("b", "meadow"))]):
            with self.subTest(groups=groups):
                result = model.scan({**fixture(), "datasets": groups})
                self.assertEqual((result["matches"], result["pairs_checked"]), ([], 0))

    def test_cli_canonical_hash_and_report_after_reordering_source_arrays(self):
        options = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "config.json"
        traces = []
        for _ in range(2):
            path.write_bytes(canonical(options))
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            traces.append(output.getvalue())
            options["datasets"].reverse()
            for group in options["datasets"]:
                group["rows"].reverse()
        self.assertEqual(*traces)
        self.assertEqual(len(json.loads(traces[0])["datasets"]), 3)

    def test_shingle_order_is_significant_when_width_exceeds_one(self):
        raw = {**fixture(), "shingle_width": 2, "minimum_similarity_bp": 1,
               "datasets": [dataset("a", record("forward", "alpha beta")),
                            dataset("b", record("reverse", "beta alpha"))]}
        self.assertEqual(model.scan(raw)["matches"], [])

    def test_bigram_intersection_counts_overlapping_sequence_boundaries(self):
        raw = {**fixture(), "shingle_width": 2, "minimum_similarity_bp": 2500,
               "datasets": [dataset("a", record("left", "cat runs fast here")),
                            dataset("b", record("right", "cat runs fast there"))]}
        edge, = model.scan(raw)["matches"]
        self.assertEqual(edge["similarity"], {"numerator": 1, "denominator": 2})
        self.assertEqual(edge["union_shingles"], 4)
        self.assertEqual(edge["shared_shingles"], 2)

    def test_shared_example_id_is_preserved_with_both_dataset_labels(self):
        raw = {**fixture(), "datasets": [
            dataset("a", record("same-id", "same prompt")),
            dataset("b", record("same-id", "same prompt", "held_out")),
        ]}
        edge, = model.scan(raw)["matches"]
        self.assertEqual((edge["left"]["dataset"], edge["right"]["dataset"]), ("a", "b"))
        self.assertEqual({edge["left"]["id"], edge["right"]["id"]}, {"same-id"})
