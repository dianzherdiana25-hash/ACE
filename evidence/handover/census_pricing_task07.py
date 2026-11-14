"""Task 07 — INITIAL census of unique pricing programs.

Runs curriculum_lab.generate_task("pricing", level, seed=...) AS IS
(read-only against the repo; nothing here modifies repo code),
deduplicates by curriculum_lab.normalized_form(buggy_code), and
reports the measured unique-program population per defect set and
per level, plus a discovery-saturation curve (new uniques per seed
block) so the reader can judge whether the space is exhausted.

This is an ANALYSIS script for the Antigravity bench's Task 07.
It is not the official B-3 stage census.

Usage: PYTHONPATH=<wt>/code python3 census_pricing_task07.py [seeds_per_level]
"""
import json
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-g3inst/code")

from ace_operational.curriculum_lab import (  # noqa: E402
    InvalidTaskError, generate_task, normalized_form)

SEEDS_PER_LEVEL = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
BLOCK = 500

programs = {}          # normalized_form -> record
per_level_unique = defaultdict(set)   # level -> {normalized_form}
per_level_gen = Counter()             # level -> successful generations
per_level_err = Counter()             # level -> InvalidTaskError count
curve = []             # (level, block_index, cumulative_uniques)
param_combos = set()

PARAM_RE = re.compile(
    r"if subtotal >= (\d+):\s*\n\s*t -= t \* (\d+) // 100\s*\n"
    r"\s*if member:\s*\n\s*t -= t \* (\d+) // 100\s*\n"
    r"\s*t \+= t \* (\d+) // 100")

for level in (1, 2, 3, 4):
    seen_at_block_start = len(per_level_unique[level])
    for seed in range(SEEDS_PER_LEVEL):
        try:
            task = generate_task("pricing", level, seed=seed)
        except InvalidTaskError:
            per_level_err[level] += 1
            continue
        per_level_gen[level] += 1
        form = normalized_form(task["buggy_code"])
        per_level_unique[level].add(form)
        m = PARAM_RE.search(task["reference_code"])
        if m:
            param_combos.add(tuple(int(x) for x in m.groups()))
        if form not in programs:
            programs[form] = {
                "defects": tuple(sorted(d["name"] for d in task["defects"])),
                "levels_seen": set(),
                "example_task_id": task["task_id"],
                "shown_size": len(task["shown_cases"]),
                "cases": len(task["cases"]),
            }
        programs[form]["levels_seen"].add(level)
        if (seed + 1) % BLOCK == 0:
            curve.append((level, (seed + 1) // BLOCK,
                          len(per_level_unique[level])))

by_defect_set = Counter(rec["defects"] for rec in programs.values())
singles = {k: v for k, v in by_defect_set.items() if len(k) == 1}
pairs = {k: v for k, v in by_defect_set.items() if len(k) == 2}

out = {
    "seeds_per_level": SEEDS_PER_LEVEL,
    "total_unique_programs": len(programs),
    "theoretical_ceiling": 216,
    "param_combos_seen": len(param_combos),
    "param_combos_theoretical": 36,
    "by_defect_set": {"+".join(k): v for k, v in sorted(by_defect_set.items())},
    "singles_total": sum(singles.values()),
    "pairs_total": sum(pairs.values()),
    "per_level": {
        str(lvl): {
            "generated_ok": per_level_gen[lvl],
            "invalid": per_level_err[lvl],
            "unique_programs_seen_at_level": len(per_level_unique[lvl]),
        } for lvl in (1, 2, 3, 4)},
    "programs_seen_at_multiple_levels": sum(
        1 for rec in programs.values() if len(rec["levels_seen"]) > 1),
    "saturation_curve": [
        {"level": l, "after_seeds": b * BLOCK, "cumulative_uniques": c}
        for (l, b, c) in curve],
}
print(json.dumps(out, indent=1, ensure_ascii=False))
