# ACE E1.4f — prescoring cryptographic lock (2026-11-04)

**PRE-SCORING registration. No E1.4f outcome scores have been observed.** Scientific class: public *benchmark opportunity development*, not independent confirmation, AGI or established OAIE progress. This manifest freezes the exact local source and protocol byte hashes before target scoring. **Source archive bytes are not included in this specific commit**; they must later be recovered with the exact registered SHA-256 and Git blob SHA. Never replace this manifest or alter the locked algorithm/gates after seeing scores.

Parent: `a7f912e97ace47cf4d3502e397d56152f70ee6e9`.

## Hash-locked files

| File | SHA-256 |
|---|---|
| `code/e14/e14f_bank.py` | `1316c10a72a1a4d3c4873408f67151eff1f6b3da045512b2ea2e4589eda7fbda` |
| `code/e14/e14f_run.py` | `32a160806f72d624c1de03f75d93aa999f4a6ef645016197603c405bc3fe4cab` |
| `code/e14/e14f_selector.py` | `cf892c3e4e83106d10a2b0f3484a3064b425dd4433043824fa62db59b4edd35e` |
| `code/e14/e14f_audit.py` | `efc23d8c3fc04d278c767ee856267bcba81ad278e6fa587ac839c28e0e8736d1` |
| `code/e14/test_e14f_prescore.py` | `8102bd91dd499df7c21555ac1aea6fabb249496150108afa1e5dd124b03df2a4` |
| `design/e1.4/E14F_OPPORTUNITY_PRELOCK_v1.md` | `660c8e84142ad489b784c70a425c5f80a52dbbea198abd4508a1222040cd8f74` |

Frozen deterministic source+protocol `tar.xz` SHA-256 **`2f5f365c7d7940b39cdce361c31bdb28bf448a45a8ecc2e0c1503c3257be9865`**; expected Git blob SHA-1 **`d9c867040a76e8903b534dd0f0e06bd6f608e731`**. Locally stored as `ACE_E14f_artifacts/E14F_FROZEN_SOURCE_2026-11-04.tar.xz` and must be placed in the research Git tree before final archival acceptance.

Fresh bank SHA-256 **`d79acfec7a9778bae4f2e6599a00cdbe5b3e22b4a13d269fa74bf7d54bdfbf2b`**. Pre-score 8/8 structural unit tests passed in 8.428 seconds, including prior-input disjointness, 24 task IDs and word classes, no-oracle pool preallocation, candidate-only selector, curated selected-index integrity, and no pool/probe overlap. Earlier pre-score failed once when graph random event length exceeded typed contract; input lengths were corrected 9–14 **before this freeze**.

## Frozen design and decision (summary; full text in archived protocol)

- 24 tasks: S/G × represented five-event/out-of-basis six-event true rules × 6 tasks.
- Each task: two labeled demonstrations, 8 independent random questions, 48 separately reserved unlabeled candidate queries from which 8 are selected by demo-fit predictive Gini (no hidden rule), two independent 8-probe sets: natural-heavy 6 natural+1 positive+1 negative, diagnostic-heavy 2 natural+4 positive+2 negative.
- Seeds: motifs 142001, pool 142002, demonstrations/probes 142003, selector tie 142004. All older public inputs excluded.
- Measure best one-query **hindsight oracle upper bound** vs no-label, max-Gini one-query, minimax one-query, uniform one-query expectation, and no-label. Report natural/diagnostic strata and represented/out-of-basis controls separately. Hindsight is **not deployable**.
- **Development feasibility criterion**, separately for S and G in *in-basis + diagnostic-heavy + curated pool*: hindsight positive on >=3 of 6 tasks AND max-Gini positive on >=2 of 6 tasks AND summed max-Gini gain strictly >0. Both families must pass to return `OPPORTUNITY_BENCHMARK_FEASIBLE_DEVELOPMENT_ONLY`; otherwise `BENCHMARK_HOLD_REDESIGN`. No posthoc pooled rescue.
- Budget: 24 × (2 demo + 16 counterfactual query labels +16 held-out probe labels) = 816 newly labeled public data points, excluding historical fixture computation. Curated pool uses more unlabeled candidate predictions and is **not compute-matched**.
- Candidate and evaluator live in the same process; independently isolated worker custody, official Bubblewrap and confirmatory inference remain unverified. No extra spending, no Tod change, no main merge, no sealed E1.3 data.

**Execution:** freeze confirmed by branch readback → one bounded pilot → exact canonical replay → independent JSON-only arithmetic audit → preserve outcome negative or positive as written → write GitHub checkpoint with raw evidence/code and verify HEAD.