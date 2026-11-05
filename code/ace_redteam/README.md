# ACE independent internal adversarial tests (RT-01 to RT-05)

Scope: additive only under `code/ace_redteam/`. The base for these tests is PR #27 at `965640786cbf2f8adcd89eb1d980945f78c2da77`, stacking on PR #25. These tests mutate **only temporary directories**, never frozen research banks, other branches, main, Tod, or deployed code.

Run on a clean checkout of PR #27 plus this branch:

```bash
PYTHONPATH=code:. python3 -m unittest ace_redteam.test_adversarial -v
```

On the original E1.5 GitHub `engine.py` blob `4ebef377e730e2e403c1d437903e04a202ac0bea` and `source_evolution.py` blob `8a8c2c729db3072612830c03d7bd1eb0a2371ce9`, the locally reproduced result under Python 3.13.5 was **16 tests, 11 passed, 5 expected failures, 0 unexpected successes**. Exact source Git blob hashes were recomputed from copied bytes and matched both GitHub fetch-file SHA values. This is a faithful, local source reproduction, **not an execution by GitHub Actions on the new red-team branch**. The existing PR #27 workflow filters only `code/ace_loop/**` and runs only the original 46 tests; changes exclusively within `code/ace_redteam/**` do not trigger it. No CI workflow was changed under the red-team ownership boundary.

## Reproduced deficiencies (known expected failures)

| ID | Location | Impact | Minimal repro |
|---|---|---|---|
| RT-01 | `code/ace_loop/engine.py`, `HashLedger.append()` | **P1**: `flock(fd)` locks the original inode, while `_read()` reopens by pathname; replacing that path after verification makes the append acknowledge an event absent from the active journal. | `test_rt01_ledger_path_swap_after_lock_must_not_ack_lost_receipt`; deterministic rename/recreate after `_read` within a temporary directory. |
| RT-02 | `code/ace_loop/source_evolution.py`, `SourceEvolution._expected()` | **P1**: two valid chained `trial` events with no `decision` pass replay; state-machine semantic integrity is incomplete. | `test_rt02_replay_must_reject_two_unpaired_trials`; append two correctly scored and hashed trials and reopen. |
| RT-03 | `code/ace_loop/source_evolution.py`, `SourceEvolution.__init__()` | **P2**: symlinks on a grandparent/ancestor, not immediate parent, redirect staging and journal paths. | `test_rt03_ancestor_symlink_must_not_redirect_run_root`; alias to sandbox directory, then nested root under alias. |
| RT-04 | `code/ace_loop/source_evolution.py`, `SourceEvolution.run()` / `_terminal()` | **P1**, conditional on untrusted in-process code being allowed: modify `controller.bank['holdout']` after manifest construction and before terminal evaluation; the current instance records corrupted holdout data without a digest check. A new clean instance can detect a mismatch on replay. | `test_rt04_mutated_holdout_bank_must_halt_before_terminal_receipt`. |
| RT-05 | `code/ace_loop/source_evolution.py`, `interpret()` | **P2**, API boundary: direct call with unvalidated `ast.Pow()` returns multiplication rather than rejecting unknown op. This is **not** an exploit of normal `score()` since `parse_source()` validates first. | `test_rt05_interpreter_must_reject_unvalidated_operation`. |

`@unittest.expectedFailure` is deliberate: each asserts a desired safety property that does **not** currently hold. These 5 cases are NOT passes and should remain visible until a core owner independently fixes them; after a fix, remove the decorator and rerun (unexpected success currently fails unittest). This red-team lane must not fix implementation code itself.

## Protections that passed

- Pause/resume journal matches uninterrupted runs byte-for-byte; completed replay is idempotent.
- Recovery from a recorded-but-undecided trial produces exactly one decision.
- Forged decision and terminal payloads are rejected even after recomputing the full SHA chain.
- Modified or symlinked staged source is rejected on fresh open; missing staged source can be recreated without new events.
- The normal partial run never calls holdout scoring; nevertheless the public synthetic bank is not externally sealed.
- A second stale `HashLedger` snapshot cannot append conflicting events.
- A truncated JSONL record halts; it does **not** automatically repair the journal.
- Calls/imports/attributes/power expressions are rejected by the source parser.

## Unverified / further red-team gates

The new suite is local and single-host. It does not prove behavior under power failure, full multiprocess stress, network filesystems, malicious untrusted candidate execution, memory isolation, persistent independent holdout custody, complete repository regression, or scientifically independent replication. It does not change the project's `NOT_ASSESSED` status. It does not change the project's `NOT_ASSESSED` status. Run this suite in the designated trusted CI/reviewer environment before any source-mutating or autonomous deployment stage, and verify hardening at exact HEAD after future code changes. Focus fixes on journal file identity verification and directory locking, a strict alternating event state machine, trusted path resolution/openat controls, evaluator-owned immutable holdout, and AST revalidation at API boundaries.
