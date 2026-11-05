# ACE E1.5 — executable bounded research loop (2026-11-05)

**Delivered:** a runnable Python research controller and a two-track evidence-directed budget allocator. This is an engineering **vertical slice**, not a finished general autonomous intelligence system. Built after inspecting E1.4aa Codex HEAD and atop the research/recovery stack; all frozen E1.4t/E1.4aa scoring sources remain unmodified. No `main` merge, no Tod changes, no paid infrastructure.

## What now executes

1. **Lock a typed, deterministic public bank** of E1.4y operator worlds: 24 train, 12 disjoint validation, 18 disjoint heldout; optional two unrepresented operators per split. All task and policy identities, grammar signatures and oracle module SHA256 are recorded in the run config. No sealed E1.3 or private evaluator contents are used.
2. **Propose 12 finite policy hypotheses** (fixed, active, random query selection; 1–4 simulated label acquisitions; explicit evidence count). Candidates are typed data, never arbitrary executable code. Their only observations are labels from purchased synthetic coordinates.
3. **Evaluate and decide automatically.** Training results and independent validation results are recorded. A policy replaces the incumbent only when validation utility strictly increases AND the count of false acceptances does not increase. Every rejected hypothesis is preserved. Stop when capped or unproductive; do not grant a research conclusion after a local test pass.
4. **Commit a deterministic durable event chain.** Every config, trial, decision, and terminal result is appended as canonical SHA256 JSON with `fsync` and a POSIX `flock`; conflicting writers, tampered rows (including digest-rehashed malicious decisions), truncated entries, changed bank/protocol, premature completion and replay score mismatches cause explicit failure. A pause resumes from the persisted trial without repeating the event. No automatic retry of an external paid oracle is possible; this adapter uses a pure local simulator only.
5. **Evaluate holdout only after proposal selection.** Both predeclared baseline and selected policy are evaluated for comparative scoring in a terminal event. Their scores can be recomputed for integrity checks on restart; the test split never influences candidate selection. No postscore tuning against this test is authorized.
6. **Reallocate research effort between two tracks.** Both a grammar-complete development task and a mixed out-of-grammar task receive eight pilot policy trials. The controller compares validation improvement, allocates four further trials to the more promising track, and leaves the other track frozen at its checkpoint. A corrupted/forged portfolio allocation causes an explicit stop. No background execution or cloud scheduler exists.

## Reproduction

```bash
PYTHONPATH=code:. python3 -m unittest ace_loop.test_engine ace_loop.test_portfolio -q
PYTHONPATH=code:. python3 -m ace_loop.cli run --root WORK/e15-infamily --cycles 12 --patience 12 --outsiders-per-split 0
PYTHONPATH=code:. python3 -m ace_loop.cli run --root WORK/e15-mixed --cycles 12 --patience 12 --outsiders-per-split 2
PYTHONPATH=code:. python3 -m ace_loop.cli portfolio --root WORK/e15-portfolio --cycles 12 --pilot-trials 8
PYTHONPATH=code:. python3 -m ace_loop.cli portfolio --root WORK/e15-portfolio --cycles 12 --pilot-trials 8
```

## Actual corrected public-development outputs

| Research track | Validation incumbent | Validation selected | Heldout baseline utility | Heldout selected utility | Decision |
|---|---:|---:|---:|---:|---|
| In-family | -36 (0/12 correct) | +6 (3/12 correct) | -54 (0/18 correct) | -67 (1/18 correct) | `NO_VALIDATED_GAIN` on heldout; do not promote broadly |
| Mixed with unseen operator types | -36 | -36 (no safe adoption) | -54 | -54 | No improvement; stop/reallocate |

The 12-hypothesis search makes **no claim of invented operator syntax or automatic architecture revision**. The in-family selected policy has worse holdout utility (-13) despite improved validation (+42), a **negative generalization finding**. The terminal gate sets `candidate_policy_promoted=false` and `deployment_decision=REVERT_TYPED_POLICY_TO_BASELINE`; this is a policy-state decision, not a claim that any live service or source code was deployed or rolled back. In the portfolio pilot the validation gain was +42 for in-family and 0 for mixed; the controller selected the in-family track and preserved the mixed checkpoint unchanged. Two back-to-back portfolio invocations reproduced identical JSON results and no additional events.

## Tests and known limitations

- E1.5 tests: **32/32 PASS** (`ace_loop.test_engine` and `ace_loop.test_portfolio`) on compatible local Python 3.13.5, including resume/idempotence/complete tamper with recomputed chain hashes, concurrent writer rejection, pilot allocation tampering, and holdout gating.
- Related E1.4 regression: **82/82 PASS** on compatible partial workspace (`e14.test_e14y_induction`, `e14.test_e14y_audit`, `e14.test_e14z_drift`, `e14.test_e14z_audit`, `e14.test_e14_integrated_graph`, `e14.test_e14_integrated_policy`). Total **114/114 targeted compatible tests**. These are not a clean exact-HEAD full-repository regression and do not certify Bubblewrap.
- All purchases are **synthetic logical labels**, not actual remote oracle calls. No external action exactly-once semantics, human approval workflow, dependency manager, autoresearch in the background, model training, program-code mutation, novel architecture successor, or OAIE exists here.
- A future isolated backend must use evaluator-owned explicit paid receipts and an independently tested threat model. Do not send untrusted generated programs to a Python interpreter. Confirmatory bank must be held out under separate custody, not this author-visible public development set.

**Scientific decision:** `NOT_ASSESSED`, no OAIE. **Engineering result:** runnable finite research controller / controlled self-optimization of typed strategy settings, explicit stop on false evidence, demonstrated cross-task resource reallocation, crash-safe local continuation. This moves ACE beyond disconnected scoring scripts but does not complete the broader vision.
