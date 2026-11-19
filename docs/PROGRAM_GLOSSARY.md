# Glosarium Istilah Teknis ACE — ACE

> Dibangun otomatis dari definisi Markdown & AST Python statis oleh `tools/program_glossary.py` (`ace.program-glossary.v1`). Seluruh definisi bersumber langsung dari berkas repositori (nol definisi rekaan).

## 1. Ringkasan Sumber

- Berkas Markdown dipindai: **306**
- Berkas Python AST dipindai (non-test): **464**
- Total istilah terindeks: **336** (dari 1374 kandidat unik)

### Komposisi Sumber

| Jenis Sumber | Jumlah Istilah |
| --- | ---: |
| `ast_class` | 80 |
| `ast_module` | 80 |
| `ast_schema` | 80 |
| `markdown_def` | 80 |
| `markdown_heading` | 16 |

## 2. Daftar Istilah Alfabetis

| Istilah | Jenis | Sumber & Baris | Definisi Sumber |
| --- | --- | --- | --- |
| `_CeilingExceeded` | `ast_class` | `code/ace_operational/proposer_stage2.py:128` | Internal control-flow signal raised cleanly when a hard ceiling is reached. |
| `_CycleMonitorScope` | `ast_class` | `code/ace_host_controller/resilient_watchdog.py:838` | Context manager scope for cycle monitoring. |
| `_DaemonThreadWorker` | `ast_class` | `code/ace_host_controller/resilient_watchdog.py:414` | Runs a callable in an isolated daemon thread to guarantee non-blocking timeout handling. |
| `_InequalityNode` | `ast_class` | `code/ace_smt/dpllt_solver.py:154` | Internal inequality node tracking origin literals for conflict clause generation. |
| `_StopTriggered` | `ast_class` | `code/ace_operational/proposer_stage2.py:120` | Internal control-flow signal raised cleanly inside a run when stopped. |
| `_ThinkingBudgetExhausted` | `ast_class` | `code/ace_operational/models_backend.py:227` | The server spent the whole token budget inside reasoning and produced no final content. |
| `_WorkerInterrupted` | `ast_class` | `code/ace_operational/proposer_stage2.py:136` | Supervisor unwind signal injected when a blocked worker exceeds stop/wall deadlines. |
| `A Fixed` | `markdown_def` | `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM15.md:19` | konfigurasi beku. **B Adaptive**: urutan operator |
| `AbstainPromotionError` | `ast_class` | `code/ace_operational/causal_repo_evolution.py:51` | Raised when an action in the ABSTAIN_FOR_EXPERIMENT zone attempts promotion. |
| `AbstractInterpreter` | `ast_class` | `code/ace_abstract_interp/invariants.py:175` | Evaluates program expressions and branch guards over abstract intervals. |
| `AbstractMacro` | `ast_class` | `code/ace_operational/abstraction_engine.py:91` | Anti-unified structural repair primitive transferable across functions & families. |
| `AbstractPredicateState` | `ast_class` | `code/ace_neurosymbolic/cegar_refinement.py:39` | An element in the Predicate Lattice L(P): P -> {True, False, TOP, BOT}. |
| `AbstractState` | `ast_class` | `code/ace_abstract_interp/invariants.py:114` | Environment mapping variable identifiers to abstract intervals. |
| `AbstractTraceStep` | `ast_class` | `code/ace_neurosymbolic/cegar_refinement.py:194` | A step in an abstract counterexample trace. |
| `AcceptanceDecision` | `ast_class` | `code/ace_host_controller/controller.py:22` | Decision emitted by Host Controller upon candidate evaluation. |
| `ACCESS_DEMONSTRATED` | `markdown_def` | `docs/research/ACE_G4_G5_INSTRUMENT_DESIGN_20261112.md:102` | C1–C3 pass for the assessed |
| `ace` | `ast_module` | `ace.py:1` | Run ACE from a source checkout without installing a package. |
| `ace.agenda-closure.v1` | `ast_schema` | `tools/agenda_candidates.py:20` | Skema JSON `CLOSURE_SCHEMA` pada `tools/agenda_candidates.py` |
| `ace.agenda-proposal.v1` | `ast_schema` | `tools/agenda_candidates.py:19` | Skema JSON `SCHEMA` pada `tools/agenda_candidates.py` |
| `ace.attested_server.v1` | `ast_schema` | `code/ace_operational/attested_server.py:37` | Skema JSON `ATTESTATION_SCHEMA` pada `code/ace_operational/attested_server.py` |
| `ace.autonomy.v1` | `ast_schema` | `code/ace_autonomy/core.py:54` | Skema JSON `SCHEMA` pada `code/ace_autonomy/core.py` |
| `ace.bench-table.v1` | `ast_schema` | `tools/bench_table.py:19` | Skema JSON `BENCH_SCHEMA` pada `tools/bench_table.py` |
| `ace.brain_registry.v1` | `ast_schema` | `code/ace_operational/brain_registry.py:27` | Skema JSON `REGISTRY_SCHEMA` pada `code/ace_operational/brain_registry.py` |
| `ace.builder-onboarding-pack.v1` | `ast_schema` | `tools/builder_onboarding_pack.py:20` | Skema JSON `ONBOARDING_SCHEMA` pada `tools/builder_onboarding_pack.py` |
| `ace.bundle-matrix-audit.v1` | `ast_schema` | `tools/seal_run.py:132` | Skema JSON `BUNDLE_MATRIX_SCHEMA` pada `tools/seal_run.py` |
| `ace.candidate-corpus-quality.v1` | `ast_schema` | `tools/candidate_corpus_batch.py:17` | Skema JSON `SCHEMA` pada `tools/candidate_corpus_batch.py` |
| `ace.candidate-factory-v2.v1` | `ast_schema` | `tools/candidate_factory_v2.py:40` | Skema JSON `FACTORY_V2_SCHEMA` pada `tools/candidate_factory_v2.py` |
| `ace.candidate-readiness-census.v2` | `ast_schema` | `tools/candidate_factory_v2.py:43` | Skema JSON `CENSUS_V2_SCHEMA` pada `tools/candidate_factory_v2.py` |
| `ace.chat.receipt.v1` | `ast_schema` | `code/ace_chat/task_runner.py:19` | Skema JSON `REPORT_SCHEMA` pada `code/ace_chat/task_runner.py` |
| `ace.chat.request.v1` | `ast_schema` | `code/ace_chat/task_runner.py:18` | Skema JSON `SCHEMA` pada `code/ace_chat/task_runner.py` |
| `ace.citation_rejection.v1` | `ast_schema` | `code/ace_operational/citation_validator.py:69` | Skema JSON `REJECTION_SCHEMA` pada `code/ace_operational/citation_validator.py` |
| `ace.citation_validation.v1` | `ast_schema` | `code/ace_operational/citation_validator.py:70` | Skema JSON `REPORT_SCHEMA` pada `code/ace_operational/citation_validator.py` |
| `ace.code-composite-spec.v2` | `ast_schema` | `tools/candidate_factory_v2.py:42` | Skema JSON `CODE_SPEC_V2_SCHEMA` pada `tools/candidate_factory_v2.py` |
| `ace.corpus-factory-code.v1` | `ast_schema` | `tools/corpus_factory_code.py:30` | Skema JSON `FACTORY_SCHEMA` pada `tools/corpus_factory_code.py` |
| `ace.corpus-factory-lang.v1` | `ast_schema` | `tools/corpus_factory_lang.py:33` | Skema JSON `FACTORY_LANG_SCHEMA` pada `tools/corpus_factory_lang.py` |
| `ace.corpus-freeze-pack.v1` | `ast_schema` | `tools/corpus_freeze_packer.py:32` | Skema JSON `FREEZE_PACK_SCHEMA` pada `tools/corpus_freeze_packer.py` |
| `ace.corpus-lint-v2.v1` | `ast_schema` | `tools/corpus_lint_v2.py:34` | Skema JSON `LINT_V2_SCHEMA` pada `tools/corpus_lint_v2.py` |
| `ace.corpus-tags.v1` | `ast_schema` | `tools/corpus_tag.py:26` | Skema JSON `TAG_SCHEMA` pada `tools/corpus_tag.py` |
| `ace.cover-check.v1` | `ast_schema` | `tools/cover_check.py:22` | Skema JSON `COVER_CHECK_SCHEMA` pada `tools/cover_check.py` |
| `ace.coverage-flaky-audit.v1` | `ast_schema` | `tools/coverage_and_flaky_audit.py:32` | Skema JSON `AUDIT_SCHEMA` pada `tools/coverage_and_flaky_audit.py` |
| `ace.cross-organ-agreement.v1` | `ast_schema` | `tools/cross_organ_agreement.py:23` | Skema JSON `AGREEMENT_SCHEMA` pada `tools/cross_organ_agreement.py` |
| `ace.curriculum-gen.v1` | `ast_schema` | `tools/curriculum_gen.py:21` | Skema JSON `CURRICULUM_SCHEMA` pada `tools/curriculum_gen.py` |
| `ace.director.prose-audit.v1` | `ast_schema` | `tools/director_prose_audit.py:18` | Skema JSON `PROSE_AUDIT_SCHEMA` pada `tools/director_prose_audit.py` |
| `ace.distractor_inoculation.v1` | `ast_schema` | `code/ace_operational/distractor_inoculation.py:25` | Skema JSON `SCHEMA` pada `code/ace_operational/distractor_inoculation.py` |
| `ace.distractor_registry.v1` | `ast_schema` | `code/ace_operational/distractor_inoculation.py:26` | Skema JSON `REGISTRY_SCHEMA` pada `code/ace_operational/distractor_inoculation.py` |
| `ace.draft-preflight.v1` | `ast_schema` | `tools/draft_release_preflight.py:13` | Skema JSON `SCHEMA` pada `tools/draft_release_preflight.py` |
| `ace.evidence-bundle.v1` | `ast_schema` | `tools/pack_evidence.py:19` | Skema JSON `BUNDLE_SCHEMA` pada `tools/pack_evidence.py` |
| `ace.evo-census-hook.v1` | `ast_schema` | `tools/evo_scaffold.py:25` | Skema JSON `CENSUS_HOOK_SCHEMA` pada `tools/evo_scaffold.py` |
| `ace.failure-to-agenda.v1` | `ast_schema` | `tools/failure_to_agenda.py:26` | Skema JSON `SCHEMA` pada `tools/failure_to_agenda.py` |
| `ace.four-arm-report.v1` | `ast_schema` | `tools/four_arm_report.py:20` | Skema JSON `FOUR_ARM_SCHEMA` pada `tools/four_arm_report.py` |
| `ace.frozen-corpus-registry.v1` | `ast_schema` | `tools/corpus_registry.py:21` | Skema JSON `REGISTRY_SCHEMA` pada `tools/corpus_registry.py` |
| `ace.frozen-corpus-registry.v2` | `ast_schema` | `tools/frozen_corpus_registry.py:21` | Skema JSON `REGISTRY_V2_SCHEMA` pada `tools/frozen_corpus_registry.py` |
| `ace.handover-decisions.v1` | `ast_schema` | `tools/handover_decision_extractor.py:21` | Skema JSON `DECISIONS_SCHEMA` pada `tools/handover_decision_extractor.py` |
| `ace.handover-index.v1` | `ast_schema` | `tools/handover_index.py:21` | Skema JSON `HANDOVER_INDEX_SCHEMA` pada `tools/handover_index.py` |
| `ace.introspect-recall.v1` | `ast_schema` | `tools/introspect_recall.py:28` | Skema JSON `SCHEMA` pada `tools/introspect_recall.py` |
| `ace.judge-saturation-scan.v1` | `ast_schema` | `tools/saturation_scan.py:29` | Skema JSON `SATURATION_SCHEMA` pada `tools/saturation_scan.py` |
| `ace.kbm-pack-check.v1` | `ast_schema` | `tools/kbm_pack_check.py:23` | Skema JSON `PACK_CHECK_SCHEMA` pada `tools/kbm_pack_check.py` |
| `ace.kbm-pipeline.v1` | `ast_schema` | `tools/kbm_pipeline.py:52` | Skema JSON `KBM_PIPELINE_SCHEMA` pada `tools/kbm_pipeline.py` |
| `ace.kbm-queue.v1` | `ast_schema` | `tools/kbm_production_queue.py:20` | Skema JSON `SCHEMA` pada `tools/kbm_production_queue.py` |
| `ace.kbm-schedule.v1` | `ast_schema` | `tools/kbm_schedule.py:19` | Skema JSON `SCHEDULE_SCHEMA` pada `tools/kbm_schedule.py` |
| `ace.kbm-split.v1` | `ast_schema` | `tools/kbm_split.py:18` | Skema JSON `KBM_SPLIT_SCHEMA` pada `tools/kbm_split.py` |
| `ace.kbm-suite.v2` | `ast_schema` | `tools/kbm_suite_v2.py:36` | Skema JSON `KBM_SUITE_V2_SCHEMA` pada `tools/kbm_suite_v2.py` |
| `ace.kbm-upload-manifest.v1` | `ast_schema` | `tools/kbm_pipeline.py:53` | Skema JSON `KBM_UPLOAD_MANIFEST_SCHEMA` pada `tools/kbm_pipeline.py` |
| `ace.lang-constraint-spec.v1` | `ast_schema` | `tools/corpus_factory_lang.py:34` | Skema JSON `CONSTRAINT_SPEC_SCHEMA` pada `tools/corpus_factory_lang.py` |
| `ace.lang-layered-spec.v2` | `ast_schema` | `tools/candidate_factory_v2.py:41` | Skema JSON `LANG_SPEC_V2_SCHEMA` pada `tools/candidate_factory_v2.py` |
| `ace.metacog-consolidation.v1` | `ast_schema` | `tools/metacog_memory_consolidate.py:22` | Skema JSON `SCHEMA` pada `tools/metacog_memory_consolidate.py` |
| `ace.migration-rehearsal.v1` | `ast_schema` | `tools/migration_rehearsal.py:15` | Skema JSON `SCHEMA` pada `tools/migration_rehearsal.py` |
| `ace.mission.reasoning-candidate.v1` | `ast_schema` | `code/ace_mission/admission.py:16` | Skema JSON `ARTIFACT_SCHEMA` pada `code/ace_mission/admission.py` |
| `ace.narrative-self-model.v1` | `ast_schema` | `tools/narrative_self_model.py:32` | Skema JSON `SCHEMA` pada `tools/narrative_self_model.py` |
| `ace.novel_discovery.v1` | `ast_schema` | `code/ace_research_discovery/__init__.py:12` | Skema JSON `SCHEMA` pada `code/ace_research_discovery/__init__.py` |
| `ace.open_world.plan.v1` | `ast_schema` | `code/ace_operational/open_world_task_bridge.py:25` | Skema JSON `SCHEMA` pada `code/ace_operational/open_world_task_bridge.py` |
| `ace.organ-quota-ledger.v1` | `ast_schema` | `tools/organ_quota_ledger.py:20` | Skema JSON `LEDGER_SCHEMA` pada `tools/organ_quota_ledger.py` |
| `ace.organ-registry-validate.v1` | `ast_schema` | `tools/organ_registry_validate.py:20` | Skema JSON `VALIDATOR_SCHEMA` pada `tools/organ_registry_validate.py` |
| `ace.organ-slate.v1` | `ast_schema` | `tools/organ_registry_validate.py:21` | Skema JSON `SLATE_SCHEMA` pada `tools/organ_registry_validate.py` |
| `ace.organ-smoke-harness.v1` | `ast_schema` | `tools/organ_smoke_harness.py:19` | Skema JSON `SMOKE_SCHEMA` pada `tools/organ_smoke_harness.py` |
| `ace.pattern-catalog-diff.v1` | `ast_schema` | `tools/pattern_catalog.py:24` | Skema JSON `DIFF_SCHEMA` pada `tools/pattern_catalog.py` |
| `ace.pattern-catalog.v1` | `ast_schema` | `tools/pattern_catalog.py:19` | Skema JSON `CATALOG_SCHEMA` pada `tools/pattern_catalog.py` |
| `ace.pattern-conflict-trace.v1` | `ast_schema` | `tools/pattern_catalog.py:25` | Skema JSON `CONFLICT_TRACE_SCHEMA` pada `tools/pattern_catalog.py` |
| `ace.pattern-distilled.v1` | `ast_schema` | `tools/pattern_distill.py:22` | Skema JSON `DISTILL_SCHEMA` pada `tools/pattern_distill.py` |
| `ace.periodic-self-report.v1` | `ast_schema` | `tools/periodic_self_report.py:26` | Skema JSON `SCHEMA` pada `tools/periodic_self_report.py` |
| `ace.platform-requirements-summary.v1` | `ast_schema` | `tools/platform_requirements_summary.py:20` | Skema JSON `PLATFORM_SUMMARY_SCHEMA` pada `tools/platform_requirements_summary.py` |
| `ace.program-glossary.v1` | `ast_schema` | `tools/program_glossary.py:21` | Skema JSON `GLOSSARY_SCHEMA` pada `tools/program_glossary.py` |
| `ace.reasoning.xy.v1` | `ast_schema` | `code/ace_cognition/reasoning.py:17` | Skema JSON `SCHEMA` pada `code/ace_cognition/reasoning.py` |
| `ace.register-agenda-draft.v1` | `ast_schema` | `tools/failure_to_agenda.py:27` | Skema JSON `DRAFT_SCHEMA` pada `tools/failure_to_agenda.py` |
| `ace.repair.memory.v1` | `ast_schema` | `code/ace_research_repair/memory.py:17` | Skema JSON `MEMORY_SCHEMA` pada `code/ace_research_repair/memory.py` |
| `ace.repair.public.v1` | `ast_schema` | `code/ace_research_repair/runner.py:33` | Skema JSON `REPORT_SCHEMA` pada `code/ace_research_repair/runner.py` |
| `ace.repo-cartography.v1` | `ast_schema` | `tools/repo_cartography.py:25` | Skema JSON `CARTOGRAPHY_SCHEMA` pada `tools/repo_cartography.py` |
| `ace.repo-index.v1` | `ast_schema` | `tools/repo_index.py:19` | Skema JSON `INDEX_SCHEMA` pada `tools/repo_index.py` |
| `ace.repo-status-dashboard.v2` | `ast_schema` | `tools/repo_status_dashboard.py:30` | Skema JSON `DASHBOARD_SCHEMA` pada `tools/repo_status_dashboard.py` |
| `ace.repo-status-dashboard.v3` | `ast_schema` | `tools/repo_status_dashboard_v3.py:28` | Skema JSON `DASHBOARD_V3_SCHEMA` pada `tools/repo_status_dashboard_v3.py` |
| `ace.revenue-evidence.v1` | `ast_schema` | `tools/revenue_verify.py:13` | Skema JSON `INPUT_SCHEMA` pada `tools/revenue_verify.py` |
| `ace.revenue-reconcile.v1` | `ast_schema` | `tools/revenue_reconcile.py:23` | Skema JSON `RECONCILE_SCHEMA` pada `tools/revenue_reconcile.py` |
| `ace.revenue-verification.v1` | `ast_schema` | `tools/revenue_reconcile.py:24` | Skema JSON `VERIFICATION_SCHEMA` pada `tools/revenue_reconcile.py` |
| `ace.royalty-summary.v1` | `ast_schema` | `tools/royalty_track.py:25` | Skema JSON `ROYALTY_SCHEMA` pada `tools/royalty_track.py` |
| `ace.run-evidence-pack.v1` | `ast_schema` | `tools/run_evidence_pack.py:35` | Skema JSON `RUN_PACK_SCHEMA` pada `tools/run_evidence_pack.py` |
| `ace.runtime.v1` | `ast_schema` | `code/ace_runtime/engine.py:16` | Skema JSON `SCHEMA` pada `code/ace_runtime/engine.py` |
| `ace.self-dev-branch-prereview.v1` | `ast_schema` | `tools/self_dev_git_audit.py:252` | Skema JSON `PREREVIEW_SCHEMA` pada `tools/self_dev_git_audit.py` |
| `ACE_BASE_RUNTIME_EXECUTED` | `markdown_def` | `docs/ACE_AUTONOMY_V1_RESULTS.md:12` | **`TRUE`** — `ace_runtime` (`931b1582...`) dijalankan langsung maupun melalui `TypedToolBroker` (`ace_demo`, `ace_status`, `ace_enqueue_task`, `ace_run_tasks`, `ace_predict`, `ace_evaluate`, `ace_report`); `tools/verify_… |
| `ace_self_evolver` | `ast_module` | `ace_self_evolver.py:1` | ACE Audited Self-Evolver (Strict Empirical Verification & Branch Isolation) |
| `ACEWebCore` | `ast_class` | `code/ace_operational/web_server.py:1600` | Shared application state and API dispatcher used by HTTP server and direct test harness. |
| `ACEWebServer` | `ast_class` | `code/ace_operational/web_server.py:2055` | Manageable localhost ThreadingHTTPServer wrapper for `ace web` and automated tests. |
| `ActiveInformationGainSynthesizer` | `ast_class` | `code/ace_research_f12/causal_agent.py:176` | Synthesizes boundary queries that maximize epistemic information gain. |
| `AdapterFeature` | `ast_class` | `code/ace_research_discovery/discovery.py:372` | Named boolean predicate atom with complexity cost for the shared target adapter. |
| `Addendum 59` | `markdown_def` | `handover/local_state_sweep_20261115/study-ace-77cca3c.md:62` | A/B/C v3 selesai, DI pooled **−1,98pp → G2 MEASURED NOT_DEMONSTRATED** (null terukur ketiga); lahir agenda regresi-kontrol. |
| `Addendum 60` | `markdown_def` | `handover/local_state_sweep_20261115/study-ace-77cca3c.md:63` | round-2 gate `LIFT_DEMONSTRATED` (round2_index tepat 0,0) — hasil mekanisme, **eksplisit bukan gerak papan G1–G5**, bertumpu pada 1 motion key/1 bentuk defect. |
| `Admisi sebelum eksistensi` | `markdown_def` | `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM10.md:11` | validasi skema (enum, universe tool, |
| `AdmissionAwareSelector` | `ast_class` | `code/ace_core_repair/admission.py:17` | Admit only on training tolerance AND exact validation fit. |
| `AdversarialChallenger` | `ast_class` | `code/ace_operational/coevolution_arena.py:221` | Generates frontier challenges verified by mandatory SolvabilityWitness certificates. |
| `AdversarialDataPoisoner` | `ast_class` | `code/ace_red_team/adversarial_suite.py:467` | Injects adversarial poisoning into synthesis datasets. |
| `AgendaEngine` | `ast_class` | `code/ace_self_dev/agenda_engine.py:32` | Autonomous search policy and agenda planner. |
| `AI-content policy` | `markdown_def` | `docs/research/ACE_KBM_PILOT_DESIGN_20261113.md:115` | no prohibition was found in any |
| `Algebraic Identity Simplification` | `markdown_def` | `docs/research/self_dev/SOTA_EXTERNAL_REPOSITORIES_SURVEY_20261107.md:272` | Implement a pure Python AST transformer (`ast.NodeTransformer`) that simplifies trivial operations (e.g., `1 * x` $\to$ `x`, `x + 0` $\to$ `x`, double negation `not (not x)` $\to$ `x`). |
| `Ambang` | `markdown_def` | `docs/research/ACE_PHASE2_PILOT_ABC_DESIGN_20261112.md:51` | target desain PRD ≥30 tugas held-out per keluarga — |
| `Amplop` | `markdown_def` | `docs/research/ACE_TWO_SIDED_BUSINESS_STUDY_20261113.md:166` | dana terikat tujuan per pemicu/pilot, berplafon; |
| `Amplop belanja` | `markdown_def` | `docs/research/ACE_TWO_SIDED_BUSINESS_STUDY_20261113.md:47` | per kebutuhan, dengan plafon yang |
| `Amplop per tujuan` | `markdown_def` | `docs/research/ACE_SELF_FUNDING_DESIGN_STUDY_20261112.md:67` | setiap penggunaan terikat pada pemicu yang |
| `AntibodyGate` | `ast_class` | `code/ace_operational/coevolution_arena.py:82` | Permanent regression/security antibody compiled from an adversarial trauma or exploit. |
| `AntifragileAntibodyCompiler` | `ast_class` | `code/ace_operational/coevolution_arena.py:105` | Compiles real detected fuzz crashes, label conflicts, and backdoor triggers into antibodies. |
| `approach` | `markdown_def` | `handover/RANCANGAN_EVO_0007.md:30` | langkah/ceklist yang menghasilkan output |
| `ArchiveError` | `ast_class` | `code/ace_operational/population_archive.py:34` | Base class for archive integrity errors. |
| `ARITHMETIC_INVARIANT` | `markdown_def` | `docs/research/hypgen/ACE_F10_HYPOTHESIS_SYNTHESIS_PRESCORE_20261107.md:29` | Modular congruence, affine relations. |
| `Armada AI` | `markdown_def` | `CHANGELOG.md:26` | [DICABUT — tanpa jejak bukti] |
| `ArmFitOutcome` | `ast_class` | `code/ace_research_discovery/arms.py:55` | Standardized fit + admission output for any capability arm before terminal scoring. |
| `AST Complexity Metric` | `markdown_def` | `docs/research/self_dev/SOTA_EXTERNAL_REPOSITORIES_SURVEY_20261107.md:268` | Measure complexity by traversing candidate ASTs using `len(list(ast.walk(tree)))`. Weight relational comparisons and binary operators appropriately. |
| `AST-Localized Fault Localization` | `markdown_def` | `docs/research/self_dev/SOTA_EXTERNAL_REPOSITORIES_SURVEY_20261107.md:386` | ACE's `DiagnosticEngine` traverses the candidate AST using Python's built-in `ast` module. When an execution or logical error occurs, it maps the failing witness directly to the offending AST node (`ast.BinOp`, `ast.Comp… |
| `ASTDepthCost` | `ast_class` | `code/ace_egraph/equality_saturation.py:512` | Penalizes tree depth and complex nesting. |
| `ASTGraph` | `ast_class` | `code/ace_gnn/ast_embedder.py:115` | Relational directed graph representation of a TypedASTNode tree. |
| `ASTGraphConverter` | `ast_class` | `code/ace_gnn/ast_embedder.py:209` | Converts strongly-typed TypedASTNode trees into relational ASTGraph structures. |
| `ASTGraphEmbedder` | `ast_class` | `code/ace_gnn/ast_embedder.py:709` | Unified Graph Neural Network & Tree-LSTM AST Representation Learning Engine. |
| `ASTNode` | `ast_class` | `code/ace_research_f14/grammar.py:20` | Abstract base class for all mechanism grammar AST expressions. |
| `ASTSizeCost` | `ast_class` | `code/ace_egraph/equality_saturation.py:500` | Parsimony cost function: penalizes AST node count (size). |
| `ASTTransducerLens` | `ast_class` | `code/ace_inversion/bidirectional_transducer.py:129` | Bijective transducer between serialized prefix S-expressions and structured AST dicts. |
| `Atom` | `ast_class` | `code/ace_ilp/relational_miner.py:24` | First-order relational atom: predicate(term1, term2, ...). |
| `Attachment` | `markdown_def` | `docs/research/external_repos/SOTA_GODEL_AND_ABSTRACTION_REPOS_20261107.md:196` | The newly synthesized child agent is attached as a descendant of the **Primary** node, so the failing lineage inherits the donor's generalized capability. |
| `AttentionController` | `ast_class` | `code/ace_selfmodel/metacognition.py:137` | Prioritizes candidate goals using expected information gain, feasibility, and cost. |
| `Aturan 1 — Kandidat self-dev hanya berhasil bila hidup` | `markdown_heading` | `handover/GOVERNANCE_RULES_20261115.md:9` | Sebuah kandidat hasil self-development (fitur, modul, |
| `Aturan 2 — Ratifikasi independen adalah standar` | `markdown_heading` | `handover/GOVERNANCE_RULES_20261115.md:30` | Tidak ada hasil lini mana pun yang menjadi status resmi |
| `AuditError` | `ast_class` | `tools/self_dev_git_audit.py:29` | Masukan audit atau objek Git lokal tidak dapat diperiksa. |
| `AuditFinding` | `ast_class` | `code/ace_operational/evolution_mission_loop.py:258` | Deterministic, evidence-backed code/capability improvement finding. |
| `AuditViewError` | `ast_class` | `tools/self_send_audit_view.py:25` | Error masukan berkas audit tidak ditemukan atau tidak bisa dibaca. |
| `auto_curriculum` | `ast_module` | `auto_curriculum.py:1` | ACE Auto-Curriculum Runner |
| `AutomataProposer` | `ast_class` | `code/ace_mission/proposers.py:103` | Active Automata Proposer using Angluin's L* algorithm. |
| `AutonomousEvolver` | `ast_class` | `code/ace_operational/autonomous_evolver.py:86` | Runs the unified, zero-theater self-evolution loop with causal lineage and passive work orders. |
| `AutonomousGenerationalDiscovery` | `ast_class` | `code/ace_research_f14/discovery_engine.py:388` | Orchestrates G0 -> G1 -> G2 capability evolution without human hardcoded features. |
| `AutonomousPRManager` | `ast_class` | `code/ace_code_agent/pr_manager.py:32` | Manages autonomous Git branching, commits, remote push, and Pull Request creation. |
| `AutonomousPRMetadata` | `ast_class` | `code/ace_code_agent/models.py:129` | Verifiable metadata for an autonomous PR generated by ACE. |
| `AutonomousRepoJanitor` | `ast_class` | `code/ace_host_controller/repo_janitor.py:24` | Maintains repository cleanliness, branch hygiene, and release documentation. |
| `AutonomousResearchCoordinator` | `ast_class` | `code/ace_research_agenda/coordinator.py:98` | Closed-loop autonomous scientific agenda engine operating under bounded authority. |
| `AutonomousSoftwareResearcher` | `ast_class` | `code/ace_code_agent/controller.py:33` | End-to-end controller for autonomous software development research. |
| `Autonomy` | `ast_class` | `code/ace_autonomy/core.py:86` | Durable, bounded autonomous goal executor integrated with real ACE Runtime. |
| `autonomy` | `ast_module` | `autonomy.py:1` | Top-level CLI launcher for ACE Autonomous Runtime. |
| `AutonomyOrchestrator` | `ast_class` | `code/ace_operational/autonomy_loop.py:40` | Coordinates gap detection, anti-stagnation pivots, worker delegation, and skill learning. |
| `AutopoieticSkillForge` | `ast_class` | `code/ace_operational/oaie_unlimited.py:342` | Synthesizes composite multi-step AST operators and verified reusable micro-skills. |
| `AutoRetryBlockedError` | `ast_class` | `code/ace_operational/proposer_stage2.py:100` | Raised when dispatch attempts to retry a STOPPED/ABORTED/FAILED staged package. |
| `B2A-02 (kandidat uji lanjutan)` | `markdown_def` | `docs/research/ACE_TWO_SIDED_BUSINESS_STUDY_20261113.md:42` | direktur memilih atas |
| `B_baserate` | `markdown_def` | `docs/ACE_SELFMODEL_PRESCORE_V1.md:50` | Historical marginal base-rate predictor (uses episodic mean without reading live `SelfState` interventions). |
| `B_const` | `markdown_def` | `docs/ACE_SELFMODEL_PRESCORE_V1.md:49` | Constant confident predictor (`p_hat = 0.85`, never abstains). |
| `B_shuffled` | `markdown_def` | `docs/ACE_SELFMODEL_PRESCORE_V1.md:51` | State-permuted ablation control (reads mismatched `SelfState` snapshots, testing causal state grounding). |
| `BALDSampler` | `ast_class` | `code/ace_epistemic/active_sampler.py:40` | Bayesian Active Learning by Disagreement (BALD) query synthesizer. |
| `BaseProposer` | `ast_class` | `code/ace_mission/proposers.py:10` | Abstract base class for mission proposers. |
| `Batas eskalasi` | `markdown_def` | `docs/research/ACE_SELF_FUNDING_DESIGN_STUDY_20261112.md:76` | ACE mengusulkan; pemilik memutuskan. Tidak ada |
| `BenchTableError` | `ast_class` | `tools/bench_table.py:22` | Kesalahan berkas masukan, format JSONL, atau field label benchmark. |
| `BijectiveLens` | `ast_class` | `code/ace_inversion/bidirectional_transducer.py:65` | Bijective lens (Isomorphism S ~= V): fwd(s) and inv(v) with exact round-trip bijectivity. |
| `BitvectorRegistry` | `ast_class` | `code/ace_self_dev/stagnation_detector.py:69` | Persistent catalog of candidate prediction bitvectors on confirmation pools. |
| `BlobIntegrityError` | `ast_class` | `code/ace_operational/proposer_stage2.py:116` | Raised when immutable blob write/digest verification fails before DB commit. |
| `BLOCKED_ENVIRONMENT` | `markdown_def` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:147` | sandbox (native isolation, cgroups/permissions/network) not verified; never execute untrusted patch. |
| `BoolExpr` | `ast_class` | `code/ace_interpolation/craig_interpolator.py:46` | Abstract base class for propositional formulas. |
| `boundary_index` | `markdown_def` | `docs/ACE_REPAIR_PRESCORE_V1.md:60` | `T01_binary_search_index` (`<` vs `<=` convergence bound), `T02_interior_local_maxima` (`range` stop off-by-one), `T03_trimmed_floor_mean` (missing empty-sample guard). |
| `BoundarySecurityViolation` | `ast_class` | `code/ace_host_controller/boundary.py:64` | Raised when an untrusted candidate attempts to breach supervisory boundaries. |
| `BoundedRepositoryRetriever` | `ast_class` | `code/ace_code_agent/repo_retrieval.py:73` | AST symbol index with exact Git ignore behavior and explicit resource caps. |
| `brain_of_origin` | `markdown_def` | `docs/research/ACE_C6_FAILURE_TO_AGENDA.md:8` | `"gravity-proposal"` |
| `brain_registry.py` | `markdown_def` | `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM29.md:5` | catatan otak bernama + log peristiwa |
| `BrainContractAdapter` | `ast_class` | `code/ace_operational/oaie_unlimited.py:121` | Wraps any AI model or symbolic solver behind a zero-trust hypothesis interface. |
| `BrainGovernanceError` | `ast_class` | `code/ace_operational/oaie_unlimited.py:111` | Raised when all candidate brains fail verification or a dismissed brain is invoked. |
| `BrainUnavailable` | `ast_class` | `code/ace_operational/brain_endpoints.py:65` | An organ is unreachable or unhealthy. Fail-closed: never faked. |
| `Budget` | `ast_class` | `code/ace_operational/reasoning_lab.py:57` | Shown-case fitness with a hard evaluation cap. |
| `Budget Preservation` | `markdown_def` | `docs/research/self_dev/ACE_ANTI_STAGNATION_SELF_REPAIR_REPORT_20261107.md:66` | When stagnation is flagged, `should_evaluate=False` and `should_commit=False`, completely bypassing holdout evaluation and suppressing commit spam. |
| `BudgetController` | `ast_class` | `code/ace_autonomy/budget.py:54` | Enforces declared step, candidate, retry, wall-time, and CPU-time ceilings. |
| `BudgetExceededError` | `ast_class` | `code/ace_host_controller/budget_permits.py:13` | Raised when an allocated compute or query budget is exhausted. |
| `BudgetExhaustedError` | `ast_class` | `code/ace_autonomy/errors.py:18` | Raised when a goal exceeds step, candidate, retry, wall-clock, or CPU ceilings. |
| `C1` | `markdown_def` | `docs/research/ACE_ROUND2_GATE_DESIGN_20261113.md:139` | identified improvement, measured |
| `C1 SESUAI` | `markdown_def` | `docs/research/PREAUDIT_VALIDATOR_V1_PILOT.md:28` | 23/23 artifacts present, sizes and SHA-256 match. |
| `C2` | `markdown_def` | `docs/research/ACE_ROUND2_GATE_DESIGN_20261113.md:144` | two distinct families evaluated: |
| `C2 SESUAI` | `markdown_def` | `docs/research/PREAUDIT_VALIDATOR_V1_PILOT.md:29` | 7/7 declared recomputations hold: per-band counts sum to |
| `C2 UNKNOWN` | `markdown_def` | `docs/research/PREAUDIT_VALIDATOR_V1_PILOT.md:49` | no count assertions declared; the validator invents none. |
| `C3` | `markdown_def` | `docs/research/ACE_ROUND2_GATE_DESIGN_20261113.md:147` | positive lift effect: the target |
| `C3 SESUAI` | `markdown_def` | `docs/research/PREAUDIT_VALIDATOR_V1_PILOT.md:35` | preregistered rule `differentiation_index_pp >= 0`; |
| `C3 UNKNOWN` | `markdown_def` | `docs/research/PREAUDIT_VALIDATOR_V1_PILOT.md:50` | no verdict check declared (these records carry no |
| `CachingBudget` | `ast_class` | `code/ace_operational/pilot_abc.py:179` | Budget with compile-once scoring. |
| `CalibrationReport` | `ast_class` | `code/ace_self_dev/metacognitive_predictor.py:128` | Complete calibration evaluation report (Brier, ECE, MCE, selective risk). |
| `CandidateFactoryV2Error` | `ast_class` | `tools/candidate_factory_v2.py:81` | Kesalahan parameter masukan atau kegagalan gerbang validasi kandidat v2. |
| `CandidateFeatures` | `ast_class` | `code/ace_self_dev/metacognitive_predictor.py:47` | Extracted structural, operator, and constraint features of a candidate mechanism. |
| `CandidateNode` | `ast_class` | `code/ace_host_controller/lineage.py:24` | Represents a discrete candidate in the evolutionary lineage. |
| `capability_record` | `markdown_def` | `docs/research/ACE_G4_PREREGISTRATION_20261113.md:209` | artifact file + digest + |
| `CapabilityAwareness` | `ast_class` | `code/ace_selfmodel/core.py:148` | Evaluates structural capability boundaries of ACE tools & Runtime against a proposed goal. |
| `CapabilityPermit` | `ast_class` | `code/ace_host_controller/budget_permits.py:101` | Explicit capability authorization granted to a research candidate or process. |
| `CapabilityRegistry` | `ast_class` | `code/ace_autonomy/registry.py:15` | Stores operational capabilities bound to signed step verification receipts. |
| `CartographyOfIgnorance` | `ast_class` | `code/ace_operational/causal_repo_evolution.py:95` | Maps every hypothesis into PROVED, CONFORMAL_BOUNDED, or ABSTAIN_FOR_EXPERIMENT. |
| `Catalog artifact` | `markdown_def` | `docs/research/ACE_CATALOG_GAP_DESIGN_20261113.md:48` | the `operator_catalog_v*` |
| `catalog_only` | `markdown_def` | `docs/research/ACE_CATALOG_GAP_DESIGN_20261113.md:105` | present in the catalog, never |
| `CatalogGapError` | `ast_class` | `code/ace_operational/catalog_gap.py:58` | Raised when a discovery record or catalog |
| `CausalEdge` | `ast_class` | `code/ace_causal/causal_miner.py:29` | Directed causal edge: source -> target (source causes target). |
| `CausalGap` | `ast_class` | `code/ace_research_f12/causal_agent.py:19` | Diagnosed structural capability gap in existing mechanisms. |
| `CausalGapAnalyzer` | `ast_class` | `code/ace_research_f12/causal_agent.py:58` | Analyzes error distributions between baseline predictions and observed evidence. |
| `CausalInvariantMiner` | `ast_class` | `code/ace_causal/causal_miner.py:187` | Discovers true causal graph invariants, eliminating spurious confounders and co-effects. |
| `code.ace_abstract_interp.__init__` | `ast_module` | `code/ace_abstract_interp/__init__.py:1` | ACE Abstract Interpretation & Invariant Synthesis Module. |
| `code.ace_abstract_interp.disjunctive_domain` | `ast_module` | `code/ace_abstract_interp/disjunctive_domain.py:1` | Disjunctive Abstract Interpretation via Semantic Trace Partitioning. |
| `code.ace_abstract_interp.invariants` | `ast_module` | `code/ace_abstract_interp/invariants.py:1` | Abstract Interpretation Invariant Analyzer & Invariant Synthesizer. |
| `code.ace_abstraction.__init__` | `ast_module` | `code/ace_abstraction/__init__.py:1` | ACE DreamCoder-style Wake-Sleep Library Abstraction Module. |
| `code.ace_abstraction.wake_sleep` | `ast_module` | `code/ace_abstraction/wake_sleep.py:1` | DreamCoder Wake-Sleep Library Abstraction Engine for Autonomous Capability Evolution. |
| `code.ace_automata.__init__` | `ast_module` | `code/ace_automata/__init__.py:1` | ACE Active Automata Learning Module based on Angluin's L* algorithm. |
| `code.ace_automata.lstar` | `ast_module` | `code/ace_automata/lstar.py:1` | Angluin's L* Active Automata Learning Algorithm. |
| `code.ace_autonomy.__init__` | `ast_module` | `code/ace_autonomy/__init__.py:1` | ACE Durable Autonomous Runtime (Fase 3 — Lane A). |
| `code.ace_autonomy.broker` | `ast_module` | `code/ace_autonomy/broker.py:1` | Typed Tool Broker enforcing allowlist, path isolation, subprocess RLIMIT_CPU, and ACE Runtime bridge. |
| `code.ace_autonomy.budget` | `ast_module` | `code/ace_autonomy/budget.py:1` | Real wall-clock, process/child CPU, step, candidate, and retry BudgetController. |
| `code.ace_autonomy.cli` | `ast_module` | `code/ace_autonomy/cli.py:1` | CLI interface for ACE Autonomous Runtime (Fase 3). |
| `code.ace_autonomy.core` | `ast_module` | `code/ace_autonomy/core.py:1` | Auditable, lease-scheduled, budget-enforced, crash-recoverable ACE Autonomous Runtime. |
| `code.ace_autonomy.errors` | `ast_module` | `code/ace_autonomy/errors.py:1` | Typed exception hierarchy for ACE Autonomous Runtime. |
| `code.ace_autonomy.escrow` | `ast_module` | `code/ace_autonomy/escrow.py:1` | Durable two-phase external action escrow with HALT_UNCERTAIN enforcement. |
| `code.ace_autonomy.planner` | `ast_module` | `code/ace_autonomy/planner.py:1` | Deterministic Planner translating high-level typed objectives into bounded step plans. |
| `code.ace_autonomy.policy` | `ast_module` | `code/ace_autonomy/policy.py:1` | ExecutionPolicy, GoalPolicy, BudgetCeiling, and safe O_NOFOLLOW/O_NONBLOCK file I/O. |
| `code.ace_autonomy.registry` | `ast_module` | `code/ace_autonomy/registry.py:1` | Authenticated CapabilityRegistry recording only IndependentVerifier-approved capabilities. |
| `code.ace_autonomy.research_pipeline` | `ast_module` | `code/ace_autonomy/research_pipeline.py:1` | Autonomous Continuous Researcher Agent Pipeline. |
| `code.ace_autonomy.verifier` | `ast_module` | `code/ace_autonomy/verifier.py:1` | Independent Host Verifier checking tool receipts against actual storage and post-conditions. |
| `code.ace_candidate_search.__init__` | `ast_module` | `code/ace_candidate_search/__init__.py:1` | Bounded arithmetic synthesis as data; no generated Python execution. |
| `code.ace_candidate_search.benchmark` | `ast_module` | `code/ace_candidate_search/benchmark.py:1` | Public, synthetic development bank. Never an independent confirmatory bank. |
| `code.ace_candidate_search.journal` | `ast_module` | `code/ace_candidate_search/journal.py:1` | Atomic durable checkpoints with canonical hash-chain and semantic prefix replay. |
| `code.ace_candidate_search.model` | `ast_module` | `code/ace_candidate_search/model.py:1` | Closed, integer-typed AST and validated resource contracts (stdlib only). |
| `code.ace_candidate_search.search` | `ast_module` | `code/ace_candidate_search/search.py:1` | Deterministic training-only proposal generation and restricted evaluation. |
| `code.ace_candidate_search.verify_results` | `ast_module` | `code/ace_candidate_search/verify_results.py:1` | Check every archived trial, decision and checksum against deterministic replay. |
| `code.ace_capability_evolution.__init__` | `ast_module` | `code/ace_capability_evolution/__init__.py:1` | Bounded public ACE capability acquisition pilot; not a production evolution runtime. |
| `code.ace_capability_evolution.compositional` | `ast_module` | `code/ace_capability_evolution/compositional.py:1` | Bounded composition of unchanged R1 guards and S2 counter programs. |
| `code.ace_capability_evolution.pilot` | `ast_module` | `code/ace_capability_evolution/pilot.py:1` | ACE bounded multi-generation public capability acquisition pilot. |
| `code.ace_capability_evolution.structural` | `ast_module` | `code/ace_capability_evolution/structural.py:1` | ACE v0.2: bounded data-conditioned transition from DFA to integer register. |
| `code.ace_capability_evolution.verify` | `ast_module` | `code/ace_capability_evolution/verify.py:1` | Fail-closed exact-report replay and provenance gate; no production approval. |
| `code.ace_capability_evolution.verify_structural` | `ast_module` | `code/ace_capability_evolution/verify_structural.py:1` | Fail-closed canonical full replay: no semantic or release promotion. |
| `code.ace_causal.__init__` | `ast_module` | `code/ace_causal/__init__.py:1` | ACE Causal Invariant Graph Mining & Pearl do-calculus Package. |
| `code.ace_causal.causal_miner` | `ast_module` | `code/ace_causal/causal_miner.py:1` | Causal Invariant Graph Mining & Pearl do-calculus. |
| `code.ace_chat.__init__` | `ast_module` | `code/ace_chat/__init__.py:1` | Data-only remote task dispatch via GitHub Actions to real ACE engine. |
| `code.ace_chat.task_runner` | `ast_module` | `code/ace_chat/task_runner.py:1` | ChatGPT/GitHub task runner for ACE, with strict data-only task envelopes. |
| `code.ace_code_agent.__init__` | `ast_module` | `code/ace_code_agent/__init__.py:1` | ACE Autonomous Source-Code Development Agent Package (V0.3). |
| `code.ace_code_agent.ai_advisor` | `ast_module` | `code/ace_code_agent/ai_advisor.py:1` | Autonomous Multi-AI Fleet Advisor for ACE (V0.5). |
| `code.ace_code_agent.cli` | `ast_module` | `code/ace_code_agent/cli.py:1` | CLI entry point for ACE Autonomous Code Agent V0.3. |
| `code.ace_code_agent.codebase_reader` | `ast_module` | `code/ace_code_agent/codebase_reader.py:1` | Codebase Reader & Failure History Analyzer. |
| `code.ace_code_agent.controller` | `ast_module` | `code/ace_code_agent/controller.py:1` | Autonomous Software Researcher Controller (ACE V0.3). |
| `code.ace_code_agent.independent_evaluator` | `ast_module` | `code/ace_code_agent/independent_evaluator.py:1` | Independent Evaluator & Scientific Meta-Productivity Benchmark. |
| `code.ace_code_agent.models` | `ast_module` | `code/ace_code_agent/models.py:1` | Data models for ACE Autonomous Source-Code Development Agent (V0.3). |
| `code.ace_code_agent.patch_diagnostic` | `ast_module` | `code/ace_code_agent/patch_diagnostic.py:1` | Candidate-bound regression diagnostics; never authorizes promotion. |
| `code.ace_code_agent.patch_synthesizer` | `ast_module` | `code/ace_code_agent/patch_synthesizer.py:1` | Modular Patch Generator for ACE Code Agent (V0.4). |
| `code.ace_code_agent.pr_manager` | `ast_module` | `code/ace_code_agent/pr_manager.py:1` | Autonomous PR Manager for ACE Code Agent (V0.4). |
| `code.ace_code_agent.problem_selector` | `ast_module` | `code/ace_code_agent/problem_selector.py:1` | Autonomous Problem Selector & Hypothesis Generator. |
| `code.ace_code_agent.repo_retrieval` | `ast_module` | `code/ace_code_agent/repo_retrieval.py:1` | Bounded, read-only AST repository retrieval for ACE coding research. |
| `code.ace_code_agent.static_probe` | `ast_module` | `code/ace_code_agent/static_probe.py:1` | Public, read-only diagnostics for bounded three-input AI predicates. |
| `code.ace_code_agent.worktree_harness` | `ast_module` | `code/ace_code_agent/worktree_harness.py:1` | ACE candidate intake gate (fail closed). |
| `code.ace_cognition.__init__` | `ast_module` | `code/ace_cognition/__init__.py:1` | ACE Cognition, Substrate Guarding, and Meta-Curriculum System. |
| `code.ace_cognition.evolutionary_memory` | `ast_module` | `code/ace_cognition/evolutionary_memory.py:1` | Evolutionary Associative Memory for Cross-Cycle Knowledge Transfer. |
| `code.ace_cognition.meta_curriculum` | `ast_module` | `code/ace_cognition/meta_curriculum.py:1` | Autonomous Meta-Curriculum & Frontier Expander. |
| `code.ace_cognition.reasoning` | `ast_module` | `code/ace_cognition/reasoning.py:1` | Bounded data-only reasoning integration; no model calls or Python source execution. |
| `code.ace_cognition.substrate_guardian` | `ast_module` | `code/ace_cognition/substrate_guardian.py:1` | ACE Substrate Guardian & Survival Controller (Somatic Self-Preservation). |
| `code.ace_component_synthesis.__init__` | `ast_module` | `code/ace_component_synthesis/__init__.py:1` | ACE Type-Directed Component-Based Program Synthesizer. |
| `code.ace_component_synthesis.component_synthesizer` | `ast_module` | `code/ace_component_synthesis/component_synthesizer.py:1` | SyGuS-style Type-Directed Component-Based Program Synthesizer. |
| `code.ace_conformal.__init__` | `ast_module` | `code/ace_conformal/__init__.py:1` | ACE Conformal Risk Control & Distribution-Free Prediction Sets Package. |
| `code.ace_conformal.conformal_risk` | `ast_module` | `code/ace_conformal/conformal_risk.py:1` | Conformal Risk Control & Distribution-Free Prediction Sets. |
| `code.ace_core_repair.__init__` | `ast_module` | `code/ace_core_repair/__init__.py:1` | ACE Core Learner Repairs (W3). |
| `code.ace_core_repair.admission` | `ast_module` | `code/ace_core_repair/admission.py:1` | Admission-aware selection, separate pos/neg reporting, and second counterexample round (W3). |
| `code.ace_core_repair.decomposed_library` | `ast_module` | `code/ace_core_repair/decomposed_library.py:1` | Decomposed component capability library supporting component-level inheritance (W3). |
| `code.ace_core_repair.doctor` | `ast_module` | `code/ace_core_repair/doctor.py:1` | System diagnostics doctor for ACE workspace, budgets, and regression suites (W3). |
| `code.ace_core_repair.drift_quarantine` | `ast_module` | `code/ace_core_repair/drift_quarantine.py:1` | Semantic drift quarantine and budgeted active query allocation (W3 e14aa). |
| `code.ace_dsl_growth.__init__` | `ast_module` | `code/ace_dsl_growth/__init__.py:1` | ACE Typed DSL Capability Growth Primitives (W4). |
| `code.ace_dsl_growth.experiment_runner` | `ast_module` | `code/ace_dsl_growth/experiment_runner.py:1` | Preregistered A/B/C comparative evaluation experiment runner (W4). |
| `code.ace_dsl_growth.graph_primitives` | `ast_module` | `code/ace_dsl_growth/graph_primitives.py:1` | Typed graph adjacency traversal primitives for bounded graph reasoning (W4). |
| `code.ace_dsl_growth.ratio4_primitives` | `ast_module` | `code/ace_dsl_growth/ratio4_primitives.py:1` | Out-of-grammar ratio 4:1 modular primitives (W4). |
| `code.ace_egraph.__init__` | `ast_module` | `code/ace_egraph/__init__.py:1` | ACE Equality Saturation & E-Graphs (Optimal AST Rewriting) Package. |
| `code.ace_egraph.equality_saturation` | `ast_module` | `code/ace_egraph/equality_saturation.py:1` | Equality Saturation & E-Graphs (Optimal AST Rewriting Engine). |
| `code.ace_epistemic.__init__` | `ast_module` | `code/ace_epistemic/__init__.py:1` | ACE Active Epistemic Uncertainty Sampling & Bayesian Active Learning (BALD) Package. |
| `code.ace_epistemic.active_sampler` | `ast_module` | `code/ace_epistemic/active_sampler.py:1` | Active Epistemic Uncertainty Sampling (BALD) for Program Synthesis & Verification. |
| `code.ace_evaluator.__init__` | `ast_module` | `code/ace_evaluator/__init__.py:1` | ACE Uncheatable Sealed Evaluator module (W2). |
| `code.ace_evaluator.cheat_detection` | `ast_module` | `code/ace_evaluator/cheat_detection.py:1` | Cheat detection enforcing behavioral and structural anti-cheating admission criteria (W2). |
| `code.ace_evaluator.sealed_generator` | `ast_module` | `code/ace_evaluator/sealed_generator.py:1` | Sealed seed generator managing secret and public fallback evaluation environments (W2 Rule 3). |
| `code.ace_evaluator.task_families` | `ast_module` | `code/ace_evaluator/task_families.py:1` | Parameterized task family generators with count-matched adversarial negatives (W2). |
| `code.ace_evolution.__init__` | `ast_module` | `code/ace_evolution/__init__.py:1` | ACE Evolutionary Island Program Search Module inspired by DeepMind's FunSearch and STGP. |
| `code/ace_autonomy/` | `markdown_def` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:10` | scheduler, typed tool interface, receipts, budget, crisis-stop, adapters to frozen source, deterministic reference planner. |
| `code/ace_operational/` | `markdown_def` | `handover/local_state_sweep_20261115/study-ace-77cca3c.md:33` | **160 berkas `.py`, 59.566 baris — 44% seluruh Python repo.** Dari 160 itu, **83 modul non-tes dan 77 berkas `test_*.py`** — hampir separuh "inti" adalah kode tes. |
| `code/ace_operational/autonomy_loop.py` | `markdown_def` | `PROJECT.md:76` | Autonomy loop, worker order lifecycle, gap discovery. |
| `code/ace_operational/coding_loop.py` | `markdown_def` | `PROJECT.md:75` | Coding agent loop, file atomic writes, general task synthesis. |
| `code/ace_operational/language.py` | `markdown_def` | `PROJECT.md:74` | Intent classifier and conversational engine. |
| `code/ace_operational/models_backend.py` | `markdown_def` | `PROJECT.md:77` | GGUF discovery, llama inference, JSON parsing. |
| `code/ace_operational/proposer_episodes.py` | `markdown_def` | `docs/research/PROPOSER_ENGINE_STAGE1_DESIGN.md:19` | frozen-episode |
| `code/ace_operational/proposer_rubric.py` | `markdown_def` | `docs/research/PROPOSER_ENGINE_STAGE1_DESIGN.md:21` | deterministic rubric |
| `code/ace_operational/proposer_schema.py` | `markdown_def` | `docs/research/PROPOSER_ENGINE_STAGE1_DESIGN.md:8` | the rejectable package |
| `code/ace_operational/proposer_simulation.py` | `markdown_def` | `docs/research/PROPOSER_ENGINE_STAGE1_DESIGN.md:24` | harness + exit |
| `code/ace_operational/proposer_validator.py` | `markdown_def` | `docs/research/PROPOSER_ENGINE_STAGE1_DESIGN.md:16` | fail-closed |
| `code/ace_operational/store.py` | `markdown_def` | `PROJECT.md:78` | SQLite WAL store with fencing leases. |
| `code/ace_operational/test_edition4_acceptance.py` | `markdown_def` | `PROJECT.md:80` | Primary 21-test acceptance suite. |
| `code/ace_operational/test_proposer_engine.py` | `markdown_def` | `docs/research/PROPOSER_ENGINE_STAGE1_DESIGN.md:27` | 17 tests: |
| `code/ace_operational/web_server.py` | `markdown_def` | `PROJECT.md:79` | Anime web server and SSE streams. |
| `code/ace_research_repair/` | `markdown_def` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:11` | bug corpus, typed repair representation, reference transformations, localization, patches, tests and evidence. No production application code executes in privileged orchestrator. |
| `code/ace_selfmodel/` | `markdown_def` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:12` | read-only runtime introspection and calibrated metacognition experiments. |
| `CONFLICTING_DECISION` | `markdown_def` | `docs/research/ACE_A2_TRANCHE2_CLOSURE.md:17` | lebih dari satu keputusan berbeda untuk ID yang sama. |
| `Context (Donor)` | `markdown_def` | `docs/research/external_repos/SOTA_GODEL_AND_ABSTRACTION_REPOS_20261107.md:195` | The *succeeding* lineage node (the donor of the working capability). |
| `covered` | `markdown_def` | `docs/research/ACE_CATALOG_GAP_DESIGN_20261113.md:101` | the extended solver solves every |
| `Cross-Task Transfer` | `markdown_def` | `docs/research/self_dev/SOTA_EXTERNAL_REPOSITORIES_SURVEY_20261107.md:325` | Candidate mechanisms evolved to solve one task family (e.g. modular stride shifts in Family K) are systematically cross-tested on other task families (e.g. balance shifts in Family J). |
| `Cryptographic Auditability` | `markdown_def` | `docs/research/self_dev/SOTA_EXTERNAL_REPOSITORIES_SURVEY_20261107.md:388` | Every decision is sealed with an HMAC SHA-256 signature, ensuring cryptographic provenance without external API calls. |
| `curriculum_lab.py` | `markdown_def` | `handover/local_state_sweep_20261115/misi9/MISI9_LAPORAN.md:93` | `_pricing_family` ranges widened (B-3 freeze 2026-11-13, |
| `Cycles Audited` | `markdown_def` | `docs/research/self_dev/ACE_ANTI_STAGNATION_SELF_REPAIR_REPORT_20261107.md:15` | 180+ completed autonomous continuity cycles recorded in `checkpoints/self_dev/research_state.json`. |
| `D1` | `markdown_def` | `handover/ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md:78` | Card results absent (U1): the exhibit is an intake + |
| `D2` | `markdown_def` | `handover/ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md:80` | KNN arm unmeasured (U2): candidate #4 has a protocol, |
| `D3` | `markdown_def` | `handover/ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md:83` | Candidate #2's companion intake is **unpinned in the |
| `D4` | `markdown_def` | `handover/ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md:90` | Sandbox intake erased by rollback (§4): current |
| `D5` | `markdown_def` | `handover/ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md:94` | Corpus provenance wording: `trial.py`'s docstring |
| `data_dependency` | `markdown_def` | `docs/ACE_REPAIR_PRESCORE_V1.md:63` | `T10_apply_row_mask` (in-place mutation of caller template list), `T11_register_route` (shared mutable default route dictionary), `T12_compute_net_total` (tax computed on stale `subtotal` instead of `discounted` local va… |
| `Date/scheduling arithmetic` | `markdown_def` | `docs/research/ACE_FAMILY3_DESIGN_20261113.md:82` | component |
| `decision_owner` | `markdown_def` | `docs/research/ACE_C6_FAILURE_TO_AGENDA.md:9` | `"Ian"` |
| `decision_status` | `markdown_def` | `docs/research/ACE_C6_FAILURE_TO_AGENDA.md:10` | `"PROPOSED_AWAITING_IAN"` (`claim_made=False`) |
| `DELIVERY_ONLY` | `markdown_def` | `docs/research/ACE_G4_G5_INSTRUMENT_DESIGN_20261112.md:104` | summaries exist and were delivered |
| `DG1` | `markdown_def` | `docs/research/generations/ACE_P4_GENERATIONS_GROWTH_PRESCORE_20261107.md:57` | `UG1` inverted terminal labels. |
| `DG2` | `markdown_def` | `docs/research/generations/ACE_P4_GENERATIONS_GROWTH_PRESCORE_20261107.md:58` | `UG3` inverted terminal labels. |
| `Diagnosis` | `markdown_def` | `docs/research/external_repos/SOTA_GODEL_AND_ABSTRACTION_REPOS_20261107.md:182` | Instead of looking at a single traceback, the diagnosis prompt compares the execution trajectories $\tau(v, t_1)$ and $\tau(v, t_2)$: |
| `Director-cycle binding` | `markdown_def` | `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM39.md:32` | `build_scan_packet` shapes |
| `Engineering GO` | `markdown_def` | `docs/ACE_CAPABILITY_DECISION_AND_CODEX_HANDOFF_20261107.md:64` | bounded deterministic source is runnable, independently verifiable, original regression intact. |
| `Environment Population` | `markdown_def` | `docs/research/self_dev/SOTA_EXTERNAL_REPOSITORIES_SURVEY_20261107.md:323` | In ACE, "environments" are diagnostic tasks and data distributions (`task_k1`, `task_k2`, `task_j1`, `task_j2`). |
| `evaluation_report` | `markdown_def` | `docs/research/ACE_G4_PREREGISTRATION_20261113.md:215` | this text's back-reference, |
| `G3 application run — starting` | `markdown_heading` | `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM52.md:32` | Protocol `5f907362…b8bb6d` (Addendum 50). The runner |
| `G4 application — INHERITANCE_DEMONSTRATED (instrument-scored)` | `markdown_heading` | `docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM57.md:11` | Experiment `g4-application-01`, protocol hash |
| `Gate 0 — reproduce baseline and pin provenance` | `markdown_heading` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:18` | Inputs: source SHA, relevant branch head SHAs, exact environment, public protocol and commit-set. Execute and archive: |
| `Gate 1 — bounded self-operating runtime` | `markdown_heading` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:29` | ```json |
| `Gate 1 — equivalence (must pass before any timing claim)` | `markdown_heading` | `docs/ACE_PARSE_ONCE_RESULTS_20261113.md:31` | - Unit/differential tests (`test_parse_once.py`, 6 tests): shared-tree |
| `Gate 1 — equivalence replay (pilot workload, seeds 1–12)` | `markdown_heading` | `docs/ACE_GENERATION_CONTEXT_RESULTS_20261113.md:26` | - 6 differential tests (`test_gen_context.py`): context contents |
| `Gate 2 — fresh-workload confirmation (seeds 901–912)` | `markdown_heading` | `docs/ACE_GENERATION_CONTEXT_RESULTS_20261113.md:41` | Disjoint from the pilot workload (1–12) and from the parse-once |
| `Gate 2 — speedup confirmation (fresh workload)` | `markdown_heading` | `docs/ACE_PARSE_ONCE_RESULTS_20261113.md:50` | Bench: `code/ace_operational/parse_once_bench.py`. Workload: |
| `Gate 3 — family-disjoint representation transfer` | `markdown_heading` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:95` | Prior to implementation or terminal scoring, freeze: |
| `Gate 4 — staged self-development generations G0 → G1 → G2` | `markdown_heading` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:113` | Allowed mutation scope: one bounded candidate module such as a repair search heuristic, learned feature extractor or policy ranking. Not mutable by candidate: evaluation, terminal data, audit, authorization, operator rev… |
| `Gate 5 — functional self-model and consciousness-related research` | `markdown_heading` | `docs/ACE_AUTONOMY_IMPLEMENTATION_GATES_20261107.md:133` | Separate scientific endpoints: |
| `Rel 1 — KBM → SeaBank (rel hidup program)` | `markdown_heading` | `handover/SPESIFIKASI_WS2_REL_DAN_BUKTI.md:35` | - Kaki platform: laporan royalti KBM. Keluaran |
| `Rel 2 — Fastwork → rekening bank` | `markdown_heading` | `handover/SPESIFIKASI_WS2_REL_DAN_BUKTI.md:47` | - Kaki platform: riwayat penarikan Fastwork. |
| `Rel 3 — GoPay / QRIS (rel langsung)` | `markdown_heading` | `handover/SPESIFIKASI_WS2_REL_DAN_BUKTI.md:60` | - Kaki platform: laporan penyelesaian (settlement) |
