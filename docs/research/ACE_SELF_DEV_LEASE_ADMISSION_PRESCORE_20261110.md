# ACE Self-Development Lease Ownership: preregistered engineering falsification (2026-11-10)

Status: public engineering-only, NOT_ASSESSED, BLOCK_RELEASE, OAIE_NOT_ESTABLISHED.

## Source and scope frozen before mutation
- Base: PR #97 head 1752119003bc8e6f2937bcdb869cfcba38747710, stacked on PR #96/#95/#94; no main merge.
- Source: code/ace_self_dev/state_manager.py, base Git blob 79b754100bb9aedfe4cbad0b81455a04c5eda492.
- Existing counterexample: evidence/w3_admission/unresolved-lock.json (locked_after_wrong_token_release=false).
- Owner: new isolated branch fix/ace-self-dev-lock-lease-20261110.
- Explicit exclusions: no active daemon, actual Termux state, historical receipts, evaluator, frozen E1.4, external AI execution, deployment or main writes.

## Falsifiable hypothesis H1
Given an active lease owned by worker A, calls to StateManager.release_lock() with a different, missing, non-string, or stale token must fail closed and preserve the exact current lock. Valid owner token must still release it, and a no-longer-locked state must retain idempotent release behavior. A stale lease token must not unlock a replacement lease after a new owner acquires it.

Null: at least one invalid-token scenario can still unlock active state, or a valid token is rejected/regresses normal recovery.

## Design and baseline
- Baseline B0: unmodified StateManager behavior. Wrong token silently releases lock after printing a warning, contradicting lease ownership. Existing state-manager continuity tests exercise only correct tokens.
- Intervention I1: replace permissive release branch with strict token ownership check, raising existing ConcurrencyLockError; avoid disclosing the current token in an error/log.
- Test on private tempfile state directories, never on user's checkpoints. No training corpus or test-driven candidate selection; test cases are public regression checks, not scientific confirmation.
- Necessary positive controls: valid owner unlock; cross-instance valid owner unlock; acquiring after correct release.
- Necessary negative controls: wrong string, empty string, None, stale token after lease replacement. Compare state before/after refusal and verify competing worker still blocked.
- Explicit non-goals: serializability of separate concurrent read-modify-write operations, power-loss fsync durability, multi-host locks over NFS and administrative force_unlock authorization. These require a separate design; this slice must not be described as a complete concurrent-state safety proof.

## Resource and evidence plan
Python standard library only, no external AI calls, no labels, financial spend Rp0. Record test names/count, actual CI compute duration and exact SHA. Execute tests in Python 3.12/3.13 GitHub-hosted CI if workflow runs, or disclose absence. Preserve failures; do not claim capabilities from synthetic cases.

## Decision rule
Engineering pass only if all new negative/positive controls and existing self-development unit regressions pass at exact source SHA. Scientific status remains NOT_ASSESSED irrespective of CI result. If tests fail, record fail and keep draft, no merge.
