# ACE E1.4b — frozen unconditioned-pool replication result v1

**Decision: GO TO CROSS-EPISODE DEVELOPMENT (public development only).** This is the exact decision returned by the frozen E1.4b rule on its public replication bank, **not** a confirmatory inference or general-intelligence claim.

## Pre-scoring freeze and integrity

- Frozen source checkpoint: [`38b1c3b`](https://github.com/dianzherdiana25-hash/ACE/commit/38b1c3b90ab8f53ae84480f60ed4d1ac603c67ea), with the protocol at `design/e1.4/E14_QUERY_REPLICATION_v1.md`.
- Unconditioned pool seed `141612`, bank seed `141611`; the source commit predates this result.
- Frozen replication bank SHA-256: `ca41042fdfbce5755f763dca1945e1de0c1420d6aa6fd29fd6ea57e40f16b29b`.
- Frozen source signature SHA-256 (as reported by runner): `ec4a6397890daa0f0443f7d3aa1fae0fb7b2e3ac714722e105275c3640fb9ded`.
- 12 episodes, six per family (`S`: symbolic, `G`: graph), eight held-out probes per episode. 132 isolated fits: 12 initial arms, 24 initial competing hypotheses, and 96 independent one-label refits. All 96 possible one-label interventions were scored for a uniform-random expectation.

## Scores (identical one-label budget)

| Family | No extra label | Uniform one-label expectation | Active disagreement query | Active - uniform |
| --- | ---: | ---: | ---: | ---: |
| S, six episodes | 17/48 | 20.25/48 | **27/48** | **+14.06 pp** |
| G, six episodes | 24/48 | 25/48 | **28/48** | **+6.25 pp** |
| Combined | 41/96 | 45.25/96 | **55/96** | **+10.16 pp** |

- S paired episode comparisons vs uniform expectation: 3 wins, 0 ties, 3 losses.
- G paired episode comparisons: 1 win, 4 ties, 1 loss.
- Query reason: `disagreement` for all 12 episodes; no caps on selector, fitting, or prediction were reported.
- Max observed active solver + selector CPU: 136825 microseconds per episode; maximum uniform-arm solver CPU: 161561 microseconds. This is an observed local profile, not a guarantee under other hosts.

## Audit, reproduction and uncertainty

1. Frozen benchmark completed with exit status zero. Its `--verify` mode reproduced the saved raw report, including deterministic fields. A separate run matched the same deterministic outcome; wall and CPU samples naturally differ.
2. Frozen E1.3/E1.4 suite: **70/70 tests PASS**; separate bank tests **2/2 PASS**. Python emitted `ResourceWarning` for unclosed SQLite connections during unrelated regression tests, but tests passed; this warrants a later isolated cleanup.
3. A separate standard-library-only report-structure auditor checked the 12 task records, the 96 control arms, scoring subtotals, uniform expectations, decisions, selector choices, ID uniqueness and cap counts. Its **17/17 corruption/consistency tests PASS**. This is an **internal consistency audit**; it does not independently validate oracle correctness, full candidate isolation, or the data-generating process.
4. A **posthoc descriptive** stratified episode bootstrap (30,000 draws, seed 141613) gives active-minus-uniform **+10.16 pp**, exploratory 95% interval **[-1.43, +23.96] pp**. The interval spans zero, and there are only six episodes per family; motifs may be dependent. It is inappropriate to infer robust generalization or claim statistical significance.

## Scientific interpretation

The *preregistered development gate* requires active scores to exceed both no-label and uniform one-label expectation **in S and G**, without resource caps. All those development conditions passed. The effect in each family is small-sample and heterogeneous, especially graph tasks (only one win).

**Decision:** advance to a new, separately designed cross-episode development pilot. Preserve frozen data and negative cases. Require stronger controls, a broader independent motif distribution, and matched labels + compute budgets. Do not reuse these 12 episodes for parameter tuning, and do not open E1.3 sealed confirmation. E1.3 v1 remains NO-GO for its original count-only candidate: that was a *scientific* decision, not a request for owner/chat approval.

## Next executable research

- Define new source/target episodes and representations from distinct motifs and test whether active question selection improves transfer and inherited representations over target-only, one random label, sham, and strong informed reference.
- Separate discovery, selection and evaluation pools; prefreeze code and primary endpoint before observing results. Report negative transfer and both-wrong/no-disagreement cases.
- Progress ACE's long-term Open-Ended Autonomous Intelligence Evolution vision without claiming that it is achieved.

## Anti-stall operational constraint

Use `tools/ace_bounded_runner.py` for bounded local subprocesses, e.g. `python tools/ace_bounded_runner.py --timeout 90 --heartbeat 10 --log /tmp/ace-replay.log -- python -m e14.query_replication --verify evidence/e14/query_replication_v1.json`. It emits heartbeat messages, returns explicit `OK/FAILED/TIMEOUT`, kills the process group at timeout and retains a log. This does not bypass ChatGPT/Work service session limits, nor does it schedule work. If the runner stops, checkpoint the actual status; never report success from a process merely started.
