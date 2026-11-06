# R5 falsification IV assumptions and cost-aware abstention — public prescore protocol

Status: exploratory public synthetic development, not blinded confirmation. This protocol is committed **before** the primary 100-world/group scoring. The research author already ran small 2-world smoke evaluations and 16 initial unit tests; no claim of prescore-unseen task families.

Five deterministic disjoint seed bands, 100 worlds/group, seed 610000–610099 (valid), 620000–620099 (direct-exclusion violation), 630000–630099 (compliance selection by hidden U and heterogeneous treatment response), 640000–640099 (both invalid), and 650000–650099 (weak first stage, 8% compliance). Uniform priors per world are encoded in `invalid_iv.py`; this is **not** a sealed bank.

SCM: hidden U~N(0,1), baseline X=U+epsilon, randomized Z∈{-1,+1}, X=Z for Bernoulli complier else baseline; potential Y=(tau+h U)X+dU+lambda Z+noise. Compliance probability is logistic(logit(p0)+sU), with s=0 in valid worlds. Ground-truth population total effect of do(X=+1) versus do(X=-1) equals 2*tau, and Z=0 during direct do(X). When lambda≠0, exclusion restriction fails; when s≠0 and h≠0, IV estimates a selected complier effect rather than population ATE. A violation of exclusion alone is generally not testable from Z,X,Y without stronger assumptions; a constructive observationally equivalent pair of SCMs is covered by unit tests.

Each learned policy receives 160 training rows/world: instrument IV gets randomized encouragement Z (cannot fully force X); observational OLS gets 160 passive samples; stronger do-control gets 160 directly randomized do(X) samples. These interventions have equal row count but **not equal access**, so the direct-do arm is a privileged upper control, not a fair deployable competitor. Random and always-abstain arms have zero training calls. Bootstrap policy consumes 64 in-memory resamples but zero extra evaluator labels; compute cost is not equal among policies.

Policy choices: do(X=+1), do(X=-1), or abstain (0); action costs fixed at 0, 0.5 and 1.0, subtracted only for acting. Utility under the target do(X) distribution is action*tau-cost (or zero for abstention). The optimal policy attains max(0,abs(tau)-cost). Regret is optimal utility less chosen utility; true tau is never supplied to learners. IV `always` picks estimated sign; `point_cost` abstains if absolute estimate <= cost; `boot_cost` abstains when first-stage <=.12, any bootstrap resample weak, or empirical signed 10th-percentile <= cost. This bootstrap rule is not calibrated and no claim of frequentist coverage is made.

Primary metrics: per-world mean policy regret, rate of accepted actions, numerator/denominator conditional wrong-sign decisions (undefined if no accepted actions), point estimate squared error of ATE, and optimal-policy frequency. Paired world-level 1200-bootstrap-percentile intervals are descriptive; do not use them as external confirmatory evidence.

Precommitted falsification questions, report positive AND negative outcomes:
- F1: Valid IV point-cost regret at cost=.5 is lower than observational point-cost regret by >=0.1; if not, no actionable benefit established.
- F2: Exclusion violation increases IV point-cost ATE MSE >= 2x compared to valid IV (world-family means); this is **failure of robustness**, not a successful algorithm.
- F3: Selected-compliance heterogeneity gives IV point-cost regret > privileged direct-do point-cost regret by >=0.1 at cost=.5.
- F4: Cost-aware bootstrap gate at cost=.5 reduces mean regret vs always-acting IV in the invalid cohorts; evaluate all 3 invalid groups separately. Report missed beneficial actions and conditional wrong rate.
- F5: Stronger direct-do control's MSE is lower than IV under both-exclusion-and-selection violation.

Falsification-first: report all five cohorts and three costs, regardless of outcome. A low regret caused by high action cost and universal abstention **must not be labeled intelligent or calibrated**. If no accepted actions, accepted-case wrong rate is **undefined**, not zero. No live ACE integration, main mutation, third-party oracle, paid calls, or merge permitted. Independent design and exact-head CI remain required.
