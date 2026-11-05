# ACE R2 v4 — PRE-SCORE public development protocol

**Owner:** `code/ace_research_lifelong/` only. **Scientific status:** exploratory; not an independent blind test.

## Motivation
R2 v3 found that novelty-triggered context gating retained skills when contexts were separated but was not superior to matched-capacity no-transfer or fixed slots. In overlap, task identity from context may be non-identifiable. R2 v4 tests an *explicitly different information contract*: a bounded support set of 12 fresh labeled examples is available for each episode and evaluation query block. This support may reveal which stored expert to retrieve without exposing a task ID. All methods receive the same support labels and their acquisition cost is counted, even if unused.

## Hypotheses (predeclared)
H4a: support-loss specialist routing materially outperforms contextual routing when task context aliases. H4b: partial specialist parameter transfer provides an additional >= 0.025 average final accuracy beyond identical evidence routing with zero-transfer initialization. H4c: a support-based uncertainty/novelty gate can reject >= 0.65 of genuinely unseen fifth-task support blocks while falsely rejecting <= 0.20 of previously learned task blocks. H4d: performance improves over a shared-head support-finetuning baseline by >= 0.03. Scientific mechanism gain requires ALL H4a–d plus mean aliased latest accuracy >= 0.75. Do not change these thresholds after scoring.

## Task generation and leakage contract
Five deterministic seeds [5,17,31,53,79]. Four independent but reproducible sparse signed-feature binary teachers over 12-dimensional inputs, with nonzero weights sampled once per (seed,task); a fifth independent teacher is held out as an **author-visible novelty diagnostic**, not a confirmatory bank. Label-flip noise 0.02. Eight consecutive training episodes use task sequence [0,1,2,0,3,1,2,0]. Each episode contains 64 labeled examples: the first 12 are the task-identification support block, the remaining 52 are training examples; all 64 can be used for weight updates, but expert choice must occur before updates, based only on the first 12 support labels. Context regimes: `distinct` with nonoverlapping scalar context centers [-.9,-.3,.3,.9] and tiny jitter; `aliased` with all centers at zero and tiny jitter; `shifted` with unreliable sign-flipped context centers at evaluation and on revisit. This manipulation is not a claim of natural task structure.

Separate deterministic RNG streams produce train, evaluation-support, evaluation-query and held-out novelty-support examples. The **same teacher seed and coefficients** must be used across all splits of each task. Training labels and query labels must never be shared by identity. The oracle alone may observe task ID. For the main evaluation, a fixed 12-support-item set per task is used to select a head and a disjoint 96-item query set is scored after each episode; no learner may update on those evaluation labels. Every method is charged with evaluation support-label accesses, including one novel fifth-task block at terminal evaluation.

## Fixed methods and training budget
- `frozen`: shared linear sigmoid head trained on episode zero only.
- `sgd`: shared 12-weight sigmoid head updated on all episode examples.
- `ewc`: shared head with diagonal EWC and explicit Fisher/penalty operations.
- `replay`: shared head with size-48 bounded reservoir and one extra gradient update per newly observed item, counting all extra compute.
- `context`: up to four experts created via context novelty >.22; route by closest centroid and update one head.
- `evidence` (candidate): at episode start, evaluate all expert log-losses on 12 support labels. Reuse minimum-loss expert if loss <= .61, otherwise create a new expert until capacity four; new expert initialized to 0.20× the closest-loss existing expert; at capacity, fall back to minimum-loss expert. Query-block inference selects the minimum-loss expert using its 12 evaluation support labels, and abstains if loss > .61. Context is not used in the candidate's expert selection. No task ID.
- `evidence_zero`: SAME support routing, threshold, optimizer, four-expert capacity, inference/abstention and evidence budget, but new experts initialized at zero; this is the **primary equal-capacity causal ablation**.
- `fast_adapt`: shared sigmoid head; at evaluation make a temporary copy, update it once over the SAME 12 support examples, then score query (extra eval compute charged).
- `oracle`: four task-ID keyed experts; privileged upper bound only, not a valid deployable baseline.

Each new training example causes exactly one gradient update for all methods except frozen and replay. Experts have 12 weights + tracked metadata each, maximum four. EWC and replay incur explicitly recorded additional compute/storage. No untrusted generated code, external labels, fees, or private bank access.

## Metrics and release gates
Report per-episode accuracy, final mean across four known tasks, aliased accuracy, terminal retained performance, mean forgetting (best historical learned post-task accuracy minus terminal), forward and backward transfer, inference abstention and known-task false-rejection, novel fifth-task rejection, training gradient updates, evaluation support probes, expert loss-evaluation operations, expert storage and replay buffers. Score abstention as incorrect on the accuracy metric (no gaming through rejection). The fifth-task novelty rejection rate is an error-detection metric only, not novel-task solving. Absent external confirmatory custody or exact-head CI, decision is exploratory HOLD even if gates pass.

### Reproduce after source lands
```bash
cd code/ace_research_lifelong
node r2_v4.js > R2_V4_REPLAY.json
node audit_v4.js R2_V4_REPLAY.json
```
No post-score rewriting of this protocol permitted. Discoveries of actual implementation defects must be described as errata and corrected with full rerun and source provenance.
