import json, sys, time
BASE = "/workspace/r5-ian/scratch"
sys.path.insert(0, BASE + "/wt-abcv3/code")
sys.path.insert(0, BASE)
import abc_v3_run as drv
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
t0 = time.perf_counter()
universe = build_universe(seed=20261601)
split = drv.split_universe(universe["tasks"])
disc = drv.run_discovery(pool=split["pool"],
                         evaluation=split["evaluation"],
                         control=split["control"],
                         pair_pool=split["pair_pool"],
                         chain_pool=split["pair_pool"],
                         adapter=GRID_ADAPTER)
keys, chains = drv._extract_admitted(disc)
digest = drv.catalog_digest(keys, chains)
dt = time.perf_counter() - t0
print(json.dumps({"band": 20261601, "seconds": round(dt, 2),
                  "n_keys": len(keys), "n_chains": len(chains),
                  "catalog_digest": digest,
                  "expected_digest":
                  "e5c7875d5e742bc4ca317569afa6a4b7a88f9aa0ea706ee99675d0d8c2d9a09c",
                  "digest_match": digest ==
                  "e5c7875d5e742bc4ca317569afa6a4b7a88f9aa0ea706ee99675d0d8c2d9a09c"},
                 indent=1), flush=True)
