# ACE R7.4 — preregistered single-candidate e-process risk gate

**Status: LOCKED BEFORE IMPLEMENTATION AND FINAL SCORING.**
This is PUBLIC SYNTHETIC DEVELOPMENT, not an independent sealed holdout. Do not use R7.1-3 scoring splits to tune this study.

## Primary question
Can a small, separately purchased diagnostic sample select *one* promising capability for fresh, anytime-valid Bernoulli certification, reducing harmful acceptance on new shifted mechanisms compared with R7.3 without the trivial always-abstain failure?

## Precommitted world bank and budgets
Seed **20261108**, new ID/RNG namespaces `r74-new-world`. Each task has six observable groups with hidden Bernoulli success p; truth criterion p >= **0.80**. Each group base p is jittered uniformly ±0.09 and clipped to [0.01,0.99]. Train 30 stable tasks, validation 12 stable tasks. **Final scoring exactly once** on 20 tasks each in stable test and four OOD families:
- stable: [0.18,0.42,0.63,0.78,0.91,0.97].
- OOD-A (swap): [0.91,0.19,0.36,0.54,0.33,0.72].
- OOD-B (reverse): [0.90,0.79,0.29,0.39,0.17,0.12].
- OOD-C (new winners in 0/1): [0.86,0.94,0.22,0.68,0.14,0.24].
- OOD-D (new winners in 2/3): [0.21,0.34,0.96,0.91,0.27,0.11].
The last two are an explicit potential counterexample to limited-group diagnostics; all families are public and author-designed, **not** real-world generalization.

Online budgets: [0,6,12,24] purchases per task; no external paid evaluator. Source prior training cost (30×6×12=2160) counted separately for comparator methods. Offline evaluator scores 64 probes per group, in a separate RNG namespace from the purchased labels; all methods evaluated on identical worlds and evaluator scoring draws. No policy can access latent task p or score probes before its decision.

## Locked decision algorithm
- Diagnostic groups fixed as [0,4,5] with **two purchased labels each** in that order, i.e. sequence [0,4,5,0,4,5]. These six labels MUST NOT count toward statistical certification. If budget <6, consume the available prefix then abstain. This policy makes at most **one** acceptance decision per task.
- Candidate group is the maximum (diagnostic successes, source-fitted prior mean for tie breaks, negative group ID). The choice is based solely on purchased diagnostic labels and fixed source training, not hidden truth.
- Purchase *fresh* sequential certification labels only for the selected group; stop at the first acceptance or cap. For each certification outcome X, multiply e-value E by p1/p0 for X=1 or (1-p1)/(1-p0) for X=0, where null boundary p0=0.8 and fixed alternative p1=0.96.
- Accept selected group at E >= **10** (alpha=0.10) and at least 3 certification labels; otherwise abstain. Other five groups always abstain. This is a single-candidate, conditional anytime-valid test of H0: p<=0.8 *under independent stationary Bernoulli certification labels*. It is **not** a guarantee that a discovered capability is safe across worlds or after mechanism drift within a task.
- When cap<6, prohibit acceptance. Do not use R7.3 post-hoc detector thresholds. An optional source prior is permitted only in diagnostic tie breaks, not the test evidence.
- Add an explicit **paired-LCB** diagnostic control that sees exactly the same chosen group and exactly the same bought labels as the e-process, but accepts via Beta(1,1) posterior mean minus 1 SD >=0.8; this isolates the stronger evidence threshold. No extra labels.
- Other controls on exactly the same worlds and label caps: R7.2 certificate, R7.3 shift-aware, matched random+LCB, and **diagnostic-only always-abstain** negative control. Privileged truth oracle is evaluation-only ceiling, never an implemented selector.

## Metrics and prespecified success/failure gate
Record correct/false accepts, abstentions, purchased labels, ECE and Brier, false acceptance rate (null for zero predictions), per-world number of certifications, utility 20 true -60 false -2 abstain - purchased labels, utility per 100 purchased labels, detection/selection histogram, and oracle ceiling.

PASS requires **all**:
1. Stable: e-process accepts >= **25%** of R7.3 true accepts, with no more false accepts than R7.3.
2. Every OOD family: e-process false accepts <= R7.3; at least one shifted family has *strictly* fewer false accepts.
3. At least two shifted families have **nonzero** correct accepted strata (avoid a trivial always-abstain solution).
4. Safety-adjusted total utility over all OOD families >= R7.3 aggregate utility and <=24 purchases per task, with every reported cost charged.
5. The matched paired-LCB comparison is reported even when e-process fails; do not cherry pick.

The main scientific question is stricter than a single pilot: **one-seed PASS still remains exploratory**, no OAIE or ACE promotion until new independent family-locked replication.

## Sequence and safeguards
1. Commit this document before coding/sampling.
2. Implement separately within `code/ace_research_uncertainty/`; tests for: e-process supermartingale under p<=p0 (analytical), diagnostic/certification split, no oracle access, hard budgets, role separation, unique splits, deterministic replay, zero-acceptance denominator and paired acquisitions.
3. Run validation-only smoke, correct *software bugs only* before final; freeze the candidate and test source, SHA-readback.
4. Score the final bank **exactly once**, record full JSON stdout SHA256, source blob SHA, Python version, costs, negative cases and rule outcomes.
5. No re-evaluation/re-tuning of the same final bank as a new scientific confirmation; keep PR #43 draft and HOLD until independent review.

No changes to `main`, E1.4 frozen artifacts, other agents, Tod, or paid evaluator.
