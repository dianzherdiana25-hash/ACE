# S4-v4 — inherited Beta transition prior: REJECT (PUBLIC SYNTHETIC)

Preregistered protocol commit **590b46cf388b6f7f76e54995645ed9527f7be4b7**; runner committed before evaluation at **cf502821b955e69c726a02c8c687199192cf4977**. Local CPython execution of a semantically equivalent runner succeeded, exit 0; source was retrieved from GitHub after commit, but exact-byte independent clean-checkout execution has NOT been established. Local source SHA256 44edeeb0762654f6f9147d52517e97bb415ac83a85e0de21c1aabfe7d276a048. Local process CPU time **0.012965664 s** (environment dependent). No GitHub Actions verified.

Four generations, 48 tasks/generation, 8 labels/task, six policies. 9,216 development + 9,216 future + 9,216 reversed adversarial = **27,648 simulated label presentations**. Disjoint deterministic seeds; common random potential outcomes across policies. No paid oracle or sealed holdout. Successor prior (Beta same, flip) genuinely persists between generations: [1,1] -> [18,31] -> [42,54] -> [65,78] -> [86,104]. Reset comparator uses only current generation's inferred development transitions.

| Policy | Future / 1536 | Reversed adversarial / 1536 |
|---|---:|---:|
| Successor inherited | 1063 | 1016 |
| Reset per-generation | 1065 | 1022 |
| Online-last | 1065 | 1020 |
| Online-flip | 1063 | 1016 |
| Fixed0 | **1078** | 1012 |
| Fixed1 | 1058 | 1020 |

Future difference vs best control: **-15/1536 = -0.9766 percentage points**, fails prespecified +77-success gate. Negative difference vs best control: **-6/1536 = -0.3906 percentage points**, passes prespecified no-worse-than-76-success gate. **Scientific decision: REJECT.** Earlier S4-v1/v2/v3 negative results remain unchanged. No OAIE or self-authored-code/architecture claim.

Important limitations: successor's inherited posterior only selects a binary prior direction, with no structural mutation. Both successor and reset infer transition counts from the successor's own development trajectory, which is a shared-information control but does not evaluate a fully independent reset learning trajectory. Latent type distribution is not forced balanced; fixed0 is strongest on future split. Only one small public seed family was tested, and no confidence intervals or independent exact-head replay are available. This is an exploratory negative result, not confirmatory evidence of absence of intergenerational benefit.

Next falsifiable hypothesis (NOT executed): a hierarchical posterior conditioned on observed regime features, rather than a global Beta count, improves >=5pp over a budget-matched hierarchical Bayesian reset control on balanced, family-disjoint public synthetic sequences without >5pp adversarial loss. Precommit balanced latent-type generation and per-policy independent development observations before scoring; stop if no identifiable features separate regimes.
