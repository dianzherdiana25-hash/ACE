"""Misi 10 + lanjutan — verifikasi ulang digest katalog band
20261801/02/03/04 dari berkas discovery yang tersimpan, memakai kode main
7541782 (wt-m9main).
Menghitung ulang via drv._extract_admitted + drv.catalog_digest dan
membandingkan dengan record rebaseline_*.json. Juga memeriksa apakah kunci
kausal registry ('name_swap', (5,2,3,0,1,4), 'nc') sudah diterima alami.
"""
import json
import sys
from pathlib import Path

WT = Path("/home/hatch/workspace/ace-omega/ACE/wt-m9main")
OUT = Path("/home/hatch/workspace/misi10-args")
sys.path.insert(0, str(WT / "tools"))
sys.path.insert(0, str(WT / "code"))

import abc_v3_run as drv

CAUSAL = ("name_swap", (5, 2, 3, 0, 1, 4), "nc")

results = {}
for seed in (20261801, 20261802, 20261803, 20261804):
    disc = json.loads((OUT / f"discovery_{seed}.json").read_text())
    rec = json.loads((OUT / f"rebaseline_{seed}.json").read_text())
    keys, chains = drv._extract_admitted(disc)
    digest = drv.catalog_digest(keys, chains)
    match = digest == rec["catalog_digest"]
    nc_keys = [k for k in keys if k[0] == "name_swap" and k[-1] == "nc"]
    results[seed] = {
        "recomputed_digest": digest,
        "record_digest": rec["catalog_digest"],
        "match": match,
        "n_keys": len(keys),
        "n_keys_record": rec["n_keys"],
        "n_chains": len(chains),
        "n_chains_record": rec["n_chains"],
        "causal_key_naturally_admitted": CAUSAL in keys,
        "nc_name_swap_keys": [repr(k) for k in nc_keys],
    }
    print(f"band {seed}: digest_match={match} keys={len(keys)}/{rec['n_keys']} "
          f"chains={len(chains)}/{rec['n_chains']} "
          f"causal_natural={CAUSAL in keys} nc_keys={len(nc_keys)}", flush=True)

(OUT / "digest_verification.json").write_text(json.dumps(results, indent=1))
print("ALL_MATCH" if all(r["match"] for r in results.values()) else "MISMATCH",
      flush=True)
