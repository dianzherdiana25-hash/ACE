"""Verifier pasangan trap, confidence, cakupan, dan label yang tertambat."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import trap_bench as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


ARTIFACT = "a"*64


def case(key, category, target="reject"):
    return {"id": key, "category": category, "family_id": f"fixture/family/{key}",
            "trap": {"expected": target, "prompt_ref": f"fixture/trap/{key}", "gold_ref": f"fixture/gold/t/{key}"},
            "control": {"expected": "accept", "prompt_ref": f"fixture/control/{key}", "gold_ref": f"fixture/gold/c/{key}"}}


def verdict(key, arm, action, confidence):
    return None if action is None else {"action": action, "confidence_bp": confidence,
                                        "receipt_ref": f"fixture/answer/{key}/{arm}"}


def answer(key, first, second, confidence):
    return {"id": key, "artifact_sha256": ARTIFACT, "trap": verdict(key, "trap", first, confidence),
            "control": verdict(key, "control", second, 4900)}


def fixture():
    protocol = {"protocol_ref": "fixture/probes", "artifact_sha256": ARTIFACT, "high_confidence_bp": 8000,
                "minimum_pairs": 2, "pairs": [
                    case("a", "logic", "abstain"), case("b", "logic"), case("c", "language"),
                    case("d", "language"), case("e", "logic"),
                ]}
    responses = [answer("a", "abstain", "accept", 6000), answer("b", "accept", "accept", 8000),
                 answer("c", "reject", "reject", None), answer("d", "accept", "reject", 2000),
                 answer("e", "accept", None, 9200)]
    return protocol, responses


def assess(protocol, responses):
    return model.assess(protocol, responses, identity(protocol))


class TrapTests(unittest.TestCase):
    def test_paired_accuracy_excludes_incomplete_while_tracking_observed_confident_errors(self):
        result = assess(*fixture())
        report = result["report"]
        self.assertEqual((report["expected"], report["paired"]), (5, 4))
        self.assertEqual(report["trap_accuracy"], q(1, 2))
        self.assertEqual(report["control_accuracy"], q(1, 2))
        self.assertEqual(report["trap_minus_control"], q(0))
        self.assertEqual(report["trap_errors_with_high_confidence"], 2)
        self.assertEqual(report["trap_replies_with_confidence"], 4)
        self.assertEqual(report["appropriate_trap_abstentions"], 1)
        self.assertEqual(result["pairs"][-1]["pair_outcome"], "incomplete")
        self.assertTrue(result["pairs"][-1]["trap_high_confidence_error"])
        self.assertEqual(result["pairs"][0]["trap"]["gold_ref"], "fixture/gold/t/a")
        self.assertEqual(result["pairs"][0]["trap"]["answer"]["receipt_ref"], "fixture/answer/a/trap")

    def test_categories_align_error_direction_with_trap_minus_control(self):
        first, second = assess(*fixture())["categories"]
        self.assertEqual(first["category"], "language")
        self.assertEqual(first["trap_minus_control"], q(1, 2))
        self.assertEqual(second["category"], "logic")
        self.assertEqual(second["trap_minus_control"], q(-1, 2))

    def test_one_point_change_inclusive_confidence_threshold(self):
        raw, responses = fixture()
        total = assess(raw, responses)["report"]["trap_errors_with_high_confidence"]
        raw["high_confidence_bp"] += 1
        self.assertEqual(assess(raw, responses)["report"]["trap_errors_with_high_confidence"], total-1)

    def test_no_receipts_or_insufficient_counts_leave_rates_absent(self):
        raw, responses = fixture()
        vacant = assess(raw, [])["report"]
        self.assertEqual(vacant["paired"], 0)
        self.assertIsNone(vacant["trap_accuracy"])
        self.assertEqual(vacant["trap_replies_with_confidence"], 0)
        raw["minimum_pairs"] = 3
        marginal = assess(raw, responses)
        self.assertEqual(marginal["report"]["status"], "paired")
        self.assertTrue(all(row["status"] == "insufficient_evidence" for row in marginal["categories"]))

    def test_every_combination_of_paired_results_is_accounted_for(self):
        result = assess(*fixture())
        self.assertEqual(result["report"]["counts"], {key: 1 for key in (
            "both_correct", "trap_error_only", "control_error_only", "both_incorrect", "incomplete",
        )})
        self.assertFalse(result["pairs"][2]["trap_high_confidence_error"])
        self.assertIsNone(result["pairs"][2]["trap"]["answer"]["confidence_bp"])

    def test_invalid_receipt_or_pair_binding_do_not_count_as_confident_failures(self):
        for update in ({"artifact_sha256": "b"*64}, {"trap": verdict("a", "trap", "unknown", 9999)},
                       {"trap": verdict("a", "trap", "accept", True)}, {"id": "unknown"}):
            raw, responses = fixture()
            responses[0].update(update)
            with self.subTest(update=update), self.assertRaises(model.InputError):
                assess(raw, responses)
        raw, answers = fixture()
        answers[1]["trap"]["receipt_ref"] = answers[0]["trap"]["receipt_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            assess(raw, answers)

    def test_gold_change_and_reused_refs_detected_against_plan(self):
        raw, outcomes = fixture()
        original = identity(raw)
        raw["pairs"][0]["trap"]["expected"] = "accept"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.assess(raw, outcomes, original)
        raw["pairs"][0]["trap"]["gold_ref"] = raw["pairs"][0]["control"]["gold_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            assess(raw, outcomes)

    def test_cli_keeps_existing_observation_files_and_matches_api(self):
        raw, outcomes = fixture()
        path = Path(self.enterContext(TemporaryDirectory()))
        p, o = path / "plan.json", path / "outcomes.json"
        p.write_bytes(canonical(raw))
        o.write_bytes(canonical(outcomes))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(p), str(o), "--expect-protocol-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(out.getvalue()), assess(raw, outcomes))
        self.assertEqual(o.read_bytes(), canonical(outcomes))

    def test_reordering_evidence_retains_deterministic_case_rows(self):
        raw, records = fixture()
        original = assess(raw, records)
        other = assess(raw, records[::-1])
        self.assertNotEqual(original.pop("responses_sha256"), other.pop("responses_sha256"))
        self.assertEqual(original, other)

    def test_empty_roster_and_duplicate_observation_are_rejected(self):
        plan, observations = fixture()
        with self.assertRaisesRegex(model.InputError, "kosong"):
            assess({**plan, "pairs": []}, [])
        with self.assertRaisesRegex(model.InputError, "ganda"):
            assess(plan, [*observations, observations[0]])

    def test_all_correct_and_all_wrong_pairs_report_measured_zero_delta(self):
        for observed in (True, False):
            with self.subTest(observed=observed):
                plan, _ = fixture()
                records = [answer(item["id"],
                                  item["trap"]["expected"] if observed else "accept",
                                  "accept" if observed else "reject", None)
                           for item in plan["pairs"]]
                result = assess(plan, records)
                self.assertEqual(result["report"]["paired"], len(records))
                self.assertEqual(result["report"]["trap_accuracy"], q(int(observed)))
                self.assertEqual(result["report"]["control_accuracy"], q(int(observed)))
                self.assertEqual(result["report"]["trap_minus_control"], q(0))

    def test_unrecorded_trap_stays_unknown_even_with_recorded_control(self):
        raw, outcomes = fixture()
        outcomes[0]["trap"] = None
        result = assess(raw, outcomes)
        row = result["pairs"][0]
        self.assertIsNone(row["trap"]["answer"])
        self.assertIsNotNone(row["control"]["answer"])
        self.assertEqual(row["pair_outcome"], "incomplete")

    def test_threshold_belongs_to_the_committed_protocol(self):
        raw, outcomes = fixture()
        anchor = identity(raw)
        raw["high_confidence_bp"] = 5000
        self.assertNotEqual(identity(raw), anchor)
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.assess(raw, outcomes, anchor)
