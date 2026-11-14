"""HOLDOUT corpus for the pre-audit validator v2 contract machinery.

Authored AFTER the v2 freeze:
  freeze commit 6cccc7f (branch feat/preaudit-validator-v2)
  preaudit_validator.py SHA-256 at freeze:
    e8451ae804c23faa0ba74cde5ebfeda4badb1f6d1ecfce1b276930642187dfd1

None of these shapes were used while developing v2: a custom rule_pointer
location for the pass rule, a zero-denominator rate assertion, a relabeled
manifest (package_id only) re-run into the same out-dir, and a source root
that is a file. A holdout failure is a finding to report, not a tuning loop.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ace_operational import preaudit_validator as pv


def _c(obj):
    return json.dumps(obj).encode("utf-8")


class HoldoutV2Fixture:
    """Prereg rule lives at /spec/rule (custom pointer); verdict eq rule."""

    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        self.src.mkdir(parents=True)
        self.files = {
            "pre.json": _c({"spec": {"rule": {"metric": "n_exact", "op": "eq",
                                              "threshold": 7}}}),
            "res.jsonl": _c({"seq": 9, "result": {"metrics": {"n_exact": 7},
                                                  "verdict": "pass"}}) + b"\n",
            "tally.json": _c({"pair": [0, 0], "rate": 0}),
        }
        self.rebuild()

    def rebuild(self):
        for name, data in self.files.items():
            (self.src / name).write_bytes(data)
        self.manifest = {
            "schema": pv.SCHEMA_MANIFEST,
            "package_id": "holdout-v2-01",
            "artifacts": [
                {"path": n, "sha256": hashlib.sha256(d).hexdigest(),
                 "size_bytes": len(d)}
                for n, d in sorted(self.files.items())
            ],
            "count_assertions": [
                {"id": "zero-rate", "kind": "rate_equals",
                 "source": {"artifact": "tally.json", "pointer": "/pair"},
                 "target": {"artifact": "tally.json", "pointer": "/rate"},
                 "tolerance": "0"},
            ],
            "verdict_check": {
                "preregistration": {"artifact": "pre.json",
                                    "rule_pointer": "/spec/rule"},
                "results": {"artifact": "res.jsonl"},
            },
        }
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_bytes(_c(self.manifest))

    def run(self, out_name="out"):
        out = self.root / out_name
        code = pv.main(["--manifest", str(self.manifest_path),
                        "--source-root", str(self.src), "--out-dir", str(out)])
        reports = sorted(out.glob("report-*.json"))
        report = json.loads(reports[0].read_text()) if reports else None
        return code, report, out


def codes_of(report, check_id):
    check = [c for c in report["checks"] if c["check_id"] == check_id][0]
    return [i["reason_code"] for i in check["items"]]


class HoldoutV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-preaudit-holdout-v2-")
        self.addCleanup(self.temp.cleanup)
        self.fx = HoldoutV2Fixture(Path(self.temp.name))

    def test_custom_rule_pointer_and_zero_denominator(self):
        code, report, _ = self.fx.run()
        states = {c["check_id"]: c["state"] for c in report["checks"]}
        # Custom rule_pointer is honoured: eq 7 == 7 -> pass == recorded pass.
        self.assertEqual(states["C3"], pv.SESUAI)
        # Zero denominator: rate undefined -> UNKNOWN with the frozen code,
        # never a crash and never a guessed mismatch.
        self.assertEqual(states["C2"], pv.UNKNOWN)
        self.assertIn("RATE_UNDEFINED", codes_of(report, "C2"))
        self.assertEqual(code, 3)
        self.assertEqual(report["lifecycle"]["output_stage"], "VALIDATION VERDICT")

    def test_relabeled_manifest_same_spec_conflicts_in_same_out_dir(self):
        code1, report1, out = self.fx.run()
        self.assertEqual(code1, 3)  # RATE_UNDEFINED keeps it at UNKNOWN
        digest1 = report1["validation_spec_digest"]
        # Change ONLY the package label: closure, ruleset, build, config are
        # untouched, so the spec digest must not move — and because the
        # report bytes do move (the label is printed), a re-run into the
        # same out-dir must surface as an audited conflict, not an overwrite.
        self.fx.manifest["package_id"] = "holdout-v2-01-RENAMED"
        self.fx.manifest_path.write_bytes(_c(self.fx.manifest))
        code2, report2, _ = self.fx.run()
        self.assertEqual(code2, 4)
        self.assertTrue(list(out.glob("nondeterminism_conflict-*.json")))
        # Into a fresh out-dir the same spec runs cleanly with the same digest.
        code3, report3, _ = self.fx.run("out-fresh")
        self.assertEqual(code3, 3)
        self.assertEqual(report3["validation_spec_digest"], digest1)

    def test_source_root_is_a_file_is_process_error(self):
        out = Path(self.temp.name) / "out-file-root"
        code = pv.main(["--manifest", str(self.fx.manifest_path),
                        "--source-root", str(self.fx.src / "pre.json"),
                        "--out-dir", str(out)])
        self.assertEqual(code, 1)
        self.assertEqual(list(out.glob("report-*.json")), [])

    def test_idempotent_rerun_of_holdout_fixture(self):
        code1, _, _ = self.fx.run()
        code2, _, out = self.fx.run()
        self.assertEqual(code1, code2)
        self.assertEqual(list(out.glob("nondeterminism_conflict-*.json")), [])


if __name__ == "__main__":
    unittest.main()
