# ACE Cross-family Transfer v1 — actual executed negative result (2026-11-06)

**Scientific NOT_ASSESSED; H1 REJECTED; H2 REJECTED; OPEN-WORLD SAFETY FAIL; RELEASE BLOCK_RELEASE; OAIE NOT_ESTABLISHED.**

## Evidence

- Pre-score committed **`37706b8b86121f2052de08c14e4f09285830901a`** before code/outcomes. Stacked draft PR #62 on PR #60, no changes to main, core ACE, frozen E1.4, Tod, other agents.
- Original runtime source fixed at **`80104ce50ecbcea21080bed8c0eabce88d47ccb5`**; GitHub CI compares original bytes and runs source-integrity verification.
- First run #42240904108 failed Python syntax parsing in evaluator regression predicate, repaired at `8983d20aa374b24c05dd949945506e4e92031e1c`; no prescore/baseline changes.
- [Actual exact-head Actions #42240984060](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42240984060) **SUCCESS**: 13/13 study/tamper tests and 14/14 source runtime tests; complete deterministic experiment executed **four times** (tests, two direct runs, full replay verifier), byte-identical; `PASS_PUBLIC_REPLAY_ONLY`. Raw `report.json` **809,860 bytes**, SHA256 **`2212b1021e5ce93d6375b30cd32b30dc988ac87355996d011a038fc9892573af`**. ZIP artifact **13516295145**, SHA256 **`7dd2007b016ec567ca1d1be2a5ba308459e9a3a975fc3853027b7dc278e851b0`**. Downloaded ZIP checked against source log; 3 files and model receipts inspected.

## Protocol and results

**16 nominal family-disjoint target comparisons**: eight four-family sequences (cyclic orders, two seeds) and eight distinct family pairs, each target compared against **fresh isolated ACE Runtime** using identical 63 training +128 validation +128 length-24..36 terminal labels. Runtime persists library within each sequence and is reopened to verify event chain/SQLite durability. No target terminal label enters training/selection. Four existing families: `ratio3`, `ratio2_boundaries`, `parity_a_odd`, `boundary_same`. Note these are different task *rules* but the **same binary string domain**, not real cross-domain generalization.

| Outcome | Retained cross-family library | Fresh ACE baseline |
|---|---:|---:|
| Nominal target tasks | 16 | 16 |
| Accepted/staged targets | 12 | 12 |
| Total correct (zero coverage for 4 rejected) | **1536/2048** | **1536/2048** |
| Fresh-fit calls avoided by retained library | **0** | n/a |
| Coverage or accuracy regressions | **0** | baseline |

**H1 REJECTED:** none of the 16 targets achieved `REUSE_VALIDATED`. All 12 accepted targets used `LEARNED_STAGED`; all four `ratio2_boundaries` targets had `NO_VALIDATED_MODEL`. Source model memory was persisted, but it did not enable cross-family zero-fit transfer. The baseline was equally accurate. There is no evidence of saved CPU, label or compute cost; `learning_called` remains true on all target trials. The total 1536/2048 is 75% of nominal terminal labels if rejected targets are scored as zero coverage; conditional accuracy is 1536/1536=100%, but coverage only 12/16=75%.

**H2 REJECTED:** two `ratio3→ratio3_late_flip` controls share exactly the same train/validation labels and terminal words but invert terminal truth. Runtime `REUSE_VALIDATED` both, with **0/128 correct each**. This is false semantic transfer despite perfect observational validation, and demonstrates that nominal exact-fit reuse is **not safe against unobserved semantic drift**. Such hidden changes are logically unidentifiable from unchanged observed data, not a problem solved by raising validation thresholds alone.

## Limitations and next mechanism

- All public synthetic strings; source grammar fixed, four rules in same alphabet, no independent sealed evaluator, no compute matching or CPU timing; no novel primitive discovered.
- Next experiment should test **feature-level reusable structure** instead of exact-program identity: learn task-agnostic representations from source data, transfer representation to new target while refitting only a small head, and compare to equally budgeted *fresh* and *hand-authored feature library* controls. Precommit family-disjoint task splits, held-out transfer targets and adaptation-label budgets; require real sample efficiency rather than model fingerprint reuse.
- Need a shift-aware abstention or environment-change evidence acquisition policy. Identical observed data cannot certify a changed terminal rule, so enforce explicit unknown/abstain under unsupported distribution shift and audit coverage tradeoff.

Engineering CI PASS, science NOT_ASSESSED, release BLOCK_RELEASE; PR remains draft.
