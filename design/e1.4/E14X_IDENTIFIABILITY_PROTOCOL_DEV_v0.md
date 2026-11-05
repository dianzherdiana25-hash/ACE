# E1.4x — Constructive countermodels for finite-label graph programs

**2026-11-05 | Retrospective / postscore proof protocol | NOT FROZEN | SCIENTIFIC_NOT_ASSESSED**

## Research question

Does the E1.4w `synthesis-safe` policy's acceptance after at most four purchased labels establish the *unique semantic truth* when the true graph cost operator need not belong to the researcher-supplied DSL?

## Construction

On each previously correctly accepted E1.4w development world (12 motif pairs × 12 in-grammar operator trees, with successful predecessor identification), read the complete purchased receipt journal and derive all route-cost pairs actually measured by those paid queries. The legal cost-pair domain consists of the **120** ordered integer points `(lo, hi)` with `4 <= lo <= hi <= 18`.

Choose a legal point `q*` absent from **all** of the paid query graphs, preferring the point maximizing its minimum L1 distance from paid points, with deterministic ties. If the accepted DSL computes `F(q)`, define an out-of-grammar countermodel `G(q) = F(q) + 1[q = q*]`. Verify its full finite signature is not represented by the original 5-node DSL.

For each purchased query `Q`, independently enumerate its graph paths and all matching two-route pairs. By construction, none is `q*`, so the observable answer is identical under `F` and `G`. A legal witness graph `W(q*)` explicitly separates them. Both oracles produce exactly the same entire adaptive interaction transcript for any deterministic policy that made the recorded queries; therefore the policy cannot distinguish them from its observed data. This is a constructive **worst-case semantic-identifiability lower bound**, not a claim about average-world performance.

## Proof replay (postscore)

Run the unmodified deterministic E1.4w selector and acceptance logic against `G` with the *same source task and learned motif artifact*. Require every recorded target query SHA, label, stage, cost and reuse record to match the original run, and require the same program to be accepted but now wrong. A replay failure is an explicit test failure, never silently discarded. All countermodels and separating witnesses are computed **after** observing outcomes; they must never be used to reclassify the frozen E1.4w score or tune its original hyperparameters.

## Controlled evidence

Use original 12 public development batch files `WORK/e14w-batch-00..11.json`, with their canonical SHA-256 digests. Before interpreting any countermodel proof, audit the source receipts, all target labels, resource topology, exact acceptance flags, and six probe responses per arm with the previous independent DFS implementation (`e14w_audit.py`). Source and target oracle calls are separate; any additional hindsight call is an **auditor-only** evaluation outside the four purchased target labels.

## Boundaries

This proves impossibility **only for unrestricted true operator classes** on the finite cost-pair grid and deterministic learner transcripts, assuming observations are exact. It does not show existing fitted programs are wrong within the original DSL, or that real-world natural operators are random single-point patches. Randomized policies with secret seeds require a conditional argument per realized seed and are not automatically covered by a uniform adversarial guarantee. It also does not establish full-system isolation, autonomous new-primitives discovery, successor architectures, AGI or OAIE.

## Reproduce

```bash
PYTHONPATH=code:. python3 -m e14.e14x_identifiability WORK/e14w-batch-*.json --output WORK/e14x-identifiability-main.json
PYTHONPATH=code:. python3 -m e14.e14x_replay WORK/e14w-batch-*.json --output WORK/e14x-countermodel-replay.json
PYTHONPATH=code:. python3 -m e14.e14w_audit WORK/e14w-batch-00.json --output WORK/e14x-audit-check.json
python3 tools/ace_e14x_regression.py --group x_identifiability
python3 tools/ace_e14x_regression.py --collect
```

The complete nine + three new tests and long legacy ablation tests are run in **bounded groups** to avoid host-level timeouts. No historical frozen E1.4t data, ACE `main`, Tod or sealed E1.3 data are modified.

## Postscore typed claim-interface intervention

A follow-up software change exposes the assumption required by a finite-DLS acceptance rather than silently presenting it as universal. The evaluator checks the purchased receipt journal, graph resource counters, pair artifact type and the exact set of consistent DSL candidates before issuing either `accept_conditional` (when the user explicitly assumes this bounded grammar is complete) or `abstain` (when arbitrary unseen operator forms are permitted). The changed decision does not purchase a new target label, access oracle truth or inspect held-out probes. It is an **epistemic contract**, not a procedure that discovers unknown operator forms. Run the claim-interface postscore matrix on the original 192 public worlds; report both conditional coverage and unrestricted-world abstention.
