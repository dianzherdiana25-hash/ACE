"""Demonstration of the distractor-inoculation
battery on the real witnesses (Stage 0/1/2 subject):
the band-20261501 admitted catalog WITHOUT the seed
distractor (59 keys) is the catalog under test; the
battery must inject the 'nc' key, watch both
witnesses solve clean and fail injected, and return
SUSCEPTIBLE. Output: evidence JSON.
"""
import json
import sys
import time
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "wt-inoc" / "code"))
import ctrlreg_stage1_counterfactual as s1
import importlib.util


def _atomic_write(path, text):
    """Crash-safe write: temp file in the same
    directory, fsync, then os.replace — the PR #181
    pattern generalized (2026-11-13). A host death
    mid-write leaves the old file or the new one,
    never a torn one."""
    import os as _os
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text); fh.flush(); _os.fsync(fh.fileno())
    _os.replace(tmp, path)

_spec = importlib.util.spec_from_file_location(
    "distractor_inoculation",
    BASE / "wt-inoc" / "code" / "ace_operational"
    / "distractor_inoculation.py")
_di = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_di)
load_registry = _di.load_registry
run_battery = _di.run_battery

NC = ("name_swap", (5, 2, 3, 0, 1, 4), "nc")
subject = [k for k in s1.keys if k != NC]
assert len(subject) == 59

registry = load_registry(
    BASE / "wt-inoc" / "code" / "ace_operational"
    / "distractor_registry.json")


def solve(task_id, keys):
    rec = s1.solve_instr(s1.control[task_id], keys)
    return bool(rec["solved"])


t0 = time.time()
report = run_battery(catalog_keys=subject, solve=solve,
                     registry=registry)
report["demonstration"] = {
    "subject": "abc-v3 band 20261501 admitted catalog "
               "minus the seed distractor (59 keys)",
    "wall_seconds": round(time.time() - t0, 1),
    "expected": "SUSCEPTIBLE",
}
_atomic_write(BASE / "evidence"
 / "distractor_inoculation_demo.json",
    json.dumps(report, indent=1))
print(json.dumps({"overall": report["overall"],
                  "wall": report["demonstration"]
                  ["wall_seconds"]}, indent=1))
