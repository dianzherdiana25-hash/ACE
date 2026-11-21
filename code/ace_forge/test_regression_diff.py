"""Verifier transisi kemampuan, perubahan kontrak, dan hasil belum diuji."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import regression_diff as model
from ace_forge._forge_io import canonical, identity


def check(key, verdict, arm, contract=None):
    return {"id": key, "verdict": verdict, "contract_sha256": contract or identity(key),
            "evidence_ref": f"fixture/{arm}/case/{key}" if verdict != "not_run" else None}


def group(key, arm, *checks):
    return {"id": key, "spec_ref": f"fixture/{arm}/spec/{key}", "checks": list(checks)}


def snapshot(artifact, arm, *capabilities):
    return {"artifact_sha256": artifact * 64, "snapshot_ref": f"fixture/{arm}", "capabilities": list(capabilities)}


def fixture():
    old = snapshot("1", "old",
                   group("parse", "old", check("broken", "pass", "old"), check("repaired", "fail", "old"),
                         check("removed", "pass", "old"), check("changed", "pass", "old")),
                   group("index", "old", check("same", "pass", "old"), check("two", "fail", "old")),
                   group("retrieval", "old", check("retried", "fail", "old")),
                   group("obsolete", "old", check("old-only", "pass", "old")))
    new = snapshot("2", "new",
                   group("parse", "new", check("broken", "fail", "new"), check("repaired", "pass", "new"),
                         check("new-test", "pass", "new"), check("changed", "fail", "new", "3" * 64)),
                   group("index", "new", check("same", "pass", "new"), check("two", "fail", "new")),
                   group("retrieval", "new", check("retried", "pass", "new")),
                   group("later", "new", check("new-only", "pass", "new")))
    return old, new


def compare(old, new):
    return model.compare(old, new, identity(old), identity(new))


class RegressionTests(unittest.TestCase):
    def test_detects_named_transitions_without_averaging_away_regressions(self):
        report = compare(*fixture())
        self.assertEqual(report["regressions"], [{"capability_id": "parse", "check_ids": ["broken"]}])
        self.assertEqual(report["capability_states"], {
            "capability_added": 1, "capability_removed": 1, "improved": 1,
            "no_transition": 1, "regression_observed": 1,
        })
        capabilities = {row["id"]: row for row in report["capabilities"]}
        self.assertEqual(capabilities["parse"]["matched_checks"], 2)
        self.assertEqual(capabilities["parse"]["counts"], {
            "check_added": 1, "check_removed": 1, "contract_changed": 1, "fixed": 1, "regressed": 1,
        })
        self.assertEqual(capabilities["parse"]["before_spec_ref"], "fixture/old/spec/parse")
        self.assertEqual(capabilities["retrieval"]["changes"][0]["after"]["evidence_ref"],
                         "fixture/new/case/retried")

    def test_unknown_and_contract_changes_are_not_reported_as_quality_loss(self):
        old, new = fixture()
        after_checks = new["capabilities"][0]["checks"]
        after_checks[0] = check("broken", "not_run", "new")
        report = compare(old, new)
        row = next(row for row in report["capabilities"] if row["id"] == "parse")
        self.assertEqual(row["status"], "coverage_changed")
        self.assertEqual(row["counts"]["unmeasured"], 1)
        self.assertEqual(row["counts"]["contract_changed"], 1)
        self.assertEqual(report["regressions"], [])

    def test_unchanged_evidence_pointer_cannot_measure_independent_arms(self):
        old, new = fixture()
        new["capabilities"][2]["checks"][0]["evidence_ref"] = "fixture/old/case/retried"
        group_ = next(row for row in compare(old, new)["capabilities"] if row["id"] == "retrieval")
        self.assertEqual(group_["status"], "coverage_changed")
        self.assertEqual(group_["counts"], {"shared_evidence": 1})
        self.assertEqual(group_["matched_checks"], 0)

    def test_empty_snapshot_and_empty_named_capability_do_not_fabricate_retention(self):
        old = snapshot("1", "old")
        new = snapshot("2", "new")
        self.assertEqual(compare(old, new)["capabilities"], [])
        old["capabilities"] = [group("known", "old")]
        new["capabilities"] = [group("known", "new")]
        result, = compare(old, new)["capabilities"]
        self.assertEqual(result["status"], "coverage_changed")
        self.assertEqual(result["matched_checks"], 0)

    def test_anchor_separates_editing_each_arm(self):
        old, new = fixture()
        old_hash, new_hash = identity(old), identity(new)
        old["capabilities"][0]["checks"][0]["verdict"] = "fail"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.compare(old, new, old_hash, new_hash)
        new["snapshot_ref"] += "/after"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.compare(old, new, identity(old), new_hash)

    def test_two_artifacts_have_to_be_distinct(self):
        old, new = fixture()
        new["artifact_sha256"] = old["artifact_sha256"]
        with self.assertRaisesRegex(model.InputError, "berbeda"):
            compare(old, new)

    def test_bad_evidence_and_duplicate_check_records_fail_closed(self):
        for update in ({"verdict": "not_run"}, {"evidence_ref": None}, {"contract_sha256": "arbitrary"},
                       {"id": "repaired"}, {"evidence_ref": "fixture/new/case/repaired"}):
            old, new = fixture()
            new["capabilities"][0]["checks"][0].update(update)
            with self.subTest(update=update), self.assertRaises(model.InputError):
                compare(old, new)

    def test_conflicting_reused_capability_and_empty_label_are_invalid(self):
        old, new = fixture()
        new["capabilities"].append(group("parse", "elsewhere"))
        with self.assertRaisesRegex(model.InputError, "ganda"):
            compare(old, new)
        new["capabilities"][-1]["id"] = " "
        with self.assertRaises(model.InputError):
            compare(old, new)

    def test_missing_capability_diagnosis_retains_checks_and_provenance(self):
        report = compare(*fixture())
        rows = {row["id"]: row for row in report["capabilities"]}
        removed = rows["obsolete"]
        self.assertIsNone(removed["after_spec_ref"])
        self.assertEqual(removed["changes"][0]["status"], "check_removed")
        self.assertEqual(removed["changes"][0]["before"]["evidence_ref"], "fixture/old/case/old-only")
        self.assertEqual(rows["later"]["changes"][0]["status"], "check_added")

    def test_reverse_comparison_migrates_regression_to_previous_improvement(self):
        old, new = fixture()
        report = compare(new, old)
        self.assertEqual(report["regressions"], [
            {"capability_id": "parse", "check_ids": ["repaired"]},
            {"capability_id": "retrieval", "check_ids": ["retried"]},
        ])

    def test_cli_is_stable_and_does_not_rewrite_input_files(self):
        old, new = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        left, right = root / "before.json", root / "after.json"
        left.write_bytes(canonical(old))
        right.write_bytes(canonical(new))
        args = [str(left), str(right), "--expect-before", identity(old), "--expect-after", identity(new)]
        logs = []
        for _ in range(2):
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main(args), 0)
            logs.append(output.getvalue())
        self.assertEqual(*logs)
        self.assertEqual(json.loads(logs[0]), compare(old, new))
        self.assertEqual(left.read_bytes(), canonical(old))
        self.assertEqual(right.read_bytes(), canonical(new))

    def test_reordered_checks_keep_diagnostics_with_correct_snapshot_identity(self):
        old, new = fixture()
        first = compare(old, new)
        old["capabilities"].reverse()
        new["capabilities"][0]["checks"].reverse()
        second = compare(old, new)
        self.assertNotEqual(first["after"]["snapshot_sha256"], second["after"]["snapshot_sha256"])
        self.assertEqual(first["capabilities"], second["capabilities"])

    def test_named_capability_still_failing_has_no_fabricated_improvement(self):
        old = snapshot("1", "before", group("known", "before", check("probe", "fail", "before")))
        new = snapshot("2", "after", group("known", "after", check("probe", "fail", "after")))
        row, = compare(old, new)["capabilities"]
        self.assertEqual(row["counts"], {"still_failing": 1})
        self.assertEqual(row["status"], "no_transition")
