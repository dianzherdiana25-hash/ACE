"""Self-test ladder for the Stage-3 extension (C4).

Design: docs/research/PREAUDIT_VALIDATOR_S3_EXTENSION_DESIGN.md
Fixtures are built from the real PR #184 dev-harness outputs — the
ctrlreg_stage3 cell_control records for catalog_control-020/-021 (band
20261501, DEVELOPMENT witnesses) — values copied verbatim below. Sealed
Stage-3 bands (20261601-03) and Ian's unpublished package are never touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ace_operational import preaudit_oracle as oracle
from ace_operational import preaudit_validator as pv


def _tp():
    return {"generated": False, "scored": False, "rank": None,
            "score": None, "in_frontier": False, "is_best": False}


# Verbatim from PR #184 evidence/ctrlreg_stage3_state/cell_control.json
ROUND_LOG_020 = [
    {"round": 1, "n_candidates_generated": 57, "n_scored": 57, "cap_break": False, "best_score_after": 2, "frontier_size": 1, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 2, "n_candidates_generated": 49, "n_scored": 49, "cap_break": False, "best_score_after": 2, "frontier_size": 2, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 3, "n_candidates_generated": 105, "n_scored": 105, "cap_break": False, "best_score_after": 2, "frontier_size": 1, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 4, "n_candidates_generated": 53, "n_scored": 53, "cap_break": False, "best_score_after": 2, "frontier_size": 1, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 5, "n_candidates_generated": 47, "n_scored": 47, "cap_break": False, "best_score_after": 2, "frontier_size": 2, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 6, "n_candidates_generated": 98, "n_scored": 98, "cap_break": False, "best_score_after": 2, "frontier_size": 0, "frontier_cutoff_score": 2, "true_path": _tp()},
]
ROUND_LOG_021 = [
    {"round": 1, "n_candidates_generated": 57, "n_scored": 57, "cap_break": False, "best_score_after": 2, "frontier_size": 1, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 2, "n_candidates_generated": 49, "n_scored": 49, "cap_break": False, "best_score_after": 2, "frontier_size": 1, "frontier_cutoff_score": 2, "true_path": _tp()},
    {"round": 3, "n_candidates_generated": 52, "n_scored": 52, "cap_break": False, "best_score_after": 2, "frontier_size": 0, "frontier_cutoff_score": 2, "true_path": _tp()},
]
CELL = {
    "cell": "control",
    "config": {"rounds": 6, "frontier_width": 4},
    "records": {
        "catalog_control-020": {"task_id": "catalog_control-020", "solved": False,
                                "timeout": False, "termination": "frontier_empty",
                                "score_calls": 410, "round_log": ROUND_LOG_020},
        "catalog_control-021": {"task_id": "catalog_control-021", "solved": False,
                                "timeout": False, "termination": "frontier_empty",
                                "score_calls": 159, "round_log": ROUND_LOG_021},
    },
}
MEMBER_LOG = [
    {"round": 1, "frontier_size": 1, "frontier": [{"candidate": "c1", "parents": []}]},
    {"round": 2, "frontier_size": 2, "frontier": [{"candidate": "c2", "parents": ["c1"]},
                                                  {"candidate": "c3", "parents": ["c1"]}]},
    {"round": 3, "frontier_size": 1, "frontier": [{"candidate": "c4", "parents": ["c2", "c3"]}]},
]


def _c(obj):
    return json.dumps(obj).encode("utf-8")


class S3Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        self.src.mkdir(parents=True)
        self.files = {
            "cell.json": _c(CELL),
            "members.json": _c({"log": MEMBER_LOG}),
            "counts.json": _c({"arm_B": [0, 2]}),
            "prereg.json": _c({"protocol": {"pass_rule": {"metric": "x", "gte": 0}}}),
            "results.jsonl": _c({"seq": 1, "result": {"metrics": {"x": 1}, "verdict": "pass"}}) + b"\n",
            "parts.json": _c({"parts": [[1, 2]]}),
            "totals.json": _c({"grand": [1, 2]}),
        }
        self.rebuild()

    def rebuild(self):
        for name, data in self.files.items():
            (self.src / name).write_bytes(data)
        self.manifest = {
            "schema": pv.SCHEMA_MANIFEST,
            "package_id": "s3-dev-fixture (PR #184 shapes)",
            "artifacts": [{"path": n, "sha256": hashlib.sha256(d).hexdigest(),
                           "size_bytes": len(d)}
                          for n, d in sorted(self.files.items())],
            "count_assertions": [
                {"id": "sum", "kind": "sum_pairs_equals",
                 "source": {"artifact": "parts.json", "pointer": "/parts"},
                 "target": {"artifact": "totals.json", "pointer": "/grand"}}],
            "verdict_check": {"preregistration": {"artifact": "prereg.json"},
                              "results": {"artifact": "results.jsonl"}},
            "stage3_check": {
                "task_maps": [{"artifact": "cell.json", "pointer": "/records",
                               "counts_ref": {"artifact": "counts.json", "pointer": "/arm_B"}}],
                "frontier_logs": [
                    {"artifact": "cell.json", "pointer": "/records/catalog_control-020/round_log"},
                    {"artifact": "cell.json", "pointer": "/records/catalog_control-021/round_log"},
                    {"artifact": "members.json", "pointer": "/log"}],
            },
        }
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_bytes(_c(self.manifest))

    def run(self):
        out = self.root / "out"
        code = pv.main(["--manifest", str(self.manifest_path),
                        "--source-root", str(self.src), "--out-dir", str(out)])
        report = json.loads(next(out.glob("report-*.json")).read_text())
        return code, {c["check_id"]: c for c in report["checks"]}, report

    def mutate_cell(self, fn):
        cell = json.loads(self.files["cell.json"])
        fn(cell)
        self.files["cell.json"] = _c(cell)
        self.rebuild()


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-preaudit-s3-")
        self.addCleanup(self.temp.cleanup)
        self.fx = S3Fixture(Path(self.temp.name))

    def c4_codes(self, checks):
        return [i["reason_code"] for i in checks["C4"]["items"]]


class ValidShapeTests(Base):
    def test_dev_harness_shapes_all_sesuai(self):
        code, checks, _ = self.fx.run()
        self.assertEqual(code, 0)
        for cid in ("C1", "C2", "C3", "C4"):
            self.assertEqual(checks[cid]["state"], pv.SESUAI, cid)
        # Oracle agreement on the aggregations.
        solved, total, contradictions, dups = oracle.oracle_task_map(CELL["records"])
        self.assertEqual((solved, total, contradictions, dups), (0, 2, [], []))
        self.assertIsNone(oracle.oracle_round_series(ROUND_LOG_020))
        self.assertIsNone(oracle.oracle_round_series(ROUND_LOG_021))

    def test_no_stage3_block_means_no_c4(self):
        manifest = json.loads(Path(self.fx.manifest_path).read_text())
        del manifest["stage3_check"]
        Path(self.fx.manifest_path).write_bytes(_c(manifest))
        out = Path(self.temp.name) / "out-noc4"
        code = pv.main(["--manifest", str(self.fx.manifest_path),
                        "--source-root", str(self.fx.src), "--out-dir", str(out)])
        report = json.loads(next(out.glob("report-*.json")).read_text())
        self.assertEqual([c["check_id"] for c in report["checks"]], ["C1", "C2", "C3"])
        self.assertEqual(code, 0)


class SeededDefectTests(Base):
    def test_solved_and_timeout_both_true(self):
        self.fx.mutate_cell(lambda c: c["records"]["catalog_control-020"].update(timeout=True, solved=True))
        _, checks, _ = self.fx.run()
        self.assertEqual(checks["C4"]["state"], pv.TIDAK_SESUAI)
        self.assertIn("TASK_STATE_CONTRADICTION", self.c4_codes(checks))

    def test_counts_mismatch(self):
        counts = json.loads(self.fx.files["counts.json"])
        counts["arm_B"] = [1, 2]
        self.fx.files["counts.json"] = _c(counts)
        self.fx.rebuild()
        _, checks, _ = self.fx.run()
        self.assertEqual(checks["C4"]["state"], pv.TIDAK_SESUAI)
        self.assertIn("COUNT_MISMATCH", self.c4_codes(checks))

    def test_round_sequence_gap(self):
        def mut(c):
            c["records"]["catalog_control-021"]["round_log"][2]["round"] = 4
        self.fx.mutate_cell(mut)
        _, checks, _ = self.fx.run()
        self.assertIn("ROUND_SEQUENCE_BROKEN", self.c4_codes(checks))
        self.assertEqual(oracle.oracle_round_series(
            json.loads(self.fx.files["cell.json"])["records"]["catalog_control-021"]["round_log"]), 2)

    def test_scored_exceeds_generated(self):
        def mut(c):
            c["records"]["catalog_control-020"]["round_log"][0]["n_scored"] = 999
        self.fx.mutate_cell(mut)
        _, checks, _ = self.fx.run()
        self.assertIn("COUNT_MISMATCH", self.c4_codes(checks))

    def test_true_path_contradiction(self):
        def mut(c):
            c["records"]["catalog_control-020"]["round_log"][0]["true_path"]["in_frontier"] = True
        self.fx.mutate_cell(mut)
        _, checks, _ = self.fx.run()
        self.assertIn("FIELD_MISMATCH", self.c4_codes(checks))

    def test_unresolvable_parent(self):
        members = json.loads(self.fx.files["members.json"])
        members["log"][1]["frontier"][0]["parents"] = ["ghost"]
        self.fx.files["members.json"] = _c(members)
        self.fx.rebuild()
        _, checks, _ = self.fx.run()
        self.assertIn("PROVENANCE_BROKEN", self.c4_codes(checks))

    def test_member_without_identity_is_unknown(self):
        # Single-round log isolates the defect: in the 3-round log the same
        # defect would ALSO orphan round 2's parents (a genuine second,
        # deterministic PROVENANCE_BROKEN) and the worst state would win.
        members = json.loads(self.fx.files["members.json"])
        members["log"] = [{"round": 1, "frontier_size": 1,
                           "frontier": [{"parents": []}]}]
        self.fx.files["members.json"] = _c(members)
        self.fx.rebuild()
        _, checks, _ = self.fx.run()
        self.assertEqual(checks["C4"]["state"], pv.UNKNOWN)
        self.assertIn("PROVENANCE_MISSING", self.c4_codes(checks))

    def test_frontier_size_mismatch(self):
        members = json.loads(self.fx.files["members.json"])
        members["log"][1]["frontier_size"] = 5
        self.fx.files["members.json"] = _c(members)
        self.fx.rebuild()
        _, checks, _ = self.fx.run()
        self.assertIn("COUNT_MISMATCH", self.c4_codes(checks))

    def test_duplicate_task_in_list_form(self):
        lst = [{"task_id": "t1", "solved": True, "timeout": False},
               {"task_id": "t1", "solved": False, "timeout": False}]
        self.fx.files["cell.json"] = _c({"records": lst})
        self.fx.manifest["stage3_check"]["task_maps"][0].pop("counts_ref")
        self.fx.rebuild()
        # rebuild() regenerates the manifest from scratch; re-apply the form:
        manifest = json.loads(Path(self.fx.manifest_path).read_text())
        manifest["stage3_check"]["task_maps"] = [{"artifact": "cell.json", "pointer": "/records"}]
        Path(self.fx.manifest_path).write_bytes(_c(manifest))
        out = Path(self.temp.name) / "out-dup"
        pv.main(["--manifest", str(self.fx.manifest_path),
                 "--source-root", str(self.fx.src), "--out-dir", str(out)])
        report = json.loads(next(out.glob("report-*.json")).read_text())
        codes = [i["reason_code"] for c in report["checks"] if c["check_id"] == "C4"
                 for i in c["items"]]
        self.assertIn("DUPLICATE_RECORD", codes)


class FalsePositiveProbeTests(Base):
    def test_valid_variants_stay_sesuai(self):
        variants = {}
        def extra_keys(cell):
            for rec in cell["records"].values():
                rec["wall_seconds"] = 12.5
                for r in rec["round_log"]:
                    r["extra_telemetry"] = {"note": "bebas"}
        variants["extra_keys"] = extra_keys
        def one_solved(cell):
            cell["records"]["catalog_control-020"]["solved"] = True
        variants["one_solved"] = one_solved
        fp = 0
        total = 0
        for name, mut in variants.items():
            with self.subTest(variant=name):
                fx = S3Fixture(Path(self.temp.name) / name)
                if name == "one_solved":
                    mut(json.loads(fx.files["cell.json"]))  # placeholder, replaced below
                    cell = json.loads(fx.files["cell.json"])
                    cell["records"]["catalog_control-020"]["solved"] = True
                    fx.files["cell.json"] = _c(cell)
                    counts = json.loads(fx.files["counts.json"])
                    counts["arm_B"] = [1, 2]
                    fx.files["counts.json"] = _c(counts)
                    fx.rebuild()
                else:
                    fx.mutate_cell(mut)
                _, checks, _ = fx.run()
                total += 1
                if checks["C4"]["state"] == pv.TIDAK_SESUAI:
                    fp += 1
                self.assertEqual(checks["C4"]["state"], pv.SESUAI)
        print("C4 false-positive measurement over %d valid variants: %d" % (total, fp))
        self.assertEqual(fp, 0)


if __name__ == "__main__":
    unittest.main()
