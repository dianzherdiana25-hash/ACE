# ACE E1.4e — source/meta-separated policy learning: PRE-SCORE REGISTRATION

**Status: PRE-SCORE FREEZE. No E1.4e target outcomes were inspected before this record.** Scientific status development-only; this is not independent confirmation. Frozen archive is available in the originating ChatGPT session as `ACE_E14e_PRELOCK_2026-11-04.tar.gz` (full code, structural tests, protocol). Its exact SHA-256 is recorded below. This commit registers a cryptographic code freeze; the archive is **not** embedded in this GitHub commit, so recovery requires the verified archive. Do not claim otherwise.

## Frozen source and evidence digests

| Path | SHA-256 |
| --- | --- |
| `code/e14/e14e_bank.py` | `d0f2533ed4bc861eafc3f0eb52457a1c5f9e253f1e734d3751aaa7dcf5f8f730` |
| `code/e14/e14e_policy.py` | `19eaff09a5a62dbae1ca523858dea55632c0576a2dcc12743f02dbe15073a2ec` |
| `code/e14/e14e_run.py` | `9066ab0069a63305b5b27797d588052e320fbc951ab1c642e27fca6de6c49f23` |
| `code/e14/test_e14e.py` | `596e9089bf8cbda4acb86c34b5d77838ca117fff74f268d5b921dd29ccebeece` |
| `design/e1.4/E14E_META_VALIDATED_QUERY_PRELOCK_v1.md` | `acb7d93241510329f8a0d1a5e907c6b5192f304de9f774834db6ae3c43e8c2a9` |
| complete deterministic tar.gz source archive | `0890c747d92d0b99fb47496c3fd437ee53b37c19362fc1e23970b55c945f19c6` |
| complete deterministic tar.xz source archive | `73920eda07e866c8e02b664511d1cfda158eb6348b2fc424fd7c473ab0648710` |
| pre-score 8/8 unittest log | `710e27d5d086327089d5a8a6591793dabfa1a0bc5e99b2be2c73eef6ef08aa56` |
| new entire public bank digest | `2019d5ac169871b82295ac994160c033a4b6fe690dab0e5e2c91f483214417d0` |

The first prescoring test invocation TIMEOUT was diagnosed as expensive repeated historical bank generation. A source-only `lru_cache` of previous bank structures was introduced **before scoring**. The corrected prescoring tests passed **8/8** in ~8.6 seconds.

## Locked design

- Fixed S/G five-event grammar, new rule IDs excluding E1.4d; 12 source-training, 6 disjoint meta-validation, 12 distinct target episodes. Each source-target pair related by one edit or unrelated by ≥3 edits. Random seeds: motifs **141901**, query pools **141902**, demonstrations/probes **141903**, selector ties **141904**.
- **Thirty** eight-question unlabeled pools preallocated before any hidden-rule-conditioned demos/probes, excluding all historical public examples. Each task: 2 labeled demonstrations, 8 unlabeled candidate queries, 8 held-out probes (4 random/natural + 4 engineered diagnostic).
- Train a heuristic from 6 training episodes/family using *gross improvement over abstention* (ties abstain), then accept only if 3 disjoint meta episodes/family show **strictly positive** aggregate improvement for that context. No meta example or no-disagreement/resolved contexts => abstain. This is a deliberately new exploratory method after E1.4d, not a preregistered independent reproduction.
- Target score: correct /8 probes per episode, independently S/G × related/unrelated (four strata of 3 targets, 24 probes/stratum). Compare inherited versus local max-Gini, minimax, sham abstention, no-label, exact uniform 1-label expectation; eight-label target fit as higher-budget diagnostic.
- **GO only if inherited strictly exceeds all one-label/no-label controls on every one of four strata**; otherwise `HOLD_META_VALIDATED_QUERY_TRANSFER`. Any GO can only be called `GO_PREDICTIVE_ONLY_COST_UNPROVEN`.
- Source + meta acquisition cost: 12 train × (2 demos + 8 intervention labels + 8 source probe labels) + 6 meta ×18 = **324 observed oracle label events**; target research measurement: 12 × (2 demos + 8 counterfactual interventions + 8 probe labels) = 216, total research 540. Source overhead 27 labels per target at 12 targets; not end-to-end cost parity.
- Candidate/evaluator modules share a process; official Bubblewrap isolation remains unproven. The benchmark is a synthetic closed human-defined grammar, not verified OAIE.

No sealed data, no Tod/main changes, no spending. After this freeze, execute bounded score once, run exact replay + independent arithmetic audit; preserve any negative result rather than changing seeds or thresholds.
