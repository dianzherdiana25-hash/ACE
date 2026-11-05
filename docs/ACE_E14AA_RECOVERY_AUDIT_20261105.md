# ACE E1.4aa — read-only recovery audit (5 November 2026)

**Scope:** additive engineering evidence; the original Codex E1.4aa prescore bank, lock, learner, and scorer remain unchanged. Base commit `4cbe8630f21db7ae58a64018fcf07547d8bcdb30`.

## Why this tool exists

The E1.4aa runner refuses to start when its output directory is nonempty. A crash can leave a purchased-but-unsettled SQLite reservation, stored source evidence, or incomplete snapshots. A blind rerun may double-buy labels and invalidate scientific accounting.

Run: `PYTHONPATH=code:. python3 tools/ace_e14aa_recovery_audit.py --root WORK/e14aa-run`.

The inspector opens journal databases read-only (`mode=ro` plus `query_only=ON`), verifies SHA-256 and canonical payloads, reconstructed four-label budgets, strict integer counters (reject bool/float aliases), typed progress records, typed oracle labels and graph costs, final report/summary digests and source/target snapshot correspondence. It never calls the oracle, repairs a journal, purchases evidence, or automatically resumes.

- Exit 0: `COMPLETE_CONSISTENT_NOT_ORACLE_VERIFIED`. Local evidence agrees internally, **not** a scientific GO or independent semantic proof.
- Exit 2: `EMPTY`, `INCOMPLETE_NO_AUTORETRY` or `BLOCKED_PENDING_NO_RETRY`. Stop and reconcile externally, never silently repurchase.
- Exit 3: `BLOCKED_CORRUPT_OR_UNVERIFIABLE`. Stop and investigate integrity violations.

The current original E1.4aa study driver does not implement safe continuation from partial outputs. This utility is a **triage gate**, not a resumed execution engine. Provider receipts and original independent oracle evidence are still necessary for reconciliation. SHA-256 without signatures or external custody does not protect a database against an attacker who rewrites all records and digests.

## Tests actually executed

On the compatible local ACE E1.4 workspace (not a full exact-head GitHub checkout):

- 12/12 new recovery tests PASS, including pending reservations, cost forgery with recomputed checksum, digest corruption, symlinks, invalid report and mismatched snapshots.
- 45/45 combined relevant existing+new tests PASS, in ~1.6s: `e14.test_e14_integrated_graph`, `e14.test_e14_integrated_policy`, `e14.test_e14_issue13_smoke`, `tools.test_ace_e14aa_recovery_audit`.
- Local SHA-256 code: `4ae95563725447e4ee13469e58d6f21810390fe5597d8a1023c103d195e864b1`.
- Local SHA-256 tests: `8593fef2ee8daf22afaaa376413bcfc3fe8b6db0c121ff49b2e49aec7d7dd475`.

The E1.4aa source lock at base HEAD was independently checked against all its 17 specified GitHub file contents: **17/17 SHA-256 matches**. Native Bubblewrap, full repository regression, and independent scientific confirmation remain open. This additive checker is intentionally outside the frozen prescore files.

## Independent prescore byte gate, added after recovery audit

`PYTHONPATH=code:. python3 tools/ace_e14aa_prescore_gate.py --repo . --lock design/e1.4/E14AA_PRESCORE_LOCK_v1.json`

The pure-stdlib verifier performs **zero experiment calls** and refuses changed source bytes, path traversal, symlinks, malformed hashes, numeric type aliases and missing files. It does not establish external custody of the lock itself or certify worker isolation. At the original Codex HEAD, the 17 SHA256 hashes were also recomputed independently through the connected GitHub source API and matched 17/17.

Seven new lock-gate tests pass. Total local relevant-suite results after this addition: **52/52 PASS**, with non-fatal SQLite `ResourceWarning` messages under Python 3.13 in the compatible local environment; the warnings are not treated as proof of a leak in the new Codex head. Full exact-head CI remains unverified.
