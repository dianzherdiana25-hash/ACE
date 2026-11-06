# ACE — Precommitted Generalization & Baseline Study, executed 2026-11-06

**Classification:** public synthetic methodology development / exact-head source replay. **Scientific status NOT_ASSESSED. Open-world safety FAIL. Release BLOCK_RELEASE. OAIE NOT_ESTABLISHED.** No model deployment, no merge or main/frozen edit.

## Evidence chain

- Prescored before implementation/evaluation: `docs/ACE_CHAT_GENERALIZATION_PRESCORE_20261106.md` committed **`96d714bcf8709c0f88f85ca3254f1cef97eaee18`**. CI proves pre-score ancestry and byte-for-byte protocol immutability.
- Exact actual source baseline: `main` `80104ce50ecbcea21080bed8c0eabce88d47ccb5`, untouched imported `Runtime`, `compositional.fit`, original `dfa`, `counter`, `composition`, `fixed_product` program implementations. CI compares bytes against that SHA, and original `tools/verify_sources.py` passes (25 imported files). This is not a new learning method.
- First CI `42193011436` failed due to evaluator code mistakenly indexing the terminal nested `program_id` at its parent. No evaluation/baseline/threshold changes. Fixed code at **`bea9c7f6cbfaa67bc5522dbe6e3318cf6035cc56`**.
- [Exact-head GitHub Actions #42193104042](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42193104042) **SUCCESS**, 12/12 study and adversarial tests and 14/14 original ACE Runtime tests pass. Two complete byte-identical evaluations plus distinct complete source reexecution verifier return **`PASS_PUBLIC_REPLAY_ONLY`**. `report.json` **102,099 bytes**, SHA256 `d8ad45e3b860956b4f93ba38011a6bcfd9bec3beb4ca1e31af5b0871ad51821d`. GitHub Actions artifact `ace-chat-generalization-public` ID **13490916374**, archive SHA256 `f73bec04788d4c6bc73c7df2e6d177159935d6b199ce9786436f82230ed3b3f5`. Coordinator downloaded ZIP and independently checked the hash and values of all 3 files. Raw data contain per-task program signatures, fit costs, predictions SHA, terminal results, and stage/reject receipts.

## Task and label protocol

4 nominal families × 2 seeds = 8 nominal task instances; plus 2 hidden-rule inversion controls. Training 63 exhaustive binary words of lengths 0–5, validation 128 class-balanced words of lengths 6–15, and terminal 128 class-balanced words of lengths 24–36, each instance. **3,190** public synthetic label presentations overall; 1,280 terminal labels unused for selection, 1,024 terminal predictions in nominal comparison. Distinct lengths prevent train/validation/terminal input overlap. Each trial has its own fresh SQLite workspace, so this measures **independent task admission and length extrapolation, not lifelong retention or cross-family reuse**.

Fixed methods and source selection rules: `dfa` (R1), `counter`, learned `composition` with R1 residual guards, and 35-program author-designed `fixed_product` selected by training/validation. Majority always negative is 50% due to class-balanced terminal. The training/validation procedure is not compute-matched across arm families; full source merge attempts, proposal work, candidate counts, and observed terminal AST work are captured; internal R1 consistency checks are not fully accounted for.

## Results

All arms score the same 1,024 nominal class-balanced terminal labels:

| Arm | Terminal correct | Accuracy |
|---|---:|---:|
| **ACE learned composition** | **900 / 1024** | **87.89%** |
| R1 DFA | 774 / 1024 | 75.59% |
| Strong 35-program fixed-product | 769 / 1024 | 75.10% |
| Counters | 642 / 1024 | 62.70% |
| Always-negative | 512 / 1024 | 50.00% |

Learned composition exceeds fixed-product by **131 correct / 1024**, **12.79 percentage points** on this prescored public benchmark, meeting diagnostic G3 (≥32). This is not statistically validated across independent domains, different task distributions or compute-matched methods.

**Heterogeneous per-family evidence** (each denominator 256 across 2 seeds):

| Family | Composition | Fixed-product | DFA | Counter | Runtime nominal admitted |
|---|---:|---:|---:|---:|---:|
| `ratio3` | 256 | 256 | 134 | 256 | 2/2 |
| `ratio2_boundaries` | **132** | **256** | 128 | 128 | 0/2 |
| `parity_a_odd` | **256** | 128 | 256 | 129 | 2/2 |
| `boundary_same` | **256** | 129 | 256 | 129 | 2/2 |

**Counterexamples matter:** the strong fixed-product baseline decisively wins on `ratio2_boundaries` (256 vs 132); the ACE runtime declines to stage any candidate for this family. Composition's aggregate advantage arises from the regular `parity_a_odd` and `boundary_same` families where DFA already achieves **the same 256/256**. Thus these are **not newly created primitive classes** or uniform generalization supremacy.

Actual runtime `LEARNED_STAGED` occurs on **6/8** nominal worlds; all 6 have 128/128 terminal correctness (768/768) **conditional on admission**. Two fail selection (`NO_VALIDATED_MODEL`); their prediction coverage is zero. Report coverage **75%**, admitted conditional terminal accuracy **100%**; never report only 100% without coverage. These nominal outcomes are favorable because validation-only exact-fit selection filters failures; the shifted controls reveal this filter is not a semantic guarantee.

**Hidden rule inversion:** For each `ratio3` seed, a second world has *exactly the same train and validation labels/words and exactly the same terminal words*, but opposite terminal truth. Runtime stages both hidden controls anyway: **2/2 false safe admissions; 0/128 and 0/128 terminal correct**. Fixed-product, counter and learned composition also get 0/128 on shifted truth. There is no final-output abstention mechanism; hidden semantic changes cannot be logically distinguished by available data. **G4 FAIL, open-world safety unestablished.**

## Predeclared diagnostic gates

| Gate | Verdict | Evidence |
|---|---|---|
| G1: real original ACE source + deterministic executable cohort | PASS | Exact source checksum, 12 tests, 14 runtime tests, full double replay |
| G2: ≥4/8 runtime admissions, every staged ≥90% terminal | PASS | 6 admitted, 768/768 staged-correct |
| G3: composition ≥32 extra correct vs fixed-product | PASS | +131/1024 |
| G4: semantic-shift/open-world safety | **FAIL** | 2/2 false accepted, 0/256 shifted correct |
| G5: source provenance and tamper rejection | PASS within public development | Pre-score locked, canonical JSON identical, strict verifier |

Engineering reproducibility does not imply third-party scientific acceptance.

## Next falsifiable study / admission policy

1. Retest learned composition on **family-disjoint reviewer-owned** tasks with independently generated seeds after method freeze, comparing not only fixed-product but also best source DFA and an equal-budget meta-selector. In this cohort learned composition **ties DFA** on its two biggest winning families, so stronger baseline is essential.
2. Compare on per-family **worst group**, not pooled-only; explicitly require nondegradation vs strong baseline on `ratio2_boundaries` to avoid Goodhart selection.
3. Treat observed **selective prediction and open-world** separately. Conditional 100% accuracy with 75% acceptance is not full-domain performance; on the indistinguishable late-flip control stage confidence fails catastrophically.
4. Close label-cost / actual CPU-work accounting gaps, require independent evaluator custody, preserve negative results. No automatic deployment, merge or claims of OAIE.
