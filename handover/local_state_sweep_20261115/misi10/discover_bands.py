"""Misi 10 — re-baseline discovery untuk band konfirmasi baru (main 7541782).

Menjalankan discovery (bukan larian tersegel, bukan sel, bukan vonis) untuk
tiga band baru 20261801-20261803 di bawah kode main 7541782, mengikuti pola
probe R5 (probe_discovery.py): build_universe(seed) -> split_universe ->
run_discovery(pool, evaluation, control, pair_pool, chain_pool=pair_pool,
adapter=GRID_ADAPTER) -> catalog_digest(keys, chains).

Rumah eksekusi: VM Ian (Muse VM). Alasan: discovery butuh kode main BARU
(bukan populasi kustodi); worktree segar sudah di VM; pintu SSH sandbox
terblokir (re-auth Tailscale pemilik tertunda sejak 14 Nov 05:22); pintu MCP
1-CPU dan butuh transfer kode ke scratch sandbox. Biaya: wall time
(~20-40 mnt/band di VM).

Checkpoint per band (atomic tmp+fsync+os.replace); lanjutan aman bila
VM restart: band yang discovery-nya sudah tersimpan dilewati.
"""
import json
import os
import sys
import time
from pathlib import Path

WT = Path("/home/hatch/workspace/ace-omega/ACE/wt-m9main")
OUT = Path("/home/hatch/workspace/misi10-args")
SEEDS = [20261801, 20261802, 20261803]

sys.path.insert(0, str(WT / "tools"))
sys.path.insert(0, str(WT / "code"))

import abc_v3_run as drv
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def discover(seed: int) -> dict:
    out_discovery = OUT / f"discovery_{seed}.json"
    out_record = OUT / f"rebaseline_{seed}.json"
    if out_discovery.exists() and out_record.exists():
        rec = json.loads(out_record.read_text())
        print(f"[m10] band {seed}: checkpoint, skip "
              f"(digest {rec['catalog_digest'][:12]}...)", flush=True)
        return rec
    t0 = time.perf_counter()
    print(f"[m10] band {seed}: build_universe...", flush=True)
    universe = build_universe(seed=seed)
    split = drv.split_universe(universe["tasks"])
    print(f"[m10] band {seed}: pool={len(split['pool'])} "
          f"evaluation={len(split['evaluation'])} "
          f"control={len(split['control'])} "
          f"pair_pool={len(split['pair_pool'])}; run_discovery...",
          flush=True)
    disc = drv.run_discovery(pool=split["pool"],
                             evaluation=split["evaluation"],
                             control=split["control"],
                             pair_pool=split["pair_pool"],
                             chain_pool=split["pair_pool"],
                             adapter=GRID_ADAPTER)
    keys, chains = drv._extract_admitted(disc)
    digest = drv.catalog_digest(keys, chains)
    dt = time.perf_counter() - t0
    _atomic_write(out_discovery, json.dumps(disc, indent=1))
    rec = {"band": seed, "seconds": round(dt, 2),
           "n_pool": len(split["pool"]),
           "n_evaluation": len(split["evaluation"]),
           "n_control": len(split["control"]),
           "n_pair_pool": len(split["pair_pool"]),
           "n_keys": len(keys), "n_chains": len(chains),
           "keys": [repr(k) for k in keys],
           "chains": [repr(c) for c in chains],
           "catalog_digest": digest,
           "code_base": "origin/main 7541782 (wt-m9main)",
           "driver": "misi10 discover_bands.py (pola probe R5)"}
    _atomic_write(out_record, json.dumps(rec, indent=1))
    print(f"[m10] band {seed}: DONE {dt:.1f}s keys={len(keys)} "
          f"chains={len(chains)} digest={digest}", flush=True)
    return rec


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = [discover(s) for s in SEEDS]
    summary = {"experiment": "misi10-rebaseline-discovery",
               "scope": "DISCOVERY ONLY — no cells, no sealed run, no verdict",
               "code_base": "origin/main 7541782",
               "bands": results}
    _atomic_write(OUT / "rebaseline_summary.json",
                  json.dumps(summary, indent=1))
    print("[m10] ALL DONE", flush=True)


if __name__ == "__main__":
    main()
