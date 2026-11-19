# Audit Keterhubungan Modul & Wilayah Menunggu — ACE

- Schema: `ace.wiring-audit.v1`
- Total modul non-tes dipindai: 363
- `WIRED` (aktif dipakai non-test): 234
- `CLI_STANDALONE` (punya `__main__`, belum tersambung ke orkestrator): 65
- `ORPHAN` (aman, belum tersambung): 42
- `MENUNGGU_ENGINEER_UTAMA` (wilayah terlarang / titik sambung EVO 0007 / evaluator / memory writeback): 22

## Daftar Wilayah Menunggu Engineer Utama

| Modul | Berkas | Alasan |
| --- | --- | --- |
| `ace_evaluator.cheat_detection` | `code/ace_evaluator/cheat_detection.py` | `modul_wilayah_terlarang` |
| `ace_evaluator.sealed_generator` | `code/ace_evaluator/sealed_generator.py` | `modul_wilayah_terlarang` |
| `ace_evaluator.task_families` | `code/ace_evaluator/task_families.py` | `modul_wilayah_terlarang` |
| `ace_operational.abc_v3_scorer` | `code/ace_operational/abc_v3_scorer.py` | `modul_wilayah_terlarang` |
| `ace_operational.cognitive_memory` | `code/ace_operational/cognitive_memory.py` | `modul_wilayah_terlarang` |
| `ace_operational.g1_instrument` | `code/ace_operational/g1_instrument.py` | `modul_wilayah_terlarang` |
| `ace_operational.g3_instrument` | `code/ace_operational/g3_instrument.py` | `modul_wilayah_terlarang` |
| `ace_operational.g4_instrument` | `code/ace_operational/g4_instrument.py` | `modul_wilayah_terlarang` |
| `ace_operational.g5_instrument` | `code/ace_operational/g5_instrument.py` | `modul_wilayah_terlarang` |
| `ace_operational.memory_writeback` | `code/ace_operational/memory_writeback.py` | `modul_wilayah_terlarang` |
| `ace_operational.round2_instrument` | `code/ace_operational/round2_instrument.py` | `modul_wilayah_terlarang` |
| `tools.abc_v3_run` | `tools/abc_v3_run.py` | `modul_wilayah_terlarang` |
| `tools.corpus_lint` | `tools/corpus_lint.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.corpus_registry` | `tools/corpus_registry.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.corpus_tag` | `tools/corpus_tag.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.curriculum_gen` | `tools/curriculum_gen.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.four_arm_report` | `tools/four_arm_report.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.memory_writeback` | `tools/memory_writeback.py` | `modul_wilayah_terlarang` |
| `tools.pattern_distill` | `tools/pattern_distill.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.round2_gate_run` | `tools/round2_gate_run.py` | `modul_wilayah_terlarang` |
| `tools.screen_census` | `tools/screen_census.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |
| `tools.verify_f13_f14` | `tools/verify_f13_f14.py` | `pemanggil_berada_di_jalur_evo0007_atau_evaluator` |

## Perkakas Aman Belum Tersambung di `tools/` (46)

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
| `tools/bakeoff02_a.py` | `ORPHAN` | 0 |
| `tools/bakeoff02_b.py` | `ORPHAN` | 0 |
| `tools/bakeoff02_c.py` | `ORPHAN` | 0 |
| `tools/bakeoff02_finalize.py` | `ORPHAN` | 0 |
| `tools/bakeoff_a.py` | `ORPHAN` | 0 |
| `tools/bakeoff_b.py` | `ORPHAN` | 0 |
| `tools/bakeoff_c.py` | `ORPHAN` | 0 |
| `tools/bench_table.py` | `CLI_STANDALONE` | 1 |
| `tools/corpus_factory_code.py` | `CLI_STANDALONE` | 1 |
| `tools/corpus_factory_lang.py` | `CLI_STANDALONE` | 1 |
| `tools/cover_check.py` | `CLI_STANDALONE` | 1 |
| `tools/ctrlreg_stage0_replay.py` | `CLI_STANDALONE` | 0 |
| `tools/ctrlreg_stage2_dose.py` | `CLI_STANDALONE` | 0 |
| `tools/daily_digest.py` | `CLI_STANDALONE` | 1 |
| `tools/evo_scaffold.py` | `CLI_STANDALONE` | 1 |
| `tools/fuzz_parsers.py` | `CLI_STANDALONE` | 1 |
| `tools/inoculation_demo.py` | `ORPHAN` | 0 |
| `tools/instance_kit.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_pipeline.py` | `CLI_STANDALONE` | 1 |
| `tools/kbm_schedule.py` | `CLI_STANDALONE` | 1 |
| `tools/omega_environment_probe.py` | `CLI_STANDALONE` | 1 |
| `tools/opportunity_register.py` | `CLI_STANDALONE` | 1 |
| `tools/pack_evidence.py` | `CLI_STANDALONE` | 1 |
| `tools/portability_pack.py` | `CLI_STANDALONE` | 1 |
| `tools/regression_anchor.py` | `CLI_STANDALONE` | 0 |
| `tools/repair_v2_probe.py` | `CLI_STANDALONE` | 0 |
| `tools/repo_index.py` | `CLI_STANDALONE` | 2 |
| `tools/repo_status_dashboard.py` | `CLI_STANDALONE` | 1 |
| `tools/royalty_track.py` | `CLI_STANDALONE` | 1 |
| `tools/ruleset_readiness.py` | `CLI_STANDALONE` | 1 |
| `tools/self_send_audit_view.py` | `CLI_STANDALONE` | 1 |
| `tools/stage_verify.py` | `CLI_STANDALONE` | 1 |
| `tools/storage_debt.py` | `CLI_STANDALONE` | 1 |
| `tools/verify_full_system.py` | `CLI_STANDALONE` | 0 |
| `tools/verify_repair_v2.py` | `CLI_STANDALONE` | 1 |
| `tools/verify_runtime_demo_v2.py` | `CLI_STANDALONE` | 1 |
| `tools/verify_self_dev.py` | `CLI_STANDALONE` | 0 |
| `tools/wiring_audit.py` | `CLI_STANDALONE` | 1 |

## Modul Aman `ORPHAN` di `code/` (Top 34 dari 34)

| Berkas | Modul | Pemanggil Tes |
| --- | --- | ---: |
| `code/ace_abstract_interp/disjunctive_domain.py` | `ace_abstract_interp.disjunctive_domain` | 1 |
| `code/ace_abstraction/wake_sleep.py` | `ace_abstraction.wake_sleep` | 1 |
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
| `code/ace_mission/proposers.py` | `ace_mission.proposers` | 1 |
| `code/ace_neurosymbolic/cegar_refinement.py` | `ace_neurosymbolic.cegar_refinement` | 1 |
| `code/ace_neurosymbolic/graph_embedding.py` | `ace_neurosymbolic.graph_embedding` | 2 |
| `code/ace_neurosymbolic/sketch_synthesizer.py` | `ace_neurosymbolic.sketch_synthesizer` | 2 |
| `code/ace_operational/catalog_artifact.py` | `ace_operational.catalog_artifact` | 1 |
| `code/ace_operational/citation_validator.py` | `ace_operational.citation_validator` | 1 |
| `code/ace_operational/massive_skills_expansion.py` | `ace_operational.massive_skills_expansion` | 1 |
| `code/ace_operational/mutation_engine.py` | `ace_operational.mutation_engine` | 1 |
| `code/ace_operational/preaudit_oracle.py` | `ace_operational.preaudit_oracle` | 3 |
| `code/ace_operational/proposer_stage1_v2.py` | `ace_operational.proposer_stage1_v2` | 1 |
| `code/ace_operational/software_factory.py` | `ace_operational.software_factory` | 1 |
| `code/ace_report/mobile_report.py` | `ace_report.mobile_report` | 2 |
| `code/ace_research_f13/benchmark.py` | `ace_research_f13.benchmark` | 1 |
| `code/ace_research_f14/benchmark.py` | `ace_research_f14.benchmark` | 1 |
| `code/ace_self_dev/atomic_lease.py` | `ace_self_dev.atomic_lease` | 0 |
| `code/ace_self_dev/evidence_archiver.py` | `ace_self_dev.evidence_archiver` | 1 |
| `code/ace_self_dev/generational_ladder.py` | `ace_self_dev.generational_ladder` | 1 |
