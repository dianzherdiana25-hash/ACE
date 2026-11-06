# Protocol feasibility amendment v0.3.1

Before completing or publishing a v0.3 score, the first runner halted with
`balanced sample budget exhausted`. The unchanged protocol's ratio4 validation
range 6..12 has positives only at length 10: C(10,2)=45 distinct strings, fewer
than the required 64. This is a combinatorial bank-design error.

Keep the original protocol immutable. Extend validation lengths to 6..15 for ALL
tasks and seeds; length 15 supplies C(15,3)=455 additional ratio4 positives.
Training 0..5 and terminal 16..30 stay unchanged and disjoint. All task identities,
seeds, labels, comparators, admission rules, budgets and interpretation limits
stay unchanged. No method, threshold or task is changed in response to accuracy.
The incomplete first execution produced no published result or evidence artifact.
Commit this amendment before rerunning the corrected evaluator.
