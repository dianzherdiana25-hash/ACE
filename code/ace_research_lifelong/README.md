# ACE R2 — Lifelong learning (public development only)

Research-only prototype. No modification of frozen E1.4, no integration into live ACE or autonomous self-improvement claim.

## Question / falsifiable gate
Can a task-ID-free nearest-context prototype cache with frozen, separately trained specialist weights retain earlier tasks while still adapting to new tasks? The proposed **selective** strategy creates an expert when observed context is >0.19 away from every prior centroid (maximum four), initializes it using 0.35× its nearest expert, and consolidates prior experts by not updating them on distinct contexts. Same 96 newly observed labels per sequential stage for every method.

Primary benchmark: four deterministic sign tasks with slopes [+, +, -, -], contexts [-.75,-.25,.25,.75], five fixed seeds, per stage 96 observed training examples, 192 separately generated test examples per task. Distinct out-of-distribution test uses context shifted +0.12. Contradictory **collapsed-context** condition erases the routing signal while keeping task labels different (negative control). At prediction, neither method nor its scorer receives task ID; a fixed-slots comparator does receive the four public context centers as a capacity/architecture-prior advantage.

Controls: first-task-only frozen policy (no continual updates), shared three-feature logistic SGD, diagonal online EWC with quadratic regularization, size-64 reservoir replay with one extra gradient step per observed training sample, and fixed four-context-slot specialist weights. The EWC and shared baselines use nonlinear x*c and x*c² interactions. All methods see the same task stream, label identities and test splits, except for random replay scheduling. Replay explicitly spends more compute. The proposed and fixed-slot methods use four specialist parameters plus centroid metadata versus three shared feature parameters; not capacity-matched, so no causal novelty claim.

## Metrics
- Retention = average final accuracy on previously learned stages 0–2 divided by average immediate post-learning accuracy on those stages (can exceed 1).
- BWT = mean(final accuracy of stages 0–2 minus immediate post-learning accuracy); positive is beneficial.
- FWT = mean(zero-shot pre-learning accuracy on tasks 1–3 minus 0.5 chance).
- Generalization = mean final accuracy on independent tests and shifted-context OOD tests.
- Cost = observed label count, explicit gradient-update operations, EWC penalty operations, buffer size, scalar count and expert count. These are logical algorithmic counts, not CPU-time estimates or real memory allocations.

**Predeclared exploratory gate:** retention >= .95, OOD >= .90, > strongest comparator final accuracy by .03, collapsed negative control <= .65; all four required. Benchmark and threshold are author-visible; independent preregistered confirmatory evaluation is NOT performed.

## Reproduce
From this directory run `node r2.js > R2_REPLAY.json` (Node.js 18+). No dependency or network access. CLI executes assertions, prints test result to stderr and full JSON to stdout. `node -e 'const {experiment,tests}=require("./r2.js"); console.log(tests(experiment))'` runs checks. Compare the deterministic results JSON with `R2_DEVELOPMENT_RESULTS.json` (the latter omits no observations).

## Limitations
The tasks are low-dimensional binary classification, deterministic and hand-authored. Context separation is a conspicuous clue, so routing may appear successful because the problem has been structured to permit it. Collapsed context is logically non-identifiable without an additional input or task ID; a model cannot simultaneously solve contradictory targets. Fixed slots get privileged context centers; replay gets 2x update budget. The five seeds are NOT independent natural task families. No confidence interval, hardware-time profiling, blind holdout custody, neural network scale-up, long-duration drift, model integration or OAIE evidence. Any postscore research must use a new precommitted test bank.
