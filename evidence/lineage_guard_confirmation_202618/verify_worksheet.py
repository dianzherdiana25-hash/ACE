#!/usr/bin/env python3
"""Recompute the A.7 worksheet from the sealed cell files using the
FROZEN harness's own worksheet()/death_round_of() source (extracted
by AST, unmodified) and compare against the run's top record."""
import ast
import json
from pathlib import Path

PKG = Path.home() / "workspace/q1-evidence/sandbox"
HARNESS = Path.home() / "workspace/supp2/lineage_guard_harness.py"
REG = (Path.home() / "workspace/ace-omega/wt-battery/code/"
       "ace_operational/distractor_registry.json")

src = HARNESS.read_text()
tree = ast.parse(src)
funcs = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in (
            "worksheet", "death_round_of"):
        funcs[node.name] = ast.get_source_segment(src, node)
ns = {}
exec(funcs["death_round_of"], ns)
exec(funcs["worksheet"], ns)
worksheet = ns["worksheet"]

reg = json.loads(REG.read_text())
records = [{"id": r["id"], "key": ast.literal_eval(r["key"])}
           for r in reg["distractors"]]
cond_inf = f"infected_{records[0]['id']}"

state = PKG / "evidence/lineage_guard_state"
bands = {}
for seed in (20261803, 20261804, 20261805):
    cells = {}
    for arm in ("stock", "guarded"):
        for cond, suffix in (("clean", "clean"),
                             (cond_inf, cond_inf)):
            f = state / f"cell_{seed}_{arm}_{suffix}.json"
            cells[(arm, cond)] = json.loads(f.read_text())
    bands[seed] = cells

ws = worksheet(bands, records)
top = json.loads((PKG / "evidence/lineage_guard_run.json").read_text())
ref = top["worksheet"]

def norm(x):
    return json.dumps(x, sort_keys=True)

checks = {
    "verdict": ws["verdict"] == ref["verdict"] == top["verdict"],
    "W": norm(ws["W"]) == norm(ref["W"]),
    "R": norm(ws["R"]) == norm(ref["R"]),
    "H": norm(ws["H"]) == norm(ref["H"]),
    "cost_ratios": ws["cost_ratios"] == ref["cost_ratios"],
    "median_cost_ratio": ws["median_cost_ratio"] == ref["median_cost_ratio"],
    "death_rounds": norm(ws["death_rounds"]) == norm(ref["death_rounds"]),
    "l5_violations": ws["l5_violations"] == ref["l5_violations"],
}
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
print("WORKSHEET_REPRODUCED" if all(checks.values())
      else "WORKSHEET_MISMATCH")
