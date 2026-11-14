"""Tests for g4_instrument (design: PR #136 Part I;
dossier design: bench Task 08; build brief: bench
Task 10).

All dossiers are synthetic — constructed in temp dirs by
these tests. No real program evidence is scored here;
this file tests the instrument, not G4.
"""

import json
import tempfile
import unittest
from pathlib import Path

from ace_operational.g4_instrument import assess_g4

DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64
THIRD_DIGEST = "c" * 64
PREDECESSOR = "cand_predecessor_v4"
SUCCESSOR = "cand_successor_g4"


def _lineage(**over):
    record = {"predecessor_id": PREDECESSOR,
              "successor_id": SUCCESSOR,
              "successor_parents": [PREDECESSOR],
              "capability_digest": DIGEST,
              "archive_audit": "CLEAN",
              "chain_valid": True}
    record.update(over)
    return record


def _capability(*, digest=DIGEST, discovery_digest=DIGEST,
                evidence=None, name="operator_catalog_v4"):
    if evidence is None:
        evidence = {"admitted_operators_total": 6,
                    "admitted_chains_total": 2,
                    "admission_rule": "fixes >= 2 pool tasks"}
    return {"artifact_name": name,
            "artifact_digest": digest,
            "discovery_record": {
                "artifact_name": name,
                "artifact_digest": discovery_digest,
                "admission_evidence": evidence}}


def _evaluation(**over):
    report = {"protocol_hash": "hash-g4-1",
              "audit": "CLEAN",
              "successor_id": SUCCESSOR,
              "artifact_digest_loaded": DIGEST,
              "discovery_invoked": False,
              "margin_pp": 20.0,
              "with_floor": 0.25,
              "without_ceiling": 0.10,
              "min_capability_tasks": 40,
              "capability": {"n": 47, "with_solved": 15,
                             "without_solved": 0},
              "control": {"with_solved": 34, "without_solved": 34}}
    report.update(over)
    return report


class G4InstrumentTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, filename, obj):
        path = self.dir / filename
        path.write_text(obj if isinstance(obj, str)
                        else json.dumps(obj))
        return path.name

    def _dossier(self, *, lineage=None, capability=None,
                 evaluation=None, drop=()):
        files = {}
        if "lineage" not in drop:
            files["lineage"] = self._write(
                "lineage_record.json",
                _lineage() if lineage is None else lineage)
        if "capability" not in drop:
            files["capability"] = self._write(
                "capability_record.json",
                _capability() if capability is None else capability)
        if "evaluation" not in drop:
            files["evaluation"] = self._write(
                "evaluation_report.json",
                _evaluation() if evaluation is None else evaluation)
        (self.dir / "dossier.json").write_text(json.dumps(files))
        return self.dir

    # -- the outcome map -------------------------------------

    def test_complete_dossier_inheritance_demonstrated(self):
        out = assess_g4(dossier=self._dossier())
        self.assertEqual(out["gate"], "G4")
        self.assertEqual(out["criteria_version"], 1)
        self.assertEqual(out["overall"], "INHERITANCE_DEMONSTRATED")
        self.assertEqual(out["identity_mismatches"], [])
        for clause in out["clauses"].values():
            self.assertEqual(clause["verdict"], "PASS", clause)

    def test_delta_below_margin_only_is_lineage_only(self):
        # n=40, with=11 (27.5% >= floor), without=4 (10.0% <=
        # ceiling): delta = 17.5pp < 20pp margin — only the
        # margin condition fails.
        ev = _evaluation(capability={"n": 40, "with_solved": 11,
                                     "without_solved": 4})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.margin_not_met",
                      out["clauses"]["C3"]["missing"])
        self.assertNotIn("c3.with_floor_not_met",
                         out["clauses"]["C3"]["missing"])
        self.assertNotIn("c3.attribution_ceiling_exceeded",
                         out["clauses"]["C3"]["missing"])

    def test_with_arm_below_floor_is_lineage_only(self):
        # delta = 22.5pp >= margin, but with/n = 22.5% < 25%.
        ev = _evaluation(capability={"n": 40, "with_solved": 9,
                                     "without_solved": 0})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.with_floor_not_met",
                      out["clauses"]["C3"]["missing"])
        self.assertNotIn("c3.margin_not_met",
                         out["clauses"]["C3"]["missing"])

    def test_without_arm_above_ceiling_is_lineage_only(self):
        # delta = 35pp, with/n = 50%, but without/n = 15% >
        # 10%: the effect cannot be attributed to inheritance.
        ev = _evaluation(capability={"n": 40, "with_solved": 20,
                                     "without_solved": 6})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.attribution_ceiling_exceeded",
                      out["clauses"]["C3"]["missing"])

    def test_control_regression_is_lineage_only(self):
        ev = _evaluation(control={"with_solved": 30,
                                  "without_solved": 34})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.control_regression",
                      out["clauses"]["C3"]["missing"])

    def test_evaluation_absent_is_lineage_only(self):
        out = assess_g4(dossier=self._dossier(drop=("evaluation",)))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertEqual(out["clauses"]["C1"]["verdict"], "PASS")
        self.assertEqual(out["clauses"]["C2"]["verdict"], "PASS")
        self.assertEqual(out["clauses"]["C3"]["verdict"], "FAIL")

    # -- fail-closed and adversarial --------------------------

    def test_broken_lineage_chain_fails_c1(self):
        out = assess_g4(dossier=self._dossier(
            lineage=_lineage(chain_valid=False)))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertIn("lineage.chain_valid_not_true",
                      out["clauses"]["C1"]["missing"])
        out = assess_g4(dossier=self._dossier(
            lineage=_lineage(archive_audit="DIRTY")))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertIn("lineage.archive_audit_not_clean",
                      out["clauses"]["C1"]["missing"])

    def test_successor_parent_link_missing_fails_c1(self):
        out = assess_g4(dossier=self._dossier(
            lineage=_lineage(successor_parents=["cand_someone_else"])))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertIn("lineage.successor_parent_link_missing",
                      out["clauses"]["C1"]["missing"])

    def test_lineage_digest_differs_from_capability_record(self):
        out = assess_g4(dossier=self._dossier(
            lineage=_lineage(capability_digest=OTHER_DIGEST)))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(len(out["identity_mismatches"]), 1)
        self.assertEqual(out["clauses"]["C1"]["verdict"], "FAIL")

    def test_name_trap_same_name_different_discovery_digest(self):
        cap = _capability(discovery_digest=OTHER_DIGEST)
        out = assess_g4(dossier=self._dossier(capability=cap))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(out["clauses"]["C2"]["verdict"], "FAIL")
        self.assertEqual(len(out["identity_mismatches"]), 1)

    def test_successor_that_rediscovers_fails_c3_by_name(self):
        ev = _evaluation(discovery_invoked=True)
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.successor_rediscovered",
                      out["clauses"]["C3"]["missing"])

    def test_missing_without_arm_is_control_arm_missing(self):
        ev = _evaluation(capability={"n": 47, "with_solved": 15})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.control_arm_missing",
                      out["clauses"]["C3"]["missing"])

    def test_loaded_digest_differs_from_capability_digest(self):
        ev = _evaluation(artifact_digest_loaded=THIRD_DIGEST)
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(len(out["identity_mismatches"]), 1)
        self.assertEqual(out["clauses"]["C3"]["verdict"], "FAIL")

    def test_evaluation_successor_differs_from_lineage(self):
        ev = _evaluation(successor_id="cand_impostor")
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.successor_id_mismatch",
                      out["clauses"]["C3"]["missing"])

    def test_missing_threshold_field_fails_c3_by_name(self):
        ev = _evaluation()
        del ev["margin_pp"]
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.threshold_field_missing:margin_pp",
                      out["clauses"]["C3"]["missing"])

    def test_capability_n_below_minimum_fails_c3(self):
        ev = _evaluation(capability={"n": 30, "with_solved": 15,
                                     "without_solved": 0})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.capability_tasks_below_minimum",
                      out["clauses"]["C3"]["missing"])

    def test_missing_dossier_is_fail_closed(self):
        out = assess_g4(dossier=None)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(out["gate"], "G4")
        out = assess_g4(dossier=self.dir / "no_such_dir")
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        for clause in out["clauses"].values():
            self.assertEqual(clause["verdict"], "FAIL", clause)

    def test_malformed_json_is_named_fail_not_exception(self):
        dossier = self._dossier()
        (self.dir / "capability_record.json").write_text("{not json")
        out = assess_g4(dossier=dossier)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertIn("capability.record_missing_or_unparseable",
                      out["clauses"]["C2"]["missing"])

    def test_non_numeric_counts_are_named_fail_not_exception(self):
        ev = _evaluation(capability={"n": "47", "with_solved": "15",
                                     "without_solved": "0"})
        out = assess_g4(dossier=self._dossier(evaluation=ev))
        self.assertEqual(out["overall"], "LINEAGE_ONLY")
        self.assertIn("c3.capability_counts_not_numeric",
                      out["clauses"]["C3"]["missing"])

    def test_mismatch_recorded_once_and_superseded_is_warning(self):
        # Lesson 1: a digest mismatch is described exactly
        # once in the whole assessment (in
        # identity_mismatches); clauses carry only the
        # pointer.
        cap = _capability(discovery_digest=OTHER_DIGEST)
        out = assess_g4(dossier=self._dossier(capability=cap))
        self.assertEqual(len(out["identity_mismatches"]), 1)
        description = out["identity_mismatches"][0]
        self.assertEqual(
            json.dumps(out, ensure_ascii=False).count(description), 1)
        # Lesson 2: a superseded lineage record listed
        # alongside the current one is a warning; C1 stands
        # on the valid evidence.
        lineage = _lineage(superseded_records=[
            {"successor_id": "cand_old", "chain_valid": False}])
        out = assess_g4(dossier=self._dossier(lineage=lineage))
        self.assertEqual(out["overall"], "INHERITANCE_DEMONSTRATED")
        self.assertEqual(out["clauses"]["C1"]["verdict"], "PASS")
        self.assertTrue(any("superseded" in w for w in
                            out["clauses"]["C1"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
