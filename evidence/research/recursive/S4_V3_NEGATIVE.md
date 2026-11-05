# S4-v3 — public synthetic alternating-regime result: REJECT

Preregistration was committed before any scoring at `ce5a9f94facfd4baa04cf3f8134f2e19cb816833`. Runner committed at `052328bb82adef9336c7bcabf7858cadb77a3d0e`. Runner Git blob `6aadc77593418e7b1dead83f0ac5311bb0585708` matches the locally executed file's git hash-object, 3,531 UTF-8 bytes. Runner SHA256 `40f3781e2e100aa286600fa98b133ea2ef07aa39d7c1b5f61081dfe37664b20f`, as declared before scoring. Local CPython run exit 0; process CPU time 0.033855302 s (machine-dependent). No GitHub Actions or independent checkout replay claimed.

Four generations, 48 tasks/generation, eight labels/task, six evaluation policies, five development successor offsets. Development: 7,680 simulated labels; future: 9,216; adversarial reversed: 9,216; **total 26,112**. Potential outcomes shared across policies for paired comparison; each policy's inference history independent. Seeds and policy definitions are fixed in precommitted protocol. All tasks are PUBLIC SYNTHETIC development, not sealed evaluation.

Future success counts (denominator 1,536 labels per policy): successor **1060**, online_change 1054, online_last 1053, online_flip 1030, fixed0 **1059**, fixed1 1034. Best control 1059; successor advantage **+1/1536 = +0.0651 percentage points**. Required +5pp = at least 77 additional successes; **FAIL**.

Adversarial reversed transition success: successor **1045**, online_change 1060, online_last 1050, online_flip 1043, fixed0 **1065**, fixed1 1024. Best control 1065; successor gap **-20/1536 = -1.3021pp**, within prespecified -5pp tolerance; this gate passes but cannot rescue future failure.

Development-selected successor offsets by generation: +2, +2, -2, -4. Development raw scores by offsets (-4,-2,0,+2,+4):
g0 (260,267,272,275,269); g1 (271,267,270,273,272); g2 (281,281,264,269,259); g3 (264,258,253,256,251). Selection applies the prespecified abs(offset) penalty.

**Scientific decision: REJECT.** The successor is a bounded scalar policy adaptation; it neither authors new code nor changes architecture. Positive future difference of one reward is far below threshold and is not a generalization claim. Existing S4-v1/v2 REJECT and E1.4/E1.4aa HOLD/NOT_ASSESSED remain unchanged. This is a single public-seed exploratory study, not independent confirmation, and uses no paid services or production actions.

Limitation: the fixed0 control nearly matches the successor on the future bank, and task types may be too weakly identifiable under eight labels. The current comparator is a rolling change-point heuristic, not an oracle or a learned Bayesian changepoint baseline. Next falsifiable hypothesis (not executed here): with a preregistered budget-matched Bayesian changepoint controller and randomized latent-arm balance across many disjoint public seed families, learned intergenerational transition priors can exceed the strongest adaptive controller by >=5pp without >5pp adversarial degradation. Otherwise reject. Do not tune on these now-public results.
