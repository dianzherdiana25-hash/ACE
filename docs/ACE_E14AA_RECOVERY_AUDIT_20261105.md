# ACE E1.4aa — read-only recovery audit (5 November 2026)

**Scope:** additive engineering evidence; the original Codex E1.4aa prescore bank, lock, learner, and scorer remain unchanged. Base commit `4cbe8630f21db7ae58a64018fcf07547d8bcdb30`.

## Why this tool exists

The E1.4aa runner refuses to start when its output directory is nonempty. A crash can leave a purchased-but-unsettled SQLite reservation, stored source evidence, or incomplete snapshots. A blind rerun may double-buy labels and invalidate scientific accounting.

Run: `PYTHONPATH=code:. python3 tools/ace_e14aa_recovery_audit.py --root WORK/e14aa-run`.

The inspector opens journal databases read-only (`mode=ro` plus `query_only=ON`), verifies SHA-256 and canonical payloads, reconstructed four-label budgets, typed oracle labels and graph costs, final report/summary digests and source/target snapshot correspondence. It never calls the oracle, repairs a journal, purchases evidence, or automatically resumes.

- Exit 0: `COMPLETE_CONSISTENT_NOT_ORACLE_VERIFIED`. Local evidence agrees internally, **not** a scientific GO or independent semantic proof.
- Exit 2: `EMPTY`, `INCOMPLETE_NO_AUTORETRY` or `BLOCKED_PENDING_NO_RETRY`. Stop and reconcile externally, never silently repurchase.
- Exit 3: `BLOCKED_CORRUPT_OR_UNVERIFIABLE`. Stop and investigate integrity violations.

The current original E1.4aa study driver does not implement safe continuation from partial outputs. This utility is a **triage gate**, not a resumed execution engine. Provider receipts and original independent oracle evidence are still necessary for reconciliation. SHA-256 without signatures or external custody does not protect a database against an attacker who rewrites all records and digests.

## Tests actually executed

On the compatible local ACE E1.4 workspace (not a full exact-head GitHub checkout):

- 10/10 new recovery tests PASS, including pending reservations, cost forgery with recomputed checksum, digest corruption, symlinks, invalid report and mismatched snapshots.
- 43/43 combined relevant existing+new tests PASS, in ~1.6s: `e14.test_e14_integrated_graph`, `e14.test_e14_integrated_policy`, `e14.test_e14_issue13_smoke`, `tools.test_ace_e14aa_recovery_audit`.
- Local SHA-256 code: `e1f3bae6cad5ab26160f8e8ae59ee7e171f7683ee52a7fad412626ac89bfacac`.
- Local SHA-256 tests: `2b254ffb3201cad15c023a49ca233958543af454dd4d0cbc5d1caaca2b4692f5`.

The E1.4aa source lock at base HEAD was independently checked against all its 17 specified GitHub file contents: **17/17 SHA-256 matches**. Native Bubblewrap, full repository regression, and independent scientific confirmation remain open. This additive checker is intentionally outside the frozen prescore files.
