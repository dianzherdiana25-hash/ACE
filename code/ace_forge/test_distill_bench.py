"""Verifier split, retensi guru, dan perbandingan kasus berpasangan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import distill_bench as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


TEACHER, STUDENT = "a" * 64, "b" * 64


def item(key, family, domain=None):
    value = {"id": key, "family_id": family, "source_ref": f"fixture/questions/{key}",
             "prompt_sha256": identity({"question_id": key})}
    if domain is not None:
        value["domain"] = domain
    return value


def result(key, first, second):
    return {"id": key,
            "teacher": {"artifact_sha256": TEACHER, "passed": first, "assessment_ref": f"fixture/judge/t/{key}"}
            if first is not None else None,
            "student": {"artifact_sha256": STUDENT, "passed": second, "assessment_ref": f"fixture/judge/s/{key}"}
            if second is not None else None}


def fixture():
    qset = {"protocol_ref": "fixture/distill", "teacher_sha256": TEACHER, "student_sha256": STUDENT,
            "minimum_pairs": 2, "training": [item("lesson", "train-family")],
            "held_out": [item("a", "logic", "table"), item("b", "logic", "table"), item("c", "math", "sum"),
                         item("d", "math", "sum"), item("e", "logic", "table")]}
    return qset, [result("a", True, True), result("b", True, False),
                  result("c", False, True), result("d", False, False), result("e", False, None)]


def score(policy, observations):
    return model.score(policy, observations, identity(policy))


class DistillTests(unittest.TestCase):
    def test_exact_retention_separates_teacher_loss_from_student_only_gain(self):
        report = score(*fixture())
        stats = report["summary"]
        self.assertEqual(stats["expected"], 5)
        self.assertEqual(stats["paired"], 4)
        self.assertEqual(stats["missing_pairs"], 1)
        self.assertEqual((stats["both_pass"], stats["teacher_only"], stats["student_only"], stats["both_fail"]),
                         (1, 1, 1, 1))
        self.assertEqual(stats["teacher_accuracy"], q(1, 2))
        self.assertEqual(stats["student_accuracy"], q(1, 2))
        self.assertEqual(stats["accuracy_delta"], q(0))
        self.assertEqual(stats["retained_teacher_successes"], q(1, 2))
        self.assertEqual(stats["pair_sign_p_two_sided"], q(1))
        self.assertEqual(report["cases"][0]["source_ref"], "fixture/questions/a")
        self.assertEqual(report["cases"][0]["student"]["assessment_ref"], "fixture/judge/s/a")
        self.assertEqual(report["cases"][-1]["missing"], ["student"])

    def test_no_teacher_success_means_no_retention_denominator(self):
        policy, _ = fixture()
        rows = [result(case["id"], False, True) for case in policy["held_out"][:4]]
        stats = score(policy, rows)["summary"]
        self.assertEqual(stats["teacher_accuracy"], q(0))
        self.assertEqual(stats["student_accuracy"], q(1))
        self.assertEqual(stats["accuracy_delta"], q(1))
        self.assertIsNone(stats["retained_teacher_successes"])
        self.assertEqual(stats["pair_sign_p_two_sided"], q(1, 8))

    def test_insufficient_domains_are_visible_while_overall_sample_qualifies(self):
        policy, observations = fixture()
        policy["minimum_pairs"] = 3
        report = score(policy, observations)
        self.assertEqual(report["summary"]["status"], "paired")
        for row in report["domains"]:
            self.assertEqual(row["paired"], 2)
            self.assertEqual(row["status"], "insufficient_pairs")
            self.assertIsNone(row["pair_sign_p_two_sided"])
            self.assertIsNone(row["accuracy_delta"])

    def test_conflicting_training_and_held_out_identity_is_refused_every_way(self):
        for field in ("id", "family_id", "prompt_sha256", "source_ref"):
            policy, observations = fixture()
            policy["held_out"][0][field] = policy["training"][0][field]
            with self.subTest(field=field), self.assertRaises(model.InputError):
                score(policy, observations)

    def test_unregistered_receipts_duplicate_references_and_wrong_artifact_are_rejected(self):
        policy, rows = fixture()
        for extra in (result("lesson", False, True), rows[0]):
            with self.subTest(extra=extra), self.assertRaises(model.InputError):
                score(policy, [*rows, extra])
        rows[0]["teacher"]["artifact_sha256"] = STUDENT
        with self.assertRaisesRegex(model.InputError, "artefak"):
            score(policy, rows)
        rows[0]["teacher"]["artifact_sha256"] = TEACHER
        rows[0]["teacher"]["assessment_ref"] = rows[0]["student"]["assessment_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            score(policy, rows)

    def test_policy_hash_and_every_arm_identity_bound_before_observations(self):
        policy, rows = fixture()
        anchor = identity(policy)
        policy["teacher_sha256"] = STUDENT
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.score(policy, rows, anchor)
        with self.assertRaisesRegex(model.InputError, "berbeda"):
            score(policy, rows)

    def test_exact_paired_test_is_symmetric_and_bounded_for_large_cohorts(self):
        self.assertEqual(model._paired_sign_test(5, 0), q(1, 16))
        self.assertEqual(model._paired_sign_test(0, 5), q(1, 16))
        self.assertEqual(model._paired_sign_test(2, 3), q(1))
        self.assertEqual(model._paired_sign_test(0, 0), q(1))
        self.assertIsNone(model._paired_sign_test(0, 513))

    def test_neither_arm_reporting_leaves_no_comparisons_and_listed_absences(self):
        policy, _ = fixture()
        report = score(policy, [])
        stats = report["summary"]
        self.assertEqual((stats["paired"], stats["missing_pairs"]), (0, 5))
        self.assertIsNone(stats["teacher_accuracy"])
        self.assertEqual(report["cases"][0]["missing"], ["teacher", "student"])

    def test_cli_is_byte_reproducible_and_pins_both_artifacts_in_output(self):
        policy, obs = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p, data = root / "protocol.json", root / "observations.json"
        p.write_bytes(canonical(policy))
        data.write_bytes(canonical(obs))
        args = [str(p), str(data), "--expect-protocol-sha256", identity(policy)]
        lines = []
        for _ in range(2):
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main(args), 0)
            lines.append(out.getvalue())
        self.assertEqual(*lines)
        report = json.loads(lines[0])
        self.assertEqual(report, score(policy, obs))
        self.assertEqual((report["teacher_sha256"], report["student_sha256"]), (TEACHER, STUDENT))
        self.assertEqual(data.read_bytes(), canonical(obs))

    def test_training_and_held_out_must_be_present_even_for_no_observations(self):
        policy, _ = fixture()
        for field in ("training", "held_out"):
            with self.subTest(field=field), self.assertRaisesRegex(model.InputError, "dicatat"):
                score({**policy, field: []}, [])

    def test_all_paired_teacher_successes_can_be_preserved_even_when_students_add_cases(self):
        policy, observations = fixture()
        observations[1]["student"]["passed"] = True
        summary = score(policy, observations)["summary"]
        self.assertEqual(summary["retained_teacher_successes"], q(1))
        self.assertEqual(summary["accuracy_delta"], q(1, 4))
        self.assertEqual(summary["student_only"], 1)
