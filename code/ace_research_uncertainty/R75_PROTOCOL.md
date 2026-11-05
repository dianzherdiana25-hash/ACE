# ACE R7.5 — precommitted all-six candidate discovery with conditional e-testing

STATUS: PRE-FINAL-SCORING. Public author-visible synthetic development, not independently sealed scientific confirmation. Base R7.4 is draft PR #43. Changes only in code/ace_research_uncertainty. No edits to main, E1.4 or other teams.

## Question
Does diagnostic sampling across all six strata resolve R7.4's narrow-candidate failure on new OOD-D tasks, without increasing false capability acceptance or losing total safety-adjusted utility?

## Frozen worlds
Six observable groups per task, hidden Bernoulli reliability p, safe iff p>=.80. Uniform jitter +/-0.09, clipped [.01,.99]. Source family stable [.18,.42,.63,.78,.91,.97], OOD swap [.91,.19,.36,.54,.33,.72], reverse [.90,.79,.29,.39,.17,.12], new01 [.86,.94,.22,.68,.14,.24], new23 [.21,.34,.96,.91,.27,.11], all_null [.55,.62,.70,.73,.75,.77] clipped to <=.799, correlated uses stable bases but acquired replies copied in consecutive within-group pairs. Correlation breaks iid assumption.

Train 18 independent stable worlds (1296 offline source labels, 12 per group), validation 12 stable worlds; final: 3 seeds [20261109,20261110,20261111], 24 worlds/family/seed × 7 families = 504 worlds. New deterministic r75-* namespaces, no earlier final world IDs. Online caps [0,6,12,18,24] labels per world. 64 evaluator-only scoring probes per group in different namespace. Final scoring once AFTER protocol, code, tests and validation smoke; no test/OOD retuning. No external/paid evaluator.

## Locked policies
Full-coverage selection: buy 12 diagnostic labels sequence 0,1,2,3,4,5,0,1,2,3,4,5; if fewer than 12 labels available, only prefix and abstain. Pick ONE group with most diagnostic successes; tie by fitted source mean, then lower group index. Diagnostic labels not reused for certification. Sequentially buy fresh selected-group labels, multiply e-process by p1/.8 for success and (1-p1)/.2 for failure; accept at e>=10 after >=3 new certification labels, stop at cap; p1=.99.

Controls: R7.4-style narrow diagnostic 0,4,5,0,4,5, with p1=.96 (original) and p1=.99 (matched), and full six-group same acquisition with p1=.96 (evidence threshold ablation). Random-group choice after same 12 diagnostic labels with p1=.99 isolates selection. Always-abstain diagnostics control measures trivial false acceptance. All methods have same cap. Source prior only for ties, never test labels. Oracle upper bound is evaluation-only.

## Metrics / frozen success gate
Per family and cap: true/false accepted, abstained, purchases, conditional false acceptance rate (null when no acceptances), ECE, Brier, correct accepted per 100 labels, utility = 20 correct -60 false -2 abstain -1 online label. Track source prior labels separately; calculate per-seed breakdown and model-assumption counterexamples.

PASS requires ALL:
(1) new23 true accepts greater than narrow p1=.99;
(2) true accepts no worse on at least 3 of four shifted families (swap, reverse, new01, new23);
(3) all_null false accepts no worse than narrow p1=.99;
(4) total utility across stable+four shifted families >= narrow p1=.99;
(5) bounded cost <=24 and at most one certified group/world; no source or scoring leakage.
Correlated family is a stress test where the iid e-process guarantee does NOT apply. Even PASS is only public development, never a production scientific GO.

## Ordered verification
Commit THIS protocol before implementation/final eval; implement locally, test and validation smoke; save exact tested source in branch, Git blob readback; final score ONCE, JSON-only independent audit; report negative cases and reproducibility; maintain PR #43 DRAFT and do not merge.