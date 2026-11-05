# R4 post-hoc class-balance audit (NOT preregistered)

Primary H1 in `PROTOCOL.md` remains **REJECTED** and is not revised. On the sparse family each task has just 3 positive among 24 points, so an all-negative model achieves 87.5% raw accuracy with **no learning**. The prior threshold of 80% raw accuracy is therefore a weak adaptation-speed criterion.

This audit computes *balanced accuracy* (mean TPR and TNR) and Brier across **all 24 points**, including queried points (credited as exactly known after purchase). That denominator is identical across arms; it is a different, post-hoc estimand from the original unqueried-only accuracy. Four pre-existing frozen seeds and all original OOD task signatures were reused; no trainable parameters or source-family labels changed. As a post-hoc audit, this cannot establish a newly defined scientific GO.

| Arm | Balanced accuracy k=4 | Balanced accuracy k=8 | Brier k=4 (all points) |
|---|---:|---:|---:|
| scratch | 57.80% | 68.00% | 0.2766 |
| static_transfer | 47.03% | 47.03% | 0.2405 |
| static_finetune | 57.66% | 66.65% | 0.1795 |
| simple_meta | 55.39% | 63.74% | 0.1952 |
| learned_meta | 55.44% | 63.77% | 0.1964 |
| learned_random | 57.04% | 66.69% | 0.1918 |

Full per-seed/per-family evidence and deterministic script in `posthoc_balanced_results.json` and `posthoc_balanced.mjs` respectively. Run: `node code/ace_research_metalearning/posthoc_balanced.mjs code/ace_research_metalearning/prescore.json /tmp/r4_posthoc.json`. Internal JS isolate replay two passes identical. OS-level Node execution/CI remains unverified.
