"""Verifier skor Beta eksak, coverage, dan ekspor anotasi."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import difficulty_scorer as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


SOLVERS = {key: key * 64 for key in "abc"}


def fixture():
    protocol = {"protocol_ref": "fixture/protocol", "report_ref": "fixture/scores.json", "minimum_observed": 2,
                "prior": {"failure": 1, "success": 1, "ref": "fixture/prior"},
                "bands": [{"id": "easy", "max_bp": 3000}, {"id": "medium", "max_bp": 6000},
                          {"id": "hard", "max_bp": 10_000}],
                "examples": [{"id": key, "source_ref": f"fixture/example/{key}", "task_kind": "logic"} for key in "xyz"],
                "solvers": [{"id": key, "artifact_sha256": sha, "source_ref": f"fixture/solver/{key}"}
                            for key, sha in SOLVERS.items()]}
    evidence = [obs(key, solver, status) for key, solver, status in (
        ("x", "a", True), ("x", "b", False), ("x", "c", False), ("y", "a", True),
    )]
    return protocol, evidence


def obs(example, solver, status):
    return {"example_id": example, "solver": solver, "artifact_sha256": SOLVERS[solver], "passed": status,
            "receipt_ref": f"fixture/receipt/{example}/{solver}"}


def score(raw, observations):
    return model.score(raw, observations, identity(raw))


class DifficultyTests(unittest.TestCase):
    def test_posterior_and_leave_one_out_values_match_hand_calculation(self):
        report = score(*fixture())
        row, sparse, absent = report["examples"]
        self.assertEqual(row["failures"], 2)
        self.assertEqual(row["difficulty"], q(3, 5))
        self.assertEqual(row["difficulty_bp"], 6000)
        self.assertEqual(row["band"], "medium")
        self.assertEqual(row["leave_one_out"], {"low": q(1, 2), "high": q(3, 4)})
        self.assertEqual(row["attempts"][0]["receipt_ref"], "fixture/receipt/x/a")
        self.assertEqual(row["attempts"][0]["solver_ref"], "fixture/solver/a")
        self.assertEqual(sparse["missing_solvers"], ["b", "c"])
        self.assertEqual(sparse["status"], "insufficient_observations")
        self.assertIsNone(sparse["difficulty"])
        self.assertEqual(absent["observed"], 0)
        self.assertEqual(report["annotations"], [{"example_id": "x", "difficulty_bp": 6000,
                                                  "evidence_ref": "fixture/scores.json#x"}])

    def test_true_zero_and_full_failure_are_smoothed_by_explicit_prior(self):
        raw, _ = fixture()
        first = [obs("x", solver, True) for solver in SOLVERS]
        second = [obs("x", solver, False) for solver in SOLVERS]
        self.assertEqual(score(raw, first)["examples"][0]["difficulty"], q(1, 5))
        self.assertEqual(score(raw, second)["examples"][0]["difficulty"], q(4, 5))
        self.assertEqual(score(raw, first)["examples"][0]["band"], "easy")
        self.assertEqual(score(raw, second)["examples"][0]["band"], "hard")

    def test_half_basis_point_rounding_is_deterministic(self):
        raw, _ = fixture()
        raw["minimum_observed"] = 1
        raw["prior"] = {"failure": 1, "success": 30, "ref": "fixture/rounded"}
        observations = [obs("x", "a", True)]
        value = score(raw, observations)["examples"][0]
        self.assertEqual(value["difficulty"], q(1, 32))
        self.assertEqual(value["difficulty_bp"], 313)
        self.assertEqual(value["leave_one_out"]["high"], q(1, 31))

    def test_same_solver_cannot_vote_twice_or_cross_aliases(self):
        raw, evidence = fixture()
        with self.assertRaisesRegex(model.InputError, "ganda"):
            score(raw, [*evidence, {**evidence[0], "receipt_ref": "fixture/extra"}])
        raw["solvers"][1]["artifact_sha256"] = raw["solvers"][0]["artifact_sha256"]
        with self.assertRaisesRegex(model.InputError, "artefaknya ganda"):
            score(raw, evidence)

    def test_wrong_binding_invalid_status_and_unknown_roster_fail(self):
        raw, evidence = fixture()
        for update in ({"solver": "unknown"}, {"example_id": "unknown"}, {"passed": 1}, {"artifact_sha256": "0" * 64},
                       {"receipt_ref": "fixture/prior"}):
            with self.subTest(update=update), self.assertRaises(model.InputError):
                score(raw, [{**evidence[0], **update}])

    def test_bands_must_cover_entire_domain_in_ascending_order(self):
        raw, evidence = fixture()
        for bands in ([], list(reversed(raw["bands"])), raw["bands"][:-1], raw["bands"][:1] * 2):
            with self.subTest(bands=bands), self.assertRaises(model.InputError):
                score({**raw, "bands": bands}, evidence)

    def test_report_pointers_keep_staged_curriculum_compatible_ids(self):
        raw, evidence = fixture()
        for example in ("bad#id", "x" * 245):
            raw["examples"][0]["id"] = example
            with self.subTest(example=example), self.assertRaisesRegex(model.InputError, "Rujukan anotasi"):
                score(raw, evidence)

    def test_changed_prior_is_rejected_with_old_anchor_and_changes_posterior_with_new(self):
        raw, evidence = fixture()
        checksum = identity(raw)
        raw["prior"]["failure"] = 2
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.score(raw, evidence, checksum)
        self.assertEqual(score(raw, evidence)["examples"][0]["difficulty"], q(2, 3))

    def test_cli_is_deterministic_and_preserves_vote_source_bytes(self):
        raw, evidence = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p, d = root / "plan.json", root / "observations.json"
        p.write_bytes(canonical(raw))
        d.write_bytes(canonical(evidence))
        args = [str(p), str(d), "--expect-protocol-sha256", identity(raw)]
        with redirect_stdout(StringIO()) as result:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(result.getvalue()), score(raw, evidence))
        self.assertEqual(d.read_bytes(), canonical(evidence))

    def test_reordered_receipts_keep_annotation_content_but_change_evidence_binding(self):
        raw, evidence = fixture()
        before = score(raw, evidence)
        after = score(raw, evidence[::-1])
        self.assertNotEqual(before.pop("evidence_sha256"), after.pop("evidence_sha256"))
        self.assertEqual(before, after)

    def test_insufficient_attempts_in_every_group_cannot_materialize_annotation(self):
        raw, evidence = fixture()
        raw["minimum_observed"] = 3
        minimum = score(raw, evidence[1:])
        self.assertEqual(minimum["annotations"], [])
        self.assertEqual(minimum["examples"][0]["observed"], 2)
        self.assertIsNone(minimum["examples"][0]["band"])

    def test_duplicate_evidence_refs_do_not_count_as_distinct_attempts(self):
        raw, evidence = fixture()
        evidence[1]["receipt_ref"] = evidence[0]["receipt_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            score(raw, evidence)

    def test_one_observation_sensitivity_equals_prior_when_removed(self):
        raw, _ = fixture()
        raw["minimum_observed"] = 1
        value = score(raw, [obs("x", "a", False)])["examples"][0]
        self.assertEqual(value["difficulty"], q(2, 3))
        self.assertEqual(value["leave_one_out"], {"low": q(1, 2), "high": q(1, 2)})

    def test_annotations_join_directly_to_staged_curriculum_fixture_by_example_id(self):
        from ace_forge import staged_curriculum
        from ace_forge.test_staged_curriculum import fixture as curriculum_fixture

        dataset, manifest, head, plan, _ = curriculum_fixture()
        index = {row["example_id"]: row for row in map(json.loads, dataset.splitlines()) if row["split"] == "train"}
        raw, _ = fixture()
        raw["examples"] = [{"id": key, "source_ref": row["provenance"]["evidence_ref"],
                            "task_kind": row["payload"]["task_kind"]} for key, row in index.items()]
        receipts = [obs(key, solver, True) for key in index for solver in SOLVERS]
        report = score(raw, receipts)
        self.assertEqual(len(report["annotations"]), len(index))
        plan["stages"] = [{"id": "base", "max_difficulty_bp": 2000, "new_examples": 3, "replay_limit": 0}]
        plan["annotations"] = report["annotations"]
        exported, result = staged_curriculum.prepare(dataset, manifest, head, plan, identity(plan))
        self.assertEqual(result["status"], "ready")
        for row in exported["base"]:
            self.assertEqual(row, index[row["example_id"]])
        self.assertTrue(all(item["difficulty_ref"].startswith("fixture/scores.json#")
                            for item in result["stages"][0]["new"]))

    def test_empty_case_roster_is_invalid_even_when_prior_and_solvers_are_valid(self):
        raw, _ = fixture()
        with self.assertRaisesRegex(model.InputError, "Roster"):
            score({**raw, "examples": []}, [])
