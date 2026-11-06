# ACE Main Coordinator — independent H7 grammar-limit and measurement-trap evaluation

**Date:** 2026-11-06. **Status:** Public synthetic development, scientific `NOT_ASSESSED`, unconditional `OPEN_WORLD_HOLD`, NO MERGE / NO PROMOTION. This extends PR #50 without changing R1, R7, R8, E1.4 or `main`.

## Chronological custody

- [Pre-score protocol](ACE_RESEARCH_INTAKE_H7_PRESCORE_V1.md) written to coordinator Git commit `e4280bb3ebf4372a4ee69834e55dd0c8085b68b6` **before** H7 coordinator source, tests and new scoring. CI verifies the protocol bytes are identical to this parent commit.
- Frozen R1 H7 implementation and H6 base source from PR #38 at **exact** SHA `8952c8ac55613e61b362841f4722c66a5aa990b3`. Neither was edited. The coordinator independently authored target generator, score screen, controls and separate balanced terminal evaluation.
- [GitHub Actions #42150392422](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42150392422) exact coordinator source HEAD `44d4fe62b0fa212bbfe7c7bdcb9f165eaf98b928`: H7 source/coordination **28/28 tests PASS**, whole experiment run twice with byte-identical JSON. R1 old pinned high-state and R8 public null canary jobs in the same workflow also PASS.
- SHA256 `6cbd2d5ff2b2894bf0cca6e3cd328f28800ccbff5631331371c9f0759590b000` of complete **74,096-byte** canonical result JSON. Independent GitHub Actions artifact `ace-r1-h7-independent-crossclass`, ID `13472062586`, ZIP SHA256 `7bbecb3ad0cfba8eb7658769f1ef1ea9e2514797969f49590335e648d64664e7`; both data and short summary stored there. Archive bytes were separately downloaded, unzipped and the JSON SHA256 matched in coordinator review.

## Design and actual outcomes

24 worlds: four H7 base functions × two feature patterns per target length 5/6/7. Pattern seeds are independent of H7's H7 training-bank generator. Only syntax (`>=2 a`, `>=2 b`) filters targets; no target-label or model-success filtering. For each task 128 train query labels, 128 disjoint validation labels, 256 natural terminal and 256 **feature-balanced** terminal labels. Terminal balanced sample is intentionally selected 128 containing and 128 non-containing *target strings*, strictly evaluator-only, not used by any feature proposal. Total 18,432 task-specific synthetic oracle judgments, 6,144 of them query/validation and 12,288 terminal reporting. All query and terminal strings disjoint.

| Target substring length | H7 new-feature acceptance | H7 balanced correct | H7 natural correct | Expanded 2..7 class: acceptance | Expanded balanced correct |
|---|---:|---:|---:|---:|---:|
| 5 (within H7 2..5 grammar) | 8/8 | 2048/2048 = **100%** | 2048/2048 = 100% | 8/8 | 2048/2048 = 100% |
| 6 (outside H7 grammar) | 0/8 | 1024/2048 = **50%** | 1723/2048 = **84.13%** | 8/8 | 2048/2048 = **100%** |
| 7 (outside H7 grammar) | 0/8 | 1024/2048 = **50%** | 1910/2048 = **93.26%** | 7/8 | 1920/2048 = **93.75%** |

- **G1 PASS:** all 8 new five-character target patterns induced and score 100% on *balanced* terminal strings. The R1 hand-authored substring grammar generalizes within this known representation class, not to new primitive classes.
- **G2 PASS within THIS public bank:** all 16 out-of-grammar tasks decline to accept a new feature; none falsely accepts a feature with balanced accuracy below 90%. However H7 still issues **8,192 forced predictions** across 16×512 terminal observations, since it falls back to the base. *No new feature* is NOT an actual final-prediction abstention.
- **G3 PASS as diagnostic only:** an expanded 2..7 substring class, fitted on exactly the same 128+128 labels, solves 15/16 outclass targets perfectly. The lone failure is `a_mod3 / aabaaba` length7, with **two training residual positives and one validation positive**, below the prespecified two-validation-positive support gate. Expanded search has a larger grammar permitting up to 254 candidates (at most 252 distinct binary 2..7-grams) vs H7's at most 60: **compute is NOT matched** and the same author-designed substrate is reused. Do not interpret this as an independently better intelligence algorithm.
- **G4 FAIL / OPEN_WORLD_HOLD:** the unchanged H7 API returns forced binary final outputs on all 12,288 reported terminal predictions, with zero semantic abstentions. Worlds identical on observed query lengths and opposite on longer inputs cannot be distinguished by any of these observations alone. A different counterexample can always defeat an unqualified extrapolation claim.
- **Critical measurement trap:** H7 had no learned length-7 residual feature but scored **93.26% natural-input accuracy**, compared with **50% on matched target-balanced inputs**. Reporting the natural number alone would falsely imply generalization. This is a concrete method-validity/Goodhart warning relevant to R8, *not* a replay of R8's growth-gate source.

One positive control: R1 H7's five-character performance is a genuine measured restricted-domain success. One negative result: H7's ability cannot extend outside its strict substring-length grammar without an enlarged hypothesis class. The expanded diagnostic shows representation capacity is a binding obstacle on 15 of 16 tasks, although query support constrains one length-7 case.

## Scientific interpretation and integration decision

**ENGINEERING REPRODUCIBILITY: PASS scoped. RESTRICTED FEATURE CONSTRUCTION: SUPPORTED (5-grams). CROSS-CLASS ADAPTATION: NOT SUPPORTED. SEMANTIC OOD SAFETY: NOT ESTABLISHED. SCIENTIFIC GO: NOT_ASSESSED. OAIE: NOT_ESTABLISHED.**

This is a coordinator-designed *public synthetic* evaluator with source-visible world generation, target-feature balancing during **evaluation only**, privileged correct base mechanism and a hand-authored expanded diagnostic class. It is not a third-party sealed benchmark; the full research team has now seen these tasks. These words/seeds must never be reused as an independent blind test after tuning.

**Next source-owner handoffs:** R1 should predeclare a way to create hypothesis-*class structure*, not simply increase the maximum known substring length; evaluate on non-substring grammatical dependencies with matched true compute and label budgets. R7 should distinguish prediction abstention from mere feature-proposal refusal and calibrate safety/cost under distribution shift. R8 should make class-balanced, novelty-disjoint, evaluator-custodied metrics mandatory in any growth gate; natural accuracy high at 93.26% can coexist with balanced random-guess performance. Red Team should attack target/validation leakage and wrong-sign or false semantic confidence. All require new disjoint evidence; no merge to `main`.
