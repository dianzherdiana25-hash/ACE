"""Stage-1 simulation harness for the proposer engine.

Reads frozen episodes, the model's raw generations (one .txt file per
episode, produced in the sandbox by the adopted local brain), and -
only after generations are frozen - the separate outcomes store with
the historical baseline packages. Emits the exit-gate report.

Exit gate (locked in PREREG_LOCK BEFORE the inaugural run):
  QUALITY  : paired per-episode rubric diffs (proposer - historical);
             non-inferior iff mean diff >= -10 AND the lower bound of
             the deterministic bootstrap 95% CI of the mean diff
             (seed 20261113, 10000 resamples) >= -20.
  TIME     : the time-saving claim needs a human drafting baseline.
             No historical drafting-time baseline exists in the
             official record, so this clause is NOT_ASSESSABLE in
             Stage 1 by construction of the record, and the gate
             cannot read PASS overall. Generation walls are reported
             descriptively only.
  Verdict  : PASS only if both clauses pass; PARTIAL if quality
             passes but time is not assessable; NOT_PASSED otherwise.

No dispatch: generations are scored, never executed.
"""

import hashlib
import json
import os
import random
import re
import statistics

from .proposer_episodes import load_episodes
from .proposer_rubric import score_package
from .proposer_validator import validate_package

NONINFERIORITY_MARGIN = -10.0
CI_LOWER_FLOOR = -20.0
BOOTSTRAP_SEED = 20261113
BOOTSTRAP_RESAMPLES = 10000


def extract_package(raw_text):
    """Extract the first balanced JSON object from a raw generation."""
    start = raw_text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw_text)):
        ch = raw_text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw_text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def bootstrap_ci_lower(diffs, seed=BOOTSTRAP_SEED,
                       resamples=BOOTSTRAP_RESAMPLES, alpha=0.05):
    if not diffs:
        return None
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(resamples):
        means.append(statistics.fmean(rng.choice(diffs) for _ in range(n)))
    means.sort()
    idx = max(0, int(alpha / 2 * resamples) - 1)
    return means[idx]


def run_simulation(generations_dir, outcomes_path, walls_path=None):
    episodes = load_episodes()
    with open(outcomes_path, encoding="utf-8") as fh:
        outcomes = json.load(fh)["outcomes"]
    walls = {}
    if walls_path and os.path.exists(walls_path):
        with open(walls_path, encoding="utf-8") as fh:
            walls = json.load(fh)

    per_episode = []
    for ep in episodes:
        eid = ep["episode_id"]
        raw_path = os.path.join(generations_dir, eid + ".txt")
        raw = ""
        if os.path.exists(raw_path):
            with open(raw_path, encoding="utf-8") as fh:
                raw = fh.read()
        pkg = extract_package(raw) if raw else None
        gen_sha = hashlib.sha256(raw.encode()).hexdigest() if raw else None
        if pkg is None:
            p_score, p_break = 0.0, {"generation": "UNPARSEABLE_OR_MISSING"}
            accepted, v_reasons = False, ["no parseable package"]
        else:
            accepted, v_reasons = validate_package(pkg)
            p_score, p_break = score_package(pkg, ep)
        hist_pkg = outcomes[eid]["historical_package"]
        h_score, h_break = score_package(hist_pkg, ep)
        per_episode.append({
            "episode_id": eid,
            "generation_sha256": gen_sha,
            "generation_wall_seconds": walls.get(eid),
            "validator_accepted": accepted,
            "validator_reasons": v_reasons,
            "proposer_score": p_score,
            "proposer_breakdown": p_break,
            "historical_score": h_score,
            "historical_breakdown": h_break,
            "diff": p_score - h_score,
            "outcome_revealed_after_scoring": outcomes[eid]["outcome"],
        })

    diffs = [r["diff"] for r in per_episode]
    mean_diff = statistics.fmean(diffs) if diffs else None
    ci_lower = bootstrap_ci_lower(diffs)
    quality_pass = (mean_diff is not None and mean_diff >= NONINFERIORITY_MARGIN
                    and ci_lower is not None and ci_lower >= CI_LOWER_FLOOR)
    verdict = "PARTIAL" if quality_pass else "NOT_PASSED"
    return {
        "simulation": "proposer_stage1_v1",
        "review_type": "SIMULATION - no proposal was dispatched or executed",
        "episodes": per_episode,
        "mean_diff": mean_diff,
        "bootstrap_ci_lower_95": ci_lower,
        "noninferiority_margin": NONINFERIORITY_MARGIN,
        "ci_lower_floor": CI_LOWER_FLOOR,
        "quality_clause": "PASS" if quality_pass else "FAIL",
        "time_clause": "NOT_ASSESSABLE - no historical drafting-time "
                       "baseline exists in the official record",
        "exit_gate_verdict": verdict,
    }


def main(argv=None):
    import sys
    argv = argv or sys.argv[1:]
    gen_dir, outcomes, out_path = argv[0], argv[1], argv[2]
    walls = argv[3] if len(argv) > 3 else None
    report = run_simulation(gen_dir, outcomes, walls)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print(json.dumps({k: report[k] for k in
                      ("mean_diff", "bootstrap_ci_lower_95",
                       "quality_clause", "time_clause",
                       "exit_gate_verdict")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
