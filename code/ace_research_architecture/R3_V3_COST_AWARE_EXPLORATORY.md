# R3-v3 — rejection attribution & cost-aware architecture search (exploratory)

Research lane R3 only, 2026-11-06. **Not a promotion claim.** This is a branch-side summary of a Python experiment executed locally; the v3 Python source, tests and JSON are currently in the conversation artifact `ACE_R3_v3_cost_aware_research.zip`, **not committed here**. The existing R3-v2 JavaScript pilot is unchanged.

## Causal diagnostic: why proposals failed (exact R3-v2 reproduction)

The previous audit established neutral under-admission but did not attribute rejections. A same-source instrumented Python copy records every proposed graph as accepted, duplicate, candidate-ceiling, or gate-work-ceiling. For each case, the accounting identity `proposals = accepted + all rejections` holds. The instrumented v2 records, with diagnostic-only fields removed, match all **180/180 archived local v2 records** exactly.

| Development, 18 cases/arm | Proposals | Accepted | Duplicate | Work cap |
|---|---:|---:|---:|---:|
| Random | 13,500 | 2,910 | 2,324 | 8,266 |
| Greedy | 8,264 | 4,307 | 3,310 | 647 |
| Neutral | 13,500 | 3,146 | 2,977 | 7,377 |
| Neutral + coverage | 13,500 | 3,127 | 2,982 | 7,391 |

| Additional public tasks, 18 cases/arm | Proposals | Accepted | Duplicate | Work cap |
|---|---:|---:|---:|---:|
| Random | 13,500 | 2,924 | 2,280 | 8,296 |
| Greedy | 8,708 | 4,285 | 3,113 | 1,310 |
| Neutral | 13,500 | 3,141 | 2,988 | 7,371 |
| Neutral + coverage | 13,500 | 3,129 | 2,956 | 7,415 |

**Correction to the previous audit's tentative diagnosis:** the dominant source of rejected neutral proposals was unaffordable gate-work, not duplicate graphs. This does not imply a causal explanation of generalization.

## v3 method and outcomes

Two new bounded arms were added only to the local study:
- `cost_aware`: when proposed gates exceed affordable remaining gate-work, generate a bounded topology instead; same per-case gate-work ceiling.
- `cost_aware_compact`: additionally normalize commutative operand order and remove output-unreachable gates, preserving the Boolean function.

All methods use five Boolean inputs, only AND/OR/XOR, maximum five gates, 18 train / 7 validation / 7 final test patterns, 3 seeds across 6 development and 6 additional *author-visible* task functions. A maximum of 240 scored graphs, 750 proposals, and 9,000 gate operations per case. No generated executable source.

| Arm | Dev accuracy | Additional-public accuracy | Dev admitted | Additional admitted | Dev gate-work | Additional gate-work |
|---|---:|---:|---:|---:|---:|---:|
| Fixed wiring config | 78.57% | 50.79% | 486 | 486 | 31,158 | 31,158 |
| Greedy | 72.22% | 62.70% | 4,307 | 4,285 | 146,079 | 151,022 |
| Neutral + coverage | 53.97% | 63.49% | 3,127 | 3,129 | 157,475 | 157,587 |
| Cost-aware | 57.94% | 63.49% | 3,151 | 3,152 | 157,594 | 157,517 |
| Cost-aware + compact | 62.70% | 56.35% | 3,250 | 3,255 | 157,500 | 157,398 |

The new mechanisms eliminated work-cap proposal rejections in the observed cases but **did not improve generalization consistently**. Extra admitted architectures did not establish scientific superiority. Work ceilings were shared; realized work was similar between neutral variants but not exactly identical, and fixed-config is much cheaper.

## Reproduction status and limits

Local Python: **32/32 unit tests pass**, including 25 prior tests and 7 new ones. Local CLI replay: **252/252 full v3 experiment records match** stored JSON on a separate invocation (two banks x 126). Archived v2 comparator records: **180/180 exact matches** after diagnostic fields are removed. Semantic normalization verified on 450 random graphs over all 32 input patterns; identical predictions and idempotence. Holdout-label inversion preserves selected graphs and candidate pools for both new arms. These are same-source local tests, **not** independent external evaluation or exact GitHub PR-head CI.

The v3 experiment followed inspection of earlier author-visible results; there is no blinded holdout and no preregistered population claim. No ACE live self-modification, OAIE, independent sandboxed evaluator, or release gate is demonstrated.

**Decision: retain negative/mixed R3 evidence. Keep PR in draft; do not merge or deploy.** Future research should evaluate structural credit assignment on independently sourced tasks under comparable *actual gate-work*, not merely a shared ceiling.
