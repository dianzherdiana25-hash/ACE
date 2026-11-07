# ACE Fase 6 — Automated Uncurated Representation Discovery & Cross-Family Transfer (Results V1)

- **Date:** 2026-11-07
- **Branch:** `research/ace-novel-reptransfer-v1-20261107`
- **Pre-Registration Commit:** `6e0eae8` (`docs/ACE_NOVEL_DISCOVERY_PRESCORE_V1.md`)
- **Evidence Artifact:** `evidence/discovery/f6_novel_discovery_v1.json.gz` (and `.json`)
- **Uncompressed Evidence SHA-256:** `51d74c0023e1a585a56e57c3125b096648584575d3dd128005a1cc5f73576f9b`

---

## 1. Execution Status Flags

- `ACE_BASE_RUNTIME_EXECUTED`: **True** (real `ace_runtime.engine.Runtime` SQLite session executed for `M1_exact_reuse`, verifying capability registration and preservation).
- `NEW_CAPABILITY_INTEGRATED_AND_EXECUTED`: **True** (automated bottom-up enumerative synthesis, MDL + probe entropy compression, typed pair functor, and agreement gate integrated into `ace_research_discovery`).
- `SCIENTIFIC_CAPABILITY_VALIDATED`: **False** (H2 failed on amortized AST compute ratio; H7a witnessed passive semantic drift failure).
- `oaie_established`: **False**
- `release_decision`: **BLOCK_RELEASE**

---

## 2. Pre-Registered Hypotheses & Verified Verdicts

| Hypothesis | Metric | Result | Threshold | Status |
|---|---|---|---|---|
| **H1 (Transfer vs Baselines)** | Gain vs $M_0, M_1, M_2$ on $U_{\text{cross}}$ at $B=32$ | $+48.3\%, +50.1\%, +42.5\%$ ($M_5 = 1.000$) | $\ge +20\%$ | **PASS** |
| **H2 (Gain & Compute vs Fresh)** | Gain vs $M_3, M_{3,4\times}$ & amortized AST ratio | $+36.1\%, +22.8\%$, AST ratio = **$1.3401$** | $\ge +15\%, \ge +10\%$, ratio $< 1.0$ | **FAIL (Refuted)** |
| **H3 (Discovered vs Random)** | Gain vs $M_4$ matched random abstractions | $+42.4\%$ | $\ge +20\%$ | **PASS** |
| **H4 (Uncurated Source Filter)** | Invariants recovered / 6; boolean distractor rate | **6 / 6** recovered; **14.3%** distractor rate | $\ge 5 / 6; < 50\%$ | **PASS** |
| **H5 (No Surface Regression)** | $M_5$ vs $M_2$ on $L_{\text{surface}}$ | $0.9969$ vs $1.0000$ (diff $-0.3\%$) | $\ge 0.90$, diff $\ge -5\%$ | **PASS** |
| **H6 (Admission Safety)** | False admission rate on $N_{\text{abstain}}$ | **$0.0000$** (reduction $1.0000$ vs ungated) | rate $\le 0.20$, red $\ge 0.75$ | **PASS** |
| **H7a (Drift Witness)** | Terminal accuracy on $D_{\text{drift}}$ | **$0.0031$** ($86.7\%$ staged) | $\le 0.20$ | **EXPECTED WITNESS** |
| **H7b (Reproducibility & Pins)** | Prescore verified; 25/25 upstream pins intact | Verified; 25/25 match | 25/25 match | **PASS** |

---

## 3. Key Findings & Negative Results

1. **Successful Functorial Transfer:** Typed sub-program discovery from an uncurated mixed pool successfully extracted the 6 tree structural projections ($M_5$ scored 100% on unseen cross-family tasks, outperforming memorization, direct model reuse, and strong fixed features).
2. **H2 Refutation (Compute Accounting):** When amortizing 100% of source synthesis ($C_{\text{source}} = 2000$) across only 15 target tasks, total AST evaluations for $M_5$ exceeded $M_{3,4\times}$ by $34\%$. Cross-family discovery requires higher target task density to achieve net compute break-even.
3. **Semantic Drift Confirmation:** Observational validation and probe agreement cannot detect inverted semantics in unobserved contexts ($H7a$).
