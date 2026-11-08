# ACE R9 (Gemini lane) — learned-feature representation transfer: PRE-REGISTRATION

Status when committed: **no experiment code, no scored result.** Lane and limits come from Issue #63
(branch `research/gemini-r9-representation-transfer`, only `code/ace_research_reptransfer/`,
`docs/ACE_R9_GEMINI_*.md`, optional `.github/workflows/ace-gemini-r9.yml`). Base: `main`
`80104ce50ecbcea21080bed8c0eabce88d47ccb5`. Scientific `NOT_ASSESSED`, release `BLOCK_RELEASE`,
OAIE `NOT_ESTABLISHED` regardless of outcome. No merge, no deployment, no spend.

## 1. Demonstrated baseline and boundary (read from main, PR #58–#62)

| Fact | Source |
|---|---|
| Runtime v1 reuses a stored model only when the *exact same program* fits the new train+validation labels (`REUSE_VALIDATED`). | `docs/ACE_RUNTIME_V1.md` |
| Across four string families, retained library saved **0/16** fresh fits; identical accuracy to fresh runtime. | PR #62 results |
| Two label-identical worlds with inverted terminal truth were **falsely accepted 2/2** (terminal 0/128). Unobservable from the labels. | PR #60, #62 |
| Composition (counter × learned DFA) beats fixed products only on some task shapes (900/1024 vs 769/1024) and loses `ratio2_boundaries`. | PR #60 |
| Graph-family transfer: runtime stages 0/4 (`NO_VALIDATED_MODEL`). | PR #61 |
| Gap this lane targets: **reuse of program identity is not reuse of structure.** Nothing yet tests whether *sub-structure* learned from source labels (feature level) lowers target label cost. | PR #62 "next mechanism" |

## 2. Mechanism under test (A)

*Learned feature dictionary + low-budget adapter.*

1. **Source representation (learned, label-only).** For each source task, run the **unchanged** R1
   learner (`ace_research_primitives.primitive_discovery.infer`) on the 63 exhaustive strings of
   length 0–5. **Source admission:** keep the DFA only if it classifies all 8,128 strings of length 6–12
   exactly (labels from the source rule). Each state `q` of an admitted DFA defines a feature
   `f_q(s) = [DFA ends in state q after reading s]` (a state-occupancy indicator). Duplicate features
   (identical value on all 511 strings of length ≤ 8) are merged. No target label, target string or
   terminal data is read when building the dictionary.
2. **Target adapter.** Hypotheses = a single literal `±f` or a pair `ℓ1 ∘ ℓ2` with
   `∘ ∈ {AND, OR, XOR}` over literals of two distinct features. Fit = all hypotheses exactly consistent
   with the target *train* labels; select by `(validation errors, complexity, canonical name)`;
   **admit iff validation errors = 0** (same "must fit train and validation" rule as ACE Runtime).
   Abstain otherwise.

What is learned vs hand-authored (declared, not hidden):
- **Learned from labels:** the DFA structure and hence every feature in A.
- **Hand-authored:** the choice of source tasks, the *form* of the feature (state occupancy), and the
  adapter hypothesis class. Source tasks were chosen by the researcher with the target family in mind
  (they share atoms). A therefore tests *transfer of learned sub-structure given related sources*, not
  discovery of unrelated structure, and not novel primitive invention.

## 3. Task design (truth-only checks done before this commit; see §9)

Alphabet `{a,b}` (R1 alphabet). `ca=count(a)`, `cb=count(b)`.

**Source set S_rel (7 tasks, relevant atoms):** `ca%4==0`, `cb%4==0`, `ca%3==0`, `ends 'ba'`,
`starts 'bb'`, `contains 'aab'`, `len%4==0`. (`ca%5==0` and `ends 'abb'` were tried in preflight and
**failed source admission** — R1 on exhaustive ≤5 strings does not identify them — so they are
excluded; this is a recorded limitation: mod ≥ 5 counters are not learnable by this source regime.)

**Source set S_irr (8 tasks, irrelevant control):** `starts 'ab'`, `starts 'ba'`, `ends 'aa'`,
`ends 'bb'`, `contains 'bab'`, `contains 'aba'`, `ca%2==0`, `len%3==0`.

**Targets (family-disjoint from every source: every target is a *two-atom composite* template;
no target equals any source rule on any string ≤ 11; enforced by test):**

| Stratum | ID | Rule |
|---|---|---|
| **U** (not expressible by base hand library C, expressible by A and C2) | U1 | `ca%4==2 AND ends 'ba'` |
| | U2 | `cb%4==1 AND starts 'bb'` |
| | U3 | `ca%4==1 XOR ends 'ba'` |
| | U4 | `cb%4==3 OR contains 'aab'` |
| | U5 | `ca%4==3 AND cb%4==2` |
| | U6 | `cb%4==2 XOR starts 'bb'` |
| **L** (expressible by C) | L1 | `ca%3==1 AND ends 'ba'` |
| | L2 | `ca%3==2 OR starts 'bb'` |
| | L3 | `ca%3==1 XOR contains 'aab'` |
| **N** (outside every pair-head class; no shared structure) | N1 | `ca==cb` |
| | N2 | Dyck prefix-balance (`a`=open, `b`=close; R1 `dyck`) |

Truth-only preflight (no labels sampled): U tasks are pair-expressible over A(S_rel) and over C2 and
**not** over C or A(S_irr); L tasks are pair-expressible over C. Strata are verified by a unit test in the
implementation commit; a failing check blocks scoring (it would be a protocol amendment).

## 4. Arms (identical labels per unit; same admission rule)

| Arm | Representation | Notes |
|---|---|---|
| **A** | learned features from S_rel | the mechanism |
| **A0** | learned features from S_irr | irrelevant-source causal control |
| **B** | none: fresh R1 `infer` on target train labels, admit iff exact on validation | the source algorithm under the Runtime protocol (not weaker than source) |
| **C** | base fixed hand-authored library: `r1.fixed_predicates()` unchanged, dedupe by behaviour | the repo's existing strong fixed-feature baseline |
| **C2** | C ∪ {`count_x%m==r`, x∈{a,b}, m∈2..6, all r} ∪ {`len%m==r`, m∈2..6} | extended hand library authored with knowledge of the target atoms; **not blind**, an upper-bound comparator |
| **D0** | constant `False` | sanity floor |

A, A0, C, C2 share the same adapter. Secondary **agreement-gate** variant (A_g, A0_g, C_g, C2_g):
among all hypotheses with minimal complexity that pass train+validation exactly, abstain if they
disagree on any of 256 *unlabeled* probe strings (lengths 16–30, seed role `probe`, disjoint from
terminal). Primary results are ungated.

## 5. Data, budgets, seeds

- Per unit `(task, seed, budget B)`: `n_train = n_val = B/2`. Budgets **B ∈ {16, 32, 64}**; seeds
  **1–5**. **Primary budget: B = 32.**
- Train words from all 63 strings of length 0–5; validation from all 8,128 strings of length 6–12.
  Class balance: `min(available, n/2)` positives, remaining filled with negatives. Words are chosen by
  ascending `sha256(role|task|seed|B|word)` (version-independent, no RNG-algorithm dependence).
- Terminal: 64 positives + 64 negatives, lengths 16–30 (uniform length, uniform symbols, rejection
  with a 400,000-draw cap per class; exceeding the cap is a protocol failure, not a silent change),
  generated by an evaluator module that is **never imported by any fit code**; terminal generated after
  selection. Labels from an independent truth implementation (regex / explicit stepping), cross-checked
  against the generating implementation on 4,096 strings per task.
- **Drift controls D1 (U1) and D2 (L1):** identical train/val as the nominal unit, terminal truth
  complemented. Used only for false-acceptance accounting.
- Total nominal units: 11 tasks × 5 seeds × 3 budgets = 165; drift units 2 × 5 × 3 = 30.

## 6. Metrics (all reported for every arm, every stratum, every budget)

`coverage` (admitted/units); `M` = terminal correct among admitted ÷ 128, **abstention scores 0** (primary);
conditional accuracy; false admission = admitted with terminal accuracy < 0.90;
transfer regret = `max(M_B, M_C, M_C2) − M_A` per unit; sample-efficiency curve over B; every
failed/inconclusive unit retained in the raw report.

**Compute accounting (reported, not matched):** per arm per unit: `symbol_reads` (each feature/DFA/predicate
evaluated on a string costs `len(s)`, counted per feature uniformly, conservative for A), `hypotheses_evaluated`,
and for R1 `merge_attempts` plus the deterministic upper bound `merge_attempts × Σ(len+1) over its examples`.
Source pretraining cost is reported separately and also amortized. Claim limited to **label budgets**;
no wall-clock or CPU-equivalence claim. External pretrained work counted: none used.

## 7. Hypotheses and decision rule (fixed now; no post-hoc change)

At **B = 32**, mean over units:

- **H1 transfer (U):** `M_A − max(M_B, M_C) ≥ 0.15` **and** A beats `max(M_B, M_C)` by ≥ 0.05 on ≥ 4 of 6 U tasks (task mean over seeds).
- **H2 source causality (U):** `M_A − M_A0 ≥ 0.15`.
- **H3 no regression (L):** `M_A ≥ M_C − 0.05`.
- **H4 sample efficiency (U):** smallest B at which A reaches mean `M ≥ 0.80` is ≤ half that of B, or B never reaches it within {16,32,64} while A does.
- **H5 admission safety (N):** false-admission units of A ≤ max(B, C).
- **H6 drift (D):** *predicted FAIL* (label-identical worlds are unidentifiable). Report false-accepts; A with admitted terminal accuracy < 0.10 ⇒ `OPEN_WORLD_SAFETY = FAIL`.
- **H7 feature recovery (U):** `M_A ≥ M_C2 − 0.10`.

**Gate G = H1 ∧ H2 ∧ H3 ∧ H5 ∧ H7.** G true ⇒ "public-diagnostic transfer evidence, still `NOT_ASSESSED`".
G false ⇒ **scientifically REJECT the mechanism and preserve the failure.** H4 and H6 are reported but
not gating (H6 is expected to fail).

## 8. Negative-result and integrity commitments

- Source of truth for stratification is the truth-only check; no arm outcome influences task, budget,
  threshold or arm definitions. Any defect fix after first scoring is logged as a deviation with the
  failing run kept.
- R1 and fixed-predicate code is imported unchanged (checked by `tools/verify_sources.py` plus an own byte hash).
  No change to `code/ace_runtime/`, main, E1.4, Tod, other lanes or PRs #59–#62.
- Evaluator-independence gaps (declared): same author designs tasks and evaluator; public bank; no sealed
  external evaluator; C2 is not blind; seeds share task rules (clustered by task, no significance claims);
  sources are related by construction.
- Tests before scoring: adversarial leakage test (fit outputs invariant to terminal labels), strata
  validity, source/target disjointness, deterministic replay, tamper rejection of the receipt verifier.
- Two exact-SHA GitHub Actions runs on Python 3.12 and 3.13; report SHA-256 must be byte-identical
  across both runs and both versions.
- Cost: pure standard-library Python on GitHub-hosted runners; extra spend Rp0; no API calls; no
  untrusted code execution.

## 9. Preflights executed before this commit (honest log)

Run 2026-11-06 ~09:47 PST on Python 3.11, no target label ever sampled, no arm scored:

1. `preflight_source.py` (sha256 `4321dbe72bc8b511eaa1fd9bb9cda06b6adda920333909d14352677de5675fa2`):
   source learnability. `ca%5==0`: 2010/8128 validation errors; `cb%5==0`: 2010; `ca%6==0`: 1717;
   `ends 'abb'`: 113 errors → excluded. `ca%4`, `cb%4`, `ca%3`, `ends ba`, `starts bb`,
   `contains aab`, `len%4` and all eight S_irr tasks: 0 errors → admitted.
2. `stratum_check.py` (sha256 `fc25e7731b9fe8d574d2bc731e8cf6c889113f1f7ea51e33afd7ab8a87fdfdee`):
   truth-only expressibility on strings ≤ 11: A(S_rel) 26 features, A0(S_irr) 26, C 100, C2 148.
   U1–U6: expressible by A and C2 only; L1–L3: expressible by A, C, C2; A0 expresses none. Both scripts are
   committed verbatim with the implementation.
