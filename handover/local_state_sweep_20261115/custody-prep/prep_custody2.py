#!/usr/bin/env python3
"""Custody preparation phase 2: install supplement #2 + band discovery
files, verify hashes, cross-check band digests with custody code."""
import hashlib
import importlib.util
import json
import os
import shutil
import sys

HOME = "/home/sshremote"
CUSTODY = "/workspace/ace-custody-lineage-guard"

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

ev = os.path.join(CUSTODY, "evidence")
for name in ("lineage_guard_harness.py", "lineage_guard_gate.py"):
    dst = os.path.join(ev, name)
    print("PREEXIST", name, sha(dst) if os.path.exists(dst) else "absent")
    shutil.copyfile(os.path.join(HOME, name), dst)
    print("INSTALLED", name, sha(dst))

state = os.path.join(CUSTODY, "abc-v3-run-state")
for seed in (20261803, 20261804, 20261805):
    src = os.path.join(HOME, f"discovery_{seed}.json")
    dst = os.path.join(state, f"discovery_{seed}.json")
    shutil.copyfile(src, dst)
    print("BAND FILE", seed, "sha_match:", sha(src) == sha(dst))

sys.path.insert(0, CUSTODY)
sys.path.insert(0, os.path.join(CUSTODY, "wt-abcv3"))
sys.path.insert(0, os.path.join(CUSTODY, "wt-abcv3", "code"))
spec = importlib.util.spec_from_file_location(
    "abc_v3_run", os.path.join(CUSTODY, "abc_v3_run.py"))
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)
EXPECTED = {
    20261803: "465508efbe082f31a3f87ccf01742cfc43fb76c97477577027a9bc0e44c35913",
    20261804: "5005072890bf608dc78a98965e6c9a3bf729a517c9689a12a9ccc051cbbaf62a",
    20261805: "465508efbe082f31a3f87ccf01742cfc43fb76c97477577027a9bc0e44c35913",
}
for seed, exp in EXPECTED.items():
    disc = json.load(open(os.path.join(state, f"discovery_{seed}.json")))
    keys, chains = drv._extract_admitted(disc)
    d = drv.catalog_digest(keys, chains)
    print("CUSTODY-CODE DIGEST", seed, d[:16], "MATCH" if d == exp else "MISMATCH " + d)
print("PHASE2 DONE")
