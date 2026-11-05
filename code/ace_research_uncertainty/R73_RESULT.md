# ACE Research R7.3 — shift-aware diagnostic, locked public-development result

**Decision: HOLD / negative overall.** The precommitted success gate in [R73_PROTOCOL.md](R73_PROTOCOL.md) was locked on the R7 branch at `fa1d5bb0029665cb2bbf05a9ae8e936fa6fd878a` **before** adding scorer code and running final test/OOD. Candidate code and 13 new tests were saved and Git blob SHA-verified before the final run. No changes to main, frozen E1.4, ACE core, or other research teams.

## Actual local execution and provenance
- Python **3.13.5**, CPU local, Python stdlib only. No network or paid evaluator.
- Local command: `PYTHONPATH=code python -m unittest ace_research_uncertainty.test_experiment ace_research_uncertainty.test_r72_certification ace_research_uncertainty.test_r73_shift -q` -> **36/36 PASS** (11 original + 12 R7.2 + 13 new tests). This is local, not exact-head CI.
- Locked source blob SHA: `c63b15e8bd36e2ec2888a59364b57817ba27a41b`; locked test blob SHA: `1a9ae30bb0d319f62c84ac8bdd55d003acabc808`. Both match GitHub readback.
- Final score invoked **once** after these files were committed: `PYTHONPATH=code python -m ace_research_uncertainty.r73_shift --phase final > ACE_R73_final_results.json`.
- Full pretty-printed JSON: **23,930 bytes**, SHA256 `ec2f902b324062e4f7bb63a23dfda830d4355c44457162bc2d1938e85fb6c5c8`. This file was generated locally; the repo records its checksum and compact results, not the full 23,930-byte output. Recompute from branch code and compare bytes.
- Source-fit purchases: 2,160 offline synthetic training labels, *in addition* to each arm's reported target-label cost. Each split has 24 tasks and 144 group decisions, with online maximum 24 labels per task.
- Oracle ceiling (score-only privileged comparator): stable=58, OOD-A=24, OOD-B=33 truly acceptable group decisions. It is **not** a zero-cost implementable policy.

## Results at 24-label maximum (each row covers 144 group decisions)

| Split | Policy | True accepted | Wrong accepted | Abstained | Online purchases | Shift flags (of 24) | ECE | Brier | Utility |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stable | Random+LCB | 22 | 0 | 122 | 576 | 0 | 0.037399 | 0.157564 | -380 |
| Stable | Certificate R7.2 | 38 | 0 | 106 | 154 | 0 | 0.051757 | 0.157442 | 394 |
| Stable | Sentinel only | 38 | 0 | 106 | 165 | 0 | 0.051634 | 0.157443 | 383 |
| Stable | Shift-aware R7.3 | **38** | **0** | 106 | 165 | **0** | 0.051634 | 0.157443 | 383 |
| OOD-A | Random+LCB | 0 | 2 | 142 | 576 | 0 | 0.198456 | 0.290389 | -980 |
| OOD-A | Certificate R7.2 | 0 | 7 | 137 | 112 | 0 | 0.328037 | 0.330221 | -806 |
| OOD-A | Sentinel only | 0 | 8 | 136 | 185 | 0 | 0.319432 | 0.323493 | -937 |
| OOD-A | Shift-aware R7.3 | **2** | **5** | 137 | 334 | **9** | 0.226479 | 0.291170 | -868 |
| OOD-B | Random+LCB | 0 | 0 | 144 | 576 | 0 | 0.346957 | 0.339895 | -864 |
| OOD-B | Certificate R7.2 | 0 | 0 | 144 | 55 | 0 | 0.501082 | 0.433088 | -343 |
| OOD-B | Sentinel only | 0 | 0 | 144 | 145 | 0 | 0.475926 | 0.400624 | -433 |
| OOD-B | Shift-aware R7.3 | **11** | **2** | 131 | 559 | **23** | 0.056029 | 0.190825 | -721 |

Utility is `20 true - 60 wrong - 2 abstain - purchased`. The detector fired on **0/24 stable**, **9/24 OOD-A**, **23/24 OOD-B**. This demonstrates that a small *observation-based* shift diagnostic carries signal, but not enough to warrant a global safe-acceptance claim.

At 6 labels R7.3: stable 23/0 correct/wrong with 144 labels; OOD-A 0/3 with 144, OOD-B 0/0 with 144. At 12 labels R7.3: stable 38/0 with 165; OOD-A 0/5 with 226; OOD-B 0/0 with 283. At zero labels all methods abstain.

## Prespecified gate verdict
1. **FAIL** — OOD false acceptance must not increase in either family. OOD-A 7->5 improves, but OOD-B 0->2 worsens.
2. **PASS** — stable true acceptance retained ≥80% (38 vs 38) and no extra stable wrong accepts (0 vs 0).
3. **FAIL** — OOD coverage became nonzero, but utility **declined in both OOD families** because of cost and unsafe acceptance.
4. **PASS** — per-task online budget hard caps respected.

**Overall: FAIL / HOLD.** Improvements in shifted-task coverage, Brier and ECE are exploratory; they cannot override increased false acceptances or worse utility. No independent holdout, confidence interval, replicates, formal calibration guarantee, Bubblewrap evidence, or actual ACE semantic-operator experiment is claimed.

## Counterexamples, limitations and next gate
- OOD-A detector misses **15/24** shifted worlds; old prior still leads to false acceptance.
- OOD-B detects **23/24**, improves calibration markedly (ECE 0.501 -> 0.056), but acceptance rule still wrongly certifies two strata; detection alone is insufficient.
- Diagnostic/skeptical fallback purchases **334** and **559** labels in OOD-A/B respectively versus the R7.2 certificate's **112** and **55**; this is a real utility regression, not a computational efficiency gain.
- Known author-built OOD families, same in-process scoring mechanism, single seed and Gaussian LCB approximation prohibit general safety conclusions.
- The published R7.3 test/OOD splits are now development data and MUST NOT be reused for confirmatory tuning. Next study should precommit a genuinely new independent family, use risk-limited Bayesian decision/abstention with calibrated time-uniform bounds and target minimum useful coverage, include an explicit false-acceptance budget and matching cost controls, and test real ACE semantic-alias cases.

No promotion to core, no PR merge. Maintain draft PR #43 and `HOLD`.
