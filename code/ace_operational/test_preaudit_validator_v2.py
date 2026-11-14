"""Self-test ladder for the pre-audit validator v2 contract machinery.

Design freeze: docs/research/PREAUDIT_VALIDATOR_V2_DESIGN_FREEZE.md
The v1 semantics are regression-locked by test_preaudit_validator.py and
test_preaudit_holdout.py running unchanged (states only; the harness file
discovery was adapted to digest-named reports). This file tests only what
v2 adds: lifecycle stages (V2-1), spec-digest binding (V2-2), process-error
separation (V2-3), machine-readable reason codes (V2-4), and
nondeterminism-conflict handling (V2-5).
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_operational import preaudit_oracle as oracle
from ace_operational import preaudit_validator as pv
from ace_operational.test_preaudit_validator import Fixture, _dump, _line


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-preaudit-v2-")
        self.addCleanup(self.temp.cleanup)
        self.fx = Fixture(Path(self.temp.name))

    def manifest_obj(self):
        return json.loads(Path(self.fx.manifest_path).read_text(),
                          parse_float=Decimal)


class LifecycleTests(Base):
    def test_stage_block_present_ordered_and_honest(self):
        _, report = self.fx.run()
        life = report["lifecycle"]
        self.assertEqual(life["stages"], ["STAGED", "REGISTERED OBSERVATION",
                                          "VALIDATION VERDICT", "PUBLISHED RESULT"])
        self.assertEqual(life["output_stage"], "VALIDATION VERDICT")
        self.assertEqual(life["stages_not_performed"], ["PUBLISHED RESULT"])
        self.assertEqual(life["input_stage"], "REGISTERED OBSERVATION")
        for check in report["checks"]:
            self.assertEqual(check["stage"], "VALIDATION VERDICT")
            for item in check["items"]:
                self.assertEqual(item["stage"], "VALIDATION VERDICT")

    def test_input_stays_staged_when_c1_fails(self):
        (self.fx.src / "bands.json").unlink()
        _, report = self.fx.run()
        self.assertEqual(report["lifecycle"]["input_stage"], "STAGED")
        self.assertEqual(report["lifecycle"]["output_stage"], "VALIDATION VERDICT")


class DigestBindingTests(Base):
    def test_oracle_agrees_on_spec_digest(self):
        _, report = self.fx.run()
        source_bytes = Path(pv.__file__).read_bytes()
        expected = oracle.oracle_spec_digest(self.manifest_obj(), source_bytes)
        self.assertEqual(report["validation_spec_digest"], expected)
        for check in report["checks"]:
            self.assertEqual(check["validation_spec_digest"], expected)

    def test_digest_changes_with_evidence_closure(self):
        _, r1 = self.fx.run("o1")
        summary = json.loads(self.fx.files["summary.json"])
        summary["label"] = "berubah"
        self.fx.files["summary.json"] = _dump(summary)
        self.fx.rebuild()
        _, r2 = self.fx.run("o2")
        self.assertNotEqual(r1["validation_spec_digest"], r2["validation_spec_digest"])

    def test_digest_changes_with_ruleset(self):
        _, r1 = self.fx.run("o1")
        self.fx.manifest["count_assertions"][1]["tolerance"] = "0.001"
        self.fx.manifest_path.write_bytes(_dump(self.fx.manifest))
        _, r2 = self.fx.run("o2")
        self.assertNotEqual(r1["validation_spec_digest"], r2["validation_spec_digest"])
        # The looser tolerance does not change any state on this package.
        self.assertEqual(self.fx.states(r1), self.fx.states(r2))

    def test_digest_changes_with_build_but_states_do_not(self):
        alt_build = {"version": pv.VALIDATOR_VERSION, "source_sha256": "0" * 64}
        manifest_bytes = Path(self.fx.manifest_path).read_bytes()
        r1 = pv.validate(manifest_bytes, self.fx.src)
        r2 = pv.validate(manifest_bytes, self.fx.src, build_stamp=alt_build)
        self.assertNotEqual(r1["validation_spec_digest"], r2["validation_spec_digest"])
        states = lambda r: {c["check_id"]: c["state"] for c in r["checks"]}
        self.assertEqual(states(r1), states(r2))

    def test_digest_changes_with_configuration(self):
        manifest = self.manifest_obj()
        build = pv.validator_build_stamp()
        d1 = pv.compute_spec_digest(manifest, build)
        with patch.object(pv, "SCHEMA_REPORT", "ace.preaudit_report.vX"):
            d2 = pv.compute_spec_digest(manifest, build)
        self.assertNotEqual(d1, d2)


class ProcessErrorTests(Base):
    def test_missing_manifest_is_process_error_not_verdict(self):
        out = Path(self.temp.name) / "out-err"
        code = pv.main(["--manifest", str(Path(self.temp.name) / "nope.json"),
                        "--source-root", str(self.fx.src), "--out-dir", str(out)])
        self.assertEqual(code, 1)
        record = json.loads((out / "process_error.json").read_text())
        self.assertEqual(record["kind"], "PROCESS_ERROR")
        self.assertIsNone(record["verdict"])
        text = json.dumps(record)
        for state_word in ("SESUAI", "TIDAK SESUAI", '"UNKNOWN"'):
            self.assertNotIn(state_word, text)
        self.assertEqual(list(out.glob("report-*.json")), [])

    def test_unparseable_manifest_is_process_error(self):
        bad = Path(self.temp.name) / "bad.json"
        bad.write_bytes(b"{not json")
        out = Path(self.temp.name) / "out-bad"
        code = pv.main(["--manifest", str(bad), "--source-root", str(self.fx.src),
                        "--out-dir", str(out)])
        self.assertEqual(code, 1)
        self.assertTrue((out / "process_error.json").is_file())
        self.assertEqual(list(out.glob("report-*.json")), [])

    def test_internal_crash_is_process_error_not_unknown(self):
        out = Path(self.temp.name) / "out-crash"
        with patch.object(pv, "check_c2", side_effect=RuntimeError("boom")):
            code = pv.main(["--manifest", str(self.fx.manifest_path),
                            "--source-root", str(self.fx.src), "--out-dir", str(out)])
        self.assertEqual(code, 1)
        record = json.loads((out / "process_error.json").read_text())
        self.assertEqual(record["kind"], "PROCESS_ERROR")
        self.assertIn("boom", record["error"])
        self.assertEqual(list(out.glob("report-*.json")), [])


class ReasonCodeTests(Base):
    def test_every_item_code_is_registered_and_matches_state(self):
        _, report = self.fx.run()
        for check in report["checks"]:
            for item in check["items"]:
                self.assertIn(item["reason_code"], pv.REASON_CODES)
                self.assertEqual(pv.REASON_CODES[item["reason_code"]], item["state"])

    def test_not_declared_codes_for_bare_manifest(self):
        bare = {"schema": pv.SCHEMA_MANIFEST, "package_id": "bare",
                "artifacts": self.fx.manifest["artifacts"]}
        path = Path(self.temp.name) / "bare.json"
        path.write_bytes(_dump(bare))
        out = Path(self.temp.name) / "out-bare"
        code = pv.main(["--manifest", str(path), "--source-root", str(self.fx.src),
                        "--out-dir", str(out)])
        report = json.loads(next(out.glob("report-*.json")).read_text())
        codes = {c["check_id"]: [i["reason_code"] for i in c["items"]]
                 for c in report["checks"]}
        self.assertEqual(codes["C2"], ["NOT_DECLARED"])
        self.assertEqual(codes["C3"], ["NOT_DECLARED"])
        self.assertEqual(code, 3)

    def test_unknown_codes_across_fuzz_shapes(self):
        cases = {}
        entry = json.loads(self.fx.files["results.jsonl"])
        entry["result"]["verdict"] = None
        cases["verdict-null"] = ("results.jsonl", _line(entry) + b"\n", "VERDICT_UNDECIDABLE")
        entry2 = json.loads(self.fx.files["results.jsonl"])
        del entry2["result"]["metrics"]["score_pp"]
        cases["metric-missing"] = ("results.jsonl", _line(entry2) + b"\n", "METRIC_MISSING")
        for name, (fname, data, expected_code) in cases.items():
            with self.subTest(case=name):
                fx = Fixture(Path(self.temp.name) / name)
                (fx.src / fname).write_bytes(data)
                fx.refresh_hash(fname)
                _, report = fx.run()
                codes = [i["reason_code"] for c in report["checks"] for i in c["items"]
                         if i["state"] == pv.UNKNOWN]
                self.assertIn(expected_code, codes)


class ConflictTests(Base):
    def test_rerun_identical_is_idempotent(self):
        code1, _ = self.fx.run("out")
        code2, _ = self.fx.run("out")
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)

    def test_tampered_stored_report_conflicts_and_is_preserved(self):
        out = Path(self.temp.name) / "out"
        code1, _ = self.fx.run("out")
        self.assertEqual(code1, 0)
        stored = next(out.glob("report-*.json"))
        tampered = stored.read_bytes().replace(b"fx-01", b"fx-XX")
        stored.write_bytes(tampered)
        code2, _ = self.fx.run("out")
        self.assertEqual(code2, 4)
        self.assertEqual(stored.read_bytes(), tampered)  # never overwritten
        conflict = json.loads(next(out.glob("nondeterminism_conflict-*.json")).read_text())
        self.assertEqual(conflict["kind"], "NONDETERMINISM_CONFLICT")
        entry = [c for c in conflict["conflicts"] if c["file"] == stored.name][0]
        self.assertEqual(entry["stored_sha256"], hashlib.sha256(tampered).hexdigest())
        self.assertNotEqual(entry["stored_sha256"], entry["computed_sha256"])

    def test_different_spec_coexists_in_same_out_dir(self):
        out = Path(self.temp.name) / "out"
        self.fx.run("out")
        before = {p.name for p in out.glob("report-*.json")}
        self.fx.manifest["count_assertions"][1]["tolerance"] = "0.5"
        self.fx.manifest_path.write_bytes(_dump(self.fx.manifest))
        code, _ = self.fx.run("out")
        after = {p.name for p in out.glob("report-*.json")}
        self.assertEqual(code, 0)
        self.assertEqual(len(after), len(before) + 1)
        self.assertTrue(before.issubset(after))


if __name__ == "__main__":
    unittest.main()
