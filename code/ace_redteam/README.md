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

The new suite is local and single-host. It does not prove behavior under power failure, full multiprocess stress, network filesystems, malicious untrusted candidate execution, memory isolation, persistent independent holdout custody, complete repository regression, or scientifically independent replication. It does not change the project's `NOT_ASSESSED` status. Run this suite in the designated trusted CI/reviewer environment before any source-mutating or autonomous deployment stage, and verify hardening at exact HEAD after future code changes. Focus fixes on journal file identity verification and directory locking, a strict alternating event state machine, trusted path resolution/openat controls, evaluator-owned immutable holdout, and AST revalidation at API boundaries.

## Second adversarial pass — 2026-11-05

Additional reproducible tests are in `test_adversarial_v2.py` (six tests: four known expected failures, two positive controls; plus one portfolio negative-path test in `test_portfolio_redteam.py`). Local test suite with portfolio addition: **23 tests, 13 safety controls PASS, 10 documented expected failures**, zero errors, zero unexpected successes. Executed twice under Python 3.13.5 on exact GitHub source blobs for `engine.py` and `source_evolution.py`; both runs agreed on normalized outcomes. The original `portfolio.py` Git blob `274fb494e127a25c7b5ecf4523e246fdf0f23501` was also verified in the local reproduction. The locally executed v2/portfolio test modules were semantically equivalent to their uploaded GitHub versions but not byte-identical due to comment/format changes. **This is not a GitHub Actions run**, nor complete independent scientific evaluation.

- **RT-06 / P1 — Shared-object concurrency corrupts a journal:** `HashLedger.append` builds the next sequence number outside the lock and updates `self.events` after unlocking. A deterministic two-thread schedule can make both appends return success while writing duplicate sequence numbers, preventing replay. `test_rt06_same_object_thread_race_must_not_corrupt_journal` uses a synchronized `os.open` hook and only temporary directories.
- **RT-07 / P1 — Valid-prefix rollback repeats terminal holdout evaluation:** remove only a completed-event line, leaving a valid SHA256 prefix. `ResearchEngine` reopens and re-completes, querying `test` twice again (test read count **2 → 4**) and regenerating a byte-identical terminal journal. The missing property is an externally anchored durable chain head/terminal record. `test_rt07_valid_prefix_rollback_must_not_repeat_holdout`.
- **RT-08 / P2 — Staged FIFO permits indefinite resume hang:** replacing `staged_candidate.py` with a FIFO causes `SourceEvolution._verify` to block inside `read_bytes()` on reopen. Confirmed by a subprocess with a two-second timeout. `test_rt08_staged_fifo_must_reject_without_hanging`.
- **RT-09 / P3 — Generic type parameters are not rejected:** `parse_source('def predict[T](x, y): ...')` accepts Python 3.13 `FunctionDef.type_params` even though the documented accepted signature is plain `def predict(x, y)`. A direct API surface mismatch, not a demonstrated execution escape. `test_rt09_generic_type_params_must_be_rejected_by_parser`.

Positive controls: intentionally short `os.write` is detected and preserved as truncated evidence (fail closed); zero-trial pause is inert and recovers. Repro:

```bash
PYTHONPATH=code:. python3 -m unittest ace_redteam.test_adversarial ace_redteam.test_adversarial_v2 -v
```

**Red-team disposition:** Keep self-improvement deployments/source mutation in HOLD until core owners address journal race, rollback anchoring, external file identity, trusted evaluator custody, and safe staging file types. No core fixes in this PR; no promotion, merge, or change to frozen research. An independent CI runner must execute this exact PR HEAD and check the nine assertions after core repairs.

### Third negative-path discovery

- **RT-10 / P2 — Valid no-gain portfolio allocation cannot resume:** `run_portfolio` correctly records a fully valid allocation with `selected: null` when no track has positive validation gain; replay then fails in `if selected not in engines: raise ResearchIntegrityError('unknown allocated track')`. Reproduced on GitHub-exact `portfolio.py` using a deterministic, constant-score `OperatorAdapter` stub only (the production E1.4 oracle need not be changed). First run returns `all_tracks_paused_no_gain`; second raises the specified integrity error. See `test_portfolio_redteam.py`. This is an engine liveness/false integrity alarm on an explicitly supported negative-evidence branch, not a demonstrated data corruption.

Combined **23 tests / 13 controls PASS / 10 known expected failures**. Two local repeat executions produced matching failure identities. The new red-team tests have **not** run in GitHub Actions; exact source bytes (engine, source_evolution, portfolio) were checked against GitHub and the proposed test files were uploaded separately. No merge or changes outside `code/ace_redteam/`.

```bash
PYTHONPATH=code:. python3 -m unittest ace_redteam.test_adversarial ace_redteam.test_adversarial_v2 ace_redteam.test_portfolio_redteam -v
```
