# R1 H2 protocol v0.1: blinded family expansion (unseen random DFA tasks)

Status: **pre-score registration**, independent exploratory replication within same research team; not third-party scientific sign-off. Must not change H1 or frozen E1.4.

## Question
Does the R1 data-induced state abstraction learner generalize beyond the nine researcher-chosen regular languages when tested on **24 new randomly generated deterministic automata** with 2, 3, 4, and 5 source states (six tasks/state count)?

## Fixed bank construction and budget
- Public seed `20261105`. For each nominal state count N in (2,3,4,5), take the earliest six accepted DFA samples enumerated with deterministic `random.Random(20261105 + 1000 + N*100 + attempt)`, starting attempt at 0. For each state and character `a,b`, choose its destination with `randrange(N)`; for each state choose acceptance from `randrange(2)`.
- Filter on *source graph topology* (all N states reachable from initial state 0) and on **training-set-only** acceptance fraction in [0.2, 0.8] (to avoid trivial all-positive or all-negative examples). Exclude exact duplicate 63-bit train-label signatures already selected. No holdout-based filtering. Limit 10,000 attempts per N and fail visibly if insufficient.
- Each learner and all baselines see only 63 labeled train words (all lengths 0..5). Validation is all lengths 6..7 (192 examples, reporting only). Holdout is independently seeded `heldout_regular(100 + task_index)` (256 disjoint words of lengths 8..13). No candidate machine tables enter learner.
- Same four methods, frozen predicates and merge budget as R1 H1. Controls: memorizer, suffix3, and best of 130 fixed single predicates chosen only by train error. Strong oracle best *holdout* control per task used for conservative **analysis** only, not model or parameter selection.
- Max label use = 24 * (63+192+256) = 12,264 synthetic labels (1,512 learning labels); max merges=10,000 per task. Stdlib only.

## Falsifiable H2 gate
H2 accepted only if BOTH (i) induced mean holdout accuracy exceeds per-task oracle baseline mean by >= 0.05 absolute; AND (ii) >=16/24 random task families achieve >=90% heldout accuracy.

No retroactive tuning of thresholds, source-state counts, filter or task seeds based on outcome. Report failures, overfitting, all individual task accuracies, attempted merges, selection counts. H1 success does not imply H2 success; a negative H2 is scientifically useful.

The entire suite is public synthetic development. A success would not demonstrate autonomous creation of a new universal primitive, real-world OOD robustness, or OAIE.
