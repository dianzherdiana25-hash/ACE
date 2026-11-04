# ACE E1.4d — context-conditioned query-policy transfer PRELOCK v1

**Registration:** pre-scoring, public-development only, 4 November 2026. Source commit is identified by the Git commit containing this file. It must be frozen and its Git blobs read back **before any source/target scoring**. Do not change scoring criteria, bank, or algorithm after viewing outcomes; use a separately versioned corrective experiment if a defect is found.

## Motivation and precise hypothesis

E1.4c-v1 and corrected E1.4c-v2 were both **scientific HOLD**: static inherited family-specific query policies failed strict four-stratum transfer tests. E1.4d tests a different, limited proposition: can a policy acquired from *source-only* labeled intervention outcomes select a method or **abstain** based on the target's unlabeled ambiguity context, outperforming locally selected and sham controls on previously unscored tasks?

ACE's long-term Open-Ended Autonomous Intelligence Evolution vision remains architecture-agnostic; this experiment uses fixed human-specified five-event symbol/graph hypotheses and eight fixed query heuristics, **not** autonomous architecture invention, general intelligence, or independent confirmation.

## Frozen bank and separation

- Families **S** symbolic adjacent-comparison traces and **G** labeled graph chains; five-event motifs (new length, disjoint from the older four-event motifs by definition). Inventories: S 243 hypotheses, G 48 hypotheses.
- Seeds: pair 141801, unlabeled pools 141802, demonstrations/probes 141803, policy tie-break 141804. Twelve source-target pairs total (six per family), split three one-edit related and three >=3-edit unrelated pairs per family. All 24 rule words unique within family. Source and target words differ. One source task and one target task per pair.
- Preallocate all **24 unlabeled pools** of eight inputs, using role/family/slot-only independent RNG streams **before** generating any rule-conditioned demonstration or probe. Previous E1.3/E1.4 public, E1.4c-v1 and v2 inputs are reserved. Input collisions fail. Policy/fit modules must never see the evaluator-only true word, held-out probe outputs, or unused pool labels.
- Exactly two demos per task, with weak negative-only or mixed negative/positive regimes fixed by slot parity. Eight probes per episode: **four natural random** and four deliberately diagnostic (two motif-positive, two negative). Report the two strata separately; aggregate performance is not representative of population prevalence.
- Each source enumerates eight one-label interventions and performs finite five-event hypothesis fitting, giving **96 source oracle labels total**. Before reading any target scores, learn one mapping per family and ambiguity context: `resolved`, `no_disagreement`, `high_ambiguity` (>40 candidate hypotheses), `low_ambiguity`. The first two contexts *always abstain*; the latter use the best source net utility (held-out source correct minus **one correct-probe-equivalent** for a label), with **abstention winning ties**. Missing-context fallback is abstention. This penalty is a fixed experimental convention, not a monetary value and not an equal-budget cost proof.
- Target interventions enumerate eight one-label counterfactual arms per task to compute exact random-one-label expectation (**96 additional oracle calls**). All policies consume the *same* target probe set. The target learned selector chooses action using only unlabeled context; a sham swaps learned high/low bucket mappings. Compare task-local class-informed max-Gini partition, independently computed **minimax worst partition** reference, no label, one-label uniform expectation, and an eight-target-label fit as a **higher-budget** comparator. Do not pretend 8-label target comparator is one-label parity.

## Locked end points and decision

Primary score: number correct among eight probes per target, separately S/G × related/unrelated = **four strata of three targets / 24 probes**. Also report natural and diagnostic probe accuracy separately. All policies may be tied; no ties count as a win. **Predictive development GO** requires inherited strictly above sham, local max-Gini, minimax, no-label, and exact one-label uniform expected score **in all four strata**, with no integrity failure. Otherwise `HOLD_CONTEXT_TRANSFER`. Any predictive GO must be explicitly labeled `GO_PREDICTIVE_ONLY_COST_UNPROVEN` until full acquisition-cost comparison and isolation gates pass; it is not an acceptance of transferable intelligence.

Explicit end-to-end accounting: inherited source acquisition **96 labels** plus 0/1 deployed target label each; local one-label comparator **12 labels** for 12 targets; an eight-label target fit **96 labels**. The unamortized inherited cost is at least 96 and can exceed eight-label target cost. Report source overhead per target (8 labels at this horizon), observed abstention rate, CPU timing (if instrumented), and resource limits. CPU parity is **not established** by this code; do not claim compute-efficiency. The higher-budget eight-label fit is diagnostic, not part of one-label primary GO gate.

## Safety, verification and negative controls

- Fit and policy selection are separate Python modules; evaluator calls occur in the orchestrator, and the policy module must not import the evaluator or call its oracle. **All code runs in the same process**; separate module names do not establish a security boundary. A genuine Bubblewrap/equivalent isolated worker remains an unpassed external gate. Never run untrusted candidate-generated code without tested isolation.
- Prescore tests: reproducible pool generation independent of hidden word and oracle, no reuse of public inputs, source-target and word separation, correct oracle semantics on public examples, candidate/oracle nonaccess during choose, deterministic minimax, abstain on resolved context, source-only training and frozen inventory lengths. No E1.3 sealed-confirmation access.
- Explicitly check/report no-disagreement, model-equivalence, both-wrong, and out-of-basis cases; where absent in main bank, label them as **coverage gaps**, not passed stress tests. A positive score despite same-process custody or restricted synthetic regime cannot establish causal transfer.
- Run under bounded subprocess with timeout and terminal status, keep exact raw evidence and deterministic replay, independent arithmetic audit, negative transfer and failed commands. Save to `research/e1.3-design`, never `main` or Tod. No additional spending.

## Corrections and stopping

When the predeclared scoring test fails, conclude HOLD; do **not** rerun seeds or alter conditions to seek a pass. Bugs found post-score require an explicit subsequent version with preserved pre-fix result. If environments lack official Bubblewrap or tests time out, mark the unresolved validation separately from scientific findings.
