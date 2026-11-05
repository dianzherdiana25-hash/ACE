# ACE R4 v5 — gradient-direction routing (prescore public development protocol)

## Scope and preservation
Owned exclusively by `code/ace_research_metalearning/`, branch `research/chat-r4-metalearning`, extending draft PR #39. Prior v1–v4 hypotheses, sources, frozen records and outcomes remain immutable. No `main`, E1.4, team-owned directories, live agents, candidate code execution, paid evaluator, or external tasks may be modified or invoked.

## Motivation and falsifiable H5
V1–v4 did not establish positive cross-family learning-to-learn. V4 changed per-coordinate step magnitudes, not update **direction**. V5 learns an off-diagonal 3-by-3 gradient-routing operator over existing groups of 20 handcrafted features (first 4 polynomial, next 8 Fourier, last 8 bumps). The learned **conditional** route uses alignment between the current and previous purchased examples' group gradients. A distinct learned **static** route uses the same parameterization and source/validation candidate budgets but does not condition on history.

**Primary H5 (freeze before OOD scoring):** at k=4, learned conditional routing must beat the *strongest* of scratch, nearest, ordinary joint pretraining plus target SGD, Reptile, fixed untrained route and equally trained static directional route by at least **0.05 absolute full-domain balanced accuracy**. It must outperform that same strongest control in at least 3/4 independently seeded OOD banks; have target logical work no more than **1.5 times scratch**; and unqueried Brier loss no more than **0.01 worse** than the strongest control. Failing ANY condition rejects H5. Do not retune after viewing OOD outcomes.

## Families, sample purchase and reproducibility
- 32 binary inputs per task. Meta-training: threshold 18, interval 24, alternating 24 = **66 tasks** per seed. Validation: reverse threshold 10, outside interval 10, block XOR 12 = **32 tasks** per seed. All source and validation tasks come from the independently defined R4-v3 generators, with fresh v5 seeds.
- OOD-only four **new composition families**, 12 tasks each: rotating stencil, change-point parity, cyclic XOR intervals, and piecewise modulo. Fixed seeds: **1301, 1423, 1559, 1697**, 192 OOD tasks total. Truth-mask SHA256 digests enforce non-overlap of task signatures across train/validation/OOD within seed. Family names are scorer metadata; target learners never see them.
- Each target arm purchases the identical 8 positions generated deterministically from seed, task family and task ID, with no reward/label dependence. Scores at k=0/1/2/4/8; purchased observations credited as known and excluded from unqueried metrics. Do not use class-sensitive raw accuracy for the primary endpoint.
- All gradient models use the same 20-dimensional fixed feature map and same 8 supervised target updates. Conditional and static routing are both meta-optimized on source using 6 off-diagonal coefficients, 3 finite-difference rounds, 6 coordinates, 2 learning rates and 2 outer rates per arm. Training uses only source tasks; candidate selection uses validation tasks. Reptile and joint pretraining have validation-only model selection. All cumulative training-label exposure and logical feature/route operation counts are reported; end-to-end compute parity is **not** guaranteed, thus an all-in compute victory is not claimed.

## Causality and evaluative boundaries
Meta-fit must not access OOD labels. OOD outcomes are generated only by the score action **after** the code, test suite, protocol and fitted-parameter prescore JSON have been committed to GitHub with exact HEAD and readback. The prescore includes SHA256 task-bank digests, not scored OOD predictions. The scorer independently refits the source/validation weights before trusting any frozen parameters, and semantic replay checks all results. All four families must be reported, including failures and counterexamples. Author-defined OOD is **public synthetic development, not independently sealed confirmatory evaluation**. The original v4 negative result is unmodified.

## Outcome measurements
Primary full-domain balanced accuracy at k4; secondary balanced accuracy at k0/1/2/8, unqueried accuracy and Brier, sample efficiency (right-censored first k to 0.75 balanced accuracy, sentinel 9), target label counts, target logical compute, meta-training candidate objective calls, feature multiplications, validation outcomes, and per-seed/family heterogeneity. Confidence intervals may be exploratory only: tasks from each fixed seed/bank are not necessarily independent. No claims of general AGI/OAIE, natural-world transfer, or independent scientific acceptance.

## Runbook (Node.js 20+, standard library only)
```
node --test code/ace_research_metalearning/v5_test.mjs
node code/ace_research_metalearning/v5_study.mjs test
node code/ace_research_metalearning/v5_study.mjs freeze /tmp/r4_v5_prescore.json
# Commit source, tests, protocol, prescore to GitHub, verify exact blob SHA and prescore commit.
# Only after prescore is durably confirmed, then:
node code/ace_research_metalearning/v5_study.mjs score /tmp/r4_v5_prescore.json /tmp/r4_v5_results.json
node code/ace_research_metalearning/v5_study.mjs verify /tmp/r4_v5_prescore.json /tmp/r4_v5_results.json
```

Scientific gate: H5 preregistered threshold; candidate unpromoted regardless of status pending external holdout and independent review. Branch remains draft and must not merge.
