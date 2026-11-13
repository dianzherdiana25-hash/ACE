"""HOLDOUT corpus for the pre-audit validator v1.

Authored AFTER the validator and its rules were frozen:
  freeze commit 2ce468e (branch feat/preaudit-validator-v1)
  preaudit_validator.py SHA-256 at freeze:
    894bd7c94afb4ade174e94e1af56eb3b6110aeae95c49b058a2e7820d6da7646
  preaudit_oracle.py SHA-256 at freeze:
    711766943feed1ec952fcd9637f58fc40bda1d9a7578980f147b0d3172dedbc2

None of these fixtures were used while developing or tuning the validator.
Shapes deliberately differ from the development fixtures: artifacts in a
subdirectory, multiple results entries, single-pair (non-dict) count forms,
and the explicit {op, threshold} rule shape. A holdout failure is a finding
to report — not an invitation to silently re-tune (any fix re-freezes and
re-runs every layer, per the design freeze §4.6).
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


class HoldoutFixture:
    """Package in subdirectory pkg/, three results entries, rule op=lt."""

    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        (self.src / "pkg").mkdir(parents=True)
        self.prereg = {
            "experiment_id": "holdout-01",
            "protocol": {"pass_rule": {"metric": "error_rate", "op": "lt",
                                       "threshold": 0.25}},
        }
        self.entries = [
            {"seq": 1, "result": {"metrics": {"error_rate": 0.10}, "verdict": "pass",
                                  "raw_telemetry": {"tally": [3, 4]}}},
            {"seq": 2, "result": {"metrics": {"error_rate": 0.25}, "verdict": "fail",
                                  "raw_telemetry": {"tally": [1, 4]}}},
            {"seq": 3, "result": {"metrics": {"error_rate": 0.40}, "verdict": "fail",
                                  "raw_telemetry": {"tally": [2, 4]}}},
        ]
        self.parts = {"parts": [[3, 4], [1, 4], [2, 4]]}  # sums to [6, 12]
        self.totals = {"grand": [6, 12], "grand_rate": 0.5}
        self.files = {
            "pkg/prereg.json": _c(self.prereg),
            "pkg/results.jsonl": b"\n".join(_c(e) for e in self.entries) + b"\n",
            "pkg/parts.json": _c(self.parts),
            "pkg/totals.json": _c(self.totals),
        }
        self.rebuild()

    def rebuild(self):
        for name, data in self.files.items():
            (self.src / name).write_bytes(data)
        self.manifest = {
            "schema": pv.SCHEMA_MANIFEST,
            "package_id": "holdout-01",
            "artifacts": [
                {"path": name, "sha256": hashlib.sha256(d).hexdigest(),
                 "size_bytes": len(d)}
                for name, d in sorted(self.files.items())
            ],
            "count_assertions": [
                {"id": "grand-sum", "kind": "sum_pairs_equals",
                 "source": {"artifact": "pkg/parts.json", "pointer": "/parts"},
                 "target": {"artifact": "pkg/totals.json", "pointer": "/grand"}},
                {"id": "grand-rate", "kind": "rate_equals",
                 "source": {"artifact": "pkg/totals.json", "pointer": "/grand"},
                 "target": {"artifact": "pkg/totals.json", "pointer": "/grand_rate"},
                 "tolerance": "0"},
            ],
            "verdict_check": {
                "preregistration": {"artifact": "pkg/prereg.json"},
                "results": {"artifact": "pkg/results.jsonl"},
            },
        }
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_bytes(_c(self.manifest))

    def run(self):
        out = self.root / "out"
        code = pv.main(["--manifest", str(self.manifest_path),
                        "--source-root", str(self.src), "--out-dir", str(out)])
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        return code, {c["check_id"]: c["state"] for c in report["checks"]}, report


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-preaudit-holdout-")
        self.addCleanup(self.temp.cleanup)
        self.fx = HoldoutFixture(Path(self.temp.name))

    def test_holdout_valid_package_all_sesuai(self):
        code, states, _ = self.fx.run()
        self.assertEqual(code, 0)
        self.assertEqual(states, {"C1": pv.SESUAI, "C2": pv.SESUAI, "C3": pv.SESUAI})

    def test_holdout_second_entry_verdict_flip_caught(self):
        self.fx.entries[1]["result"]["verdict"] = "pass"  # 0.25 is NOT < 0.25
        self.fx.files["pkg/results.jsonl"] = \
            b"\n".join(_c(e) for e in self.fx.entries) + b"\n"
        self.fx.rebuild()
        code, states, _ = self.fx.run()
        self.assertEqual(states["C3"], pv.TIDAK_SESUAI)
        self.assertEqual(states["C2"], pv.SESUAI)
        self.assertEqual(code, 2)

    def test_holdout_abstain_entry_is_unknown(self):
        self.fx.entries[2]["result"]["verdict"] = "abstain"
        self.fx.files["pkg/results.jsonl"] = \
            b"\n".join(_c(e) for e in self.fx.entries) + b"\n"
        self.fx.rebuild()
        code, states, _ = self.fx.run()
        self.assertEqual(states["C3"], pv.UNKNOWN)
        self.assertEqual(code, 3)

    def test_holdout_sum_defect_caught_in_subdirectory_package(self):
        self.fx.files["pkg/parts.json"] = _c({"parts": [[3, 4], [1, 4], [2, 5]]})
        self.fx.rebuild()
        _, states, _ = self.fx.run()
        self.assertEqual(states["C2"], pv.TIDAK_SESUAI)
        self.assertEqual(states["C1"], pv.SESUAI)

    def test_holdout_entry_seq_pointer_form(self):
        # The entry_seq:<n> selector was in the frozen spec but unused by the
        # development fixtures; exercise it here for the first time.
        self.fx.manifest["count_assertions"].append(
            {"id": "seq2-tally", "kind": "field_equals",
             "left": {"artifact": "pkg/results.jsonl",
                      "pointer": "/entry_seq:2/result/raw_telemetry/tally"},
             "right": {"artifact": "pkg/parts.json", "pointer": "/parts/1"}})
        self.fx.manifest_path.write_bytes(_c(self.fx.manifest))
        code, states, _ = self.fx.run()
        self.assertEqual(code, 0)
        self.assertEqual(states["C2"], pv.SESUAI)


if __name__ == "__main__":
    unittest.main()
