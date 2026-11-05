# ACE R2 v6 — Fifth-task acquisition with a hard four-head memory cap

**Owner:** R2 continual/lifelong learning. **Scientific status:** `HOLD_NO_VALIDATED_LIFELONG_SKILL_ADMISSION`. Public deterministic, author-visible development only. No OAIE, real-world continual-learning, or independent confirmatory claim.

**Pre-score commitment:** `R2_V6_PRESCORE_PROTOCOL.md` committed as `6a315cbd375367b1ec3b12394ebba36daf421b50` *before* benchmark source was committed and *before* run scoring. Source `r2_v6.js` committed as `d0185080a1580d42ef4c6296690b2476648e6c14` before execution; then the exact GitHub source blob was loaded in V8 and the results recorded in `R2_V6_RESULTS.json`. No thresholds were changed after scoring. Independent output-only auditing is in `audit_v6.js` and `R2_V6_AUDIT.json`.

## Hypothesis and protocol

Unlike v5, which froze all weights and scored novelty detection, v6 actually **trains a fifth skill** after an initial four-skill supervised archive is full. Each existing task gets a separately supervised 256-label initial learning stage, yielding four 12-dimensional logistic specialist heads. The initial old task boundaries **are supplied during this supervised pretraining**. All new-task admission and evaluation retrieval is performed from labeled input/support and weights, **without task ID**. Five seeds × two known-task families (`related_pair`, `orthogonal`) × two novel-teacher modes (`unrelated`, `near`) × eight methods = **160 run records**, representing 20 paired task scenarios, **not 160 independent task sets**.

After four tasks and 1,024 training labels, a 128-label known-task-only calibration set estimates a global 90th-percentile support loss threshold from eight 16-label calibration blocks; a 16-label novel-task routing support is drawn from the 192 observed novel training labels, with all 192 used once for weight updates if admitted or reused. A fresh 16-label support and 128-label query bank per task evaluates four old skills before new learning, and all five after learning. The same samples are shared across all arm methods within a scenario; query labels are never passed to learners. The candidate is **similarity-selected weight averaging** of two old heads followed by a new zero-initialized head, retaining exactly four heads (48 weight scalars).

Fair capacity-matched controls: evict first old head, or average a random old-head pair. Additional controls: frozen four-head archive, five-head capacity expansion (+12 weight scalars), oracle novelty admission with same merge (privileged detection control), shared SGD and reservoir replay (48 examples and roughly twice as many updates). The memory compression methods are heuristics, not learned policies; they do not contain the old task ID at new-task inference.

## Fully executed public synthetic results

| Method | 4 old skills terminal | New skill | 5-skill joint | Loss of old accuracy | New-task admission |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen four-head archive | .9156 | .5273 | .8380 | .0000 | 0 |
| Evict first old head | .8611 | .9230 | .8735 | .0545 | 1 |
| Merge random pair | .8442 | .9230 | .8600 | .0714 | 1 |
| **Merge closest pair (R2 candidate)** | **.8620** | **.9230** | **.8742** | **.0536** | **1** |
| Expand to fifth head (more memory) | .9156 | .9230 | .9171 | .0000 | 1 |
| Forced oracle admission, merge closest | .8620 | .9230 | .8742 | .0536 | 1 |
| Shared SGD (single head) | .5022 | .8938 | .5805 | .1020 | N/A |
| Shared reservoir replay (48 samples) | .5538 | .7539 | .5938 | .0669 | N/A |

All table values are means across 20 paired scenarios. **Retrieval needs 16 labeled support examples per task block**. Frozen archive retains old skills but does not learn the new one; its low drop is not evidence of lifelong learning. The five-slot expansion's +4.29 percentage-point advantage over candidate reflects extra capacity, not equivalent memory cost.

Primary matched-memory contrasts: `merge_closest − evict_first` **+0.000703** joint accuracy (0.0703 percentage points), against predeclared >= +0.025; `merge_closest − merge_random` **+0.014219** (1.4219 points), against predeclared >= +0.015. **Both fail** the joint superiority criterion (which requires both comparisons).

**Cross-family negative result:** related-pair candidate joint **.91781**, orthogonal candidate joint **.83063**; gap **.08719** exceeds the allowed .05. This is a key counterexample to generic weight-space averaging as a skill-preserving merge. Within orthogonal/near tasks candidate joint .8206 vs evict .8306; the candidate is actually worse. In related-pair conditions, merging similar heads works considerably better. The archive similarity selector chose old heads [0,1] in 11 of 20 scenarios, with other pairings varying.

## Predeclared gates: 3/5 PASS, 2/5 FAIL

- Matched-capacity advantage over evict by >= .025 **and** random merge by >= .015: **FAIL**, +.000703 and +.014219 respectively.
- Old-skill terminal mean >= .72 and old mean drop <= .10: **PASS**, .8620 and .0536.
- New-skill terminal accuracy >= .78: **PASS**, .9230.
- Novel admission >= .65 in both novel-teacher modes: **PASS**, 1.000 in both modes **on this synthetic benchmark only**.
- Cross-family robustness: difference <= .05: **FAIL**, .08719.

Formal outcome: **`HOLD_NO_VALIDATED_LIFELONG_SKILL_ADMISSION`**. Do not advance a scientific claim or integrate into main. The 100% admission finding is an *easy synthetic case*, not evidence that novelty detection is solved: v5 found substantially lower new-task detection on many test-support blocks.

## Independent evidence and computational accounting

`audit_v6.js` reads the stored results without rerunning teachers or models. It verifies every unique run, exact sample budgets, training/inference stream provenance, common initial archive and calibrated novelty thresholds across expert arms, recomputes per-scenario and aggregate old/new joint scores and each gate, and calculates paired five-seed contrasts. Outcome: **PASS** across **160 method trials / 20 paired scenarios**.

Exact descriptive five-seed clustered re-sampling (NOT an independent CI):
- Closest merge minus eviction: **+.000703**, range **-.007266 to +.009219**.
- Closest merge minus random pair: **+.014219**, range **+.002969 to +.029766**.
- Closest merge minus expanded capacity: **-.042891**, range **-.049063 to -.036719**.

Logical work across all method trials: **215,020 gradient updates**; each scenario supplies 1,024 known-stage training labels and 192 observed novel-stage labels (reused across its methods). Evaluation repeats identical supports and query banks across arms. Counters record logical work, **not measured wall time or byte-accurate memory footprint**. Expert baseline weight capacity is 48 numeric scalars, except `expand5` uses 60; shared SGD is 12, replay stores 48 labeled examples and spends extra updates. Because these baselines have distinct capacities, only the evict/random comparisons are capacity- and update-matched.

**Audit limits:** independently recalculating result aggregates is not proof the candidate selected the geometrically closest pair; that property is visible in source and should be separately code-reviewed. Initial four-head training **uses supervised task boundaries**, and therefore cannot be described as fully task-free lifelong learning. The pre/post query bank is intentionally reused to measure forgetting; no update uses its labels. Tiny synthetic sample/family space, author-visible tests and no separate evaluator custody prevent independent scientific acceptance. The novel-training episode does not prove unbounded lifelong learning across many cycles of capacity reuse.

## Reproduction

From a clean checkout at the exact R2 commit:

```bash
cd code/ace_research_lifelong
node r2_v6.js > R2_V6_REPLAY.json
node audit_v6.js R2_V6_REPLAY.json
```

Compare `R2_V6_REPLAY.json` to `R2_V6_RESULTS.json`, then compare its audit output to `R2_V6_AUDIT.json`. The source has been run from GitHub blob under V8 and determinism tests passed, **but** clean-checkout Node/GitHub Actions CI remains an open gate. No merge, no main change, no frozen E1.4 edits.

## Next scientific step

An **explicitly budget-matched distillation-based merge** could preserve orthogonal skills better than blind weight averaging, but would require stored old exemplars or query/label budgets and independent training losses to justify that extra cost. Precommit exactly matched label+compute+memory budgets, and evaluate multiple *consecutive* novel tasks with capacity full after every admission. Require an independent task-family generator to check whether results transfer; do not reuse this public v6 score as confirmation.
