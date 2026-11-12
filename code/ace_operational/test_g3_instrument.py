"""Tests for g3_instrument (design: PR #135).

All dossiers are synthetic — constructed in temp dirs by
these tests. No real program evidence is scored here;
this file tests the instrument, not G3.
"""

import json
import tempfile
import unittest
from pathlib import Path

from ace_operational.g3_instrument import assess_g3

NAME = "operator-discovery-mechanism"
DIGEST = "sha256:aaa111"


def _report(*, digest=DIGEST, name=NAME, audit="CLEAN",
            protocol="hash-1", held_out=True, base=40.0,
            score=75.0, margin=10.0):
    return {"protocol_hash": protocol, "audit_status": audit,
            "improvement_name": name, "improvement_digest": digest,
            "held_out": held_out, "baseline_score": base,
            "improvement_score": score, "margin_pp": margin}


class G3InstrumentTests(unittest.TestCase):

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

    def _dossier(self, *, source=None, evaluations=None,
                 name=NAME, digest=DIGEST):
        source = _report() if source is None else source
        evaluations = [("pricing", _report())] \
            if evaluations is None else evaluations
        src = self._write("source.json", source)
        evals = [{"family": fam,
                  "report": self._write(f"eval-{fam}-{i}.json", rep)}
                 for i, (fam, rep) in enumerate(evaluations)]
        dossier = {"improvement": {"name": name, "digest": digest},
                   "source": {"family": "grid", "report": src},
                   "evaluations": evals}
        path = self.dir / "dossier.json"
        path.write_text(json.dumps(dossier))
        return path

    # -- the outcome map -------------------------------------

    def test_complete_dossier_transfer_demonstrated(self):
        out = assess_g3(dossier=self._dossier())
        self.assertEqual(out["overall"], "TRANSFER_DEMONSTRATED")
        self.assertEqual(out["criteria_version"], 1)
        for clause in out["clauses"].values():
            self.assertEqual(clause["verdict"], "PASS", clause)
        self.assertEqual(sorted(out["positive_families"]),
                         ["grid", "pricing"])

    def test_exactly_one_family_effect_is_specialization(self):
        weak = _report(score=45.0)  # +5 points < 10 margin
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", weak)]))
        self.assertEqual(out["overall"], "SPECIALIZATION")
        self.assertEqual(out["positive_families"], ["grid"])

    def test_zero_family_effect_not_demonstrated(self):
        out = assess_g3(dossier=self._dossier(
            source=_report(score=45.0),
            evaluations=[("pricing", _report(score=42.0))]))
        # Source effect is positive (+5) so C1 passes; neither
        # family meets its margin.
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(out["positive_families"], [])

    def test_removing_second_family_leaves_specialization(self):
        out = assess_g3(dossier=self._dossier(evaluations=[]))
        self.assertEqual(out["overall"], "SPECIALIZATION")
        self.assertEqual(
            out["clauses"]["C2_two_distinct_families"]["verdict"],
            "FAIL")

    # -- the identity fence ----------------------------------

    def test_digest_mismatch_is_a_hard_fence(self):
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", _report(digest="sha256:bbb222"))]))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(len(out["identity_mismatches"]), 1)
        self.assertIn("pricing", out["identity_mismatches"][0])
        self.assertIn("sha256:bbb222", out["identity_mismatches"][0])

    def test_name_trap_same_name_different_digest(self):
        # The anti-reward-hacking trap: the artifact NAME
        # matches everywhere; a quietly re-authored artifact
        # carries a different digest. Name alone must not pass.
        out = assess_g3(dossier=self._dossier(
            source=_report(name=NAME, digest=DIGEST),
            evaluations=[("pricing",
                          _report(name=NAME, digest="sha256:zzz999"))]))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertTrue(out["identity_mismatches"])

    # -- clause-level failures, named -------------------------

    def test_missing_preregistration_fails_c1_by_name(self):
        bad = _report()
        del bad["protocol_hash"]
        out = assess_g3(dossier=self._dossier(source=bad))
        c1 = out["clauses"]["C1_identified_improvement"]
        self.assertEqual(c1["verdict"], "FAIL")
        self.assertTrue(any("protocol_hash" in m
                            for m in c1["missing"]))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")

    def test_unaudited_family_report_is_rejected(self):
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", _report(audit="DIRTY"))]))
        self.assertEqual(out["overall"], "SPECIALIZATION")
        c2 = out["clauses"]["C2_two_distinct_families"]
        self.assertTrue(any("audit" in m for m in c2["rejected"]))

    def test_same_family_twice_is_one_family(self):
        out = assess_g3(dossier=self._dossier(
            evaluations=[("grid", _report())]))
        self.assertEqual(out["overall"], "SPECIALIZATION")
        c2 = out["clauses"]["C2_two_distinct_families"]
        self.assertTrue(any("twice" in m for m in c2["rejected"]))

    def test_margin_not_met_family_not_counted(self):
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", _report(score=55.0))]))  # +15 >= margin 10 -> counts
        self.assertEqual(out["overall"], "TRANSFER_DEMONSTRATED")
        out2 = assess_g3(dossier=self._dossier(
            evaluations=[("pricing",
                          _report(score=55.0, margin=20.0))]))
        self.assertEqual(out2["overall"], "SPECIALIZATION")

    def test_missing_margin_family_not_counted_and_named(self):
        rep = _report()
        del rep["margin_pp"]
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", rep)]))
        self.assertEqual(out["overall"], "SPECIALIZATION")
        c3 = out["clauses"]["C3_positive_transfer"]
        self.assertTrue(any("margin_pp" in m for m in c3["rejected"]))

    def test_unknown_family_fails_c2_by_name(self):
        out = assess_g3(dossier=self._dossier(
            evaluations=[("cooking", _report())]))
        c2 = out["clauses"]["C2_two_distinct_families"]
        self.assertEqual(c2["verdict"], "FAIL")
        self.assertTrue(any("cooking" in m for m in c2["rejected"]))

    def test_source_effect_not_positive_fails_c1(self):
        out = assess_g3(dossier=self._dossier(
            source=_report(score=30.0)))
        c1 = out["clauses"]["C1_identified_improvement"]
        self.assertEqual(c1["verdict"], "FAIL")
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")

    def test_not_held_out_family_does_not_count(self):
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", _report(held_out=False))]))
        self.assertEqual(out["overall"], "SPECIALIZATION")

    # -- verification findings (Addendum 42 section 2) --------

    def test_source_mismatch_recorded_once(self):
        # Finding 1 (probe E1b): the source report is checked
        # in both the C1 block and the family loop; its
        # identity mismatch must be recorded exactly once.
        out = assess_g3(dossier=self._dossier(
            source=_report(digest="sha256:src000")))
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(len(out["identity_mismatches"]), 1)

    def test_extra_invalid_entry_does_not_fail_c2(self):
        # Finding 2 (probe E5): two valid positive families
        # plus one extra invalid evaluation entry — C2's
        # requirement is met, so C2 passes; the invalid
        # entry is named as rejected, not as a clause failure.
        out = assess_g3(dossier=self._dossier(
            evaluations=[("pricing", _report()),
                         ("shipping", _report(audit="DIRTY"))]))
        self.assertEqual(out["overall"], "TRANSFER_DEMONSTRATED")
        c2 = out["clauses"]["C2_two_distinct_families"]
        self.assertEqual(c2["verdict"], "PASS")
        self.assertEqual(c2["missing"], [])
        self.assertTrue(any("audit" in m for m in c2["rejected"]))

    # -- fail-closed loading ----------------------------------

    def test_missing_dossier_file_fails_closed(self):
        out = assess_g3(dossier=self.dir / "nope.json")
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(out["criteria_version"], 1)
        c1 = out["clauses"]["C1_identified_improvement"]
        self.assertTrue(any("missing/unparseable" in m
                            for m in c1["missing"]))

    def test_malformed_report_fails_closed_by_name(self):
        dossier = self._dossier()
        (self.dir / "source.json").write_text("{not json")
        out = assess_g3(dossier=dossier)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        c1 = out["clauses"]["C1_identified_improvement"]
        self.assertTrue(any("missing/unparseable" in m
                            for m in c1["missing"]))

    def test_non_numeric_scores_named(self):
        out = assess_g3(dossier=self._dossier(
            source=_report(score="high")))
        c1 = out["clauses"]["C1_identified_improvement"]
        self.assertTrue(any("not numeric" in m for m in c1["missing"]))


if __name__ == "__main__":
    unittest.main()
