# ACE Next Evolution — atomic self-development state protocol

Registered before reproduction/scoring and implementation, 2026-11-10.

## Source and interpretation

- Blueprint read in full: 342 lines, 23,915 bytes; SHA-256 `b7209f282354355fd0f48a273f535fdca98907ce0a2efde8727fd6f27e73ceda` (matches requested version).
- Audited main: `c55e2b8f83ae4aa37236af2a1a685911e6ad8599`; no workflow runs at that exact main SHA. Its message includes `[skip ci]`.
- Base: PR #98 `b72c18b856cccd8cb8a46a86e15b128be42701b3`, stacked on open draft #97 → #96 → #95 → #94 → `ace-termux-20261110`. All five PRs were open drafts when inspected. #98's existing Python 3.12/3.13 full-system run succeeds; it tests token ownership, not process atomicity.
- Work branch: `research/ace-atomic-self-dev-state-20261110`. No edits to another branch, main, frozen sources, evaluators, historical evidence, or active Android state.

## Falsifiable engineering hypotheses

H1: cooperating StateManager processes serialize the complete lease read/check/write operation. At most one process owns an unexpired lease. Refutation: two successful acquisitions before release/expiry, lost state, or a shared-temporary-file race.

H2: a cycle commit with a missing, wrong, released, or expired owner token cannot mutate a currently leased state; the current coordinator passes its token. Refutation: stale worker changes completed_cycles/digest/lease, or legitimate owner cannot commit.

H3: the coordinator holds an OS-backed transaction guard across a complete cycle, including checkpoint/evidence writes. A competing cooperating coordinator cannot overlap that cycle even if the logical TTL expires. Process death releases the OS guard; the persisted logical lease still requires expiry or explicit administrative recovery. Refutation: overlapping guarded critical sections, lock never released after kill, or successful stale commit.

H4: interrupted atomic JSON replacement leaves the previous or next complete primary state; repeat cycle recording with the same identity is idempotent and conflicting/out-of-order records fail closed. Refutation: invalid primary JSON, missing old negative evidence, or duplicate/conflicting completed records.

## Design decision and reuse

Retain StateManager, PersistentResearchState, coordinator, JSON paths/schema and existing recovery/negative catalog; use the stdlib POSIX flock pattern already present in ace_autonomy.core. Serialize all StateManager reads/initialization/recovery/mutations using one stable sidecar inode, with bounded nonblocking acquisition. Nesting on the same instance uses a thread RLock. Use unique temporary files, file fsync, atomic replace and parent directory fsync. Random owner tokens avoid equal-worker/time collisions. Validate owner token and TTL at commit, not only release. A lease context integrates the guard with the existing coordinator. Keep administrative force_unlock explicit; do not introduce autonomous force unlock.

This does not turn JSON primary + backup + external artifacts into one database transaction, authenticate all historical evidence, fence non-cooperating watchdog/direct writers, make NFS/Windows reliable, provide a sandbox, or prove exactly-once external effects. SQLite migration is deferred to avoid changing authoritative storage while the JSON consumers remain unsynchronized.

## Baselines, controls, and budget

- B0: exact #98 source, unchanged, reproduced in disposable directories. Force two child processes to read the same unlocked snapshot, then order their writes: deterministic counterexample rather than timing luck. Also run an uninstrumented simultaneous-acquisition stress test.
- I1: guarded transactions + commit fencing + coordinator lease context, no solver/planner/memory replacement.
- Public engineering controls: cold concurrent initialization; simultaneous and serial acquire; wrong/missing/stale/non-ASCII tokens; equal clock/same worker IDs; owner commit; expiry/replacement; concurrent cycle recording; idempotent/conflicting retry; corruption recovery; OS guard contention timeout; process termination while guard held; interrupted replacement; separate-process restart.
- Preserve the original six #98 token tests and self-development continuity tests. Add multiprocess integration controls using spawn and explicit synchronization, deadlines and child cleanup. Do not use terminal data as a tuning signal.
- Standard-library Linux Python only, target CI 3.12/3.13; at most 4 worker processes, ≤30 seconds per process scenario, no API/provider calls, no paid services, no installations, no live daemon. All execution is trusted repository/test code, not an untrusted generated Python candidate.
- Record raw test outcomes, source SHA/digests, actual CPU/wall/RSS and process IDs (tokens are not public evidence), CI job logs and artifact hashes. Finite public engineering fixtures are not independent scientific confirmation. No train/development/terminal ML split applies to this reliability regression; those splits remain mandatory for subsequent learning studies.

## Gates and next step

Engineering GO for this scoped path requires all new controls and existing affected regressions, unchanged source pins, and successful exact-head CI. Any failure is retained and blocks this gate. Scientific status always `NOT_ASSESSED`, release `BLOCK_RELEASE`, OAIE `NOT_ESTABLISHED`. Actual provider A/B/C experiment: `EXTERNAL_AI_EXPERIMENT_NOT_RUN` unless a separate lawful provider run is evidenced. Real Termux hardware remains unmeasured.

After reliability acceptance, the next independent milestone is a data-only bounded coding pilot using the existing codebase reader, internal synthesis, static interpreter, evidence and retained executable memory. General source execution stays `BLOCKED_ENVIRONMENT` until containment is separately proven. Do not claim this reliability slice completes the autonomous coding PRD or supplies a new learned capability.
