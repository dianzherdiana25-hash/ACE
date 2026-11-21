"""Verifier AST pasif, update ranker, dan pasangan held-out."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import code_reasoner_forge as model
from ace_forge._forge_io import canonical, identity


GOOD = "def solve(xs):\n    return sum(xs)\n"
BAD = "def other(xs):\n    return len(xs)\n"


def pair(key, good=GOOD, other=BAD, *, split="train", family=None, name="solve", call="sum"):
    return {"id": key, "family_id": family or f"family/{key}", "split": split,
            "task_ref": f"fixture/task/{key}", "assessment_ref": f"fixture/score/{key}",
            "required_defs": [name], "required_calls": [call],
            "preferred": {"code": good, "ref": f"fixture/preferred/{key}"},
            "alternative": {"code": other, "ref": f"fixture/alt/{key}"}}


def fixture():
    return {"recipe_ref": "fixture/ranker", "epochs": 3, "pairs": [
        pair("a"),
        pair("b", "def tally(xs):\n    return sum(xs)\n", "def unknown(xs):\n    return abs(xs)\n", name="tally"),
        pair("held", "def total(xs):\n    return sum(xs) + 1\n", "bad def =", name="total", split="held_out"),
    ]}


def derive(raw):
    return model.forge(raw, identity(raw))


class ReasonerTests(unittest.TestCase):
    def test_ast_respects_names_and_counts_branches_without_execution(self):
        code = "def solve(xs):\n if xs: return sum(xs)\n raise ValueError()"
        with patch("builtins.exec", side_effect=AssertionError("kandidat tereksekusi")):
            found = model.features(code, {"missing", "solve"}, {"sum"})
        self.assertEqual(found[:6], (1, 1, 1, 1, 1, 1))
        self.assertEqual(model.features("def=", set(), set()), (0,) * len(model.FEATURES))

    def test_training_updates_weights_and_ranks_held_out_by_fixed_features(self):
        raw = fixture()
        report = derive(raw)
        self.assertEqual(report["adapter"]["features"], list(model.FEATURES))
        self.assertEqual(report["adapter"]["weights"][:4], [0, 1, 1, 0])
        self.assertEqual(report["updates_per_epoch"], [1, 0, 0])
        self.assertEqual(report["held_out_summary"], {"cases": 1, "preferred": 1, "tie": 0, "alternative": 0})
        self.assertEqual(report["held_out"][0]["assessment_ref"], "fixture/score/held")
        self.assertEqual(report["held_out"][0]["margin"], 2)
        self.assertEqual(report["adapter_sha256"], identity(report["adapter"]))
        self.assertNotIn(b"def total", canonical(report))

    def test_fixture_with_no_signal_keeps_a_tie_without_promoting_preferred(self):
        raw = fixture()
        raw["pairs"] = [pair("a", "def solve(): return 1", "def solve(): return 2"),
                        pair("held", "def solve(): return 3", "def solve(): return 4", split="held_out")]
        state = derive(raw)
        self.assertEqual(state["updates_per_epoch"], [0, 0, 0])
        self.assertEqual(state["held_out_summary"]["tie"], 1)
        self.assertEqual(state["training"][0]["outcome"], "tie")

    def test_holdout_changes_do_not_change_adapter_or_training_updates(self):
        raw = fixture()
        full = derive(raw)
        raw["pairs"].pop()
        training = derive(raw)
        self.assertEqual(training["adapter"], full["adapter"])
        self.assertEqual(training["updates_per_epoch"], full["updates_per_epoch"])
        self.assertIsNone(training["held_out_summary"])

    def test_duplicate_whitespace_only_candidate_and_swapped_pair_are_rejected(self):
        one = pair("a")
        for additional in (pair("b", GOOD + "\n# a comment", GOOD),
                           pair("b", BAD + "\n# a comment", GOOD, split="held_out")):
            with self.subTest(additional=additional["preferred"]["ref"]), self.assertRaisesRegex(model.InputError, "identik|diulang"):
                derive({**fixture(), "pairs": [one, additional]})

    def test_family_collision_proof_duplicate_and_wrong_hash_are_refused(self):
        raw = fixture()
        bound = identity(raw)
        raw["pairs"][-1]["family_id"] = raw["pairs"][0]["family_id"]
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.forge(raw, bound)
        with self.assertRaisesRegex(model.InputError, "bocor"):
            derive(raw)
        raw = fixture()
        raw["pairs"][1]["assessment_ref"] = raw["pairs"][0]["assessment_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            derive(raw)

    def test_unknown_symbol_no_training_and_oversized_ast_are_invalid(self):
        raw = fixture()
        for wrong in ({"epochs": False}, {"pairs": raw["pairs"][-1:]}, {"pairs": []},
                      {"pairs": [{**raw["pairs"][0], "required_defs": ["not-valid"]}]}):
            with self.subTest(wrong=wrong), self.assertRaises(model.InputError):
                derive({**raw, **wrong})
        with patch.object(model, "MAX_NODES", 3), self.assertRaisesRegex(model.InputError, "AST"):
            derive(raw)

    def test_ranking_mode_scores_unlabeled_candidate_query_and_refuses_unbound_adapter(self):
        report = derive(fixture())
        question = {"task_ref": "fixture/question", "required_defs": ["solve"], "required_calls": ["sum"],
                    "candidates": [{"ref": "x/less", "code": BAD}, {"ref": "x/more", "code": GOOD}]}
        args = question, identity(question), report["adapter"], report["adapter_sha256"]
        ranking = model.rank_candidates(*args)
        self.assertEqual(ranking["ranking"], [{"candidate_ref": "x/more", "score": 2},
                                               {"candidate_ref": "x/less", "score": 0}])
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.rank_candidates(*args[:-1], "0" * 64)

    def test_cli_fit_and_apply_share_identical_receipt_with_independent_read_only_paths(self):
        raw = fixture()
        report = derive(raw)
        question = {"task_ref": "fixture/question", "required_defs": [], "required_calls": [],
                    "candidates": [{"ref": "one", "code": GOOD}]}
        root = Path(self.enterContext(TemporaryDirectory()))
        path, adapter, query = (root / name for name in ("pairs.json", "ranker.json", "query.json"))
        path.write_bytes(canonical(raw))
        adapter.write_bytes(canonical(report["adapter"]))
        query.write_bytes(canonical(question))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(path), "--expect-input-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(output.getvalue()), report)
        args = [str(query), "--expect-input-sha256", identity(question),
                "--adapter", str(adapter), "--expect-adapter-sha256", report["adapter_sha256"]]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["ranking"], [{"candidate_ref": "one", "score": 0}])
        self.assertEqual(path.read_bytes(), canonical(raw))
