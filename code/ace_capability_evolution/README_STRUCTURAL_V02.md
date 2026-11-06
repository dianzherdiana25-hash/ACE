# ACE v0.2 — data-conditioned typed counter-register mutation

Coordinator-owned exploratory additive extension to [v0.1](README.md). It compares the actual pinned R1 DFA learner with a **different, researcher-authored representation class**: persistent count registers feeding unchanged S2 typed `Expr` and an equality-to-zero classifier. The controller selects counter weights by training evidence and chooses architecture based on validation gain. This is **not** the original S2 beam search nor invention of new primitive types.

The experiment trains six task worlds and a hidden semantic-shift control. It retains selected G1 counter programs at G2, does not refit them, reports the fixed counter ratio1/ratio2 comparator, and reserves all terminal labels for postselection reporting.

From an isolated exact GitHub checkout, with R1 `8952c8ac55613e61b362841f4722c66a5aa990b3` under `_lane/r1` and S2 `08da5702828285e0bd4d0f4dd8876f331ac89fe2` under `_lane/s2`:

```sh
PYTHONPATH='_lane/r1/code:_lane/s2/code:code:.' python -m unittest ace_capability_evolution.test_pilot ace_capability_evolution.test_structural -v
PYTHONPATH='_lane/r1/code:_lane/s2/code:code:.' python -m ace_capability_evolution.structural --output /tmp/ace-v02.json
PYTHONPATH='_lane/r1/code:_lane/s2/code:code:.' python -m ace_capability_evolution.verify_structural /tmp/ace-v02.json
```

References: [pre-score protocol](../../docs/ACE_CAPABILITY_STRUCTURAL_V02_PRESCORE_20261106.md), [exact raw evidence and negative results](../../docs/ACE_CAPABILITY_STRUCTURAL_V02_RESULTS_20261106.md).

**Exact-head GitHub Actions #42162466833:** 31/31 tests pass (13 v0.1 + 18 v0.2); identical double replay; raw JSON SHA256 `f68c75af8efefeb99150f6ad81364b1f460996030bfa9317697b2d7678692c48`.

Scientific `NOT_ASSESSED`, release `BLOCK_RELEASE`, no OAIE. Never promote any candidate from this prototype, and do not reuse these visible public split seeds as a fresh independent holdout after development.
