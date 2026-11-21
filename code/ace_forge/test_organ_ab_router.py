"""Verifier kuota strata, pengecualian, dan replay rencana A/B."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import organ_ab_router as model
from ace_forge._forge_io import canonical, identity


def task(key, kind, level, eligible=True):
    return {"id": key, "task_kind": kind, "difficulty": level, "eligible": eligible,
            "task_ref": f"fixture/task/{key}", "eligibility_ref": f"fixture/eligible/{key}"}


def fixture():
    return {"plan_ref": "fixture/ab", "seed": 52, "candidate_ratio_bp": 5000,
            "baseline": {"artifact_sha256": "a" * 64, "artifact_ref": "fixture/one"},
            "candidate": {"artifact_sha256": "b" * 64, "artifact_ref": "fixture/two"},
            "tasks": [task(f"d{i}", "logic", "hard") for i in range(4)]
            + [task(f"e{i}", "logic", "easy") for i in range(3)]
            + [task("outside", "logic", "hard", False)]}


def assign(raw):
    return model.assign(raw, identity(raw))


class RouterTests(unittest.TestCase):
    def test_balances_each_stratum_and_preserves_outside_comparison_separately(self):
        raw = fixture()
        result = assign(raw)
        self.assertEqual((result["eligible"], result["excluded"]), (7, 1))
        self.assertEqual(result["strata"], [
            {"task_kind": "logic", "difficulty": "easy", "candidate": 2, "baseline": 1, "both_arms": True},
            {"task_kind": "logic", "difficulty": "hard", "candidate": 2, "baseline": 2, "both_arms": True},
        ])
        excluded = result["allocations"][-1]
        self.assertFalse(excluded["in_comparison"])
        self.assertEqual(excluded["allocation"], "outside_comparison")
        self.assertEqual(excluded["artifact_ref"], "fixture/one")
        self.assertEqual(excluded["eligibility_ref"], "fixture/eligible/outside")
        self.assertEqual(excluded["task_ref"], "fixture/task/outside")

    def test_program_matches_independent_ranking_by_seed_and_scope(self):
        raw = fixture()
        outcome = assign(raw)
        for level in ("hard", "easy"):
            rows = [row for row in raw["tasks"] if row["difficulty"] == level and row["eligible"]]
            expected = sorted(rows, key=lambda row: identity([52, "logic", level, row["id"]]))[:2]
            observed = {row["id"] for row in outcome["allocations"] if row["difficulty"] == level
                        and row["arm"] == "candidate"}
            self.assertEqual(observed, {row["id"] for row in expected})

    def test_different_task_kinds_do_not_share_quota_even_at_same_difficulty(self):
        raw = fixture()
        raw["tasks"] = [task("a", "syntax", "basic"), task("b", "retrieval", "basic")]
        summary = assign(raw)["strata"]
        self.assertEqual([row["candidate"] for row in summary], [1, 1])
        self.assertTrue(all(not row["both_arms"] for row in summary))

    def test_exact_zero_and_full_ratio_do_not_leak_unapproved_tasks_to_candidate(self):
        for ratio, expected in ((0, 0), (10_000, 7)):
            with self.subTest(ratio=ratio):
                result = assign({**fixture(), "candidate_ratio_bp": ratio})
                self.assertEqual(sum(row["arm"] == "candidate" for row in result["allocations"]), expected)
                self.assertEqual(result["allocations"][-1]["arm"], "baseline")

    def test_deterministic_byte_replay_and_unique_receipt_hashes(self):
        raw = fixture()
        first = assign(raw)
        self.assertEqual(first, assign(raw))
        hashes = {row["allocation_sha256"] for row in first["allocations"]}
        self.assertEqual(len(hashes), len(raw["tasks"]))
        for item in first["allocations"]:
            header = {key: value for key, value in item.items() if key != "allocation_sha256"}
            self.assertEqual(identity(header), item["allocation_sha256"])
            self.assertEqual(header["plan_sha256"], identity(raw))

    def test_changed_plan_seed_or_roster_refused_when_experiment_anchor_kept(self):
        raw = fixture()
        checksum = identity(raw)
        for update in ({"seed": 3}, {"tasks": raw["tasks"][:-1]}):
            with self.subTest(update=update), self.assertRaisesRegex(model.InputError, "anchor"):
                model.assign({**raw, **update}, checksum)

    def test_registry_references_and_task_identifiers_cannot_be_reused(self):
        raw = fixture()
        for update in ({"seed": True}, {"candidate_ratio_bp": -1}, {"candidate": raw["baseline"]},
                       {"tasks": [raw["tasks"][0]] * 2}, {"tasks": [{**raw["tasks"][0], "eligible": 1}]},
                       {"tasks": [{**raw["tasks"][0], "task_ref": raw["candidate"]["artifact_ref"]}]}):
            with self.subTest(update=update), self.assertRaises(model.InputError):
                assign({**raw, **update})

    def test_audit_localizes_tampered_deleted_and_header_only_records(self):
        raw = fixture()
        original = assign(raw)
        corrupted = deepcopy(original)
        corrupted["allocations"][2]["arm"] = "other"
        self.assertEqual(model.audit(raw, corrupted, identity(raw))["changed"], ["d2"])
        reduced = {**original, "allocations": original["allocations"][:-1]}
        self.assertEqual(model.audit(raw, reduced, identity(raw))["changed"], ["outside"])
        header = {**original, "plan_ref": "wrong"}
        self.assertEqual(model.audit(raw, header, identity(raw))["reason"], "header_mismatch")
        invalid = {**original, "allocations": None}
        self.assertEqual(model.audit(raw, invalid, identity(raw))["reason"], "allocation_list_missing_or_invalid")

    def test_reordering_tasks_preserves_hash_rank_based_decisions(self):
        raw = fixture()
        first = assign(raw)
        raw["tasks"].reverse()
        another = assign(raw)
        def decisions(report):
            return [(row["id"], row["arm"]) for row in report["allocations"]]
        self.assertEqual(decisions(first), decisions(another))
        self.assertNotEqual(first["plan_sha256"], another["plan_sha256"])

    def test_empty_roster_produces_zero_without_allocations(self):
        raw = {**fixture(), "tasks": []}
        value = assign(raw)
        self.assertEqual((value["eligible"], value["excluded"]), (0, 0))
        self.assertEqual(value["allocations"], [])
        self.assertTrue(model.audit(raw, value, identity(raw))["valid"])

    def test_cli_emits_allocations_or_verifies_receipts_and_preserves_input_files(self):
        raw = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        experiment, receipts = root / "experiment.json", root / "allocations.json"
        experiment.write_bytes(canonical(raw))
        args = [str(experiment), "--expect-plan-sha256", identity(raw)]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(args), 0)
        expected = json.loads(output.getvalue())
        receipts.write_bytes(canonical(expected))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([*args, "--verify", str(receipts)]), 0)
        self.assertTrue(json.loads(output.getvalue())["valid"])
        amended = {**expected, "allocations": expected["allocations"][:-1]}
        receipts.write_bytes(canonical(amended))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([*args, "--verify", str(receipts)]), 1)
        self.assertEqual(json.loads(output.getvalue())["changed"], ["outside"])
        self.assertEqual(experiment.read_bytes(), canonical(raw))

    def test_different_seed_changes_within_stratum_but_preserves_all_quotas(self):
        raw = fixture()
        first, another = assign(raw), assign({**raw, "seed": 13})
        self.assertEqual(first["strata"], another["strata"])
        self.assertNotEqual([row["arm"] for row in first["allocations"]],
                            [row["arm"] for row in another["allocations"]])

    def test_half_basis_point_boundary_rounds_only_inside_each_stratum(self):
        raw = {**fixture(), "tasks": [task("one", "logic", "hard"), task("two", "logic", "hard")]}
        for assigned, expected in ((2499, 0), (2500, 1), (7499, 1), (7500, 2)):
            with self.subTest(assigned=assigned):
                item, = assign({**raw, "candidate_ratio_bp": assigned})["strata"]
                self.assertEqual(item["candidate"], expected)
                self.assertEqual(item["baseline"], 2 - expected)

    def test_audit_finds_extra_and_ordered_receipt_records_without_accepting_numeric_booleans(self):
        raw = {**fixture(), "tasks": [task("a", "logic", "hard"), task("b", "logic", "easy")]}
        report = assign(raw)
        extra = {**report, "allocations": [*report["allocations"], report["allocations"][0]]}
        integrity = model.audit(raw, extra, identity(raw))
        self.assertFalse(integrity["valid"])
        self.assertEqual(integrity["given_count"], 3)
        reordered = {**report, "allocations": report["allocations"][::-1]}
        self.assertEqual(model.audit(raw, reordered, identity(raw))["changed"], ["a", "b"])
        first = {**report["allocations"][0], "in_comparison": 1}
        mutated = {**report, "allocations": [first, report["allocations"][1]]}
        self.assertEqual(model.audit(raw, mutated, identity(raw))["changed"], ["a"])

    def test_excluded_only_roster_keeps_baseline_receipt_without_strata(self):
        raw = fixture()
        raw.update(candidate_ratio_bp=10_000, tasks=[task("outside", "logic", "hard", False)])
        result = assign(raw)
        self.assertEqual(result["eligible"], 0)
        self.assertEqual(result["strata"], [])
        self.assertEqual(result["allocations"][0]["artifact_sha256"], raw["baseline"]["artifact_sha256"])
