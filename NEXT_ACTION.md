# NEXT_ACTION — ACE E1.4e

**Latest scientific checkpoint:** E1.4d `HOLD_CONTEXT_TRANSFER` on frozen source `32f73d7`; inherited question policy abstained in **12/12** targets (77/96 correct), local/max-Gini 79/96, minimax 79/96, 8-label reference 87/96. Full source meta-policy acquisition consumed 216 label events (not just the 96 source query-label subtotal). [Result](design/e1.4/E14D_CONTEXT_POLICY_RESULT_v1.md) | [gzip raw result](evidence/e14/e14d_public_development_v1.json.gz) | [direct workflow](docs/ACE_DIRECT_EXECUTION.md).

**E1.4e priority:** diagnose when source-trained abstention becomes a degenerate policy, using **new data and before-scoring protocol**. Specifically:
1. Audit source bucket occupancy and net utilities without using E1.4d target scores to tune hyperparameters. Separate research diagnosis from new effect estimation.
2. Predefine fresh source/meta-validation and target splits; use genuinely target-independent preallocated unlabeled query pools, both-wrong and no-disagreement controls, and an out-of-grammar challenge.
3. Compare abstaining inherited policy, context-conditioned policy, task-only max-Gini, minimax, uniform one-label, no-label, sham and a strong informed reference. Count **source initial demos + source probe labels + source query labels + target interventions + target scoring** separately. Report amortized budget and CPU.
4. Freeze code, bank and acceptance rule at a new GitHub commit **before** scoring. Run isolated candidates with official tested Bubblewrap or a verified equivalent; if unavailable, label the experiment development-only without independent custody.
5. Use bounded execution and explicit failure status; archive negative results in GitHub. Do not change the Tod repo, merge `main` or open E1.3 sealed confirmation.

The vision remains **Open-Ended Autonomous Intelligence Evolution**, not a claim already achieved.
