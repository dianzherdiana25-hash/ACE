# Ekstraksi Keputusan Pemilik/Hub, Verdit, & Usulan Terbuka

> Dihasilkan deterministik oleh `tools/handover_decision_extractor.py` (`ace.handover-decisions.v1`, `brain_of_origin: gravity-proposal`). Setiap butir ber-sitasi persis `<path>:<line>`; bukan otorisasi eksekusi.

## 1. Ringkasan Pemindaian

- Berkas `handover/` & `docs/` dipindai: **259**
- Total baris dipindai: **33377**
- Total butir tersitasi: **140**
- Tag asal ringkasan: `gravity-proposal`

### Distribusi per Kategori

| Kategori | Jumlah Tersitasi |
| --- | ---: |
| `GOVERNANCE_RULE` | 35 |
| `OPEN_PROPOSAL` | 35 |
| `OWNER_HUB_DECISION` | 35 |
| `PARKED_OR_BLOCKED` | 35 |

## Aturan Tata Kelola & Kontrak Tetap (`GOVERNANCE_RULE`)

- Kecocokan total: **236** | Ditampilkan: **35**

| Sumber & Baris | Aktor Sumber | Asal Ringkasan | Kutipan |
| --- | --- | --- | --- |
| `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:113` | `repo_record` | `gravity-proposal` | ## Gate 4 — staged self-development generations G0 → G1 → G2 |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:15` | `repo_record` | `gravity-proposal` | `G0`: no task-specific learned capability. `G1`: R1 infers a data-driven finite automaton on `a_mod4`, and S2 searches closed integer ASTs for `x_minus_y`. Both pass predefined *validation-only* staging gates. `G2`: same… |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:19` | `repo_record` | `gravity-proposal` | \| R1 `a_mod4` \| G1 STAGED \| 197/256 (76.95%) \| **256/256** \| PASS \| |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:20` | `repo_record` | `gravity-proposal` | \| S2 `x_minus_y` \| G1 STAGED \| 2/16 (12.50%) \| **16/16** \| PASS \| |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:21` | `repo_record` | `gravity-proposal` | \| R1 `b_mod4` \| G2 STAGED \| 192/256 (75.00%) \| **256/256** \| PASS \| |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:22` | `repo_record` | `gravity-proposal` | \| S2 `product_plus_two` \| G2 STAGED \| 0/16 (0%) \| **16/16** \| PASS \| |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:32` | `repo_record` | `gravity-proposal` | \| G1 — at least one G1 capability staged \| Two staged \| PASS \| |
| `docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md:33` | `repo_record` | `gravity-proposal` | \| G2 — both modality families + immutable G1 replay \| Four staged, original scores unchanged \| PASS \| |
| `docs/ACE_CAPABILITY_STRUCTURAL_V02_RESULTS_20261106.md:3` | `repo_record` | `gravity-proposal` | **Date:** 2026-11-06. **Classification:** PUBLIC SYNTHETIC DEVELOPMENT, staged-only. Scientific `NOT_ASSESSED`; release `BLOCK_RELEASE`; OAIE `NOT_ESTABLISHED`. No source self-modification or production candidate adoptio… |
| `docs/ACE_CAPABILITY_STRUCTURAL_V02_RESULTS_20261106.md:51` | `repo_record` | `gravity-proposal` | \| S4: G1 immutable retention \| Model hashes and validation retained without refit \| PASS \| |
| `docs/ACE_G0_G2_PRESCORE_V1.md:15` | `repo_record` | `gravity-proposal` | ## 2. Immutable Security & Anti-Goodhart Boundary |
| `docs/ACE_G0_G2_RESULTS_V1.md:11` | `repo_record` | `gravity-proposal` | ## 1. Mandatory Three-Status Separation |
| `docs/ACE_G0_G2_RESULTS_V1.md:30` | `repo_record` | `gravity-proposal` | - Eight second-generation candidates were staged in `Autonomy` (`STAGED_FOR_REVIEW`); candidates that dropped `G1`'s strided inheritance failed the `M1_VAL` non-regression gate (`max_prior_regression <= 0.02`) and were r… |
| `docs/ACE_G0_G2_RESULTS_V1.md:49` | `repo_record` | `gravity-proposal` | ## 4. Immutable Core, Anti-Goodhart & Honest Limitations |
| `docs/ACE_G0_G2_RESULTS_V1.md:51` | `repo_record` | `gravity-proposal` | - **Immutable Lock Integrity (`H5` PASS)**: `ImmutableCoreGuard` verified all `7` SHA-256 file locks (`evaluator.py` `66e87d6a...`, `policy.py`, `verifier.py`, `core.py`, `escrow.py`, `engine.py`, `UPSTREAM_SOURCES.json`… |
| `docs/ACE_REPAIR_PRESCORE_V1.md:127` | `repo_record` | `gravity-proposal` | 3. **Interpretation Limits:** All bug families, typed AST mutation operators, binary trace encoders, and unlabeled metamorphic perturbation generators are researcher-authored. Passing engineering tests or local hypothese… |
| `docs/ACE_REPAIR_RESULTS_V1.md:1` | `repo_record` | `gravity-proposal` | # ACE Autonomous Software Repair v1 — Executed Staged Repair Results |
| `docs/ACE_REPAIR_RESULTS_V1.md:11` | `repo_record` | `gravity-proposal` | ## 1. Mandatory Evidence Flags Summary |
| `docs/ACE_Research_Execution_Spec_v0.1.md:46` | `repo_record` | `gravity-proposal` | **Kontrol yang dikunci sebelum run:** versi model awal, prompt dasar (jika ada), daftar alat, format tugas, kode evaluator, input generasi tugas, seed, limit eksperimen, dan kebijakan gagal/berhenti. B dan C memperoleh p… |
| `docs/ACE_Research_Execution_Spec_v0.1.md:96` | `repo_record` | `gravity-proposal` | **Tata kelola komputasi:** preferensi CPU lokal/komputasi gratis. Batas awal *per run* yang **harus ditetapkan ulang saat F0**: maksimum 30 menit *wall-clock* untuk percobaan pilot, maksimum 12 proposal B/C, batas proses… |
| `docs/ACE_SELFMODEL_RESULTS_V1.md:10` | `repo_record` | `gravity-proposal` | ## 1. Mandatory Epistemic & Execution Status Separation |
| `docs/ACE_SELFMODEL_RESULTS_V1.md:36` | `repo_record` | `gravity-proposal` | - **`H1` State Introspection Fidelity (`PASS`)**: `SelfState` read live SQLite states from `Autonomy` and `ace_runtime` (`staged` vs `unstaged` tasks, missing task IDs, tool allowlists, remaining budgets, mandatory invar… |
| `docs/ACE_SELFMODEL_RESULTS_V1.md:39` | `repo_record` | `gravity-proposal` | - **`H4` Honest Memory-Drop Uncertainty (`PASS`)**: Purging `36` non-mandatory episodic rows in `I4` reduced recalled episodes from `6` to exact `0` (zero hallucinated history), retained all `4/4` HMAC-signed mandatory s… |
| `docs/research/ACE_CONTROL_REGRESSION_DESIGN_DRAFT_20261113.md:199` | `repo_record` | `gravity-proposal` | ## 4. Staged experiment plan |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md:135` | `repo_record` | `gravity-proposal` | mandatory QA gate. Bab 1 verdict: FAIL for single-voice release |
| `docs/research/PREAUDIT_VALIDATOR_V2_DESIGN_FREEZE.md:15` | `repo_record` | `gravity-proposal` | `STAGED → REGISTERED OBSERVATION → VALIDATION VERDICT → PUBLISHED RESULT`. |
| `docs/research/PREAUDIT_VALIDATOR_V2_PILOT.md:13` | `repo_record` | `gravity-proposal` | block: stages `STAGED → REGISTERED OBSERVATION → VALIDATION VERDICT → |
| `docs/security/ACE_HOST_BOUNDARY_V2_SPEC_20261107.md:87` | `repo_record` | `gravity-proposal` | \| **5. Rules Tampering** \| `rules.min_gain = 0.0` \| FrozenInstanceError on immutable rules \| **BLOCKED (PASS)** \| |
| `handover/EVO_0003_STAGING_NOTE.md:48` | `repo_record` | `gravity-proposal` | ## Dialogue corpus (tail) — STAGED v1 |
| `handover/GOVERNANCE_RULES_20261115.md:1` | `repo_record` | `gravity-proposal` | # Aturan Tata Kelola Tetap — ACE Ω (15 November 2026) |
| `handover/GOVERNANCE_RULES_20261115.md:9` | `repo_record` | `gravity-proposal` | ## Aturan 1 — Kandidat self-dev hanya berhasil bila hidup |
| `handover/GOVERNANCE_RULES_20261115.md:30` | `repo_record` | `gravity-proposal` | ## Aturan 2 — Ratifikasi independen adalah standar |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:32` | `repo_record` | `gravity-proposal` | \| `C1_DO_NOT_RUN_BLOCK` \| `EP1-G3-APPLICATION.txt` (`G3-20261113-LOCKED`) \| `recommended_option="do_not_run"` ratified -> `dispatch_staged` refuses (`DoNotRunError`), `runs_created=0` \| **PASS** \| |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:36` | `repo_record` | `gravity-proposal` | \| `C5_IRREVOCABLE_MIDFLIGHT_REVOCATION` \| `EP5-G4-INHERITANCE.txt` (`G4-HERIT-20261113`) \| Mid-flight `revoke_staged(actor="evidence")` -> `STOPPED` (`revoked_at_seq:26`), `preaudit_exit_code=0`, re-ratify blocked (`Revo… |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:46` | `repo_record` | `gravity-proposal` | ## 2. TATA KELOLA & KLAIM — APA KATA REPO TENTANG DIRINYA |

## Keputusan Pemilik / Hub / Verdict (`OWNER_HUB_DECISION`)

- Kecocokan total: **776** | Ditampilkan: **35**

| Sumber & Baris | Aktor Sumber | Asal Ringkasan | Kutipan |
| --- | --- | --- | --- |
| `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:111` | `repo_record` | `gravity-proposal` | If all terminal controls are publicly known or reused to tune candidates, assign `SCIENTIFIC_NOT_ASSESSED` even if all CI tests pass. If 0 gain or worse, log a negative result and update hypotheses; do not re-score repea… |
| `docs/ACE_G0_G2_RESULTS_V1.md:17` | `repo_record` | `gravity-proposal` | \| `SCIENTIFIC_CAPABILITY_VALIDATED` \| **`TRUE` (Public Pre-Registered Benchmark `H1..H5` Pass; `NOT_ASSESSED` externally)** \| Monotonic generational gains (`0.5111 → 0.6875 → 0.9625` on unseen `U_gen`), beating `4×` comp… |
| `docs/ACE_PARSE_ONCE_RESULTS_20261113.md:31` | `repo_record` | `gravity-proposal` | ## Gate 1 — equivalence (must pass before any timing claim) |
| `docs/ACE_REPAIR_RESULTS_V1.md:117` | `repo_record` | `gravity-proposal` | \| **`H3`:** Anti-overfitting rejection on `TRAP_overfit` and abstention on `OOD_abstain` \| **`PASS`** \| Unverified arms committed `4` total false admissions on `TRAP_overfit` (`R_fresh`: `2/2` on `T17` `OP_OVERFIT_CONSTA… |
| `docs/ACE_SELFMODEL_RESULTS_V1.md:16` | `repo_record` | `gravity-proposal` | \| `SCIENTIFIC_CAPABILITY_VALIDATED` \| **`TRUE` (Public Diagnostic Gate Pass; `NOT_ASSESSED` externally)** \| Pre-registered 60-trial causal intervention benchmark (`I1..I5`) beat `B_const`, `B_baserate`, and `B_shuffled` … |
| `docs/research/ACE_BAKEOFF_02_DESIGN_20261113.md:1` | `repo_record` | `gravity-proposal` | # Bake-off 02 — design (successor candidate selection, citation-validator hardening, single composite pass rule) |
| `docs/research/ACE_BAKEOFF_02_DESIGN_20261113.md:193` | `repo_record` | `gravity-proposal` | ## 3. Pass rule: ONE composite metric, from the start |
| `docs/research/ACE_BAKEOFF_02_PREREGISTRATION_20261113.md:103` | `hub` | `gravity-proposal` | PER-PROPOSAL (hub decision 2026-11-13 16:07); every |
| `docs/research/ACE_BAKEOFF_02_PREREGISTRATION_20261113.md:114` | `repo_record` | `gravity-proposal` | ## 5. Pass rule (ONE composite metric, design §3) |
| `docs/research/ACE_BAKEOFF_02_PREREGISTRATION_DRAFT_20261113.md:72` | `repo_record` | `gravity-proposal` | ## 5. Pass rule (ONE composite metric, design §3) |
| `docs/research/ACE_BAKEOFF_ARENA_EXPANSION_DESIGN_DRAFT_20261113.md:276` | `hub` | `gravity-proposal` | semantics per-proposal per the hub decision |
| `docs/research/ACE_BRAIN_BAKEOFF_01_20261113.md:35` | `repo_record` | `gravity-proposal` | ## 3. Verdict and consequence |
| `docs/research/ACE_G3_PREREGISTRATION_20261113.md:235` | `repo_record` | `gravity-proposal` | ## 6. Pass rule (mechanical; verdicts derived) |
| `docs/research/ACE_G4_PREREGISTRATION_20261113.md:170` | `repo_record` | `gravity-proposal` | ## §6 Pass rule (mechanical; scored by the G4 instrument) |
| `docs/research/ACE_G5_HARVEST_PREREGISTRATION_DRAFT_20261113.md:9` | `repo_record` | `gravity-proposal` | NOT_ASSESSED** — no verdict is recorded anywhere |
| `docs/research/ACE_LINEAGE_GUARD_PREREG_FRAMEWORK_DRAFT_20261113.md:192` | `repo_record` | `gravity-proposal` | ## 5. Verdict criteria |
| `docs/research/ACE_LINEAGE_GUARD_PREREG_FULL_DRAFT_20261113.md:141` | `repo_record` | `gravity-proposal` | ### A.7 Endpoints and mechanical verdict worksheet |
| `handover/BRAIN_SLATE_V2_INTAKE_20261116.md:1` | `pemilik` | `gravity-proposal` | # REKAMAN INTAKE — Slate Otak v2 (Keputusan Pemilik 15 Nov 23:46 WIB) |
| `handover/ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md:103` | `repo_record` | `gravity-proposal` | ## 6. What an adoption verdict needs, exactly |
| `handover/EVO_0003_KONSOLIDASI_20261116.md:82` | `repo_record` | `gravity-proposal` | ### B5 — live-fire fail-closed: PASS |
| `handover/EVO_0004_KONSOLIDASI_20261116.md:8` | `repo_record` | `gravity-proposal` | ## Blok B — audit jalur tulis (PASS, ter-ratifikasi) |
| `handover/EVO_0005_KONSOLIDASI_20261116.md:42` | `hub` | `gravity-proposal` | ## Insiden outage + koreksi (keputusan hub ±20:00) |
| `handover/LINEAGE_GUARD_CONFIRMATION_VERDICT_20261114.md:1` | `repo_record` | `gravity-proposal` | # PROGRAM VERDICT — LINEAGE-GUARD CONFIRMATION RUN: GUARD_ADOPTED (2026-11-14) |
| `handover/LINEAGE_GUARD_CONFIRMATION_VERDICT_20261114.md:7` | `repo_record` | `gravity-proposal` | ## 1. Verdict & Activation Record (§8 + §A.7) |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:1` | `repo_record` | `gravity-proposal` | # PROGRAM VERDICT — PROPOSER ENGINE STAGE 1 EXIT GATE: NOT_PASSED |
| `handover/PROPOSER_STAGE1_V2_EXIT_GATE_VERDICT_20261114.md:1` | `repo_record` | `gravity-proposal` | # PROGRAM VERDICT — PROPOSER ENGINE STAGE 1 V2 EXIT GATE: PARTIAL (QUALITY PASS) |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:1` | `repo_record` | `gravity-proposal` | # PROPOSER STAGE 2 — ISOLATED STAGING & CONSTITUTION ENGINE VERDICT (2026-11-14) |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:26` | `repo_record` | `gravity-proposal` | ## 2. Constitution Battery Results (7/7 PASS over Real Frozen Stage-1 v2 Packages) |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:34` | `repo_record` | `gravity-proposal` | \| `C3_VISIBLE_STOP_AND_NO_AUTO_RETRY` \| `EP3-ROUND2-GATE.txt` (`g3-lift-round2-20261113`) \| Visible mid-flight `request_stop` -> `STOPPED` (`calls_used=3`, `cost_units=0.15`), `preaudit_exit_code=0`, re-dispatch blocked … |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:35` | `repo_record` | `gravity-proposal` | \| `C4_HARD_CEILING_ABORT` \| `EP4-CONTROL-REGRESSION-ATTRIBUTION.txt` (`pr-20261113-v3-attrib`) \| Projected step exceeding `max_calls=2` -> `ABORTED_CEILING`, `preaudit_exit_code=0`, re-dispatch blocked \| **PASS** \| |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:38` | `repo_record` | `gravity-proposal` | \| `C7_BLOB_BEFORE_COMMIT_AND_CHAIN_AUDIT` \| All 6 packages \| #8C pre-commit corrupted blob blocked (`BlobIntegrityError`), `verify_ledger()=True` (36 entries), `MissionBus` chain & eval journal valid \| **PASS** \| |
| `handover/RANCANGAN_EVO_0007.md:4` | `hub` | `gravity-proposal` | Status: rancangan saja, atas arahan hub. Praregistrasi |
| `handover/SERVING_INTEGRATION_REVIEW_20261114.md:94` | `repo_record` | `gravity-proposal` | ## 5. What an adoption verdict needs, exactly |
| `handover/local_state_sweep_20261115/misi9/MISI9_LAPORAN.md:16` | `repo_record` | `gravity-proposal` | ## 1. Verdict per baseline |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:60` | `repo_record` | `gravity-proposal` | - **[BERKAS]** "G0 PASS (session-scoped); G1 DEMONSTRATED; **G2 MEASURED — NOT_DEMONSTRATED**; **G3 MEASURED — SPECIALIZATION**; **G4 MEASURED — INHERITANCE_DEMONSTRATED**; **G5 NOT_ASSESSED** (period locked 12 Nov → 30 … |

## Butir Diparkir / Terblokir / Menunggu (`PARKED_OR_BLOCKED`)

- Kecocokan total: **379** | Ditampilkan: **35**

| Sumber & Baris | Aktor Sumber | Asal Ringkasan | Kutipan |
| --- | --- | --- | --- |
| `docs/ACE_AUTONOMOUS_RUNTIME_DEEP_RESEARCH_20261107.md:96` | `repo_record` | `gravity-proposal` | → REJECTED \| STAGED_FOR_REVIEW \| HALT_UNCERTAIN |
| `docs/ACE_AUTONOMY_CORE_PRESCORE_V01.md:38` | `repo_record` | `gravity-proposal` | Scientific NOT_ASSESSED; OAIE, unrestricted repair, new representation classes |
| `docs/ACE_AUTONOMY_CORE_PRESCORE_V01.md:40` | `repo_record` | `gravity-proposal` | its own verified sandbox and is blocked until then. |
| `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:122` | `repo_record` | `gravity-proposal` | - Preserve complete ancestry and rejected variants; record model-provider weights/version when available, not only patch source. |
| `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:152` | `repo_record` | `gravity-proposal` | - `SCIENTIFIC_NOT_ASSESSED`: independence, blinding or compute comparison missing. |
| `docs/ACE_AUTONOMY_V1_RESULTS.md:6` | `repo_record` | `gravity-proposal` | **Scientific status:** `NOT_ASSESSED` \| **Release status:** `BLOCK_RELEASE` \| **OAIE:** `NOT_ESTABLISHED` |
| `docs/ACE_AUTONOMY_V1_RESULTS.md:14` | `repo_record` | `gravity-proposal` | - `SCIENTIFIC_CAPABILITY_VALIDATED`: **`FALSE` (`NOT_ASSESSED`)** — `ace_autonomy` adalah fondasi rekayasa ketahanan operasional (Gate 1), bukan klaim keunggulan pembelajaran ilmiah. |
| `docs/ACE_CAPABILITY_DECISION_AND_CODEX_HANDOFF_20261107.md:13` | `repo_record` | `gravity-proposal` | - PR #62 (unmerged stacked on #60) persistent model-library cross-rule transfer: **0/16 target model reuses without refitting**; retained and fresh both stage 12/16, score 1536/2048 counting rejected targets as zero cove… |
| `docs/ACE_CAPABILITY_DECISION_AND_CODEX_HANDOFF_20261107.md:16` | `repo_record` | `gravity-proposal` | - Red Team [Issue #53](https://github.com/dianzherdiana25-hash/ACE/issues/53), PR #30 report unresolved **P1 problems in historical E1.5 / source-evolution branch**, including journal concurrency and external holdout rep… |
| `docs/evolution/neutral_archive_prescore_20261109.md:11` | `repo_record` | `gravity-proposal` | Budget cap: 24 tasks x 5 arms x 25 proposals = 3000 proposal evaluations; 24 x 3 = 72 unique environment labels, reused across arms; 24 x 4 = 96 terminal labels for measurement; negative control additional 4 terminal lab… |
| `docs/research/ACE_CROSS_FAMILY_TRANSFER_PRESCORE_V1.md:3` | `repo_record` | `gravity-proposal` | **State: DESIGN ONLY; scoring prohibited pending release gates.** Proposed on 2026-11-09. Research base `main` c0fd5bdb0b8654a3f6a50d9043eae77f50ef40b3; the integration candidate PR #93 is a separate, unmerged, changing … |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM23.md:1` | `pemilik` | `gravity-proposal` | # ACE Ω — Addendum 23, 2026-11-12: Tahap A — Rantai Blocker OMEGA-03, Vonis BLOCKED yang Persis, dan Amendemen Arah Pemilik |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM29.md:30` | `repo_record` | `gravity-proposal` | **rejected** oleh validator (proposal ke-3 tidak menyitir |
| `docs/research/hypgen/ACE_F10_HYPOTHESIS_SYNTHESIS_PRESCORE_20261107.md:13` | `repo_record` | `gravity-proposal` | Prior autonomous execution in ACE Fase 9 (`code/ace_research_agenda/coordinator.py`) demonstrated autonomous multi-cycle execution, but its hypothesis proposal mechanism selected hypotheses from a fixed, hand-authored ca… |
| `docs/research/self_dev/ACE_SELF_DEV_LOOP_V01_RESULTS_20261107.md:92` | `repo_record` | `gravity-proposal` | - **Proposal Title:** `ACE Self-Dev Cycle 1: task_k2_modular_stride_shift [REJECTED]` |
| `handover/ECOSYSTEM_INTAKE_01_20261113.md:14` | `repo_record` | `gravity-proposal` | rejected (worse both axes). Recorded in the |
| `handover/EVO_0003_STAGING_NOTE.md:16` | `repo_record` | `gravity-proposal` | 1801 suitable-unused, 1802 rejected) |
| `handover/PETA_ARAH_SERIBU_TAHUN.md:33` | `repo_record` | `gravity-proposal` | G4 INHERITANCE_DEMONSTRATED; G5 NOT_ASSESSED |
| `handover/PETA_ARAH_SERIBU_TAHUN.md:106` | `pemilik` | `gravity-proposal` | yang oleh pemilik sendiri diparkir bila ia memakan |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:33` | `repo_record` | `gravity-proposal` | \| EP1 G3 application \| 699 \| 887 \| REJECTED \| 0 \| 100 \| −100 \| |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:36` | `repo_record` | `gravity-proposal` | \| EP4 control-regression attribution \| 764 \| 841 \| REJECTED \| 0 \| 90 \| −90 \| |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:37` | `repo_record` | `gravity-proposal` | \| EP5 G4 inheritance \| 863 \| 891 \| REJECTED \| 0 \| 80 \| −80 \| |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:38` | `repo_record` | `gravity-proposal` | \| EP6 per-task recording \| 779 \| 898 \| REJECTED \| 0 \| 80 \| −80 \| |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:59` | `repo_record` | `gravity-proposal` | of a list of strings. The fail-closed validator rejected |
| `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md:71` | `repo_record` | `gravity-proposal` | under the locked rule a validator-rejected package scores 0, |
| `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md:12` | `pemilik` | `gravity-proposal` | `FORBIDDEN_RATIFICATION_TERMS` (`owner_approval`, `owner_permission`, `izin_pemilik`, `persetujuan_pemilik`) are rejected fail-closed across proposal packages, `request_id`, ratification records, revocation metadata, sto… |
| `handover/RANCANGAN_EVO_0007.md:5` | `repo_record` | `gravity-proposal` | 0007 menunggu vonis penerus 0006 — karena mesin probe |
| `handover/local_state_sweep_20261115/misi9/MISI9_LAPORAN.md:104` | `repo_record` | `gravity-proposal` | G5 NOT_ASSESSED) BERDIRI — tidak ada dokumen papan gerbang yang berubah |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:55` | `repo_record` | `gravity-proposal` | - **[BERKAS]** `release_gate=BLOCK_RELEASE`, `scientific_status=NOT_ASSESSED`, `oaie_established=False` — verbatim sama di `STATUS.md` §5, `README.md`, `TEST_READY.md` §5, `docs/ACE_VISION_ALIGNMENT_CURRENT.md`, dan blok… |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:148` | `repo_record` | `gravity-proposal` | - Governance verbatim: `{"release_gate": "BLOCK_RELEASE", "scientific_status": "NOT_ASSESSED", "oaie_established": false}`. |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:181` | `repo_record` | `gravity-proposal` | - **G5:** **tidak ada** berkas panen G5 di `evidence/`. Yang ada hanya memo kesiapan yang menyatakan verbatim: "Status: MEMO KESIAPAN — bukan panen, bukan praregistrasi, bukan penilaian. G5 tetap NOT_ASSESSED." (`evidenc… |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:207` | `hub` | `gravity-proposal` | Papan Ω repo sendiri (Addendum 59/60, §2.3) **identik** dengan papan hub: G2 NOT_DEMONSTRATED, G3 SPECIALIZATION, G4 INHERITANCE_DEMONSTRATED, round-2 LIFT_DEMONSTRATED, G5 NOT_ASSESSED. Proposer stage-1 v1 NOT_PASSED da… |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:212` | `pemilik` | `gravity-proposal` | 2. **`STATUS.md` kontradiksi diri + basi.** Header `CONFIRMED_SEALED (diotorisasi pemilik)` vs §5-nya sendiri `NOT_ASSESSED/BLOCK_RELEASE`; bertanggal 8 Nov/commit `de1f644` sementara tree 15 Nov; `CURRENT_STATE.md`/`NEX… |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:228` | `repo_record` | `gravity-proposal` | - **[KODE] yang benar-benar bekerja:** jalur terukur grid/discovery/scorer (tersambung, tanpa import hilang, tanpa stub); instrumen gerbang fail-closed; proposer/validator/battery sebagai subsistem mandiri yang utuh; `co… |
| `handover/local_state_sweep_20261115/study-ace-77cca3c.md:230` | `repo_record` | `gravity-proposal` | - Repo ini secara tidak biasa **memuat koreksinya sendiri**: dokumen audit internal (`docs/validation/ACE_OAIE_AUDIT_20261110.md`, `docs/research/ACE_OMEGA_CAPABILITY_AUDIT_20261111.md`), field governance `BLOCK_RELEASE/… |

## Usulan / Draf / Langkah Berikutnya (`OPEN_PROPOSAL`)

- Kecocokan total: **211** | Ditampilkan: **35**

| Sumber & Baris | Aktor Sumber | Asal Ringkasan | Kutipan |
| --- | --- | --- | --- |
| `docs/research/ACE_MASTER_PROMPT_ANTIGRAVITY_UNIVERSAL_OFFLINE_OAIE_20261110.md:1274` | `repo_record` | `gravity-proposal` | ## 38. STATE, ANTREAN, LEASE, DAN CRASH RECOVERY |
| `docs/research/ACE_MISSION_ADMISSION_PROTOCOL_20261110.md:23` | `repo_record` | `gravity-proposal` | ## Rancangan terkunci sebelum implementasi/scoring |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM10.md:58` | `repo_record` | `gravity-proposal` | ## Antrean berikutnya |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM17.md:40` | `repo_record` | `gravity-proposal` | ## Urutan tahap berikutnya (dalam mandat) |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM4.md:39` | `repo_record` | `gravity-proposal` | ## Draf vonis (usulan direktur program) |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM8.md:48` | `repo_record` | `gravity-proposal` | ## Antrean Fase 1 berikutnya |
| `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM9.md:52` | `repo_record` | `gravity-proposal` | ## Antrean berikutnya |
| `docs/research/ACE_PHASE2_PILOT_ABC_RESULTS_20261112.md:62` | `repo_record` | `gravity-proposal` | ## Konsekuensi untuk tahap berikutnya |
| `docs/research/ACE_PHASE2_SHIPPING_MEASUREMENT_20261112.md:42` | `repo_record` | `gravity-proposal` | ## Konsekuensi terukur untuk tahap berikutnya |
| `docs/research/ACE_SELF_FUNDING_DESIGN_STUDY_20261112.md:81` | `pemilik` | `gravity-proposal` | ## 5. Tahap berikutnya (bila pemilik memberi mandat studi lanjut) |
| `docs/research/ACE_W3_ADMISSION_PRESCORE_20261110.md:27` | `repo_record` | `gravity-proposal` | ## Rancangan terkunci |
| `docs/research/self_dev/ACE_SELF_DEV_LOOP_V01_RESULTS_20261107.md:89` | `repo_record` | `gravity-proposal` | ### Phase 6 & 7: Checkpoint & Proposal |
| `docs/validation/ACE_OAIE_AUDIT_20261110.md:1` | `repo_record` | `gravity-proposal` | # ACE menuju OAIE — audit, rancangan, dan implementasi teruji |
| `handover/ABSORPTION_AUDIT_20261115.md:1` | `hub` | `gravity-proposal` | # AUDIT PENYERAPAN BELAJAR — Inventaris + Klasifikasi (DRAF untuk hub) |
| `handover/ABSORPTION_AUDIT_20261115.md:35` | `repo_record` | `gravity-proposal` | \| 8 \| Jalur tulis engine → ingatan kognitif (menghubungkan keluaran siklus ke memory store mission 0002) \| **(b) kandidat desain** \| Menjawab temuan #2. Perlu rancangan dulu (skema record apa yang layak disimpan; jangan … |
| `handover/ABSORPTION_AUDIT_20261115.md:39` | `repo_record` | `gravity-proposal` | \| 12 \| **Lineage guard → perilaku baku solver (default-on)** \| **(b) JALUR CEPAT** \| Lisensi: vonis GUARD_ADOPTED tersegel (PR #230). Rancangan aktivasi di bawah. \| |
| `handover/ABSORPTION_AUDIT_20261115.md:41` | `repo_record` | `gravity-proposal` | ## Rancangan aktivasi kandidat #12 (guard default-on) |
| `handover/ABSORPTION_AUDIT_20261115.md:61` | `repo_record` | `gravity-proposal` | ## Usulan urutan eksekusi kelas (b) |
| `handover/BRAIN_SLATE_V2_INTAKE_20261116.md:24` | `repo_record` | `gravity-proposal` | disajikan. Tahap berikutnya bench (MTP on/off via |
| `handover/EVO_0003_KONSOLIDASI_20261116.md:37` | `repo_record` | `gravity-proposal` | dijeda selama jendela. Target rancangan ±10 menit tidak tercapai; |
| `handover/EVO_0004_BLOKD_RUN_NOTE.md:1` | `hub` | `gravity-proposal` | # BLOK D — catatan operasional (DRAF, ditulis sebelum lari; diungkap ke hub sebelum eksekusi) |
| `handover/EVO_0004_STAGING_NOTE.md:3` | `repo_record` | `gravity-proposal` | Paket praregistrasi mengikuti pola PR #239. Rancangan: |
| `handover/EVO_0006_BAHAN_INHERITANCE.md:15` | `repo_record` | `gravity-proposal` | ## Bentuk uji (draf) |
| `handover/GOVERNANCE_RULES_20261115.md:50` | `repo_record` | `gravity-proposal` | sebagai artefak/draf (mis. draf PR), dengan labelnya |
| `handover/MEMORY_WRITE_PATH_DESIGN_20261115.md:1` | `repo_record` | `gravity-proposal` | # RANCANGAN — Jalur Tulis Engine → Ingatan Kognitif |
| `handover/MEMORY_WRITE_PATH_DESIGN_20261115.md:2` | `hub` | `gravity-proposal` | ## (Audit penyerapan PR #231, butir #8 — rancangan dulu, hub menilai) |
| `handover/MEMORY_WRITE_PATH_DESIGN_20261115.md:4` | `engineer_utama` | `gravity-proposal` | Status: RANCANGAN, belum dibangun. Ditulis Ian 2026-11-15. |
| `handover/PETA_ARAH_SERIBU_TAHUN.md:10` | `repo_record` | `gravity-proposal` | ini; peta hanya memastikan setiap butir antrean hari |
| `handover/PREREGISTRASI_EVO_0003_DRAF.md:1` | `repo_record` | `gravity-proposal` | # PRAREGISTRASI EVO 0003 — BENTUK KILAT (DRAF) |
| `handover/PREREGISTRASI_EVO_0004_DRAF.md:1` | `hub` | `gravity-proposal` | # RANCANGAN EVO 0004 — draft praregistrasi (dirancang hub, 2026-11-16) |
| `handover/PREREGISTRASI_EVO_0005_DRAF.md:1` | `hub` | `gravity-proposal` | # PREREGISTRASI EVO 0005 — DRAF (Ian, 2026-11-16; untuk ratifikasi hub) |
| `handover/PREREGISTRASI_EVO_0006_DRAF.md:1` | `engineer_utama` | `gravity-proposal` | # PREREGISTRASI EVO 0006 — DRAF (Ian, 2026-11-16 malam) |
| `handover/PREREGISTRASI_EVO_0006_PENERUS_DRAF.md:1` | `engineer_utama` | `gravity-proposal` | # PREREGISTRASI PENERUS EVO 0006 — DRAF (Ian, 2026-11-17 pagi) |
| `handover/RANCANGAN_EVO_0007.md:1` | `repo_record` | `gravity-proposal` | # RANCANGAN EVO 0007 — Recall Pola Terdistilasi ala Katalog |
| `handover/local_state_sweep_20261115/misi9/inventory_notes.md:1` | `repo_record` | `gravity-proposal` | # Misi 9 — Inventarisasi 08bd836..7541782 (draf kerja, 2026-11-15) |
