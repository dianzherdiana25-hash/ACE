"""Control-regression Stage 2 — dose-response over
prefix catalogs (design PR #173): solve the two
Stage 0/1 tasks under arm B with the first k admitted
keys, k in {0, 6, 12, 24, 48, 60}. The Stage 1 causal
key ('name_swap', (5, 2, 3, 0, 1, 4), 'nc') sits at
position 31 of the frozen admitted order, so the
preregistered grid brackets its entry between k=24
(absent) and k=48 (present). Records solved, score
calls, and whether A's winning code was scored.
Checkpointed per k under ctrlreg-stage2-state/.
"""
import json
import sys
import time
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE))
import ctrlreg_stage1_counterfactual as s1


def _atomic_write(path, text):
    """Crash-safe write: temp file in the same
    directory, fsync, then os.replace — the PR #181
    pattern generalized (2026-11-13). A host death
    mid-write leaves the old file or the new one,
    never a torn one."""
    import os as _os
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        _os.fsync(fh.fileno())
    _os.replace(tmp, path)


STATE = BASE / "ctrlreg-stage2-state"
STATE.mkdir(exist_ok=True)
EVIDENCE = BASE / "evidence" / "ctrlreg_stage2_dose.json"
GRID = (0, 6, 12, 24, 48, 60)
NC_POS = 31  # 1-based position of the 'nc' key in keys


def run_k(k):
    ckpt = STATE / f"k{k:02d}.json"
    if ckpt.exists():
        print(f"[stage2] k={k}: checkpoint, skip", flush=True)
        return json.loads(ckpt.read_text())
    t0 = time.time()
    recs = {t: s1.solve_instr(s1.control[t], s1.keys[:k])
            for t in s1.TASKS}
    out = {"k": k, "nc_key_present": k >= NC_POS,
           "wall_seconds": round(time.time() - t0, 1),
           "records": recs}
    _atomic_write(ckpt, json.dumps(out, indent=1))
    print(f"[stage2] k={k} (nc present={k >= NC_POS}): "
          + "; ".join(
              f"{t} solved={r['solved']} "
              f"calls={r.get('score_calls')} "
              f"a_scored={r.get('a_solution_scored')}"
              for t, r in recs.items()), flush=True)
    return out


def main():
    results = [run_k(k) for k in GRID]
    record = {
        "experiment": "ctrlreg-stage2-dose (PR #173)",
        "tasks": list(s1.TASKS),
        "nc_key_position_1based": NC_POS,
        "grid": [{"k": r["k"],
                  "nc_key_present": r["nc_key_present"],
                  "records": {t: {"solved": rec["solved"],
                                  "score_calls":
                                  rec.get("score_calls"),
                                  "a_solution_scored":
                                  rec.get("a_solution_scored")}
                              for t, rec in
                              r["records"].items()}}
                 for r in results],
    }
    _atomic_write(EVIDENCE, json.dumps(record, indent=1))
    print("[stage2] DONE — evidence written", flush=True)


if __name__ == "__main__":
    main()
