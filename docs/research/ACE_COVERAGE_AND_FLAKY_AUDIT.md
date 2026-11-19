# Audit Cakupan Simbol & Deteksi Tes Flaky — ACE

- Schema: `ace.coverage-flaky-audit.v1`
- Modul sumber dipindai (non-terlarang): 344
- Modul punya berkas tes tertaut: 296 / 344
- Modul bersimbol publik tanpa tes tertaut: 40
- Berkas tes dipindai: 233
- Cakupan simbol publik (AST): 1066 / 1565 (68.1%)
- Wilayah terlarang dilewati eksplisit: 24 berkas

## Ringkasan Cakupan per Paket

| Paket | Modul | Modul dgn Tes | Simbol Tercakup | Total Simbol | Cakupan |
| --- | ---: | ---: | ---: | ---: | ---: |
| `code/ace_abstract_interp` | 2 | 2 | 7 | 7 | 100.0% |
| `code/ace_abstraction` | 1 | 1 | 2 | 2 | 100.0% |
| `code/ace_automata` | 1 | 1 | 2 | 3 | 66.7% |
| `code/ace_autonomy` | 11 | 7 | 16 | 31 | 51.6% |
| `code/ace_candidate_search` | 5 | 5 | 18 | 23 | 78.3% |
| `code/ace_capability_evolution` | 5 | 5 | 26 | 52 | 50.0% |
| `code/ace_causal` | 1 | 1 | 3 | 5 | 60.0% |
| `code/ace_chat` | 1 | 1 | 6 | 6 | 100.0% |
| `code/ace_code_agent` | 13 | 12 | 22 | 23 | 95.7% |
| `code/ace_cognition` | 4 | 4 | 13 | 18 | 72.2% |
| `code/ace_component_synthesis` | 1 | 1 | 7 | 7 | 100.0% |
| `code/ace_conformal` | 1 | 1 | 5 | 5 | 100.0% |
| `code/ace_core_repair` | 4 | 4 | 6 | 6 | 100.0% |
| `code/ace_dsl_growth` | 3 | 3 | 3 | 4 | 75.0% |
| `code/ace_egraph` | 1 | 1 | 11 | 13 | 84.6% |
| `code/ace_epistemic` | 1 | 1 | 3 | 3 | 100.0% |
| `code/ace_evolution` | 3 | 2 | 21 | 23 | 91.3% |
| `code/ace_game_theory` | 1 | 1 | 4 | 4 | 100.0% |
| `code/ace_gnn` | 1 | 1 | 9 | 15 | 60.0% |
| `code/ace_host_controller` | 12 | 11 | 39 | 50 | 78.0% |
| `code/ace_host_exchange` | 2 | 2 | 5 | 5 | 100.0% |
| `code/ace_ilp` | 1 | 1 | 5 | 5 | 100.0% |
| `code/ace_indo_nlp` | 4 | 4 | 18 | 21 | 85.7% |
| `code/ace_integration_redteam` | 1 | 1 | 2 | 2 | 100.0% |
| `code/ace_interpolation` | 1 | 1 | 12 | 19 | 63.2% |
| `code/ace_inversion` | 1 | 1 | 7 | 8 | 87.5% |
| `code/ace_loop` | 1 | 1 | 19 | 24 | 79.2% |
| `code/ace_mcp` | 3 | 3 | 7 | 7 | 100.0% |
| `code/ace_mcts` | 1 | 1 | 2 | 2 | 100.0% |
| `code/ace_mission` | 5 | 5 | 8 | 13 | 61.5% |
| `code/ace_neurosymbolic` | 4 | 4 | 26 | 36 | 72.2% |
| `code/ace_operational` | 77 | 75 | 296 | 415 | 71.3% |
| `code/ace_pac_bayes` | 1 | 1 | 7 | 7 | 100.0% |
| `code/ace_real_world` | 7 | 7 | 7 | 14 | 50.0% |
| `code/ace_red_team` | 1 | 1 | 15 | 15 | 100.0% |
| `code/ace_report` | 1 | 1 | 1 | 1 | 100.0% |
| `code/ace_research_agenda` | 3 | 3 | 9 | 12 | 75.0% |
| `code/ace_research_discovery` | 8 | 8 | 32 | 71 | 45.1% |
| `code/ace_research_f12` | 5 | 5 | 10 | 21 | 47.6% |
| `code/ace_research_f13` | 5 | 4 | 6 | 11 | 54.5% |
| `code/ace_research_f14` | 8 | 5 | 15 | 34 | 44.1% |
| `code/ace_research_generations` | 9 | 8 | 17 | 36 | 47.2% |
| `code/ace_research_hypgen` | 5 | 4 | 14 | 15 | 93.3% |
| `code/ace_research_primitives` | 2 | 2 | 18 | 23 | 78.3% |
| `code/ace_research_repair` | 9 | 9 | 28 | 34 | 82.4% |
| `code/ace_research_reptransfer` | 9 | 6 | 14 | 37 | 37.8% |
| `code/ace_runtime` | 2 | 2 | 5 | 13 | 38.5% |
| `code/ace_self_dev` | 25 | 18 | 59 | 70 | 84.3% |
| `code/ace_selfmodel` | 5 | 5 | 9 | 14 | 64.3% |
| `code/ace_smt` | 1 | 1 | 20 | 28 | 71.4% |
| `code/ace_synthesis` | 1 | 1 | 1 | 2 | 50.0% |
| `code/ace_visual_bridge` | 2 | 2 | 7 | 10 | 70.0% |
| `tools` | 62 | 39 | 142 | 240 | 59.2% |

## Modul Bersimbol Publik Tanpa Tes Tertaut (Top 25 dari 40)

| Modul | Berkas | Jumlah Simbol Publik |
| --- | --- | ---: |
| `ace_autonomy.broker` | `code/ace_autonomy/broker.py` | 1 |
| `ace_autonomy.cli` | `code/ace_autonomy/cli.py` | 1 |
| `ace_autonomy.planner` | `code/ace_autonomy/planner.py` | 1 |
| `ace_autonomy.verifier` | `code/ace_autonomy/verifier.py` | 1 |
| `ace_code_agent.cli` | `code/ace_code_agent/cli.py` | 1 |
| `ace_evolution.neutral_archive_pilot_20261109` | `code/ace_evolution/neutral_archive_pilot_20261109.py` | 2 |
| `ace_host_controller.isolated_worker` | `code/ace_host_controller/isolated_worker.py` | 4 |
| `ace_operational.memory_snapshot` | `code/ace_operational/memory_snapshot.py` | 3 |
| `ace_operational.oaie_cli` | `code/ace_operational/oaie_cli.py` | 3 |
| `ace_research_f13.verify` | `code/ace_research_f13/verify.py` | 2 |
| `ace_research_f14.benchmark_v3` | `code/ace_research_f14/benchmark_v3.py` | 3 |
| `ace_research_f14.terminal_tasks_v3` | `code/ace_research_f14/terminal_tasks_v3.py` | 2 |
| `ace_research_f14.verify_v3` | `code/ace_research_f14/verify_v3.py` | 2 |
| `ace_research_generations.mechanisms` | `code/ace_research_generations/mechanisms.py` | 7 |
| `ace_research_hypgen.runner` | `code/ace_research_hypgen/runner.py` | 1 |
| `ace_research_reptransfer.head` | `code/ace_research_reptransfer/head.py` | 3 |
| `ace_research_reptransfer.runner` | `code/ace_research_reptransfer/runner.py` | 5 |
| `ace_research_reptransfer.verify` | `code/ace_research_reptransfer/verify.py` | 2 |
| `ace_self_dev.checkpoint_manager` | `code/ace_self_dev/checkpoint_manager.py` | 1 |
| `ace_self_dev.cli` | `code/ace_self_dev/cli.py` | 1 |
| `ace_self_dev.diagnostic_engine` | `code/ace_self_dev/diagnostic_engine.py` | 1 |
| `ace_self_dev.hypothesis_selector` | `code/ace_self_dev/hypothesis_selector.py` | 1 |
| `ace_self_dev.isolated_evaluator` | `code/ace_self_dev/isolated_evaluator.py` | 1 |
| `ace_self_dev.proposal_engine` | `code/ace_self_dev/proposal_engine.py` | 1 |
| `tools.ace_autonomous_daemon` | `tools/ace_autonomous_daemon.py` | 7 |

## Audit Tes Flaky (Subproses Berulang)

- Target diuji: 4 (masing-masing 3 eksekusi)
- Konsisten lulus & tree bersih: 4
- Flaky terdeteksi: 0
- Konsisten gagal: 0
- Kotor tree (dirty_targets): 0
- Status keseluruhan: `PASS`

| Target | Lulus/Run | Flaky | Tree Bersih | Rerata (ms) | Stdev (ms) |
| --- | ---: | --- | --- | ---: | ---: |
| `tools.test_repo_index` | 3/3 | TIDAK | YA | 203.77 | 1.05 |
| `tools.test_repo_index_doc` | 3/3 | TIDAK | YA | 237.78 | 1.68 |
| `tools.test_verify_repair_v2` | 3/3 | TIDAK | YA | 137.43 | 1.48 |
| `tools.test_coverage_and_flaky_audit` | 3/3 | TIDAK | YA | 1095.13 | 15.9 |

## Berkas Wilayah Terlarang yang Dilewati Eksplisit

- `code/ace_evaluator/__init__.py`
- `code/ace_evaluator/cheat_detection.py`
- `code/ace_evaluator/sealed_generator.py`
- `code/ace_evaluator/task_families.py`
- `code/ace_evaluator/test_sealed_evaluator.py`
- `code/ace_host_controller/sealed_evaluator.py`
- `code/ace_operational/abc_v3_scorer.py`
- `code/ace_operational/cognitive_memory.py`
- `code/ace_operational/g1_instrument.py`
- `code/ace_operational/g3_instrument.py`
- `code/ace_operational/g4_instrument.py`
- `code/ace_operational/g5_instrument.py`
- `code/ace_operational/memory_writeback.py`
- `code/ace_operational/round2_instrument.py`
- `code/ace_operational/test_abc_v3_scorer.py`
- `code/ace_operational/test_g1_instrument.py`
- `code/ace_operational/test_g3_instrument.py`
- `code/ace_operational/test_g4_instrument.py`
- `code/ace_operational/test_g5_instrument.py`
- `code/ace_operational/test_memory_writeback.py`
- `code/ace_operational/test_round2_instrument.py`
- `tools/abc_v3_run.py`
- `tools/memory_writeback.py`
- `tools/round2_gate_run.py`
