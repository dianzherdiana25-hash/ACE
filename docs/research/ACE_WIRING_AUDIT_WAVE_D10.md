# Audit & Backlog Penyambungan Gelombang D10 — ACE

- Schema: `ace.wiring-audit.v1`
- Acuan commit `main`: `ba7f4b9` (diukur langsung via `python3 tools/wiring_audit.py --format json`)
- Total modul non-tes dipindai: **425**
- `WIRED` (aktif dipakai non-test): **262**
- `CLI_STANDALONE` (punya `__main__`, belum tersambung ke orkestrator): **98**
- `ORPHAN` (tanpa pemanggil non-test & tanpa `__main__`): **42**
- `MENUNGGU_ENGINEER_UTAMA` (wilayah terlarang / titik sambung EVO 0007 / evaluator / memory writeback): **23**
- Backlog aman siap sambung: **75** perkakas `tools/` + **34** modul orphan `code/`

> **Aturan D10**: Modul berstatus `MENUNGGU_ENGINEER_UTAMA` (23 modul) **TIDAK DISENTUH** pada gelombang ini dan diserahkan ke engineer utama. Penyambungan dilakukan bertahap **1 perkakas per PR** pada jalur non-terlarang.

## Status Pasca-Penyambungan (diperbarui engineer utama, 20 Nov 2026)

Keempat antrean prioritas di bawah **SUDAH disambungkan dan tergabung ke `main`**: `tools/kbm_qc.py` → `tools/kbm_produce.py` (#425), `tools/kbm_suite_v2.py` → `tools/kbm_pipeline.py` (#426), `tools/organ_quota_ledger.py` → `tools/daily_digest.py` (#427), `tools/writeback_diagnose.py` → `tools/daily_digest.py` (#428). Angka dan tabel di dokumen ini adalah potret audit pada `ba7f4b9` (sebelum penyambungan); audit langsung pasca-penggabungan melaporkan keempatnya berstatus `WIRED`. Daftar 23 modul `MENUNGGU_ENGINEER_UTAMA` tidak berubah.

## Antrean Prioritas Penyambungan Aman (1 PR per Perkakas)

| Prioritas | Perkakas Target | Orkestrator Tujuan | Cabang D10 | Alasan |
| ---: | --- | --- | --- | --- |
| 1 | `tools/kbm_qc.py` | `tools/kbm_produce.py` | `gravity/wiring-kbm-qc` | Menjalankan gerbang QC manuskrip KBM pra-pecah secara opsional via `--qc` |
| 2 | `tools/kbm_suite_v2.py` | `tools/kbm_pipeline.py` | `gravity/wiring-kbm-suite-v2` | Menambah audit *pacing* (mean/stddev) & duplikat bab pasca-split via `--qa-v2` |
| 3 | `tools/organ_quota_ledger.py` | `tools/daily_digest.py` | `gravity/wiring-organ-quota-ledger` | Membaca/merekonsiliasi buku anggaran kuota organ multi-rute ke sinyal digest harian |
| 4 | `tools/writeback_diagnose.py` | `tools/daily_digest.py` | `gravity/wiring-writeback-diagnose` | Merangkum kesehatan write-back cognitive memory (read-only) ke digest harian |

## Daftar Wilayah Menunggu Engineer Utama (23 — TIDAK DISENTUH)

| Modul | Berkas | Alasan | Pemanggil Non-Tes |
| --- | --- | --- | ---: |
| `ace_evaluator.cheat_detection` | `code/ace_evaluator/cheat_detection.py` | `modul_wilayah_terlarang` | 1 |
| `ace_evaluator.sealed_generator` | `code/ace_evaluator/sealed_generator.py` | `modul_wilayah_terlarang` | 1 |
| `ace_evaluator.task_families` | `code/ace_evaluator/task_families.py` | `modul_wilayah_terlarang` | 1 |
| `ace_operational.abc_v3_scorer` | `code/ace_operational/abc_v3_scorer.py` | `modul_wilayah_terlarang` | 2 |
| `ace_operational.cognitive_memory` | `code/ace_operational/cognitive_memory.py` | `modul_wilayah_terlarang` | 6 |
| `ace_operational.evo0007_run` | `code/ace_operational/evo0007_run.py` | `modul_wilayah_terlarang` | 0 |
| `ace_operational.g1_instrument` | `code/ace_operational/g1_instrument.py` | `modul_wilayah_terlarang` | 0 |
| `ace_operational.g3_instrument` | `code/ace_operational/g3_instrument.py` | `modul_wilayah_terlarang` | 0 |
| `ace_operational.g4_instrument` | `code/ace_operational/g4_instrument.py` | `modul_wilayah_terlarang` | 0 |
| `ace_operational.g5_instrument` | `code/ace_operational/g5_instrument.py` | `modul_wilayah_terlarang` | 0 |
| `ace_operational.memory_writeback` | `code/ace_operational/memory_writeback.py` | `modul_wilayah_terlarang` | 5 |
| `ace_operational.round2_instrument` | `code/ace_operational/round2_instrument.py` | `modul_wilayah_terlarang` | 0 |
| `tools.abc_v3_run` | `tools/abc_v3_run.py` | `modul_wilayah_terlarang` | 2 |
| `tools.corpus_lint` | `tools/corpus_lint.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 6 |
| `tools.corpus_registry` | `tools/corpus_registry.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 1 |
| `tools.corpus_tag` | `tools/corpus_tag.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 0 |
| `tools.curriculum_gen` | `tools/curriculum_gen.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 0 |
| `tools.four_arm_report` | `tools/four_arm_report.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 0 |
| `tools.memory_writeback` | `tools/memory_writeback.py` | `modul_wilayah_terlarang` | 0 |
| `tools.pattern_distill` | `tools/pattern_distill.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 2 |
| `tools.round2_gate_run` | `tools/round2_gate_run.py` | `modul_wilayah_terlarang` | 0 |
| `tools.screen_census` | `tools/screen_census.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 1 |
| `tools.verify_f13_f14` | `tools/verify_f13_f14.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` | 0 |

## Seluruh `tools_unwired_safe` (75)

| Berkas | Status | Pemanggil Tes |
| --- | --- | ---: |
| `tools/ace_autonomous_daemon.py` | `CLI_STANDALONE` | 0 |
| `tools/ace_fr01_retrieval_benchmark.py` | `CLI_STANDALONE` | 0 |
| `tools/ace_mission_admission_benchmark.py` | `CLI_STANDALONE` | 0 |
| `tools/ace_mission_worker.py` | `CLI_STANDALONE` | 0 |
| `tools/ace_real_world_cli.py` | `CLI_STANDALONE` | 0 |
| `tools/ace_reasoning.py` | `CLI_STANDALONE` | 1 |
| `tools/ace_reasoning_audit.py` | `CLI_STANDALONE` | 1 |
| `tools/ace_w3_admission_benchmark.py` | `CLI_STANDALONE` | 0 |
| `tools/agenda_candidates.py` | `CLI_STANDALONE` | 2 |
| `tools/bakeoff02_a.py` | `ORPHAN` | 0 |
| `tools/bakeoff02_b.py` | `ORPHAN` | 0 |
| `tools/bakeoff02_c.py` | `ORPHAN` | 0 |
| `tools/bakeoff02_finalize.py` | `ORPHAN` | 0 |
| `tools/bakeoff_a.py` | `ORPHAN` | 0 |
| `tools/bakeoff_b.py` | `ORPHAN` | 0 |
| `tools/bakeoff_c.py` | `ORPHAN` | 0 |
| `tools/builder_onboarding_pack.py` | `CLI_STANDALONE` | 1 |
| `tools/candidate_corpus_batch.py` | `CLI_STANDALONE` | 1 |
| `tools/candidate_factory_v2.py` | `CLI_STANDALONE` | 1 |
| `tools/corpus_freeze_packer.py` | `CLI_STANDALONE` | 1 |
| `tools/coverage_and_flaky_audit.py` | `CLI_STANDALONE` | 1 |
| `tools/cross_organ_agreement.py` | `CLI_STANDALONE` | 1 |
| `tools/ctrlreg_stage0_replay.py` | `CLI_STANDALONE` | 0 |
| `tools/ctrlreg_stage2_dose.py` | `CLI_STANDALONE` | 0 |
| `tools/curriculum_lab.py` | `CLI_STANDALONE` | 1 |
| `tools/daily_digest.py` | `CLI_STANDALONE` | 2 |
| `tools/director_cycle_record.py` | `CLI_STANDALONE` | 1 |
| `tools/director_prose_audit.py` | `CLI_STANDALONE` | 1 |
| `tools/director_value_check.py` | `CLI_STANDALONE` | 1 |
| `tools/draft_release_preflight.py` | `CLI_STANDALONE` | 1 |
| `tools/eval_bench.py` | `CLI_STANDALONE` | 1 |
| `tools/evo_results.py` | `CLI_STANDALONE` | 2 |
| `tools/evo_scaffold.py` | `CLI_STANDALONE` | 1 |
| `tools/failure_to_agenda.py` | `CLI_STANDALONE` | 1 |
| `tools/fuzz_parsers.py` | `CLI_STANDALONE` | 1 |
| `tools/fuzz_wseh.py` | `CLI_STANDALONE` | 1 |
| `tools/handover_decision_extractor.py` | `CLI_STANDALONE` | 1 |
| `tools/handover_index.py` | `CLI_STANDALONE` | 1 |
| `tools/income_report.py` | `CLI_STANDALONE` | 1 |
| `tools/income_verify.py` | `CLI_STANDALONE` | 1 |
| `tools/inoculation_demo.py` | `ORPHAN` | 0 |
| `tools/introspect_recall.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_produce.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_production_queue.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_qc.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_suite_v2.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_titles.py` | `CLI_STANDALONE` | 1 |
| `tools/metacog_memory_consolidate.py` | `CLI_STANDALONE` | 1 |
| `tools/migration_rehearsal.py` | `CLI_STANDALONE` | 1 |
| `tools/omega_environment_probe.py` | `CLI_STANDALONE` | 1 |
| `tools/organ_quota_ledger.py` | `CLI_STANDALONE` | 1 |
| `tools/organ_registry_validate.py` | `CLI_STANDALONE` | 1 |
| `tools/organ_smoke_harness.py` | `CLI_STANDALONE` | 1 |
| `tools/pattern_catalog.py` | `CLI_STANDALONE` | 2 |
| `tools/periodic_self_report.py` | `CLI_STANDALONE` | 1 |
| `tools/platform_requirements_summary.py` | `CLI_STANDALONE` | 1 |
| `tools/program_glossary.py` | `CLI_STANDALONE` | 1 |
| `tools/regression_anchor.py` | `CLI_STANDALONE` | 0 |
| `tools/repair_v2_probe.py` | `CLI_STANDALONE` | 0 |
| `tools/repo_cartography.py` | `CLI_STANDALONE` | 1 |
| `tools/repo_status_dashboard_v3.py` | `CLI_STANDALONE` | 1 |
| `tools/revenue_reconcile.py` | `CLI_STANDALONE` | 1 |
| `tools/run_evidence_pack.py` | `CLI_STANDALONE` | 1 |
| `tools/saturation_scan.py` | `CLI_STANDALONE` | 1 |
| `tools/seal_run.py` | `CLI_STANDALONE` | 2 |
| `tools/secrets_bundle.py` | `CLI_STANDALONE` | 1 |
| `tools/self_dev_git_audit.py` | `CLI_STANDALONE` | 2 |
| `tools/self_model_continuity_probe.py` | `CLI_STANDALONE` | 1 |
| `tools/verify_full_system.py` | `CLI_STANDALONE` | 0 |
| `tools/verify_repair_v2.py` | `CLI_STANDALONE` | 1 |
| `tools/verify_runtime_demo_v2.py` | `CLI_STANDALONE` | 1 |
| `tools/verify_self_dev.py` | `CLI_STANDALONE` | 0 |
| `tools/wiring_audit.py` | `CLI_STANDALONE` | 1 |
| `tools/writeback_diagnose.py` | `CLI_STANDALONE` | 1 |
| `tools/ws2_fixture_harness.py` | `CLI_STANDALONE` | 1 |

## Seluruh `code_orphans_safe` (34)

| Berkas | Modul | Pemanggil Tes |
| --- | --- | ---: |
| `code/ace_abstract_interp/disjunctive_domain.py` | `ace_abstract_interp.disjunctive_domain` | 1 |
| `code/ace_abstraction/wake_sleep.py` | `ace_abstraction.wake_sleep` | 2 |
| `code/ace_autonomy/research_pipeline.py` | `ace_autonomy.research_pipeline` | 1 |
| `code/ace_cognition/evolutionary_memory.py` | `ace_cognition.evolutionary_memory` | 2 |
| `code/ace_cognition/meta_curriculum.py` | `ace_cognition.meta_curriculum` | 1 |
| `code/ace_core_repair/decomposed_library.py` | `ace_core_repair.decomposed_library` | 1 |
| `code/ace_core_repair/drift_quarantine.py` | `ace_core_repair.drift_quarantine` | 3 |
| `code/ace_dsl_growth/experiment_runner.py` | `ace_dsl_growth.experiment_runner` | 1 |
| `code/ace_epistemic/active_sampler.py` | `ace_epistemic.active_sampler` | 1 |
| `code/ace_evolution/pareto_dsl_optimizer.py` | `ace_evolution.pareto_dsl_optimizer` | 1 |
| `code/ace_gnn/ast_embedder.py` | `ace_gnn.ast_embedder` | 1 |
| `code/ace_host_controller/controller.py` | `ace_host_controller.controller` | 0 |
| `code/ace_host_controller/evaluator_v2.py` | `ace_host_controller.evaluator_v2` | 2 |
| `code/ace_host_controller/subprocess_evaluator.py` | `ace_host_controller.subprocess_evaluator` | 1 |
| `code/ace_ilp/relational_miner.py` | `ace_ilp.relational_miner` | 1 |
| `code/ace_inversion/bidirectional_transducer.py` | `ace_inversion.bidirectional_transducer` | 1 |
| `code/ace_mcts/program_mcts.py` | `ace_mcts.program_mcts` | 2 |
| `code/ace_mission/proposers.py` | `ace_mission.proposers` | 2 |
| `code/ace_neurosymbolic/cegar_refinement.py` | `ace_neurosymbolic.cegar_refinement` | 1 |
| `code/ace_neurosymbolic/graph_embedding.py` | `ace_neurosymbolic.graph_embedding` | 2 |
| `code/ace_neurosymbolic/sketch_synthesizer.py` | `ace_neurosymbolic.sketch_synthesizer` | 2 |
| `code/ace_operational/catalog_artifact.py` | `ace_operational.catalog_artifact` | 2 |
| `code/ace_operational/citation_validator.py` | `ace_operational.citation_validator` | 1 |
| `code/ace_operational/massive_skills_expansion.py` | `ace_operational.massive_skills_expansion` | 2 |
| `code/ace_operational/mutation_engine.py` | `ace_operational.mutation_engine` | 1 |
| `code/ace_operational/preaudit_oracle.py` | `ace_operational.preaudit_oracle` | 3 |
| `code/ace_operational/proposer_stage1_v2.py` | `ace_operational.proposer_stage1_v2` | 1 |
| `code/ace_operational/software_factory.py` | `ace_operational.software_factory` | 1 |
| `code/ace_report/mobile_report.py` | `ace_report.mobile_report` | 3 |
| `code/ace_research_f13/benchmark.py` | `ace_research_f13.benchmark` | 1 |
| `code/ace_research_f14/benchmark.py` | `ace_research_f14.benchmark` | 1 |
| `code/ace_self_dev/atomic_lease.py` | `ace_self_dev.atomic_lease` | 1 |
| `code/ace_self_dev/evidence_archiver.py` | `ace_self_dev.evidence_archiver` | 1 |
| `code/ace_self_dev/generational_ladder.py` | `ace_self_dev.generational_ladder` | 1 |
