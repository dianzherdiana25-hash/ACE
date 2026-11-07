# S1 public synthetic hypothesis discovery — exploratory negative result

Date: 2026-11-05. Status: **REJECT** against prespecified improvement threshold; **NOT_ASSESSED** for ACE scientific gates.

## Falsifiable proposal and protocol

Hypothesis: adaptive version-space splitting after composing candidate Boolean hypotheses from a bounded grammar will improve mean out-of-sample accuracy by at least **0.05 absolute** over both random and static-query policies with **no more labels**. A four-variable Boolean world has 16 points. Grammar composes 1–3 signed literals using AND/OR/XOR, deduplicated by truth table (140 unique hypotheses). The world is drawn deterministically from this constructed set; each seed shuffles 12 development query points and four disjoint evaluation points. Sixty paired worlds, four evaluator labels per world. Adaptive query selects maximum Gini split over consistent hypotheses; random selects an unqueried development point; static uses fixed seeded order. Each policy uses the same world, split, and label cap. Evaluation labels are never passed into the selection loop.

Counterexample: four-variable parity lies **outside** the 1–3-literal grammar. Run 30 separate seeded worlds for this adversarial negative control. Candidate posterior emptiness alone is not sufficient to detect misspecification.

## Local execution evidence

A local Python 3 prototype was executed once before the GitHub branch was created. Its original script SHA256 is `a022e7f0c99581d9d2fc6b532f67b5eedb8a09efe0da4dca60367367dd179f8f`; the committed module is a refactored equivalent and **has not yet been rerun at its exact GitHub SHA**. Therefore numbers below are local-prototype evidence, not exact-commit CI verification.

| Policy | 60-world test accuracy | Evaluator labels | Mean posterior size |
| --- | ---: | ---: | ---: |
| Adaptive | 0.74167 | 240 | 11.567 |
| Random | 0.72500 | 240 | 15.433 |
| Static | 0.73750 | 240 | 13.817 |

Adaptive minus best matched control = **0.00417** absolute, below the precommitted 0.05 threshold: **REJECT**. Accuracy gained per evaluator label over static: **0.00417/240 = 0.0000174** mean accuracy points per aggregate label (descriptive, not a causal estimator). Query-selection criterion shrinks posterior faster but fails to yield meaningful predictive improvement.

Adversarial four-variable parity, 30 paired worlds, 120 labels per policy: adaptive 0.30000; random 0.26667; static 0.26667. All approaches generalize poorly. This demonstrates grammar misspecification; no claim of successful novel operator discovery.

Prototype CPU process time 0.02695 s; 60 × 3 × 4 = 720 primary labels and 30 × 3 × 4 = 360 negative-control labels, total **1080 evaluator calls**, with synthetic oracle labels generated locally at no cost. Each arm evaluates four held-out labels for reporting only: 720 primary evaluation lookups and 360 negative-control evaluation lookups, distinct from training evaluator calls. No paid labels, external oracles, or hidden ACE E1.4 banks were accessed.

## Limitations and next hypothesis

Only 60 deterministic author-selected in-grammar worlds; model posterior treats all deduplicated programs equally, not a calibrated scientific prior. The random baseline is a single seeded draw rather than a Monte Carlo confidence interval. Synthetic truth functions and test points are public, so this is **development** evidence, not blinded confirmation. A separate exact-SHA clean checkout rerun and CPU log remain required.

Next falsifiable hypothesis: **grammar expansion triggered by predictive disagreement on disjoint diagnostic probes** (not merely high entropy within a misspecified grammar) reduces worst-case four-variable parity test error by at least 0.10 absolute relative to fixed-grammar active learning at equal total evaluator-label budget, without increasing false acceptances on noisy/no-function controls. Freeze new public world seeds and evaluation split before testing.

No changes to main, Tod, E1.4/E1.4aa locks, existing controllers or other agents' branches. Do not merge this exploratory branch without review.
