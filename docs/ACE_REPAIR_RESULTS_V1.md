# ACE Autonomous Software Repair v1 — Executed Staged Repair Results

**Date:** 2026-11-07  
**Branch:** `research/ace-software-repair-v1-20261107`  
**Pre-Score Protocol Commit:** `5369e8ea1d3fe03cd96c4bc9a3108684aed150cf` (`docs/ACE_REPAIR_PRESCORE_V1.md`, SHA-256 `7586ac81e3899347845a5e9a29320bb2c3624c3862e1dbd42367e8f25165de00`)  
**Classification:** PUBLIC SYNTHETIC / CURATED STAGED BENCHMARK  
**Governance Flags:** `scientific_decision = "NOT_ASSESSED"`, `release_gate = "BLOCK_RELEASE"`, `oaie_established = False`, `candidate_deployed = False`, `open_world_safe = False`

---

## 1. Mandatory Evidence Flags Summary

| Evidence Flag | Value | Basis |
|---|---|---|
| `ACE_BASE_RUNTIME_EXECUTED` | **`True`** | Offline source pin check (`25/25`), `ace.py demo` & `ace.py status`, and `ace_runtime` unit tests (`17/17`) executed cleanly prior to Fase 5 implementation. |
| `NEW_CAPABILITY_INTEGRATED_AND_EXECUTED` | **`True`** | Full 8-stage `RepairEngine` (`Goal -> Inspect -> Reproduce -> Diagnose -> Represent -> Patch -> Test -> Verify -> Remember`) integrated with unchanged `ace_runtime.engine.Runtime` + SQLite WAL `RepairMemory`, executed and verified identically on Python 3.12.16 and Python 3.13.18. |
| `SCIENTIFIC_CAPABILITY_VALIDATED` | **`False`** | Hypotheses `H2`, `H3`, and `H4` **PASSED**, whereas `H1` **FAILED** its strict inequality clause against `R_fixed` (`R_ace` solved `12/12` nominal targets vs. `R_rule` `11/12`, tying `R_fixed` `12/12` and `R_fresh` `12/12` at ceiling because single-module candidate pools averaged `12.6 <= K=16`). Per pre-registered negative-result commitment, no post-score benchmark padding or budget reduction was applied. |

---

## 2. Fase 2 Base Runtime Execution & Provenance Custody

1. **Upstream Pin Verification (`tools/verify_sources.py`):** `PASS: 25 imported files match their recorded Git blob IDs (offline)`. Zero bytes modified in `code/ace_runtime/` or any pinned file.
2. **Operational Base Runtime (`ace.py` in isolated `TemporaryDirectory`):**
   - `ace_runtime` implementation digest: `931b1582e4dc9579a56712936097a9d476941cdc1bc19c876f6ea4936aab644c`
   - `ace.py demo` output SHA-256: `19de85575a075574a52c20bf6bf53ce9c7b303ddb5c4ac7d0d6103ef76a1fe02` (`3/3` tasks `128/128` terminal, `2` capabilities, `1` `REUSE_VALIDATED`)
   - `ace.py status` output SHA-256: `97bb189fb9862a5309136f66e7a40ca20f496e229f0308cba81e82d9aeacae3a`
   - Base runtime unit suite (`ace_runtime.test_engine` + `ace_runtime.test_cli`): `17/17 OK`.
3. **Fase 5 Evidence Bundle (`evidence/repair/ace_repair_v1.json.gz`):**
   - Canonical uncompressed JSON: **`491,811` bytes**, SHA-256 `0eb98aa4eb967fb1207589cb28a3d595278557af033ce309c83922d684b04929`
   - Deterministic RFC 1952 gzip artifact: **`62,745` bytes**, SHA-256 `6d9adf3dbc6a3a3e2326e50bf67e28cddb3cdea3865fadf4de209f4ecea6edf7`
   - Cross-version determinism: **byte-for-byte identical** across `Python 3.12.16` and `Python 3.13.18`.
   - Independent fail-closed verifier (`python -m ace_research_repair.verify`): `PASS_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO` (`7/7` AST-isolated modules verified, `25/25` upstream pins verified, exact full replay verified).

---

## 3. Source Bank Acquisition & `ace_runtime` Capability Inheritance (`S01`–`S08`)

Starting from an empty workspace (`0` capabilities, `0` `RepairMemory` records), `R_ace` solved, verified, and remembered **`8/8`** source bugs within budget `K = 16`, inducing **`4`** distinct binary trace capabilities in `ace_runtime.engine.Runtime` and **`4`** `REUSE_VALIDATED` inheritances (`learning_called = False`):

| Source Unit | Family | Evals (`dev+ver`) | Selected Operator | `ace_runtime` Phase | `ace_runtime` `model_id` (prefix) |
|---|---|---:|---|---|---|
| `S01_sliding_window_sums` | `boundary_index` | `2` (`1+1`) | `OP_RANGE_STOP_ADJUST` | `LEARNED_STAGED` | `7c6506bd6952...` |
| `S02_safe_head_ratio` | `boundary_index` | `3` (`2+1`) | `OP_EMPTY_GUARD_INSERT` | `REUSE_VALIDATED` | `7c6506bd6952...` |
| `S03_kv_header_parse` | `parsing` | `2` (`1+1`) | `OP_SPLIT_MAXSPLIT_ONE` | `LEARNED_STAGED` | `d8d1e22ad48a...` |
| `S04_csv_int_sum` | `parsing` | `3` (`2+1`) | `OP_SIGN_GUARD_EXPAND` | `REUSE_VALIDATED` | `d8d1e22ad48a...` |
| `S05_run_length_max` | `state_invariant` | `5` (`4+1`) | `OP_SWAP_ADJACENT_STATE_STMTS` | `LEARNED_STAGED` | `3e5b5b32c8db...` |
| `S06_batch_packet_accumulator` | `state_invariant` | `7` (`6+1`) | `OP_STATE_RESET_ON_FLUSH` | `REUSE_VALIDATED` | `3e5b5b32c8db...` |
| `S07_snapshot_ledger` | `data_dependency` | `5` (`4+1`) | `OP_MUTABLE_COPY_WRAP` | `LEARNED_STAGED` | `26b7f644e523...` |
| `S08_tag_collector` | `data_dependency` | `3` (`2+1`) | `OP_DEFAULT_NONE_INIT` | `REUSE_VALIDATED` | `26b7f644e523...` |

Post-source `RepairMemory` head hash: `1d799fc78aea449189e93501348745c57b8dd349d32c32f0a7b2df6b822bd73e` (`8` records). After completing all `18` target evaluations (`26` total `ace_runtime` tasks, `52` hash-linked runtime events), `RepairMemory` holds `20` validated records (head hash `198763e816dc434090dd6a33bd1535f99fc16e80d72021ab18b6c03f44769ddc`).

---

## 4. Target Bank Outcomes Across All 4 Arms (`K = 16` Matched Sandbox Budget)

### 4.1 Aggregate Arm Comparison (`18` Unseen Target Units)

> **Budget Accounting Note:** Every candidate execution in `sandbox.py` counts against `K = 16`. For `R_ace`, `total_candidate_sandbox_evals = dev_sandbox_evals + verify_sandbox_evals` (so every admitted `R_ace` patch includes `+1` extra sandbox execution for Stage 7 `Verify` perturbation checking). Initial dynamic fault reproduction (`Reproduce`: `18` runs for `R_fresh` and `R_ace`, `0` for static `R_rule` and `R_fixed`) is reported separately.

| Metric | `R_rule` | `R_fixed` | `R_fresh` | `R_ace` |
|---|---:|---:|---:|---:|
| Nominal Staged (`12` units) | `11/12` | `12/12` | `12/12` | **`12/12`** |
| Nominal Terminal-Verified (`12` units) | `11/12` | `12/12` | `12/12` | **`12/12`** |
| Nominal Total Candidate Sandbox Evals | `118` | `73` | `64` | **`41`** (`29` dev + `12` verify) |
| Nominal Mean Evals / Solved Unit | `9.2727` | `6.0833` | `5.3333` | **`3.4167`** (`2.4167` dev rank) |
| `OOD_abstain` Safe Abstentions (`4` units) | `4/4` | `4/4` | `4/4` | **`4/4`** |
| `TRAP_overfit` Safe Abstentions (`2` units) | `1/2` | `1/2` | `0/2` | **`2/2`** |
| Overfitting False Admissions (`TRAP` + `OOD` + Nominal) | `1` | `1` | `2` | **`0`** |
| Admitted Patch Terminal Precision (`verified / admitted`) | `11/12` (`91.7%`) | `12/13` (`92.3%`) | `12/14` (`85.7%`) | **`12/12` (`100.0%`)** |
| Total Candidate Sandbox Evals (all `18` units) | `184` | `139` | `127` | **`108`** |
| Separate `Reproduce` Trace Runs (all `18` units) | `0` | `0` | `18` | `18` |

### 4.2 Nominal Performance by Bug Family (`3` Unseen Units per Family)

| Bug Family | `R_rule` Verified (Mean Evals) | `R_fixed` Verified (Mean Evals) | `R_fresh` Verified (Mean Evals) | `R_ace` Verified (Mean Evals) |
|---|---|---|---|---|
| `boundary_index` | `3/3` (`11.3333`) | `3/3` (`4.3333`) | `3/3` (`4.0000`) | **`3/3` (`4.0000`)** |
| `parsing` | `3/3` (`8.0000`) | `3/3` (`4.3333`) | `3/3` (`4.3333`) | **`3/3` (`2.6667`)** |
| `state_invariant` | `2/3` (`12.3333` all / `10.50` solved) | `3/3` (`9.0000`) | `3/3` (`7.6667`) | **`3/3` (`4.6667`)** |
| `data_dependency` | `3/3` (`7.6667`) | `3/3` (`6.6667`) | `3/3` (`5.3333`) | **`3/3` (`2.3333`)** |

Four of the twelve nominal target repairs (`T01` `OP_CMP_BOUNDARY_FLIP`, `T05` `OP_STR_STRIP_NORMALIZE`, `T09` `OP_LOOP_TAIL_FLUSH`, and `T12` `OP_RHS_VAR_REBIND`) required typed operators **never instantiated in the 8-bug source bank**, confirming family-level `(runtime_model_id -> operator_family)` representation transfer rather than exact operator-ID memorization.

### 4.3 Per-Unit Target Ledger (`T01`–`T18`)

| Target Unit | Category / Family | Pool | `R_rule` (Evals, Term) | `R_fixed` (Evals, Term) | `R_fresh` (Evals, Term) | `R_ace` (Evals `dev+ver`, Term, Outcome) |
|---|---|---:|---|---|---|---|
| `T01_binary_search_index` | `boundary_index` | `13` | `11`, `8/8` | `1`, `8/8` | `6`, `8/8` | `6` (`5+1`), `8/8`, `STAGED_VERIFIED` |
| `T02_interior_local_maxima` | `boundary_index` | `17` | `13`, `8/8` | `3`, `8/8` | `4`, `8/8` | `3` (`2+1`), `8/8`, `STAGED_VERIFIED` |
| `T03_trimmed_floor_mean` | `boundary_index` | `18` | `10`, `8/8` | `9`, `8/8` | `2`, `8/8` | `3` (`2+1`), `8/8`, `STAGED_VERIFIED` |
| `T04_parse_env_entries` | `parsing` | `8` | `6`, `8/8` | `1`, `8/8` | `4`, `8/8` | `2` (`1+1`), `8/8`, `STAGED_VERIFIED` |
| `T05_parse_version_triple` | `parsing` | `11` | `9`, `8/8` | `5`, `8/8` | `4`, `8/8` | `4` (`3+1`), `8/8`, `STAGED_VERIFIED` |
| `T06_replay_stock_deltas` | `parsing` | `11` | `9`, `8/8` | `7`, `8/8` | `5`, `8/8` | `2` (`1+1`), `8/8`, `STAGED_VERIFIED` |
| `T07_run_length_counts` | `state_invariant` | `15` | `10`, `8/8` | `7`, `8/8` | `10`, `8/8` | `5` (`4+1`), `8/8`, `STAGED_VERIFIED` |
| `T08_step_differences` | `state_invariant` | `12` | `11`, `8/8` | `8`, `8/8` | `5`, `8/8` | `3` (`2+1`), `8/8`, `STAGED_VERIFIED` |
| `T09_session_durations` | `state_invariant` | `18` | `16`, **`0/8` (FAIL)** | `12`, `8/8` | `8`, `8/8` | `6` (`5+1`), `8/8`, `STAGED_VERIFIED` |
| `T10_apply_row_mask` | `data_dependency` | `8` | `8`, `8/8` | `5`, `8/8` | `7`, `8/8` | `2` (`1+1`), `8/8`, `STAGED_VERIFIED` |
| `T11_register_route` | `data_dependency` | `8` | `5`, `8/8` | `7`, `8/8` | `5`, `8/8` | `2` (`1+1`), `8/8`, `STAGED_VERIFIED` |
| `T12_compute_net_total` | `data_dependency` | `12` | `10`, `8/8` | `8`, `8/8` | `4`, `8/8` | `3` (`2+1`), `8/8`, `STAGED_VERIFIED` |
| `T13_ood_greedy_coin_change` | `OOD_abstain` | `13` | `13`, abstain | `13`, abstain | `13`, abstain | `13` (`13+0`), abstain |
| `T14_ood_nested_expr_eval` | `OOD_abstain` | `12` | `12`, abstain | `12`, abstain | `12`, abstain | `12` (`12+0`), abstain |
| `T15_ood_weighted_shortest_hops` | `OOD_abstain` | `17` | `16`, abstain | `16`, abstain | `16`, abstain | `16` (`16+0`), abstain |
| `T16_ood_triple_fault_ledger` | `OOD_abstain` | `11` | `11`, abstain | `11`, abstain | `11`, abstain | `11` (`11+0`), abstain |
| `T17_trap_constant_collapse` | `TRAP_overfit` | `6` | `6`, **`0/8` FALSE ADM** | `6`, **`0/8` FALSE ADM** | `6`, **`0/8` FALSE ADM** | `7` (`6+1`), **REJECTED** (`constant_output_collapse`) |
| `T18_trap_special_case_guard` | `TRAP_overfit` | `8` | `8`, abstain | `8`, abstain | `5`, **`2/8` FALSE ADM** | `8` (`7+1`), **REJECTED** (`equivalence_pair_mismatch`) |

---

## 5. Pre-Registered Hypotheses Verdicts & Failure Diagnosis

| Hypothesis | Verdict | Quantitative Evidence |
|---|---|---|
| **`H1`:** `R_ace` strictly beats `R_rule` & `R_fixed` on nominal verified count (`>= 9/12`, `>= 2/3` per family) | **`FAIL`** | `R_ace` solved `12/12` (`3/3` in all 4 families) and beat `R_rule` (`11/12`, which failed `T09_session_durations`), **but tied `R_fixed` (`12/12`)** at ceiling. Because single-file modules generated `8`–`18` total AST candidates (mean `12.6 <= K=16`), static entrypoint-preferring search (`R_fixed`) could exhaustively test `6.08` candidates on average without hitting the `K = 16` cap. Note that under tighter budgets recorded in the exact same trace (`evals <= 4`), `R_ace` solves `9/12` nominal units vs. `R_fresh` `5/12`, `R_fixed` `3/12`, and `R_rule` `0/12`. |
| **`H2`:** `R_ace` beats `R_fresh` on verified count or reduces mean solved evals by `>= 20%` | **`PASS`** | Both solved `12/12` nominal units, while `R_ace` reduced mean total sandbox evaluations per solved bug from `5.3333` (`64` evals) to **`3.4167`** (`41` evals, **including** `12` `Verify` perturbation runs) — a **`35.94%` reduction** (`54.69%` reduction in dev-suite patch trials from `64` to `29`). |
| **`H3`:** Anti-overfitting rejection on `TRAP_overfit` and abstention on `OOD_abstain` | **`PASS`** | Unverified arms committed `4` total false admissions on `TRAP_overfit` (`R_fresh`: `2/2` on `T17` `OP_OVERFIT_CONSTANT_RETURN` scoring `0/8` terminal and `T18` `OP_OVERFIT_DEV_INPUT_GUARD` scoring `2/8` terminal; `R_rule` & `R_fixed`: `1/2` each on `T17`). `R_ace`'s Stage 7 `Verify` gate rejected `T17` via `constant_output_collapse` and `T18` via `equivalence_pair_mismatch` on unlabeled reversal probes, yielding **`0` false admissions** and **`4/4` `OOD_abstain` abstentions**. |
| **`H4`:** Cross-restart `RepairMemory` & `ace_runtime` persistence without refitting | **`PASS`** | Cold-restarting `RepairEngine` on the post-source workspace verified both SQLite chains (`8` `RepairMemory` records, `4` `ace_runtime` capabilities), achieved `12/12` `REUSE_VALIDATED` (`learning_called = False`), and produced `12/12` identical patch SHA-256 digests. |

---

## 6. Scientific Interpretation Limits & Next Gate

- **What is established:** A clean, staged 8-stage repair architecture (`RepairEngine`) integrating `ace_runtime` binary trace capabilities, transactional hash-linked `RepairMemory`, isolated subprocess sandboxing (`RLIMIT_CPU` + `O_NOFOLLOW`), AST-isolated terminal evaluation, and label-free metamorphic perturbation verification that eliminates generate-and-validate overfitting on `TRAP_overfit` while cutting candidate evaluations by `35.94%` vs. target-only spectrum search (`R_fresh`).
- **What is NOT established:** `H1` exposed a genuine benchmark-scale ceiling (`candidate_pool_size <= 16` on compact two-function modules). Moreover, the 15 AST operators, 4 trace-regime mappings, and unlabeled perturbation symmetries are researcher-authored; this does not establish autonomous synthesis of new repair operator grammars, multi-file real-world repository repair, unconditional semantic drift detection, or OAIE.
- **Next Gate:** Scale target modules to multi-file / 100+ candidate AST pools where `pool_size >> K`, and test multi-edit compositional patch synthesis without modifying this frozen v1 benchmark. `scientific_decision = "NOT_ASSESSED"` and `release_gate = "BLOCK_RELEASE"` remain enforced.
