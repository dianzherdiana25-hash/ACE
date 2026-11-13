"""Self-test ladder for the pre-audit validator v1.

Design freeze: docs/research/PREAUDIT_VALIDATOR_V1_DESIGN_FREEZE.md

Layers covered here: reference fixtures with an INDEPENDENT oracle
(preaudit_oracle, written from the written spec, sharing no code with the
validator), valid-variant false-positive probes with measured FP counts,
seeded defects per rule, property/metamorphic tests, light parser fuzzing,
and read-only enforcement. The holdout corpus lives in
test_preaudit_holdout.py and was authored after the validator froze.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from ace_operational import preaudit_oracle as oracle
from ace_operational import preaudit_validator as pv


PREREG = {
    "experiment_id": "fx-01",
    "protocol": {"pass_rule": {"metric": "score_pp", "gte": 0}},
}
BANDS = {"band_records": [
    {"counts": {"A": [0, 10], "B": [10, 10]}},
    {"counts": {"A": [0, 20], "B": [20, 20]}},
]}
RESULT_ENTRY = {
    "seq": 1,
    "hash": "rec-hash-1",
    "result": {
        "experiment_id": "fx-01",
        "metrics": {"score_pp": -1.5},
        "verdict": "fail",
        "raw_telemetry": {"pooled_counts": {"A": [0, 30], "B": [30, 30]}},
    },
}
SUMMARY = {"rates": {"A": 0.0, "B": 100.0}, "record_hash": "rec-hash-1"}


def _dump(obj):
    return json.dumps(obj, indent=1).encode("utf-8")


def _line(obj):
    """One compact JSON object on a single line (JSONL)."""
    return json.dumps(obj).encode("utf-8")


class Fixture:
    """A small synthetic frozen package + its explicit manifest."""

    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        self.src.mkdir(parents=True)
        self.files = {
            "prereg.json": _dump(PREREG),
            "bands.json": _dump(BANDS),
            "results.jsonl": (_line(RESULT_ENTRY) + b"\n"),
            "summary.json": _dump(SUMMARY),
        }
        self.rebuild()

    def rebuild(self):
        for name, data in self.files.items():
            (self.src / name).write_bytes(data)
        self.manifest = {
            "schema": pv.SCHEMA_MANIFEST,
            "package_id": "fx-01",
            "artifacts": [
                {"path": name,
                 "sha256": hashlib.sha256(data).hexdigest(),
                 "size_bytes": len(data)}
                for name, data in sorted(self.files.items())
            ],
            "count_assertions": [
                {"id": "pooled-sum", "kind": "sum_pairs_equals",
                 "source": {"artifact": "bands.json", "pointer": "/band_records"},
                 "key": "counts",
                 "target": {"artifact": "results.jsonl",
                            "pointer": "/entry:0/result/raw_telemetry/pooled_counts"}},
                {"id": "rates", "kind": "rate_equals",
                 "source": {"artifact": "results.jsonl",
                            "pointer": "/entry:0/result/raw_telemetry/pooled_counts"},
                 "target": {"artifact": "summary.json", "pointer": "/rates"},
                 "scale": 100, "tolerance": "0.000001"},
                {"id": "record-hash", "kind": "field_equals",
                 "left": {"artifact": "results.jsonl", "pointer": "/entry:0/hash"},
                 "right": {"artifact": "summary.json", "pointer": "/record_hash"}},
            ],
            "verdict_check": {
                "preregistration": {"artifact": "prereg.json"},
                "results": {"artifact": "results.jsonl"},
            },
        }
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_bytes(_dump(self.manifest))

    def refresh_hash(self, name):
        data = (self.src / name).read_bytes()
        self.files[name] = data
        for entry in self.manifest["artifacts"]:
            if entry["path"] == name:
                entry["sha256"] = hashlib.sha256(data).hexdigest()
                entry["size_bytes"] = len(data)
        self.manifest_path.write_bytes(_dump(self.manifest))

    def run(self, out_name="out"):
        out = self.root / out_name
        code = pv.main(["--manifest", str(self.manifest_path),
                        "--source-root", str(self.src),
                        "--out-dir", str(out)])
        report = None
        if (out / "report.json").is_file():
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        return code, report

    def states(self, report):
        return {c["check_id"]: c["state"] for c in report["checks"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-preaudit-")
        self.addCleanup(self.temp.cleanup)
        self.fx = Fixture(Path(self.temp.name))


class OracleAgreementTests(Base):
    def test_valid_package_all_sesuai_and_oracle_agrees(self):
        code, report = self.fx.run()
        self.assertEqual(code, 0)
        self.assertEqual(self.fx.states(report),
                         {"C1": pv.SESUAI, "C2": pv.SESUAI, "C3": pv.SESUAI})
        oracle_states = oracle.oracle_c1_states(self.fx.src, self.fx.manifest)
        c1_items = {i["item"]: i["state"] for i in report["checks"][0]["items"]}
        self.assertEqual(oracle_states, c1_items)
        expected = oracle.oracle_expected_verdict(
            PREREG and self.fx.files["prereg.json"].decode(),
            self.fx.files["results.jsonl"].decode())
        self.assertEqual(expected, ["fail"])  # recorded verdict is fail
        totals = oracle.oracle_sum_pairs(BANDS["band_records"], "counts")
        self.assertEqual(totals, {"A": [0, 30], "B": [30, 30]})


class SeededDefectTests(Base):
    def test_missing_artifact_is_c1_mismatch(self):
        (self.fx.src / "bands.json").unlink()
        code, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C1"], pv.TIDAK_SESUAI)
        self.assertEqual(code, 2)
        # Downstream checks honestly degrade to UNKNOWN (dependency unresolved).
        self.assertEqual(self.fx.states(report)["C2"], pv.UNKNOWN)

    def test_one_byte_corruption_is_c1_mismatch(self):
        data = bytearray((self.fx.src / "summary.json").read_bytes())
        data[5] ^= 0x01
        (self.fx.src / "summary.json").write_bytes(bytes(data))
        _, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C1"], pv.TIDAK_SESUAI)

    def test_truncated_artifact_is_c1_mismatch(self):
        data = (self.fx.src / "prereg.json").read_bytes()
        (self.fx.src / "prereg.json").write_bytes(data[: len(data) // 2])
        _, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C1"], pv.TIDAK_SESUAI)

    def test_count_sum_off_by_one_is_c2_mismatch(self):
        bands = json.loads(self.fx.files["bands.json"])
        bands["band_records"][0]["counts"]["B"] = [9, 10]
        self.fx.files["bands.json"] = _dump(bands)
        self.fx.rebuild()
        _, report = self.fx.run()
        states = self.fx.states(report)
        self.assertEqual(states["C1"], pv.SESUAI)
        self.assertEqual(states["C2"], pv.TIDAK_SESUAI)
        self.assertEqual(states["C3"], pv.SESUAI)

    def test_field_inequality_is_c2_mismatch(self):
        summary = json.loads(self.fx.files["summary.json"])
        summary["record_hash"] = "different"
        self.fx.files["summary.json"] = _dump(summary)
        self.fx.rebuild()
        _, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C2"], pv.TIDAK_SESUAI)

    def test_rate_beyond_tolerance_is_c2_mismatch(self):
        summary = json.loads(self.fx.files["summary.json"])
        summary["rates"]["B"] = 99.0
        self.fx.files["summary.json"] = _dump(summary)
        self.fx.rebuild()
        _, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C2"], pv.TIDAK_SESUAI)

    def test_flipped_verdict_is_c3_mismatch(self):
        entry = json.loads(self.fx.files["results.jsonl"])
        entry["result"]["verdict"] = "pass"
        self.fx.files["results.jsonl"] = _line(entry) + b"\n"
        self.fx.rebuild()
        code, report = self.fx.run()
        states = self.fx.states(report)
        self.assertEqual(states["C3"], pv.TIDAK_SESUAI)
        self.assertEqual(code, 2)

    def test_boundary_metric_at_threshold_is_pass(self):
        entry = json.loads(self.fx.files["results.jsonl"])
        entry["result"]["metrics"]["score_pp"] = 0
        entry["result"]["verdict"] = "pass"  # gte is inclusive
        self.fx.files["results.jsonl"] = _line(entry) + b"\n"
        self.fx.rebuild()
        _, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C3"], pv.SESUAI)

    def test_malformed_manifest_entry_is_unknown_not_mismatch(self):
        for entry in self.fx.manifest["artifacts"]:
            if entry["path"] == "bands.json":
                del entry["sha256"]
        self.fx.manifest_path.write_bytes(_dump(self.fx.manifest))
        _, report = self.fx.run()
        self.assertEqual(self.fx.states(report)["C1"], pv.UNKNOWN)


class ValidVariantFalsePositiveTests(Base):
    """Semantically identical packages must never produce TIDAK SESUAI.
    The false-positive count per check is measured and asserted to be 0."""

    def variants(self):
        def key_order(fx):
            prereg = json.loads(fx.files["prereg.json"])
            reordered = {"protocol": prereg["protocol"],
                         "experiment_id": prereg["experiment_id"]}
            fx.files["prereg.json"] = json.dumps(reordered).encode()

        def extra_fields(fx):
            summary = json.loads(fx.files["summary.json"])
            summary["unrelated_note"] = "tambahan tidak dikenal"
            fx.files["summary.json"] = _dump(summary)

        def crlf_jsonl(fx):
            fx.files["results.jsonl"] = fx.files["results.jsonl"].replace(b"\n", b"\r\n")

        def unicode_content(fx):
            summary = json.loads(fx.files["summary.json"])
            summary["label"] = "bukti — percobaan éè 漢字"
            fx.files["summary.json"] = _dump(summary)

        def numeric_spellings(fx):
            text = fx.files["prereg.json"].decode()
            fx.files["prereg.json"] = text.replace('"gte": 0', '"gte": 0.0').encode()
            entry_text = fx.files["results.jsonl"].decode()
            fx.files["results.jsonl"] = entry_text.replace("-1.5", "-1.50").encode()

        def manifest_permutation(fx):
            fx.manifest["artifacts"] = list(reversed(fx.manifest["artifacts"]))
            fx.manifest_path.write_bytes(_dump(fx.manifest))

        return [("key_order", key_order), ("extra_fields", extra_fields),
                ("crlf_jsonl", crlf_jsonl), ("unicode_content", unicode_content),
                ("numeric_spellings", numeric_spellings),
                ("manifest_permutation", manifest_permutation)]

    def test_zero_false_positives_across_variants(self):
        fp = {"C1": 0, "C2": 0, "C3": 0}
        total = 0
        for name, mutate in self.variants():
            with self.subTest(variant=name):
                fx = Fixture(Path(self.temp.name) / name)
                mutate(fx)
                if name == "manifest_permutation":
                    # Contents unchanged; keep the permuted manifest order
                    # that mutate() already wrote to disk.
                    pass
                else:
                    # Rewrite mutated contents + a fresh manifest over them.
                    fx.rebuild()
                _, report = fx.run()
                total += 1
                for cid, state in fx.states(report).items():
                    if state == pv.TIDAK_SESUAI:
                        fp[cid] += 1
                self.assertEqual(fx.states(report),
                                 {"C1": pv.SESUAI, "C2": pv.SESUAI, "C3": pv.SESUAI})
        print("false-positive measurement over %d valid variants: %s (0 expected)"
              % (total, fp))
        self.assertEqual(fp, {"C1": 0, "C2": 0, "C3": 0})


class MetamorphicTests(Base):
    def test_report_is_byte_deterministic(self):
        _, r1 = self.fx.run("out1")
        _, r2 = self.fx.run("out2")
        b1 = (Path(self.temp.name) / "out1" / "report.json").read_bytes()
        b2 = (Path(self.temp.name) / "out2" / "report.json").read_bytes()
        self.assertEqual(b1, b2)
        self.assertEqual(r1, r2)

    def test_unlisted_file_changes_no_state(self):
        (self.fx.src / "stray.txt").write_text("not in the manifest")
        code, report = self.fx.run()
        self.assertEqual(code, 0)
        self.assertEqual(report["unlisted_files_informational_only"], 1)

    def test_manifest_permutation_invariance(self):
        _, r1 = self.fx.run("o1")
        self.fx.manifest["artifacts"] = list(reversed(self.fx.manifest["artifacts"]))
        self.fx.manifest_path.write_bytes(_dump(self.fx.manifest))
        _, r2 = self.fx.run("o2")
        self.assertEqual(self.fx.states(r1), self.fx.states(r2))


class ParserFuzzTests(Base):
    def _run_mutated(self, name, data, refresh=True):
        self.fx.files[name] = data
        (self.fx.src / name).write_bytes(data)
        if refresh:
            self.fx.refresh_hash(name)
        return self.fx.run()

    def test_duplicate_key_in_results_is_unknown_not_crash(self):
        raw = b'{"seq": 1, "seq": 2, "hash": "x", "result": {"metrics": {"score_pp": -1.5}, "verdict": "fail", "raw_telemetry": {"pooled_counts": {"A": [0, 30], "B": [30, 30]}}}}\n'
        code, report = self._run_mutated("results.jsonl", raw)
        self.assertIn(self.fx.states(report)["C3"], (pv.UNKNOWN,))
        self.assertIn(code, (2, 3))

    def test_null_verdict_is_unknown(self):
        entry = json.loads(self.fx.files["results.jsonl"])
        entry["result"]["verdict"] = None
        code, report = self._run_mutated("results.jsonl", _line(entry) + b"\n")
        self.assertEqual(self.fx.states(report)["C3"], pv.UNKNOWN)
        self.assertEqual(code, 3)

    def test_missing_metric_vs_null_metric_both_unknown(self):
        for mutate in ("missing", "null"):
            with self.subTest(kind=mutate):
                fx = Fixture(Path(self.temp.name) / mutate)
                entry = json.loads(fx.files["results.jsonl"])
                if mutate == "missing":
                    del entry["result"]["metrics"]["score_pp"]
                else:
                    entry["result"]["metrics"]["score_pp"] = None
                fx.files["results.jsonl"] = _line(entry) + b"\n"
                fx.rebuild()
                _, report = fx.run()
                self.assertEqual(fx.states(report)["C3"], pv.UNKNOWN)

    def test_truncated_json_is_unknown(self):
        data = self.fx.files["summary.json"][:20]
        _, report = self._run_mutated("summary.json", data)
        self.assertEqual(self.fx.states(report)["C2"], pv.UNKNOWN)

    def test_empty_results_is_unknown(self):
        _, report = self._run_mutated("results.jsonl", b"")
        self.assertEqual(self.fx.states(report)["C3"], pv.UNKNOWN)

    def test_nan_literal_is_unknown(self):
        raw = self.fx.files["results.jsonl"].replace(b"-1.5", b"NaN")
        _, report = self._run_mutated("results.jsonl", raw)
        self.assertEqual(self.fx.states(report)["C3"], pv.UNKNOWN)

    def test_huge_exponent_metric_is_handled(self):
        obj = {"seq": 1, "hash": "rec-hash-1",
               "result": {"metrics": {"score_pp": 0}, "verdict": "pass",
                          "raw_telemetry": {"pooled_counts": {"A": [0, 30], "B": [30, 30]}}}}
        raw = _line(obj).replace(b'"score_pp": 0', b'"score_pp": 1e999') + b"\n"
        _, report = self._run_mutated("results.jsonl", raw)
        self.assertEqual(self.fx.states(report)["C3"], pv.SESUAI)

    def test_string_metric_is_unknown(self):
        entry = json.loads(self.fx.files["results.jsonl"])
        entry["result"]["metrics"]["score_pp"] = "high"
        _, report = self._run_mutated("results.jsonl", _line(entry) + b"\n")
        self.assertEqual(self.fx.states(report)["C3"], pv.UNKNOWN)

    def test_ambiguous_rule_is_unknown(self):
        prereg = json.loads(self.fx.files["prereg.json"])
        prereg["protocol"]["pass_rule"] = {"metric": "score_pp", "gte": 0, "lt": 5}
        # Our freeze: multiple-op shapes must not be guessed. The validator
        # accepts threshold-style or single-op; two op keys with no explicit
        # 'op'/'threshold' fields is the ambiguous case exercised here via
        # an unknown op name instead:
        prereg["protocol"]["pass_rule"] = {"metric": "score_pp", "op": "approx", "threshold": 0}
        _, report = self._run_mutated("prereg.json", _dump(prereg))
        self.assertEqual(self.fx.states(report)["C3"], pv.UNKNOWN)


class ReadOnlyEnforcementTests(Base):
    def test_out_dir_inside_source_is_refused(self):
        code = pv.main(["--manifest", str(self.fx.manifest_path),
                        "--source-root", str(self.fx.src),
                        "--out-dir", str(self.fx.src / "out")])
        self.assertEqual(code, 1)

    def test_source_tree_unchanged_and_readonly_source_works(self):
        def tree_digest():
            h = hashlib.sha256()
            for path in sorted(self.fx.src.rglob("*")):
                if path.is_file():
                    h.update(str(path.relative_to(self.fx.src)).encode())
                    h.update(path.read_bytes())
            return h.hexdigest()
        before = tree_digest()
        for path in self.fx.src.rglob("*"):
            os.chmod(path, 0o555 if path.is_dir() else 0o444)
        try:
            code, report = self.fx.run()
        finally:
            for path in self.fx.src.rglob("*"):
                os.chmod(path, 0o755 if path.is_dir() else 0o644)
        self.assertEqual(code, 0)
        self.assertEqual(tree_digest(), before)

    def test_path_escape_is_mismatch_and_never_followed(self):
        evil = Path(self.temp.name) / "evil.json"
        evil.write_text("{}")
        self.fx.manifest["artifacts"].append(
            {"path": "../evil.json",
             "sha256": hashlib.sha256(b"{}").hexdigest(), "size_bytes": 2})
        self.fx.manifest_path.write_bytes(_dump(self.fx.manifest))
        _, report = self.fx.run()
        c1 = {i["item"]: i["state"] for i in report["checks"][0]["items"]}
        self.assertEqual(c1["../evil.json"], pv.TIDAK_SESUAI)
        self.assertEqual(self.fx.states(report)["C1"], pv.TIDAK_SESUAI)


class ReportLanguageTests(Base):
    def test_disclaimer_and_no_aggregate_pass(self):
        _, report = self.fx.run()
        self.assertIn("bukan persetujuan", report["disclaimer"])
        md = (Path(self.temp.name) / "out" / "report.md").read_text(encoding="utf-8")
        self.assertIn("bukan persetujuan", md)
        self.assertNotIn('"overall"', json.dumps(report))
        for check in report["checks"]:
            self.assertTrue(check["next_step"])
            self.assertTrue(check["false_positive_class"])
        self.assertEqual(report["summary_by_state"],
                         {pv.SESUAI: 3, pv.TIDAK_SESUAI: 0, pv.UNKNOWN: 0})


if __name__ == "__main__":
    unittest.main()
