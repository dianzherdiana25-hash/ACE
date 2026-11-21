"""Verifier retensi berseri, kehilangan tertunda, recovery dan coverage."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import long_forgetting_probe as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


ARTIFACTS = [f"{value}"*64 for value in range(7)]


def observation(when, key, verdict):
    return {"case_id": key, "assessment": None if verdict is None else {
        "passed": verdict, "assessment_ref": f"fixture/grade/{when}/{key}"}}


def fixture():
    cases = [("fragile", "code", True), ("strong", "code", False), ("new", "writing", False)]
    protocol = {"protocol_ref": "fixture/protocol", "cases": [
        {"case_id": key, "domain": kind, "case_ref": f"fixture/case/{key}", "critical": critical}
        for key, kind, critical in cases]}
    states = {
        1: (True, True, False),
        2: (False, False, True),
        3: (False, None, True),
        4: (True, False, True),
        6: (False, True, True),
    }
    baseline = [observation("before", "fragile", True), observation("before", "strong", True),
                observation("before", "new", False)]
    receipts = {"receipt_ref": "fixture/timeline_receipts", "baseline_sha256": ARTIFACTS[0], "baseline": baseline,
                "snapshots": [
                    {"checkpoint_sha256": ARTIFACTS[when], "snapshot_ref": f"fixture/snapshot/{when}",
                     "assessments": [observation(when, key, passed) for (key, _, _), passed in zip(cases, values)]}
                    for when, values in states.items()]}
    plan = {"plan_ref": "fixture/retention", "protocol": protocol, "baseline_sha256": ARTIFACTS[0],
            "observations_sha256": identity(receipts), "checkpoints": [
                {"checkpoint_sha256": ARTIFACTS[index], "checkpoint_ref": f"fixture/checkpoint/{index}",
                 "at": f"2026-11-{index:02}T00:00:00Z"} for index in range(1, len(ARTIFACTS))]}
    return plan, receipts


def assess(raw, data):
    return model.assess(raw, data, identity(raw))


def fresh(raw, data):
    raw["observations_sha256"] = identity(data)
    return assess(raw, data)


class LongForgettingTests(unittest.TestCase):
    def test_late_loss_contiguous_persistence_and_recovery(self):
        product = assess(*fixture())
        fragile, strong = product["baseline_pass_cases"]
        self.assertEqual(fragile["case_id"], "fragile")
        self.assertTrue(fragile["critical"])
        self.assertEqual(fragile["delayed_regressions"], [ARTIFACTS[2]])
        self.assertEqual(fragile["recoveries"], [ARTIFACTS[4]])
        self.assertEqual(fragile["longest_regression"], 2)
        self.assertEqual([row["status"] for row in fragile["timeline"]],
                         ["retained", "regressed", "regressed", "retained", "unpaired", "regressed"])
        self.assertEqual(fragile["timeline"][1]["assessment_ref"], "fixture/grade/2/fragile")
        self.assertEqual(fragile["baseline_assessment_ref"], "fixture/grade/before/fragile")
        self.assertEqual(strong["case_id"], "strong")
        self.assertEqual(strong["longest_regression"], 1)
        self.assertEqual(strong["recoveries"], [])

    def test_domain_metrics_retained_even_when_other_domain_flagged(self):
        product = assess(*fixture())
        first, second, partial, _, missing, _ = product["checkpoints"]
        self.assertEqual(first["status"], "pass")
        self.assertEqual(second["status"], "hold")
        code, writing = second["domains"]
        self.assertEqual(code["accuracy_delta"], q(-1))
        self.assertEqual(code["critical_regressions"], ["fragile"])
        self.assertEqual(writing["accuracy_delta"], q(1))
        self.assertEqual(writing["status"], "pass")
        self.assertIsNone(partial["domains"][0]["accuracy_delta"])
        self.assertIn("missing_assessments", partial["domains"][0]["reasons"])
        self.assertIsNone(missing["snapshot_ref"])
        self.assertTrue(all(row["accuracy_delta"] is None for row in missing["domains"]))
        self.assertEqual(second["snapshot_ref"], "fixture/snapshot/2")

    def test_baseline_hash_and_receipt_payload_must_both_match(self):
        raw, receipts = fixture()
        anchor = identity(raw)
        receipts["baseline_sha256"] = "f"*64
        with self.assertRaisesRegex(model.InputError, "komitmen"):
            assess(raw, receipts)
        raw["observations_sha256"] = identity(receipts)
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.assess(raw, receipts, anchor)
        with self.assertRaisesRegex(model.InputError, "Identitas baseline"):
            assess(raw, receipts)

    def test_global_assessment_refs_cannot_reuse_same_evidence_across_later_checks(self):
        raw, receipts = fixture()
        first, second = receipts["snapshots"][:2]
        second["assessments"][0]["assessment"]["assessment_ref"] = first["assessments"][0]["assessment"]["assessment_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            fresh(raw, receipts)

    def test_requires_strictly_increasing_and_unique_checkpoints_in_commitment(self):
        for changes in ({"at": "2026-11-01T07:00:00+07:00"}, {"checkpoint_sha256": ARTIFACTS[1]},
                        {"checkpoint_sha256": ARTIFACTS[0]}):
            raw, receipts = fixture()
            raw["checkpoints"][1].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(model.InputError, "jadwal"):
                assess(raw, receipts)

    def test_no_snapshot_or_baseline_receipts_yields_unpaired_coverage(self):
        raw, receipts = fixture()
        receipts["snapshots"] = []
        receipts["baseline"] = []
        product = fresh(raw, receipts)
        self.assertFalse(product["baseline_pass_cases"])
        self.assertTrue(all(row["status"] == "hold" and row["snapshot_ref"] is None for row in product["checkpoints"]))

    def test_observations_use_checkpoint_and_case_membership_independently(self):
        raw, receipts = fixture()
        unknown = receipts["snapshots"][0]
        original = dict(unknown)
        unknown["checkpoint_sha256"] = "f"*64
        with self.assertRaisesRegex(model.InputError, "di luar timeline"):
            fresh(raw, receipts)
        unknown.update(original)
        unknown["assessments"][0]["case_id"] = "absent-case"
        with self.assertRaisesRegex(model.InputError, "di luar protokol"):
            fresh(raw, receipts)

    def test_cli_reports_hold_with_no_modification_of_recorded_snapshots(self):
        raw, receipts = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p, source = root / "plan", root / "receipts"
        p.write_bytes(canonical(raw))
        source.write_bytes(canonical(receipts))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(p), str(source), "--expect-sha256", identity(raw)]), 1)
        self.assertEqual(json.loads(out.getvalue()), assess(raw, receipts))
        self.assertEqual(source.read_bytes(), canonical(receipts))
        self.assertEqual(p.read_bytes(), canonical(raw))

    def test_critical_loss_is_reported_even_with_measured_flat_domain_accuracy(self):
        raw, receipts = fixture()
        for row in receipts["baseline"]:
            if row["case_id"] == "strong":
                row["assessment"]["passed"] = False
        for point in receipts["snapshots"]:
            if point["checkpoint_sha256"] == ARTIFACTS[2]:
                point["assessments"][1]["assessment"]["passed"] = True
        checkpoint = fresh(raw, receipts)["checkpoints"][1]
        software = checkpoint["domains"][0]
        self.assertEqual(software["accuracy_delta"], q(0))
        self.assertEqual(software["reasons"], ["critical_regression"])

    def test_checkpoint_snapshot_order_in_receipt_does_not_control_timeline(self):
        raw, receipts = fixture()
        original = assess(raw, receipts)
        receipts["snapshots"].reverse()
        result = fresh(raw, receipts)
        self.assertEqual(result["checkpoints"], original["checkpoints"])
        self.assertEqual(result["baseline_pass_cases"], original["baseline_pass_cases"])
