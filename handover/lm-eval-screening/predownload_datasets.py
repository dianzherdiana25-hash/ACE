#!/usr/bin/env python3
"""Pre-download the frozen screening-card datasets at pinned revisions.

Run ONLINE once; all later lm_eval runs use HF_HUB_OFFLINE=1 /
HF_DATASETS_OFFLINE=1 and consume exactly these cached revisions.
Pins verified against the HF API on 2026-11-13 by the intake lane.
"""
from datasets import load_dataset

PINS = [
    # (path, config, revision) — configs/splits are those lm_eval 0.4.13 tasks use
    ("allenai/ai2_arc", "ARC-Easy", "210d026faf9955653af8916fad021475a3f00453"),
    ("allenai/ai2_arc", "ARC-Challenge", "210d026faf9955653af8916fad021475a3f00453"),
    ("Rowan/hellaswag", None, "218ec52e09a7e7462a5400043bb9a69a41d06b76"),
    ("allenai/winogrande", "winogrande_xl", "01e74176c63542e6b0bcb004dcdea22d94fb67b5"),
]

for path, config, rev in PINS:
    ds = load_dataset(path, config, revision=rev)
    print(f"OK {path} {config} @{rev}: " + ", ".join(f"{k}={len(v)}" for k, v in ds.items()))
print("PREDOWNLOAD_DONE")
