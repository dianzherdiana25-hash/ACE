"""HOLDOUT corpus for the Stage-3 extension (C4).

Authored AFTER the extension freeze:
  freeze commit 053cd2d (branch feat/preaudit-validator-s3)
  preaudit_validator.py SHA-256 at freeze:
    c784b9ca20be79f792086b56fc57ee069fba6cca7b881c0acad5f852c0f3fc2c

Shapes not used during development: task records carrying band/arm fields
with counts_ref pointing INTO a v3-style band record's per-arm counts;
frontier members keyed by "id" (not "candidate"); a true_path block in its
POSITIVE form (generated+scored+ranked+in_frontier); timed-out tasks in the
map aggregate. A holdout failure is a finding, not a tuning loop.
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


TASKS = [
    {"task_id": "grid-001", "band": 777001, "arm": "C", "solved": True, "timeout": False},
    {"task_id": "grid-002", "band": 777001, "arm": "C", "solved": False, "timeout": True},
    {"task_id": "grid-003", "band": 777001, "arm": "C", "solved": False, "timeout": False},
]
BAND = {"seed": 777001, "counts": {"A": [0, 3], "B": [2, 3], "C": [1, 3]}}
LOG = [
    {"round": 1, "frontier_size": 1,
     "frontier": [{"id": "n1", "parents": []}],
     "true_path": {"generated": True, "scored": True, "rank": 1, "in_frontier": True}},
    {"round": 2, "frontier_size": 1,
     "frontier": [{"id": "n2", "parents": ["n1"]}],
     "true_path": {"generated": True, "scored": True, "rank": 2, "in_frontier": True}},
]


class HoldoutS3Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        self.src.mkdir(parents=True)
        self.files = {
            "tasks.json": _c({"tasks": TASKS}),
            "band.json": _c(BAND),
            "frontier.json": _c({"series": LOG}),
        }
        self.rebuild()

    def rebuild(self):
        for name, data in self.files.items():
            (self.src / name).write_bytes(data)
        self.manifest = {
            "schema": pv.SCHEMA_MANIFEST,
            "package_id": "holdout-s3-01",
            "artifacts": [{"path": n, "sha256": hashlib.sha256(d).hexdigest(),
                           "size_bytes": len(d)}
                          for n, d in sorted(self.files.items())],
            "stage3_check": {
                "task_maps": [{"artifact": "tasks.json", "pointer": "/tasks",
                               "counts_ref": {"artifact": "band.json",
                                              "pointer": "/counts/C"}}],
                "frontier_logs": [{"artifact": "frontier.json", "pointer": "/series"}],
            },
        }
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_bytes(_c(self.manifest))

    def run(self):
        out = self.root / "out"
        code = pv.main(["--manifest", str(self.manifest_path),
                        "--source-root", str(self.src), "--out-dir", str(out)])
        report = json.loads(next(out.glob("report-*.json")).read_text())
        c4 = [c for c in report["checks"] if c["check_id"] == "C4"][0]
        return code, c4


class HoldoutS3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-preaudit-holdout-s3-")
        self.addCleanup(self.temp.cleanup)
        self.fx = HoldoutS3Fixture(Path(self.temp.name))

    def test_holdout_shapes_all_sesuai(self):
        _, c4 = self.fx.run()
        self.assertEqual(c4["state"], pv.SESUAI)

    def test_holdout_timeout_task_flipped_to_solved_and_timeout(self):
        tasks = json.loads(self.fx.files["tasks.json"])
        tasks["tasks"][1]["solved"] = True  # was timeout=True -> contradiction
        self.fx.files["tasks.json"] = _c(tasks)
        self.fx.rebuild()
        _, c4 = self.fx.run()
        codes = [i["reason_code"] for i in c4["items"]]
        self.assertEqual(c4["state"], pv.TIDAK_SESUAI)
        self.assertIn("TASK_STATE_CONTRADICTION", codes)

    def test_holdout_positive_true_path_broken_by_rank_removal(self):
        log = json.loads(self.fx.files["frontier.json"])
        log["series"][0]["true_path"]["rank"] = None  # scored but unranked
        self.fx.files["frontier.json"] = _c(log)
        self.fx.rebuild()
        _, c4 = self.fx.run()
        codes = [i["reason_code"] for i in c4["items"]]
        self.assertIn("FIELD_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
