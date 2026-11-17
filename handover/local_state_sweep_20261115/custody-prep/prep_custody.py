#!/usr/bin/env python3
"""Custody preparation phase 1 (read-only): verify the sealed population
against its frozen manifest, recon the layout the harness expects."""
import hashlib
import json
import os
import sys

CUSTODY = "/workspace/ace-custody-lineage-guard"
MANIFEST = "/home/sshremote/ace-work-ian/handover/CUSTODY_POPULATION_MANIFEST_20261114.json"

m = json.load(open(MANIFEST))
problems = []
total = 0
concat = []
for f in m["files"]:
    p = os.path.join(CUSTODY, f["path"])
    if not os.path.exists(p):
        problems.append(f"MISSING {f['path']}")
        continue
    data = open(p, "rb").read()
    h = hashlib.sha256(data).hexdigest()
    total += len(data)
    if h != f["sha256"]:
        problems.append(f"SHA {f['path']}")
    if len(data) != f["bytes"]:
        problems.append(f"SIZE {f['path']}")
    concat.append(f"{f['sha256']}  {f['path']}\n")
tree = hashlib.sha256("".join(concat).encode()).hexdigest()
print("POPULATION files_ok:", len(m["files"]) - len(problems),
      "/", m["file_count"], "bytes:", total, "/", m["total_bytes"])
print("POPULATION tree_match:", tree == m["tree_digest_sha256"], tree[:16])
print("POPULATION problems:", problems if problems else "none")

print("---LAYOUT---")
for root, dirs, files in os.walk(CUSTODY):
    depth = root[len(CUSTODY):].count(os.sep)
    if depth > 2:
        dirs[:] = []
        continue
    for fn in files:
        if fn in ("abc_v3_run.py", "distractor_registry.json") or \
           fn.startswith("discovery_2026"):
            print(" ", os.path.join(root, fn)[len(CUSTODY) + 1:])
print("evidence dir exists:", os.path.isdir(os.path.join(CUSTODY, "evidence")))
reg = os.path.join(CUSTODY, "wt-battery/code/ace_operational/distractor_registry.json")
if os.path.exists(reg):
    print("REGISTRY sha256:", hashlib.sha256(open(reg, "rb").read()).hexdigest())
else:
    print("REGISTRY MISSING")
