# ACE Research R7.5 — candidate coverage vs certification cost

**Decision: HOLD / NEGATIVE GATE.** Public synthetic development only. No deployment, merge, independent sealed evaluator, or OAIE claim.

## Provenance and execution

1. Locked protocol committed at `2eccd3c38593048cda743c52ec8032cf05ce137c` before R7.5 candidate code or final scoring.
2. 23/23 local Python 3.13.5 tests passed, including split uniqueness, label-cap invariants, e-value expectation under independent Bernoulli null p<=0.80, candidate observation-only logic, diagnostic/certificate segregation, and no oracle lookup by policies.
3. The **first** final-scoring attempt did **not** finish: process timeout, empty output (0 bytes), no usable scientific result. This engineering failure is disclosed rather than silently hidden. The deterministic scoring-probe sequence was subsequently cached with an LRU cache; it does NOT change the candidate or evaluator outcomes, RNG, purchased label replies or scored probe bytes. The runtime fix was committed as `8fa02b8365f5c097972359da099fdeb30d1f9450`, and source byte-identity checked by Git blob SHA `26988e3e65c1aebd0001094f7087e69decb9413f`. The 23 local tests were rerun and passed after the fix; test Git blob SHA `34acc9fdda48eb0043fcfd854a9b993439913697`.
4. One successful exact-code final evaluation, command `python r75_coverage.py --phase final > R75_FINAL.json`, Python 3.13.5, elapsed 5.64 seconds, maximum RSS about 100 MiB. Full result: **433,500 bytes**, SHA256 `239a7949ea271c8f7c5392a5c87f87e85b1d3e10afc0748212d34ba04ad48409`.
5. Offline JSON-only audit: **630 method/split/budget arms**, **7,218/7,218 consistency checks PASS**, no scoring rerun. Audit JSON SHA256 `976d46a1559bb72a243cbddcb5e083f3789ab693be2e8547f6fdc86b3cff7857`. Runtime validation-only before final: full099 5 true/0 wrong with 283 labels versus narrow099 5 true/0 wrong with 253 labels; fixed policy retained.
6. Source training cost: 18 worlds × six groups × 12 synthetic labels = **1,296 offline labels**; all online costs below separately counted. Final: 3 preselected seeds × 24 worlds × seven families = **504 worlds**; six capability decisions/world, cap 24 online labels/world. 64 evaluator-only score probes per group, not acquired by learner.

## Aggregate final outcomes at 24 online-label cap

Each family contains 72 worlds = 432 decisions. Values are accepted correct / accepted wrong.

| Family | 3-group R7.4-style, same p1=.99 | All-6 R7.5 p1=.99 | R7.5 labels purchased | Comparator labels | Interpretation |
|---|---:|---:|---:|---:|---|
| stable | 41 / 0 | 41 / 0 | 1687 | 1441 | No gain, more cost |
| swap | 8 / 0 | 4 / 0 | 1724 | 1672 | Lower useful coverage |
| reverse | 27 / 0 | 4 / 2 | 1722 | 1539 | Worse coverage and risk |
| new01 | 17 / 0 | 16 / 1 | 1711 | 1609 | New false acceptance |
| new23 | 0 / 0 | **29 / 0** | 1699 | 1728 | Structural blind spot corrected |
| all_null | 0 / 3 | **0 / 3** | 1725 | 1707 | Both false-accept null capabilities; 3/72 null worlds (4.17%) |
| correlated | 58 / 0 | 58 / 0 | 1670 | 1322 | Observed no false accepts, **IID bound inapplicable** |

Five ordinary families (stable + swap + reverse + new01 + new23): R7.5 **94 true / 3 false / 8,543 labels**, utility **−10,969**; matched narrow099 **93 true / 0 false / 7,989 labels**, utility **−10,263**. Delta utility **−706**. The new23 benefit does not offset regressions elsewhere. R7.5 uses 554 more labels.

Ablations (five ordinary families): narrow096 80 true / 0 false; full096 **0 accepted** because it has at most 12 fresh certification labels after 12 diagnostics, but the p1=.96 e-value requires 13 uninterrupted successes to reach E>=10. Thus full096 is an **underpowered negative control by design**, not evidence that the older threshold is inferior. Matched random099: 49 true / 1 false. Diagnostic-only control: 0 true / 0 false (trivial always-abstain), 4,320 labels.

### Locked success gate

- New23 correct accepted > 3-group: **PASS** (29 vs 0).
- No reduction on at least three of four shifted families: **FAIL** (only new23 improves).
- All-null false accept no worse than 3-group: **PASS** (3 vs 3; neither safe at 0%).
- Five-family utility >= matched three-group: **FAIL** (−10,969 vs −10,263).
- Every purchase within cap, at most one candidate certified per world: **PASS**.

**Overall scientific decision: HOLD**. This is not a positive R7 milestone. The e-process gives only a conditional p-value-like type-I control for ONE selected candidate under independent stationary Bernoulli certificate samples, not global ACE correctness or risk control under correlated tasks. The public, author-constructed family set is no longer suitable as an unseen holdout after this run. No confidence that future real ACE semantic-alias cases behave similarly.

## Counterexamples and next independent experiment

The selection rule uses only two diagnostic labels/group. When there are several groups with two successes, source-prior tie-breaking can still select a spurious high-prior group rather than the new reliable one (reverse / new01 failures). Spending 12 of 24 labels on diagnosis also makes evidence collection expensive. New23 validates the need for candidate coverage but not an optimal acquisition policy. A future protocol should jointly constrain *selection regret*, label efficiency and conditional acceptance risk, and compare explicit posterior decision utilities under an independently custodied scorer. Test correlated/nonstationary labels with no unjustified e-process guarantee. Do not tune on this test bank.

**No merge; PR #43 remains draft.**
