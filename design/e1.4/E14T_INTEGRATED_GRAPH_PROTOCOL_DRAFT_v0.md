# E1.4 — Issue #13 integrated branching-graph scientific protocol (DRAFT, NOT FROZEN)

**Date:** 2026-11-05  
**Status:** DRAFT_PRELOCK_ONLY. **NO SCIENTIFIC SCORE AUTHORIZED ON THIS DRAFT.**  
**Baseline:** E1.4o graph autonomous loop HOLD; E1.4r mapped GO / robustness HOLD; E1.4s bounded-qualification GO / NATURAL_HOLD. All remain unchanged.

## Primary research question

Under **one cap of four purchased target labels per world × arm**, can an adaptive graph policy (i) detect that its current grammar is falsified, (ii) create and evaluate a typed extended representation, (iii) reuse the detecting receipt to narrow the repaired version space and (iv) qualify a predecessor's reusable mapping before accepting held-out predictions, outperforming matched strong policies without wrong acceptance on stress strata?

Success is scoped to a **public development distribution** only. Neither open-ended novelty, transfer to unknown natural grammars, nor OAIE is a valid inference from this gate.

## Proposed new evaluation design (freeze REQUIRED before scoring)

- **Family:** weighted, branching forward DAGs of bounded typed nodes/edges; only graph `G`, not older symbolic task.
- **Four strata:** (A) natural generated without curated target witness, (B) reachable with a valid counterexample and branch-differentiating witness, (C) rare near an information-theoretic label limit, and (D) out-of-grammar target requiring a new typed grammar or justified abstention.
- **Minimum draft coverage:** 12 novel blocks in each stratum = 48 worlds, paired across candidate/control arms; final numbers and seeds must be locked **before** scoring or adjusted only on a separate development bank.
- **Bank provenance:** independent evaluator-side generator and held-out oracle; reject overlaps with all prior E1.4 query/probe/demonstration digests and cross-split duplicates, including equivalent graphs under edge reordering. Preserve a public bank manifest and code SHA.
- **Pre-score audit:** check all query legality, route/path/event limits, witness availability and the intended ambiguity conditions. Publish the complete `FROZEN` manifest before any `run` or looking at target outcomes.

## Arms and equal-budget accounting

- `adaptive-integrated`: diagnosis → representation-extension proposal → candidate refinement → qualified inheritance.
- `fixed-grammar`: same query cap and graph resource ceiling, no expansion.
- `exhaustive/beam`: strongest available closed search in the same grammar and CPU/fit budget, selected on development-only data.
- `no-inheritance`: adaptive repair without predecessor reuse; equal target label cap.
- `sham-inheritance`: wrong typed predecessor artifact with the same storage/label overhead.
- `mapped-only`: existing E1.4r/E1.4s composition, **negative/control**, not the desired new capability.

Each arm has a single durable SQLite ledger and target label cap **4** shared across all stages. Charge the same question only once when its receipt is reused. Label `None` is paid. Distinguish demonstrations, source training, target purchased labels, replay calls, probe/oracle evaluation calls, and hindsight diagnostic counterfactuals. Record attempted/rejected queries and node/edge/path/event counts, fits, CPU, wall clock, RSS and initial source cost. Do not count abstention as a correct prediction.

## Outcome and acceptance metrics

- `detection`: true triggers and false triggers.
- `repair`: attempted/valid expansions, repaired version nonempty, probe generalization and full recovery per world.
- `qualification`: genuine artifact reuse, correct mapped acceptance, wrong acceptance, and abstention.
- `integrated`: completed diagnosis+repair+qualification using ≤4 target labels with explicit resource totals.
- `robustness`: rare/out-of-grammar wrong accepted predictions, failures to detect, negative transfer.
- `efficiency`: labels *spent* (not only cap), event cost, graph edge/node cost, candidate fits, CPU, wall time and memory.
- `reproducibility`: deterministic score/replay agreement, independent oracle audit, durable pending/settled transition proof and terminal failure states.

**Proposed draft gate, not yet binding:** adaptive must exceed both fixed-grammar and strong no-inheritance controls in **reachable full recovery**, show no wrong accepted predictions on out-of-grammar and rare stress, and not trigger on in-grammar negatives. Natural transfer is evaluated separately and remains NATURAL_HOLD unless independently supported. Exact numeric improvement margins and uncertainty procedure require pre-score power analysis and a fully independent scoring/selection split; do not choose them post hoc.

## Security, independence and recovery

- Worker code runs without evaluator implementation, hidden targets, probe labels, sealed bank, network or secrets in a verified Bubblewrap sandbox. In-process engineering smoke tests are **not** a substitute.
- The trusted evaluator validates each proposed graph from the typed input, checks computed topology cost, durably reserves a label and commits before invoking the oracle, durably writes the label and receipt, then returns only the purchased evidence to the worker.
- If worker/oracle exits between reserve and settle, mark `UNKNOWN_PENDING`, **do not retry that call or refund the slot**, and reconcile with a trusted oracle-event record. Resume from the same arm ledger only after reconciliation. Maintain explicit `COMPLETE`, `FAILED`, `TIMEOUT`, `BLOCKED_ENV` statuses.
- Score and replay use separate fresh ledgers, and audit code separately reconstructs topology costs, oracle outputs, version-space changes, qualification decisions and held-out predictions.
- Tests must cover malformed typed graphs, shuffled edge duplicates, short alias misidentification, dead routes, exponential branching, pending crash, forged label/cost, concurrent double spend, correct abstention, out-of-grammar failures and positive/negative examples.

## Gate to move from DRAFT to FROZEN

Before converting this draft to a versioned lock: (1) implement actual representation extension, (2) validate candidate/evaluator isolation, (3) finalize bank generation and novelty audit without looking at scored outcomes, (4) choose baseline and numerical decision thresholds based only on development/power work, (5) run full repository regression, (6) write SHA-256 manifest and independent frozen readback. Only then run a **new** scientific evaluation.

**Do not** overwrite E1.4n/o/p/q/r/s locked source, issue new OAIE claims, use paid services, access sealed E1.3 confirmation, or merge `main`.
