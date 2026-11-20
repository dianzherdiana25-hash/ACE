# Indeks Program AKTIVASI — EVO 0041–0050 (`AG101–AG200`)

Dokumen manual ini merangkum aktivasi modul pada jalur `autonomous_engine.py` Step 3d -> `code/ace_operational/leap_wiring.py` (gerbang `ACE_LEAPS=1`, sifat *fail-closed*) di atas basis `main` (`dc12a70`). Semua cabang berstatus **Draft PR** terpisah untuk peninjauan dan integrasi bertahap.

---

## Ringkasan 10 Paket Aktivasi (10 Papan EVO 0041–0050)

| Paket | Fokus | Rentang Pekerjaan | Draft PR | Suite Integrasi |
| --- | --- | --- | --- | --- |
| **EVO 0041** | Ingatan & Pemanggilan Kembali | AG101–AG110 | #589–#598 | `code/ace_operational/test_activation_0041.py` (#598) |
| **EVO 0042** | Kurikulum, Celah, Penguasaan & Eksekutor Wave-2 | AG111–AG120 | #599–#608 | `code/ace_operational/test_activation_0042.py` (#608) |
| **EVO 0043** | Director, Kandidat & Pertahanan Injeksi | AG121–AG130 | #609–#618 | `code/ace_operational/test_activation_0043.py` (#618) |
| **EVO 0044** | Rumah, Kustodi & Ketangguhan | AG131–AG140 | #619–#628 | `code/ace_operational/test_activation_0044.py` (#628) |
| **EVO 0045** | Perkakas, Tempa & Manajemen Proyek | AG141–AG150 | #629–#638 | `code/ace_operational/test_activation_0045.py` (#638) |
| **EVO 0046** | Organ Jembatan & Replikasi Rumah | AG151–AG160 | #639–#648 | `code/ace_operational/test_activation_0046.py` (#648) |
| **EVO 0047** | Identitas, Evaluasi & Tolok Ukur | AG161–AG170 | #649–#658 | `code/ace_operational/test_activation_0047.py` (#658) |
| **EVO 0048** | Kesadaran Diri & Metakognisi | AG171–AG180 | #659–#668 | `code/ace_operational/test_activation_0048.py` (#668) |
| **EVO 0049** | Ilmu, Sitasi & Software Factory | AG181–AG190 | #669–#677 | `code/ace_operational/test_activation_0049.py` (#677) |
| **EVO 0050** | Governansi, Transparansi & Handover | AG191–AG200 | #678–#687 | `code/ace_operational/test_activation_full.py` (#687) |

---

## Rincian Pekerjaan EVO 0041–0050

### 1. EVO 0041 — Ingatan & Pemanggilan Kembali (`AG101–AG110`, PR #589–#598)
- `AG101` `#589`: `tools/memory_hygiene_audit.py` → `memory_hygiene.json`
- `AG102` `#590`: `tools/memory_decay.py` (`%50`)
- `AG103` `#591`: `tools/memory_chain_compare.py` (`%200`)
- `AG104` `#592`: `tools/memory_anchor_audit.py` (hooked inside `step_recall`)
- `AG105` `#593`: `tools/recall_delivery_probe.py` & `tools/recall_precision_probe.py` (`%25`)
- `AG106` `#594`: `tools/embedding_index.py` (`%10`)
- `AG107` `#595`: `tools/introspect_recall.py` (`%25`)
- `AG108` `#596`: `tools/transfer_probe.py` (`%200`)
- `AG109` `#597`: `tools/metacog_memory_consolidate.py` (`%50`, `step_metacog_consolidation`)
- `AG110` `#598`: Integrasi EVO 0041 (`test_activation_0041.py`)

### 2. EVO 0042 — Kurikulum, Penguasaan & Eksekutor (`AG111–AG120`, PR #599–#608)
- `AG111` `#599`: `tools/mastery_board.py` (`%25`)
- `AG112` `#600`: `tools/gap_pattern_report.py` (inside `step_practice`)
- `AG113` `#601`: `tools/gap_root_cause_report.py` (inside `step_practice`)
- `AG114` `#602`: `tools/occurrence_outlier_scan.py` (`%10`)
- `AG115` `#603`: `tools/failure_to_agenda.py` (inside `step_practice`)
- `AG116` `#604`: `tools/practice_task_lint.py` (`%25`)
- `AG117` `#605`: `tools/curriculum_ab_report.py` (`%200`)
- `AG118` `#606`: `code/ace_operational/curriculum_wave2.py`
- `AG119` `#607`: `code/ace_operational/director_actions_wave2.py`
- `AG120` `#608`: Integrasi EVO 0042 (`test_activation_0042.py`)

### 3. EVO 0043 — Director & Pertahanan (`AG121–AG130`, PR #609–#618)
- `AG121` `#609`: `tools/director_grounding_check.py` (inside `step_director`)
- `AG122` `#610`: `tools/director_queue_router.py` (inside `step_director`)
- `AG123` `#611`: `tools/director_prose_audit.py` (`%25`)
- `AG124` `#612`: `tools/director_cap_simulator.py` (`%25`)
- `AG125` `#613`: `tools/candidate_census.py` (`%25`)
- `AG126` `#614`: `tools/candidate_factory_v2.py` (`%50`)
- `AG127` `#615`: `tools/discriminating_candidate_factory.py` (`%50`)
- `AG128` `#616`: `tools/agenda_candidates.py` (inside `step_director`)
- `AG129` `#617`: `tools/director_injection_fixtures.py` (`%25`)
- `AG130` `#618`: Integrasi EVO 0043 (`test_activation_0043.py`)

### 4. EVO 0044 — Rumah, Kustodi & Ketangguhan (`AG131–AG140`, PR #619–#628)
- `AG131` `#619`: `tools/receipt_chain_verify.py` (`%50`)
- `AG132` `#620`: `tools/custody_manifest_check.py` (`%200`)
- `AG133` `#621`: `step_checkpoint` verifikasi rantai berkala (`%10`)
- `AG134` `#622`: `tools/verify_self_dev.py` & `tools/verify_sources.py` (`%200`)
- `AG135` `#623`: `tools/restore_drill.py` (`%1000`, terisolasi `TemporaryDirectory`)
- `AG136` `#624`: `tools/coverage_and_flaky_audit.py` (`%200`)
- `AG137` `#625`: `tools/bundle_manifest_check.py` + `tools/bundle_manifest.py` (`%200`)
- `AG138` `#626`: `tools/migration_rehearsal.py` + `tools/instance_kit.py` + `tools/portability_pack.py` (`%1000`)
- `AG139` `#627`: `tools/run_evidence_pack.py` + `tools/pack_evidence.py` + `tools/stage_verify.py` (`%50`)
- `AG140` `#628`: Integrasi EVO 0044 (`test_activation_0044.py`)

### 5. EVO 0045 — Perkakas & Proyek (`AG141–AG150`, PR #629–#638)
- `AG141` `#629`: `tools/tool_registry.py` (`validate_registry`, `%25`)
- `AG142` `#630`: `tools/tool_forge.py` (hooked in `step_projects`)
- `AG143` `#631`: `tools/tool_registry.py` (`evaluate_registry`, `%200`)
- `AG144` `#632`: `tools/repo_arena.py` (`%200`)
- `AG145` `#633`: `tools/evo_scaffold.py` (hooked in `step_projects`)
- `AG146` `#634`: `tools/pattern_catalog.py` (`%50`)
- `AG147` `#635`: `tools/builder_onboarding_pack.py` (`%200`)
- `AG148` `#636`: `tools/pr_pack.py` (`%50`, dry-run)
- `AG149` `#637`: `tools/evo_results.py` + `tools/evo_range_audit.py` + `tools/evo_prereg_draft.py` (`%200`)
- `AG150` `#638`: Integrasi EVO 0045 (`test_activation_0045.py`)

### 6. EVO 0046 — Organ Jembatan & Replikasi (`AG151–AG160`, PR #639–#648)
- `AG151` `#639`: `code/ace_operational/brain_registry.py` (`%200`)
- `AG152` `#640`: `tools/organ_quality_board.py` (hooked in `step_organs`)
- `AG153` `#641`: `tools/organ_forensics.py` (`%200`)
- `AG154` `#642`: `tools/cross_organ_agreement.py` (`%25`)
- `AG155` `#643`: `tools/engine_idle_report.py` (`%50`)
- `AG156` `#644`: `tools/quota_failover_sim.py` (`%50`)
- `AG157` `#645`: `tools/ram_window.py` (preload guard in `step_organs`)
- `AG158` `#646`: `tools/failover_drill.py` (`%1000`, `plan_only=True`)
- `AG159` `#647`: `tools/home_replication_pack.py` + `tools/second_home.py` (`%1000`, isolated staging)
- `AG160` `#648`: Integrasi EVO 0046 (`test_activation_0046.py`)

### 7. EVO 0047 — Identitas, Evaluasi & Benchmarking (`AG161–AG170`, PR #649–#658)
- `AG161` `#649`: `tools/autobiography_probe.py` (`%200` -> `autobiography.md`)
- `AG162` `#650`: `tools/behavior_fingerprint.py` (`%200` -> `behavior_fingerprint.json`)
- `AG163` `#651`: `tools/story_consistency_gate.py` (`%50` -> `narrative_consistency.jsonl`; `story_state.py` tetap di karantina)
- `AG164` `#652`: `tools/constitution_dilemma.py` (`%200` -> `constitution_checks.jsonl`)
- `AG165` `#653`: `tools/omega_environment_probe.py` (`%50` -> `environment_probe.json`)
- `AG166` `#654`: `tools/capability_report.py` (`%200` -> `capability_report.md`)
- `AG167` `#655`: `tools/owner_benchmark.py` (`%1000` -> `owner_benchmark.json`)
- `AG168` `#656`: `tools/eval_bench.py` (`%200` -> `eval_bench_report.json`)
- `AG169` `#657`: `tools/saturation_scan.py` (hooked in `step_self` -> `saturation.json`)
- `AG170` `#658`: Integrasi EVO 0047 (`test_activation_0047.py`)

### 8. EVO 0048 — Kesadaran Diri & Metakognisi (`AG171–AG180`, PR #659–#668)
- `AG171` `#659`: `tools/self_assessment.py` (`%200` -> `self_assessment_chain.jsonl`, `self_assessment_latest.json`)
- `AG172` `#660`: `tools/self_model_continuity_probe.py` (`%200` -> `continuity_probe.json`)
- `AG173` `#661`: `tools/periodic_self_report.py` (`%200` -> `periodic_self_report.json`)
- `AG174` `#662`: `tools/daily_digest.py` (`%200` -> `daily_digest.json`, non-otoritatif)
- `AG175` `#663`: `tools/metacog_memory_consolidate.py` (`%50`, `step_metacog_consolidate` -> `metacog_consolidation.json`)
- `AG176` `#664`: `tools/writeback_diagnose.py` (`%200` -> `writeback_diagnose.json`, salinan snapshot SQLite `?mode=ro`)
- `AG177` `#665`: `tools/self_dev_git_audit.py` (`%200` -> `self_dev_git_audit.json`)
- `AG178` `#666`: `tools/successor_inventory.py` (`%200` -> `successor_inventory.json`)
- `AG179` `#667`: `tools/successor_variant.py` (`%1000` -> `successor_variant_status.json`)
- `AG180` `#668`: Integrasi EVO 0048 (`test_activation_0048.py`)

### 9. EVO 0049 — Ilmu, Sitasi & Software Factory (`AG181–AG190`, PR #669–#677)
- `AG181` `#669`: `tools/experiment_designer.py` (`%200` -> `experiment_designs.json`)
- `AG182` `#670`: `tools/corpus_novelty.py` (hooked in `step_self` -> `corpus_novelty.json`)
- `AG183` `#671`: `tools/teaching_program.py` (`%200` -> `teaching_program.json`)
- `AG184` `#672`: `code/ace_operational/citation_validator.py` (`%200` -> `citation_validation.json`)
- `AG185` `#673`: `code/ace_operational/catalog_artifact.py` + `catalog_gap.py` (`%200` -> `operator_catalog.json`, `catalog_audit.json`)
- `AG186` `#674`: `code/ace_operational/preaudit_oracle.py` (`%200` -> `preaudit_oracle.json`)
- `AG187` `#675`: `code/ace_operational/proposer_stage1_v2.py` (`%200`, gated `ACE_PROPOSER_V2=1` default off)
- `AG188` **DILEWATI (§3)**: `code/ace_operational/admission_hygiene.py` mengimpor `abc_v3_scorer` (wilayah terlarang §3) dan sudah tersambung di `oaie_engine.py`; tidak disambungkan ke `leap_wiring.py`
- `AG189` `#676`: `code/ace_operational/software_factory.py` (`%1000` -> `software_factory_status.json`)
- `AG190` `#677`: Integrasi EVO 0049 (`test_activation_0049.py`)

### 10. EVO 0050 — Governansi, Transparansi & Handover (`AG191–AG200`, PR #678–#687)
- `AG191` `#678`: `tools/verdict_board.py` (`%200` -> `verdict_board.json`, `verdict_board.md`)
- `AG192` `#679`: `tools/wiring_audit.py` (`%200` -> `wiring_audit_live.json`)
- `AG193` `#680`: `tools/release_manifest.py` (`%200` -> `release_manifest.json`)
- `AG194` `#681`: `tools/draft_release_preflight.py` (`%200` -> `draft_release_preflight.json`, `send_authorized=false`)
- `AG195` `#682`: `tools/self_send_standing_audit.py` (`%200` -> `self_send_standing_audit.json`, read-only tanpa `self_send`)
- `AG196` `#683`: `tools/repo_status_dashboard_v3.py` (`%200` -> `repo_dashboard_v3.json`, `repo_dashboard_v3.html`)
- `AG197` `#684`: `tools/handover_index.py` + `tools/handover_decision_extractor.py` (`%200` -> `handover_index.json`, `handover_decisions.json`)
- `AG198` `#685`: `tools/platform_requirements_summary.py` (`%200` -> `platform_requirements.json`)
- `AG199` `#686`: `docs/AKTIVASI_INDEX.md` (indeks manual seluruh papan aktivasi EVO 0041–0050)
- `AG200` `#687`: Integrasi penuh EVO 0041–0050 (`test_activation_full.py`)

---

## Pengecualian Wilayah Terlarang (§3)

Seluruh modul berikut tetap dikarantina dan **tidak pernah** disambungkan ke jalur tulis/live oleh seri PR AKTIVASI ini:
- `code/ace_operational/story_state.py`
- `code/ace_operational/abc_v3_scorer.py` & `code/ace_operational/admission_hygiene.py` (karena mengimpor `abc_v3_scorer`)
- `g*_instrument*`, `evo0007_run.py`, `code/ace_evaluator/**`
- `memory_writeback.py` & jalur tulis `cognitive_memory.py`
- Jalur uang (`income_*`, `rails_*`, `revenue_*`, `ledger_dryrun`)
- Kirim keluar langsung (`tools/self_send.py` jalur kirim)
- Harness destruktif pada loop produksi (`tools/chaos_kill_harness.py`)
