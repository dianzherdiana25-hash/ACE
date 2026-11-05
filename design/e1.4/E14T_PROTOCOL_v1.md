# ACE E1.4t — bounded length-extension graph loop, public development protocol v1

**Status: PUBLIC ENGINEERING DEVELOPMENT; no scientific GO authorized.**
**Protocol specified before scoring the 48-world bank.** Historical E1.4o graph-loop HOLD, E1.4s grammar-bounded GO, and NATURAL_HOLD are unchanged.

## Question

Can a candidate that initially represents relative-edge motifs only at lengths 5–7 diagnose a contradiction, synthesize bounded length-8/9 hypotheses from observed positive branching-graph traces, buy at most four target labels across diagnosis/repair/qualification/inheritance, reuse a diagnosis receipt, and abstain on out-of-grammar motifs of length 10? Compare against five strategies on identical worlds and target label caps.

This is **bounded representational extension by program search**, not invention of a previously unknown primitive, open-ended intelligence, AGI, or general transfer. The worker receives only labeled demonstrations, purchased receipts, remaining budget, and an explicitly provided *synthetic aligned source prefix*; this source is **not learned**. No source-label acquisition cost was charged, so conclusions about realistic inheritance cost are precluded.

## Bank and hypotheses (freeze before score)

- Seed `2026110513`, exactly `12` deterministic, distinct, public worlds per stratum: `reachable`, `natural`, `rare`, `out-of-grammar`; `48` worlds in all.
- Each world uses a weighted branching DAG with exactly two equal-cost candidate routes in its initial positive training example. Training label is ambiguous between them. Grounded negatives remove shorter candidate motifs in reachable worlds, leave ambiguity in natural and rare worlds, and eliminate all represented lengths 5–9 for out-of-grammar length-10 truths.
- Graph validation uses at most 16 nodes, 16 edges, 16 paths and 256 enumerated path-event positions. Input graph canonicalization and actual topology/cost are evaluator-owned. Re-priced graphs prevent exact cross-world and train/probe duplication in the new bank; full historical semantic overlap audit is a separate uncompleted gate.
- **No evaluator truth or held-out probe input may be staged into a worker.** Running the scorer changes no historical sealed E1.3 or frozen E1.4n–s material.

## Arms

1. `integrated`: contradiction-triggered length extension, the synthetic predecessor prefix as search-order prior, diagnosis receipt reuse in repair and inheritance, then qualification on a distinct graph.
2. `fixed`: grammar lengths 5–7 only, no extension.
3. `exhaustive`: all lengths 5–9 searched together, with the same target label cap; this strong baseline is allowed to tie the adaptive approach.
4. `no-inheritance`: adaptive length extension without the synthetic predecessor prefix.
5. `sham`: adaptive length extension with one corrupted prior position; prior is only ordering, not evidence.

All arms share exactly four *purchasable target labels per arm*, with no additional budget per stage. Each initial example label, every held-out probe evaluation, every independent audit oracle replay, and every new query is counted separately. `None` is a purchased negative label; abstain counts as zero correct predictions and reduces coverage. Node/edge/path/event usage, worker calls and wall time are recorded. CPU/RSS isolation resource measurements are not yet complete; do not compare algorithmic efficiency as proven.

## Outcome metrics and decision rule

For each stratum and arm: exact motif recovered, accepted-probe correct/incorrect, wrong acceptance, abstentions, actual target intervention labels, initial demonstration labels, held-out probe labels, auditor calls, graph costs and worker calls. Each world has six held-out probes.

**Diagnostic gate (HOLD unless all conditions met):** integrated must exactly recover at least 10/12 reachable worlds, exceed both fixed and **the strongest of exhaustive/no-inheritance/sham by at least 3/12**, accept no incorrect probes in rare/out-of-grammar, and trigger no unsupported general-transfer claims. If a strong control ties or beats integrated, record HOLD. Natural remains separately NATURAL_HOLD regardless.

Even a diagnostic pass is not a scientific GO without: independent candidate/evaluator and oracle custody review, validated full resource isolation, unbiased source acquisition, independent benchmark design, stronger baseline power and historical overlap audit. The computed result is explicitly `scientific_decision=NOT_ASSESSED` on this same-author public bank.

## Freeze, score, replay and audit

```bash
# From checkout root, after all source and protocol edits are complete
PYTHONPATH=code:. python3 -m e14.e14t_run freeze --repo . --lock design/e1.4/E14T_LOCK_v1.json --bank evidence/e14/e14t_public_bank_v1.json.gz
# Score and replay MUST use separate fresh SQLite files
PYTHONPATH=code:. python3 -m e14.e14t_run run --repo . --lock design/e1.4/E14T_LOCK_v1.json --bank evidence/e14/e14t_public_bank_v1.json.gz --ledger WORK/e14t-score.sqlite --output WORK/e14t-score.json.gz
PYTHONPATH=code:. python3 -m e14.e14t_run run --repo . --lock design/e1.4/E14T_LOCK_v1.json --bank evidence/e14/e14t_public_bank_v1.json.gz --ledger WORK/e14t-replay.sqlite --output WORK/e14t-replay.json.gz
```

An independent-from-worker auditor replays purchased oracle labels from raw SQLite journals and checks exact topology cost, four-label cap, report arithmetic, bank lock and deterministic score/replay fields. Any mismatch, native namespace denial, worker crash or pending oracle effect is a visible FAIL/BLOCKED event, not an automatic retry.

## Threat model and limits

The experimental namespace launcher mounts a small worker-only root under Linux user/mount/network/PID namespaces, with system code and worker paths read-only, private mount tree, no evaluator checkout/home/credentials/proc, sanitized environment, bounded CPU/RSS and external wall timeout. Canary tests are necessary but **not sufficient to establish equivalence with Bubblewrap**, particularly for seccomp, filesystem submounts, process lifetimes, external adversaries and the absence of complete independent review. If the host does not permit this launcher, status is `BLOCKED_ENV`; do not substitute an in-process scorer for evidence silently.

The candidate's hypothesis class is *chosen by the experimenter*. Ambiguous target routes and synthetic aligned prior are deliberately constructed. The study is biased toward success on reachable examples; no claim of spontaneous capability invention, genuine predecessor learning, or generality is allowed.
