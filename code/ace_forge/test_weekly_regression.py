"""Verifier kalender UTC dan regresi mingguan dengan baseline bersama."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import weekly_regression as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import case, q
from ace_forge.test_long_forgetting_probe import observation


BASELINE = "0"*64
FIRST = "1"*64
LATER = "2"*64


def fixture():
    protocol = {"protocol_ref": "fixture/weekly_roster", "cases": [
        case("stable", "code", True), case("stretch", "writing"),
    ]}
    evidence = {"evidence_ref": "fixture/weekly_receipts", "baseline_sha256": BASELINE, "baseline": [
        observation("base", "stable", True), observation("base", "stretch", False),
    ], "snapshots": [
        {"active_sha256": LATER, "observed_at": "2026-10-19T07:00:00+07:00", "snapshot_ref": "fixture/week/c",
         "assessments": [observation("third", "stable", False), observation("third", "stretch", True)]},
        {"active_sha256": FIRST, "observed_at": "2026-10-12T06:59:59.999999+07:00", "snapshot_ref": "fixture/week/a",
         "assessments": [observation("first", "stable", True), observation("first", "stretch", True)]},
    ]}
    raw = {"series_ref": "fixture/weekly", "start_week": "2026-10-05", "week_count": 4, "as_of": "2026-10-26T00:00:00Z",
           "protocol": protocol, "baseline_sha256": BASELINE, "evidence_sha256": identity(evidence)}
    return raw, evidence


def assess(raw, evidence):
    return model.assess(raw, evidence, identity(raw))


def fresh(raw, evidence):
    raw["evidence_sha256"] = identity(evidence)
    return assess(raw, evidence)


class WeeklyRegressionTests(unittest.TestCase):
    def test_utc_day_at_boundary_and_missing_pending_windows(self):
        report = assess(*fixture())
        self.assertEqual(report["summary"], {"pass": 1, "hold": 1, "missing": 1, "pending": 1})
        first, missing, held, pending = report["weeks"]
        self.assertEqual(first["week_start_utc"], "2026-10-05")
        self.assertEqual(first["active_sha256"], FIRST)
        self.assertEqual(first["observed_at"], "2026-10-11T23:59:59.999999+00:00")
        self.assertEqual(missing["week_start_utc"], "2026-10-12")
        self.assertIsNone(missing["active_sha256"])
        self.assertIsNone(missing["observed_at"])
        self.assertEqual(held["week_start_utc"], "2026-10-19")
        self.assertEqual(held["snapshot_ref"], "fixture/week/c")
        self.assertEqual(held["observed_at"], "2026-10-19T00:00:00+00:00")
        self.assertEqual(pending["week_start_utc"], "2026-10-26")
        self.assertEqual(pending["domains"], [])

    def test_common_baseline_shows_general_loss_even_if_target_improves(self):
        report = assess(*fixture())
        unaffected = report["weeks"][0]["domains"][0]
        code, writing = report["weeks"][2]["domains"]
        self.assertEqual(unaffected["accuracy_delta"], q(0))
        self.assertEqual(code["accuracy_delta"], q(-1))
        self.assertEqual(writing["accuracy_delta"], q(1))
        self.assertEqual(code["critical_regressions"], ["stable"])
        self.assertEqual(report["weeks"][2]["blocked_domains"], ["code"])
        self.assertEqual(code["cases"][0]["baseline"], unaffected["cases"][0]["baseline"])

    def test_when_exactly_one_window_closes_missing_is_reported_as_such(self):
        raw, evidence = fixture()
        raw["as_of"] = "2026-11-02T00:00:00Z"
        product = assess(raw, evidence)
        self.assertEqual(product["weeks"][-1]["status"], "missing")
        self.assertEqual(product["summary"]["missing"], 2)
        self.assertEqual(product["summary"]["pending"], 0)

    def test_duplicate_week_cannot_replace_result_with_a_preferred_snapshot(self):
        raw, evidence = fixture()
        evidence["snapshots"][1]["observed_at"] = "2026-10-19T00:00:01Z"
        with self.assertRaisesRegex(model.InputError, "ganda"):
            fresh(raw, evidence)

    def test_refuses_future_or_out_of_window_observations(self):
        for cap in ("2026-10-26T00:00:01Z", "2026-10-04T23:59:59Z"):
            raw, evidence = fixture()
            evidence["snapshots"][0]["observed_at"] = cap
            with self.subTest(cap=cap), self.assertRaisesRegex(model.InputError, "Snapshot"):
                fresh(raw, evidence)

    def test_snapshot_with_partial_receipt_has_named_holds_for_missing_domains(self):
        raw, evidence = fixture()
        evidence["snapshots"][1]["assessments"].pop()
        row = fresh(raw, evidence)["weeks"][0]
        self.assertEqual(row["status"], "hold")
        self.assertEqual(row["blocked_domains"], ["writing"])
        self.assertIsNone(row["domains"][1]["candidate_accuracy"])
        self.assertEqual(row["domains"][1]["reasons"], ["missing_assessments"])

    def test_requires_strict_monday_and_bounded_count(self):
        for changes in ({"start_week": "2026-10-06"}, {"start_week": "20261005"},
                        {"week_count": 0}, {"week_count": 105}, {"week_count": True}):
            raw, evidence = fixture()
            raw.update(changes)
            with self.subTest(changes=changes), self.assertRaises(model.InputError):
                assess(raw, evidence)

    def test_baseline_and_source_anchors_prevent_unrelated_snapshot_join(self):
        raw, evidence = fixture()
        anchor = identity(raw)
        evidence["baseline_sha256"] = LATER
        with self.assertRaisesRegex(model.InputError, "komitmen"):
            assess(raw, evidence)
        raw["evidence_sha256"] = identity(evidence)
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.assess(raw, evidence, anchor)
        with self.assertRaisesRegex(model.InputError, "baseline"):
            assess(raw, evidence)

    def test_cli_exact_json_and_missing_windows_keep_exit_nonzero(self):
        raw, evidence = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        plan, source = root / "weekly", root / "receipts"
        for weeks, exit_status in ((4, 1), (1, 0)):
            if weeks == 1:
                evidence["snapshots"].pop(0)
            raw.update(week_count=weeks, evidence_sha256=identity(evidence))
            plan.write_bytes(canonical(raw))
            source.write_bytes(canonical(evidence))
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main([str(plan), str(source), "--expect-sha256", identity(raw)]), exit_status)
            self.assertEqual(json.loads(out.getvalue()), assess(raw, evidence))
            self.assertEqual(source.read_bytes(), canonical(evidence))

    def test_snapshot_input_order_is_reflected_in_anchor_but_not_weekly_results(self):
        raw, evidence = fixture()
        before = assess(raw, evidence)
        evidence["snapshots"].reverse()
        after = fresh(raw, evidence)
        self.assertNotEqual(before["evidence_sha256"], after["evidence_sha256"])
        self.assertEqual(before["summary"], after["summary"])
        self.assertEqual(before["weeks"], after["weeks"])

    def test_outside_roster_and_duplicate_assessments_do_not_earn_coverage(self):
        for changes in ({"case_id": "outside"}, {"case_id": "stable"}):
            raw, evidence = fixture()
            snapshot = evidence["snapshots"][0]
            snapshot["assessments"][1].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(model.InputError, "roster"):
                fresh(raw, evidence)

    def test_closed_series_without_snapshots_does_not_claim_zero_regression(self):
        raw, evidence = fixture()
        evidence["snapshots"].clear()
        product = fresh(raw, evidence)
        self.assertEqual(product["summary"], {"pass": 0, "hold": 0, "missing": 3, "pending": 1})
        self.assertTrue(all(row["domains"] == [] for row in product["weeks"]))
        self.assertEqual({row["active_sha256"] for row in product["weeks"]}, {None})

    def test_missing_baseline_marks_gaps_even_if_all_weekly_receipts_exist(self):
        raw, evidence = fixture()
        evidence["baseline"][1]["assessment"] = None
        product = fresh(raw, evidence)
        writing = product["weeks"][0]["domains"][1]
        self.assertEqual(writing["reasons"], ["missing_assessments"])
        self.assertEqual(writing["cases"][0]["missing"], ["baseline"])
        self.assertEqual(writing["paired_cases"], 0)
        self.assertIsNone(writing["accuracy_delta"])

    def test_latest_observation_at_as_of_is_valid_with_an_open_window(self):
        raw, evidence = fixture()
        evidence["snapshots"][0]["observed_at"] = raw["as_of"]
        row = fresh(raw, evidence)["weeks"][-1]
        self.assertEqual(row["active_sha256"], LATER)
        self.assertEqual(row["status"], "hold")
