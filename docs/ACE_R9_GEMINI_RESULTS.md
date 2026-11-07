# ACE R9 (Gemini lane) — learned-feature representation transfer: RESULTS

2026-11-06. PUBLIC SYNTHETIC DEVELOPMENT; scientific **NOT_ASSESSED**.
Release gate: **BLOCK_RELEASE**. Open-world safety: **FAIL** (H6). OAIE: **NOT_ESTABLISHED**.
Zero candidate deployments. No merge to `main`.

Pre-registration committed at `3d4be019708b4efcfd720179b6cd2f50dfe0f1b5` (Issue #63 mandate).
Unchanged imported source verified against `docs/UPSTREAM_SOURCES.json` (25/25 files match).

- Raw uncompressed report: 574,834 bytes, SHA-256 `1f8f5836b79a811c6413879823ca6f21f6def998b4944d72f46f6bd697412d91`.
- Committed artifact: `evidence/reptransfer/r9_gemini_v1.json.gz`, SHA-256 `f229ed0e66214e004d10f591d0e4cd4f53e63f0c75cf8becd9f7c29119b27b44`.
- Replay: two independent runs are **byte-identical** (`cmp` exits 0). Full independent verifier `ace_research_reptransfer.verify` **PASS**.

## Summary of pre-registered hypotheses

| Hypothesis | Condition | Observed | Status |
|---|---|---|---|
| **H1 (Transfer, U)** | `M_A − max(M_B, M_C) ≥ 0.15` and beats by ≥ 0.05 on ≥ 4/6 U tasks | **+0.8737** gain (0.9805 vs 0.1068); beats on **6/6 tasks** | **PASS** |
| **H2 (Source causality, U)** | `M_A − M_A0 ≥ 0.15` | **+0.9170** gain (0.9805 vs 0.0635) | **PASS** |
| **H3 (No regression, L)** | `M_A ≥ M_C − 0.05` | 0.9911 vs 0.9911 (**diff 0.0000**) | **PASS** |
| **H4 (Sample efficiency, U)** | Smallest B with `M ≥ 0.80` is ≤ half B's, or B never reaches it | B reaches max 0.0305; A reaches **0.9557 at B=16** | **PASS** |
| **H5 (Admission safety, N)** | False admissions of A on N ≤ max(B, C) | A = 0, B = 0, C = 0 | **PASS** |
| **H6 (Drift safety, D)** | Zero false-accepts under inverted terminal truth | A falsely accepts **9/10** units | **FAIL** (predicted) |
| **H7 (Feature recovery, U)** | `M_A ≥ M_C2 − 0.10` | 0.9805 vs 0.9656 (**+0.0149**) | **PASS** |
| **Gate G (H1 ∧ H2 ∧ H3 ∧ H5 ∧ H7)** | All 5 pass | All 5 pass | **PASS** (as public diagnostic) |

## Slice tables (mean M_score, coverage)

`M` = terminal accuracy among admitted, **0 on abstention**. Terminal evaluation: 128 balanced strings, length 16–30.
Budgets: B=16 (8 tr / 8 val), B=32 (16 tr / 16 val), B=64 (32 tr / 32 val).

### Primary target stratum U (not expressible by base hand library C; 6 tasks × 5 seeds = 30 units per budget)

| Budget | A (learned) | A0 (irrelevant) | B (fresh R1) | C (base hand) | C2 (extended hand) | Cov(A) |
|---|---:|---:|---:|---:|---:|---:|
| B = 16 | **0.9557** | 0.1417 | 0.0305 | 0.3013 | 0.9125 | 100% |
| **B = 32** | **0.9805** | 0.0635 | 0.0169 | 0.1068 | 0.9656 | 100% |
| B = 64 | **1.0000** | 0.0315 | 0.0000 | 0.0315 | 0.9982 | 100% |

### Stratum L (expressible by C; 3 tasks × 5 seeds = 15 units per budget)

| Budget | A | A0 | B | C | C2 | Cov(A) |
|---|---:|---:|---:|---:|---:|---:|
| B = 16 | 0.9354 | 0.1729 | 0.0578 | 0.9172 | 0.8995 | 100% |
| **B = 32** | **0.9911** | 0.0000 | 0.0000 | **0.9911** | 0.9911 | 100% |
| B = 64 | 1.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 100% |

### Stratum N (non-regular targets: equal counts, Dyck; 2 tasks × 5 seeds = 10 units per budget)

| Budget | A | A0 | B | C | C2 | Cov(A) |
|---|---:|---:|---:|---:|---:|---:|
| B = 16 | 0.1141 | 0.1070 | 0.0000 | 0.4344 | 0.5484 | 20% |
| **B = 32** | **0.0000** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | **0%** |
| B = 64 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | **0%** |

At B ≥ 32, A correctly **abstains 100%** on N (zero coverage, zero false admission).

## Per-task gains on U at primary budget B=32

| Task | Rule | A | Best baseline (C) | Gain |
|---|---|---:|---:|---:|
| U1 | `ca%4==2 AND ends 'ba'` | 0.9375 | 0.5312 | +0.4062 |
| U2 | `cb%4==1 AND starts 'bb'` | 1.0000 | 0.0000 | +1.0000 |
| U3 | `ca%4==1 XOR ends 'ba'` | 1.0000 | 0.0000 | +1.0000 |
| U4 | `cb%4==3 OR contains 'aab'` | 1.0000 | 0.0000 | +1.0000 |
| U5 | `ca%4==3 AND cb%4==2` | 0.9453 | 0.1094 | +0.8359 |
| U6 | `cb%4==2 XOR starts 'bb'` | 1.0000 | 0.0000 | +1.0000 |

## Compute accounting (primary budget B=32, U)

| Metric | A (learned) | B (fresh R1) | C (base hand) | C2 (extended hand) |
|---|---:|---:|---:|---:|
| Hypotheses evaluated per unit | 352 | n/a (RPNI search) | 5,050 | 11,026 |
| Target fit symbol reads (mean) | 55,296 | 4,288 | 792,864 | 1,729,668 |
| Source pretraining merge attempts | 107 (total across 7 sources) | 0 | 0 (hand-authored) | 0 (hand-authored) |
| Target R1 merge attempts | 0 | 17 (mean) | 0 | 0 |

A requires **~14× fewer symbol reads** than base hand library C and **~31× fewer** than extended hand C2,
because the learned dictionary has 26 state-features vs 100 in C and 148 in C2.

## Negative outcomes and critical limitations (declared)

1. **H6 FAIL — Open-World Safety remains completely broken.** Under identical train/val labels where the
   terminal rule is secretly complemented, A falsely accepts 9/10 units (mean terminal accuracy 0.00%
   on those units). Exactly as proven in PR #60/#62, no observational-only method can detect an unobserved
   shift from identical data.
2. **Sources were selected with target atoms in mind.** The researcher chose sources that contain mod-4,
   `ends 'ba'`, `starts 'bb'`, etc. A demonstrates *compositional transfer of learned features*, NOT
   open-ended discovery of what sources to learn.
3. **Mod ≥ 5 counters are not discoverable under this source regime.** As logged in the pre-registration,
   R1 on length ≤ 5 strings failed source admission for `ca%5==0` (2,010 validation errors). The mechanism
   is strictly bounded by the underlying primitive learner's identification limit.
4. **Public synthetic benchmark.** Same alphabet, author-designed targets, no external sealed evaluator.
   Scientific status remains **NOT_ASSESSED**.

## Engineering acceptance

- 8 new unit tests in `ace_research_reptransfer.test_reptransfer` PASS in < 1s.
- 109 existing baseline tests + source blob verification PASS without change.
- No modifications to `code/ace_runtime/`, `main`, or other agents' branches.
- Workflow `.github/workflows/ace-gemini-r9.yml` added for CI reproduction.
