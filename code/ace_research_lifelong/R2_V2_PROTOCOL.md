# R2 v2 — Sequential revisit, context overlap, shift and mechanism flip

## Scope and status
This is **public development** on a small deterministic binary benchmark. It does **not** show OAIE, accepted lifelong learning, real-world generalization or independent scientific confirmation. It does not touch frozen E1.4 or other team paths. Protocol decisions and threshold values are embedded in `r2_v2.js`, and all raw run trajectories, weights/cost summaries and failures are in `R2_V2_RESULTS.json`.

## Hypothesis and experimental precommitment
**H2:** A selective novelty-gated 4-expert memory with frozen old specialists (new experts initialized at 0.25× closest expert) should improve backward retention and finite-budget adaptation compared with equal-capacity no-transfer experts, preset four-slot experts, shared polynomial SGD, diagonal EWC and reservoir replay. Treat an oracle with task ID as an upper bound, NOT a fair competitor. Accept exploratory H2 only if *all six* gates in the JSON pass: >.85 separated latest accuracy, retention decrease no worse than -.10 on unchanged tasks, overlap >=.75, shifted revisit latest >=.85, flip adaptation gain >=.20, AND >.03 margin against best equal-capacity non-oracle control on separated tasks. No post-score threshold changes permitted.

## Dataset and task stream
Four public sign classification tasks with slopes [+, -, +, -] and contexts [-.75,-.25,.25,.75], 5 PRNG seeds [7,13,29,43,61], 6 episodes [0,1,2,0,3,0] with 64 observed labeled training examples each, 128 separately generated holdout-style *public test* examples/task. Methods evaluated in deterministic same-seed order. Distinct contexts; **overlap** reduces centers to [-.24,-.08,.08,.24] and broadens jitter, making task identity ambiguous from the context; **shifted revisit** adds +.14 to task-0 context when revisited; **conflicting flip** changes task-0 sign in final episode so old/new targets cannot both remain perfect on the exact same input. Public OOD evaluation shifts context by +.10, without consulting it for training. `task` is passed in rows as a **test fixture field**; only the explicitly named oracle method uses it to predict/train, all non-oracle predictions rely solely on x/c. As source is public and used by the author, tests are not independent-blind confirmation.

## Methods and accounting
- Frozen: first 64-example episode only (no later parameter changes); all 384 labels still appear in task stream.
- Shared logistic SGD: 3 polynomial features [x,x*c,x*c^2], one online gradient step per new sample.
- EWC: same three shared weights, diagonal Fisher accumulated after every episode, quadratic penalty with lambda=2.0, Fisher-evaluation operations counted separately.
- Reservoir replay: 48 examples and at most one additional training step per observed example; 767 total gradient steps, >2× many controls' coordinate updates and additional example memory.
- Selective: nearest prototype routing; create new expert when centroid distance >.19 until budget four, initialize transferred weight 0.25× nearest; then update only routed expert. No task ID.
- No-transfer ablation: same prototype routing, cap and parameter count, but initialize new expert at zero.
- Fixed slots: four preset centroids from public context design, same parameter budget as selective.
- Oracle: four task-ID keyed experts, disallowed as a deployable comparator; establishes representational upper bound on overlap cases.

## Measurements, caveats and recovery
`final_accuracy` evaluates the latest task-0 version and unchanged 1–3 tasks, while `task0_original_final` separately shows historical compatibility for conflicting flip and shifted revisit; do not sum old and new versions when labels are contradictory. `retention_delta_unmodified` is the mean final-minus-post-first-learn accuracy for tasks 1–3, which remain unchanged by regime. `flip_adaptation_gain` / `shifted_adaptation_gain` are post-final-minus-pre-final test accuracy for changed task-0 distribution; repeated public evaluation is *diagnostic* and not used for selection. `forward_transfer_delta` compares accuracy before first training on tasks 1–3 against .5. Compute reports logical gradient updates, coordinate updates, Fisher and penalty operations, finite replay samples and persistent scalars; not hardware-time or byte-accurate heap memory.

**Known threats:** low-dimensional hand-authored signs permit easy saturation; preset centroids leak a task-design prior; overlap and flip introduce inherent nonidentifiability without extra cues; replay buys more compute/bytes; the author observes this public test and must not optimize against it to call it confirmatory. Test task IDs are present in raw records but inaccessible to non-oracle predictors by code path. The run tests use deterministic replay and structural checks, NOT an independently executed Node clean-checkout or CI job.

## Reproduce
```bash
cd code/ace_research_lifelong
node r2_v2.js > R2_V2_REPLAY.json
node -e 'const {researchV2,testV2}=require("./r2_v2.js"); console.log(testV2(researchV2))'
```
Diff the replay JSON against `R2_V2_RESULTS.json`, which has no deleted negative runs. R2 v1 remains untouched and reproducible.

## Independent matrix audit and metric interpretation
The separate `audit_v2.js` audit reads the checked-in results without rerunning any learner. It checked 160 unique (seed, regime, method) rows, 32 group means across key measures, 40 exact complement relationships for task-0 flip, label/update budgets, and the raw trajectories; all structural checks passed, as recorded in `R2_V2_AUDIT.json`. Across repeated method runs, **61,440 logical labels observed** and **62,700 gradient updates** were counted; these are not 61,440 independent unique labels, due to shared seeds and task definitions.

**Interpretation warning:** Under `conflicting_flip`, the recorded `ood_accuracy` still uses *original task-0 labels*, not the latest flipped task-0 labels; thus it measures compatibility with the historical target and must **not** be marketed as current-target OOD generalization. For changed-task performance, use `final_latest` and `flip_task0_final`. For the other regimes, the OOD conditions do not include a changed label target. The audit is an independent *aggregation and consistency check* but is not an independent model execution or confirmatory scientific assessment.
