# ACE M1 — Fenced SQLite store: public engineering protocol (2026-11-10)

Base source: PR #99 head `61553d33024c490ba47294f83fbffe842790893e`. This branch is experimental, separate from `research/ace-atomic-self-dev-state-20261110`.

## Scope and provenance

This is **not a scientific preregistration**: a local exploratory pilot of 13 development tests ran before this document was committed. Preserve that provenance. Future unseen cases must be recorded independently before inspection.

Existing `code/ace_self_dev/state_manager.py` uses `load_state() -> _atomic_save()` with an unguarded JSON read/modify/write, and PR #98 adds owner-token checks only. An atomic rename does not serialize competing read/modify/write transactions. The hypothesis is that a separate SQLite store using `BEGIN IMMEDIATE` and persistent monotonically increasing epoch reduces concurrent lease admission failures **only when all protected mutations use that store**.

## Public acceptance cases

1. Ten distinct OS processes simultaneously acquire one job; no more than one wins.
2. Epoch increments after release/restart and after expiry takeover.
3. Stale token/epoch never releases, renews or writes another worker's job.
4. Receiver-visible receipt, checkpoint, and outbox item commit in one transaction; simulated aborted outbox insert leaves no partial state.
5. Replay of identical event ID and body is idempotent; altered body with the same event ID is rejected.
6. A subprocess forcibly exiting during an uncommitted transaction does not persist that increment.
7. Corrupt database causes explicit failure, not silent reset.
8. Source and tests run with no network requests, secrets, model inference, or code execution of proposed patches.

## Explicit non-goals and blockers

The new store is **not integrated** into legacy JSON `StateManager`, `SelfDevelopmentCoordinator`, Termux daemon, or GitHub mutation. A fencing epoch has no effect on an external API unless that API's action is itself gated or protected by a hash-pinned compare-and-swap. No claim of filesystem crash survival, SIGKILL reliability on Redmi 14C, correct handling of wall-clock rollback before new ownership, real disk-full injection, production migration, 1,000 race repetitions, or independent science is supported here. Status remains `M1_PARTIAL`, `BLOCK_RELEASE`, `NOT_ASSESSED`.

The tests are development regressions, not hidden holdout. Later evaluations must establish multi-worker correctness, migration, independent replay, negative controls, crash/restart on actual Termux, and external Git fencing before enabling autonomous self-modification.

## Sources

- SQLite transaction isolation: https://www.sqlite.org/isolation.html
- SQLite WAL limitations: https://www.sqlite.org/wal.html
- SQLite transactions and fault handling: https://www.sqlite.org/lang_transaction.html
- Termux app Android 12+ process warning: https://github.com/termux/termux-app/blob/master/README.md
