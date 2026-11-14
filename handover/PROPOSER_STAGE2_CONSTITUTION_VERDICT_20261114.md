# PROPOSER STAGE 2 — ISOLATED STAGING & CONSTITUTION ENGINE VERDICT (2026-11-14)

> Implements Proposer Engine Stage 2 under the governance of:
> - `handover/PETA_ARAH_SERIBU_TAHUN.md` (Addendum §5 *"Paket uji konstitusi pagar-diri"*, *Koreksi bingkai 20:54 WIB*, and panen #8C *"Identitas bertiga mesin riset"*)
> - `handover/PROPOSER_STAGE1_V2_EXIT_GATE_VERDICT_20261114.md` (Stage 1 Quality PASS -> bounded isolated Stage 2 staging)

## 1. Constitutional Design Summary

Stage 2 opens a **strictly isolated, `staging-only` execution & constitution harness** ([`code/ace_operational/proposer_stage2.py`](file:///home/antigravity/dianzherdiana25-hash/ACE/code/ace_operational/proposer_stage2.py)) backed by four additive schema tables in [`code/ace_operational/store.py`](file:///home/antigravity/dianzherdiana25-hash/ACE/code/ace_operational/store.py): `proposer_staged_packages`, `proposer_stage2_ratifications`, `proposer_stage2_runs`, and `proposer_stage2_ledger`.

1. **Internal Ratification Only (Zero Owner-Permission Vocabulary):**
   `FORBIDDEN_RATIFICATION_TERMS` (`owner_approval`, `owner_permission`, `izin_pemilik`, `persetujuan_pemilik`) are rejected fail-closed across proposal packages, `request_id`, ratification records, revocation metadata, stop reasons, and environment profiles. Only `RATIFICATION_AUDIENCE` (`hub`, `kernel`, `evidence`) may grant internal ratification.
2. **Threefold Identity Separation (#8C):**
   - `request_id` + `payload_sha256` govern idempotent staging (reusing a `request_id` with a different canonical digest raises `RequestConflictError` and records a tamper-evident ledger rejection).
   - `payload_sha256` pins canonical UTF-8 JSON bytes (`0o444` immutable package blob on disk).
   - Every intentional dispatch / replication mints a fresh `execution_run_id` (`stgrun_<ms>_<hex>`).
3. **Exact Hash-Pinned Ratification, Finite TTL & Irrevocable Revocation:**
   `ratify_staged` requires `payload_sha256 == staged["payload_sha256"]` and finite `ttl_seconds > 0`. `revoke_staged` records an exact `revocation_ledger_seq`, marks revocation irrevocable (blocking all future `ratify_staged` and `dispatch_staged`), and immediately signals active runs to halt mid-flight.
4. **Isolated Staging Environment Bridge (§5):**
   `StagingEnvironmentProfile` requires `identity_mode="staging-only"`, `effective_identity` prefixed with `staging:` / `stg:` (blocking `prod`/`production`/`live`/`owner`/`real`), `egress_blocked=True`, `dummy_credentials_only=True` (`dummy_`/`stg_dummy_`, rejecting secret prefixes like `sk-`/`ghp_`), workspace-confined `dummy_resource_root` with path-escape checks, and runtime SHA-256 digests of the live enforcer modules (`proposer_validator`, `preaudit_validator`, `proposer_stage2`, `store`).
5. **Bounded Stop, Hard Ceilings & No Auto-Retry:**
   `StagingRunContext` enforces `max_calls`, `max_wall_seconds`, and `max_cost_units`; `request_stop` / mid-flight revocation halts runs at gate boundaries while preserving committed in-flight calls, cost, and work units; `dispatch_staged` refuses `recommended_option == "do_not_run"` (`DoNotRunError`) and blocks automatic re-dispatch after `STOPPED`, `ABORTED_CEILING`, or `FAILED` (`AutoRetryBlockedError`).
6. **Immutable-Blob-Before-Commit (#8C) + Independent Pre-Audit (`SESUAI`):**
   Every run writes read-only (`0o444`) bundle artifacts under `bundles/<execution_run_id>/source/`, verifies on-disk digests before finalization, executes `preaudit_validator` C1/C2/C3 (`SESUAI`, `exit_code == 0`, `unlisted_files_informational_only == 0`) with disjoint `--source-root` and `--out-dir`, and commits finalized DB + hash-chained ledger entries only after verification passes.

## 2. Constitution Battery Results (7/7 PASS over Real Frozen Stage-1 v2 Packages)

Executed offline (zero LLM/network calls) via [`proposer_stage2_battery.py`](file:///home/antigravity/dianzherdiana25-hash/ACE/code/ace_operational/proposer_stage2_battery.py) against all six real `Qwen3.5-4B` Stage-1 v2 packages in `evidence/proposer_stage1_v2/grammar_only/`. Recorded report: [`evidence/proposer_stage2/constitution_battery_report.json`](file:///home/antigravity/dianzherdiana25-hash/ACE/evidence/proposer_stage2/constitution_battery_report.json).

| Check | Target Episode (Real Package) | Constitutional Invariant Verified | Result |
|---|---|---|---|
| `C1_DO_NOT_RUN_BLOCK` | `EP1-G3-APPLICATION.txt` (`G3-20261113-LOCKED`) | `recommended_option="do_not_run"` ratified -> `dispatch_staged` refuses (`DoNotRunError`), `runs_created=0` | **PASS** |
| `C2_HASH_PIN_VOCAB_AND_TTL` | `EP2-ABC-V3.txt` (`abc-v3-01-run`) | Rejects `owner_approval`, mismatched hash, `request_id` conflict, expired TTL -> clean `COMPLETED` + `preaudit_exit_code=0` | **PASS** |
| `C3_VISIBLE_STOP_AND_NO_AUTO_RETRY` | `EP3-ROUND2-GATE.txt` (`g3-lift-round2-20261113`) | Visible mid-flight `request_stop` -> `STOPPED` (`calls_used=3`, `cost_units=0.15`), `preaudit_exit_code=0`, re-dispatch blocked | **PASS** |
| `C4_HARD_CEILING_ABORT` | `EP4-CONTROL-REGRESSION-ATTRIBUTION.txt` (`pr-20261113-v3-attrib`) | Projected step exceeding `max_calls=2` -> `ABORTED_CEILING`, `preaudit_exit_code=0`, re-dispatch blocked | **PASS** |
| `C5_IRREVOCABLE_MIDFLIGHT_REVOCATION` | `EP5-G4-INHERITANCE.txt` (`G4-HERIT-20261113`) | Mid-flight `revoke_staged(actor="evidence")` -> `STOPPED` (`revoked_at_seq:26`), `preaudit_exit_code=0`, re-ratify blocked (`RevokedError`) | **PASS** |
| `C6_ISOLATED_ENV_AND_8C_REPLICATION` | `EP6-PER-TASK-RECORDING.txt` (`pt-rec-20261113-001`) | Rejects `identity_mode="production"`, completes 2 intentional replications with distinct `execution_run_id`s + real enforcer SHA-256 stamps | **PASS** |
| `C7_BLOB_BEFORE_COMMIT_AND_CHAIN_AUDIT` | All 6 packages | #8C pre-commit corrupted blob blocked (`BlobIntegrityError`), `verify_ledger()=True` (36 entries), `MissionBus` chain & eval journal valid | **PASS** |

## 3. Custody & Scope Status

- **Custody untouched:** `code/ace_runtime/`, `code/ace_mission/`, and all 25 pinned files in `docs/UPSTREAM_SOURCES.json` remain byte-identical (`tools/verify_sources.py` PASS 25/25).
- **Stage 2 boundary:** Operating strictly in `identity_mode="staging-only"`. Live production credentials/venues remain untouched until dedicated post-staging gate preregistration.
