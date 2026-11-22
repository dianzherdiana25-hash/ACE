"""Verifier satu ronde, pemeriksaan independensi, dan waktu serta biaya."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import fast_track as model


def fixture():
    plan = {
        "case_id": "check", "case_ref": "fixture/case", "opens_at": "2026-11-20T00:00:00Z",
        "closes_at": "2026-11-20T00:00:09Z", "budget": 8, "impact": "low", "reversible": True,
        "prior_ref": "fixture/precedent", "conflict_screen_ref": "fixture/conflicts",
        "seats": [{"role": role, "participant": person, "family": f"family/{person}"}
                  for role, person in zip(model.ROLES, ("p", "c", "r"))],
    }
    submissions = [
        {"role": role, "participant": person, "ref": f"fixture/{person}", "summary": f"Langkah {role}",
         "submitted_at": when, "cost": cost, "basis": refs, "disposition": status}
        for role, person, when, cost, refs, status in (
            ("proponent", "p", "2026-11-20T00:00:00Z", 2, [], None),
            ("challenger", "c", "2026-11-20T00:00:03Z", 3, ["fixture/p"], None),
            ("reviewer", "r", "2026-11-20T00:00:07.5Z", 3, ["fixture/p", "fixture/c"], "mitigated"),
        )
    ]
    return {"plan": plan, "plan_sha256": model.plan_digest(plan), "submissions": submissions}


def rehash(raw):
    raw["plan_sha256"] = model.plan_digest(raw["plan"])
    return raw


class FastTests(unittest.TestCase):
    def test_exactly_one_round_can_become_reviewable(self):
        report = model.rehearse(fixture())
        self.assertEqual(report["status"], "reviewable")
        self.assertEqual(report["blockers"], [])
        self.assertIsNone(report["next_role"])
        self.assertEqual(report["spent"], 8)
        self.assertEqual(report["elapsed_seconds"], {"numerator": 15, "denominator": 2})
        self.assertEqual(report["round"][2]["basis"], ["fixture/c", "fixture/p"])
        self.assertEqual(report["plan"]["prior_ref"], "fixture/precedent")

    def test_all_incomplete_prefixes_report_next_role(self):
        raw = fixture()
        for index, role in enumerate(model.ROLES):
            with self.subTest(index=index):
                report = model.rehearse({**raw, "submissions": raw["submissions"][:index]})
                self.assertEqual(report["next_role"], role)
                self.assertEqual(report["blockers"], ["round_incomplete"])
                self.assertEqual(report["status"], "held")

    def test_second_round_is_rejected_even_if_all_turns_are_well_formed(self):
        raw = fixture()
        raw["submissions"].extend(raw["submissions"].copy())
        with self.assertRaises(model.InputError):
            model.rehearse(raw)

    def test_prerequisites_are_independently_reported(self):
        raw = fixture()
        raw["plan"].update(impact="uncertain", reversible=False, prior_ref=None, conflict_screen_ref=None)
        result = model.rehearse(rehash(raw))
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["blockers"], ["impact_requires_deeper_review", "not_reversible",
                                              "precedent_missing", "conflict_screen_missing"])
        self.assertEqual(result["spent"], 8)

    def test_sustained_and_unresolved_sanggahan_each_hold_the_result(self):
        for status in ("sustained", "unresolved"):
            raw = fixture()
            raw["submissions"][-1]["disposition"] = status
            with self.subTest(status=status):
                report = model.rehearse(raw)
                self.assertEqual(report["blockers"], [f"objection_{status}"])
                self.assertEqual(report["round"][2]["disposition"], status)

    def test_role_and_family_independence_cannot_be_faked_with_new_labels(self):
        for key, value in (("participant", "p"), ("family", "family/p"), ("role", "proponent")):
            raw = fixture()
            raw["plan"]["seats"][1][key] = value
            with self.subTest(key=key), self.assertRaises(model.InputError):
                rehash(raw)

    def test_wrong_speaker_and_wrong_turn_order_fail(self):
        raw = fixture()
        first = raw["submissions"][0]
        with self.assertRaisesRegex(model.InputError, "giliran"):
            model.rehearse({**raw, "submissions": raw["submissions"][::-1]})
        first["participant"] = "unknown"
        with self.assertRaisesRegex(model.InputError, "giliran"):
            model.rehearse(raw)

    def test_reviewer_must_reference_proposal_and_challenge(self):
        for basis in (["fixture/p"], ["fixture/c", "fixture/p", "fixture/made-up"], ["fixture/c", "fixture/c"]):
            raw = fixture()
            raw["submissions"][2]["basis"] = basis
            with self.subTest(basis=basis), self.assertRaises(model.InputError):
                model.rehearse(raw)

    def test_closed_bound_is_inclusive_to_microsecond(self):
        raw = fixture()
        final = raw["submissions"][-1]
        final["submitted_at"] = "2026-11-20T07:00:09+07:00"
        self.assertEqual(model.rehearse(raw)["elapsed_seconds"], {"numerator": 9, "denominator": 1})
        final["submitted_at"] = "2026-11-20T07:00:09.000001+07:00"
        with self.assertRaisesRegex(model.InputError, "Waktu"):
            model.rehearse(raw)

    def test_retroactive_submission_is_invalid_even_with_in_window_timestamp(self):
        raw = fixture()
        raw["submissions"][-1]["submitted_at"] = "2026-11-20T00:00:02Z"
        with self.assertRaisesRegex(model.InputError, "urutan"):
            model.rehearse(raw)

    def test_budget_counts_all_phases_even_when_last_cost_is_individually_low(self):
        raw = fixture()
        raw["submissions"][-1]["cost"] = 4
        with self.assertRaisesRegex(model.InputError, "melebihi"):
            model.rehearse(raw)
        raw["submissions"][-1]["cost"] = 0
        self.assertEqual(model.rehearse(raw)["spent"], 5)

    def test_changed_plan_requires_a_new_explicit_hash(self):
        raw = fixture()
        raw["plan"]["budget"] += 1
        with self.assertRaisesRegex(model.InputError, "hash"):
            model.rehearse(raw)
        self.assertEqual(model.rehearse(rehash(raw))["budget"], 9)

    def test_role_disposition_and_reused_sources_are_refused(self):
        for item, change in ((0, {"disposition": "mitigated"}), (2, {"disposition": None}),
                             (2, {"ref": "fixture/p"}), (0, {"ref": "fixture/precedent"}),
                             (1, {"cost": True})):
            raw = fixture()
            raw["submissions"][item].update(change)
            with self.subTest(item=item, change=change), self.assertRaises(model.InputError):
                model.rehearse(raw)

    def test_cli_canonicalizes_roster_and_round_basis_order(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "round.json"
        outputs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as stream:
                self.assertEqual(model.main([str(path)]), 0)
            outputs.append(stream.getvalue())
            raw["plan"]["seats"].reverse()
            raw["submissions"][-1]["basis"].reverse()
        self.assertEqual(outputs[0], outputs[1])

    def test_zero_duration_produces_explicit_zero_without_treating_window_as_invalid(self):
        raw = fixture()
        for turn in raw["submissions"]:
            turn["submitted_at"] = raw["plan"]["opens_at"]
        self.assertEqual(model.rehearse(raw)["elapsed_seconds"], {"numerator": 0, "denominator": 1})

    def test_numeric_reversibility_never_meets_fast_track_gate(self):
        raw = fixture()
        raw["plan"]["reversible"] = 1
        with self.assertRaisesRegex(model.InputError, "boolean"):
            model.rehearse(raw)

    def test_nonpositive_window_and_unknown_impact_cannot_be_sealed(self):
        for changes in ({"closes_at": "2026-11-20T00:00:00Z"}, {"impact": "unclassified"}, {"budget": 0}):
            raw = fixture()
            raw["plan"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(model.InputError):
                rehash(raw)

    def test_held_result_keeps_rationale_for_review(self):
        raw = fixture()
        raw["submissions"][-1]["disposition"] = "sustained"
        report = model.rehearse(raw)
        self.assertEqual(report["round"][-1]["summary"], "Langkah reviewer")
        self.assertEqual(report["plan"]["case_ref"], "fixture/case")
