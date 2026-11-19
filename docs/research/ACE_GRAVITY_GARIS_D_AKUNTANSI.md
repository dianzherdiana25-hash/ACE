# Akuntansi Garis D · Pengujian, Pengerasan Fuzz & Deteksi Flaky

Seluruh serahan Garis D disusun oleh Antigravity sebagai **draft PR** terpisah di atas `origin/main` (`478848d`), tanpa menyentuh instrumen ukur EVO 0007/G*/ABC-v3/round2, jalur tulis memory store, ataupun direktori stage Ian. Akuntansi garis sebelumnya tersedia di [PR #345](https://github.com/dianzherdiana25-hash/ACE/pull/345) (Garis B), [PR #352](https://github.com/dianzherdiana25-hash/ACE/pull/352) (Garis C), dan [PR #358](https://github.com/dianzherdiana25-hash/ACE/pull/358) (Garis A Tranche 2).

| Butir | Status | PR Draf & Commit | Branch | Ringkasan Serahan & Hasil Uji |
| --- | --- | --- | --- | --- |
| D1 · Pengerasan Fuzz `tools/` | Selesai | [PR #359](https://github.com/dianzherdiana25-hash/ACE/pull/359) (`6d25903`) | `gravity/d1-fuzz-hardening` | Perluasan `tools/fuzz_parsers.py` ke **33 target parser non-verdict** (matriks 3 seed × 300 iterasi = 900 eksekusi/target, `total_crashes = 0`), perbaikan 10 crash nyata parser `tools/`, pembaruan `tools/FUZZ_STANDARD.md`, 10 tes regresi, dan `docs/research/ACE_D1_FUZZ_HARDENING.md`. Suite D1: `52 tests — OK`. |
| D2 · Edge-case Core Ops & Budget | Selesai | [PR #360](https://github.com/dianzherdiana25-hash/ACE/pull/360) (`3bfbead`) | `gravity/d2-core-ops-edge-tests` | `code/ace_operational/test_core_ops_d2_edge.py` (**30 tes**): `brain_registry`, `catalog_artifact`, `catalog_gap`, `admission_hygiene`, `preaudit_validator`, `ace_autonomy.budget`. 2 bug nyata dicatat via `@unittest.expectedFailure`. Suite D2 + baseline: `113 tests — OK (expected failures=2)`. |
| D3 · Edge-case `ace_self_dev` & `ace_runtime` | Selesai | [PR #361](https://github.com/dianzherdiana25-hash/ACE/pull/361) (`70f6264`) | `gravity/d3-selfdev-runtime-edge-tests` | `code/ace_self_dev/test_selfdev_runtime_d3_edge.py` (**28 tes**): `fenced_store`, `atomic_lease`, `state_manager`, `checkpoint_manager`, `stagnation_detector`, `lineage_governor`, `models`, `ace_runtime.engine`. 1 bug `now=NaN` dicatat via `@unittest.expectedFailure`. Suite D3 + baseline: `74 tests — OK (expected failures=1)`. |
| D4 · Edge-case Research Synthesis & Verifikasi Matematika | Selesai | [PR #362](https://github.com/dianzherdiana25-hash/ACE/pull/362) (`0dc6ddb`) | `gravity/d4-research-synthesis-edge-tests` | `code/ace_egraph/test_synthesis_math_d4_edge.py` (**34 tes**): `ace_egraph`, `ace_smt`, `ace_conformal`, `ace_pac_bayes`, `ace_game_theory`, `ace_abstraction`, `ace_automata`. 8 bug nyata lintas 7 modul dicatat via `@unittest.expectedFailure`. Suite D4 + baseline: `74 tests — OK (expected failures=8)`. |
| D5 · Edge-case Mission, Indo NLP, MCP, Chat & Report | Selesai | [PR #363](https://github.com/dianzherdiana25-hash/ACE/pull/363) (`6fef59a`) | `gravity/d5-mission-indo-edge-tests` | `code/ace_mission/test_mission_indo_d5_edge.py` (**29 tes**): `ace_mission`, `ace_indo_nlp`, `ace_mcp`, `ace_chat`, `ace_report`. 4 bug nyata dicatat via `@unittest.expectedFailure`. Suite D5 + baseline: `102 tests — OK (expected failures=4)`. |
| D6 · Auditor Cakupan Simbol AST & Detektor Tes Flaky | Selesai | [PR #364](https://github.com/dianzherdiana25-hash/ACE/pull/364) (`3ccf1ae`) | `gravity/d6-coverage-and-flaky-audit` | `tools/coverage_and_flaky_audit.py` + `tools/test_coverage_and_flaky_audit.py` (**8 tes**) + `docs/research/ACE_COVERAGE_AND_FLAKY_AUDIT.md` (`344` modul non-terlarang dipindai, `24` berkas terlarang dilewati eksplisit, cakupan simbol AST `68.1%`, uji flaky `4/4` target × 3 run `PASS` tanpa kotor tree). |

## Uji Gabungan Lintas D1–D6 (Overlay `/tmp/garis_d_combo`, dibersihkan pascauji)

Seluruh 6 commit `D1`–`D6` diterapkan di atas `origin/main` (`478848d`) ke worktree sementara `/tmp/garis_d_combo` dan dijalankan serempak terhadap 47 modul tes unit + fuzz + baseline (`tools/verify_sources.py` ikut diverifikasi):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/garis_d_combo/code:/tmp/garis_d_combo python3 -m unittest \
  tools.test_fuzz_parsers tools.test_pattern_distill tools.test_four_arm_report tools.test_curriculum_gen tools.test_portability_pack tools.test_instance_kit tools.test_ruleset_readiness tools.test_repo_index tools.test_repo_status_dashboard tools.test_kbm_pack_check tools.test_opportunity_register tools.test_self_send_audit_view tools.test_kbm_pipeline tools.test_daily_digest \
  ace_operational.test_core_ops_d2_edge ace_operational.test_brain_registry ace_operational.test_catalog_artifact ace_operational.test_catalog_gap ace_operational.test_admission_hygiene ace_operational.test_preaudit_validator_v2 ace_autonomy.test_budget_policy_registry_edge \
  ace_self_dev.test_selfdev_runtime_d3_edge ace_self_dev.test_fenced_store ace_self_dev.test_lease_ownership ace_self_dev.test_stagnation_detector ace_runtime.test_engine \
  ace_egraph.test_synthesis_math_d4_edge ace_egraph.test_equality_saturation ace_smt.test_dpllt_solver ace_conformal.test_conformal_risk ace_pac_bayes.test_pac_bounds ace_game_theory.test_minimax_synthesizer ace_abstraction.test_wake_sleep ace_automata.test_lstar \
  ace_mission.test_mission_indo_d5_edge ace_mission.test_admission ace_mission.test_mission_bus ace_indo_nlp.test_discourse ace_indo_nlp.test_lexicon_kb ace_indo_nlp.test_morphology ace_indo_nlp.test_phonotactics ace_mcp.test_bridge ace_mcp.test_code_diagnostic ace_mcp.test_transport ace_chat.test_task_runner ace_report.test_mobile_report \
  tools.test_coverage_and_flaky_audit
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/garis_d_combo/tools/verify_sources.py
```

- **Suite gabungan D1–D6:** **Ran 423 tests in 68.854s — OK (expected failures=15)**
- **Integritas sumber:** **PASS: 25 imported files match their recorded Git blob IDs (offline)**

## Rekap Bug Nyata Ditemukan untuk Review Engineer (15 `@unittest.expectedFailure` di `code/` + 10 Perbaikan di `tools/`)

Sesuai kebijakan `tools/FUZZ_STANDARD.md`, perkakas `tools/` pada D1 diperbaiki langsung di branch D1 (`10` crash parser), sedangkan seluruh bug nyata yang ditemukan di modul produksi `code/` **tidak diubah** dan didokumentasikan secara eksplisit via `@unittest.expectedFailure`:

- **D2 (2 bug):**
  1. `code/ace_operational/brain_registry.py` (`BrainRegistry.match`): `descriptor=""` bertindak sebagai wildcard (`"" in hint == True`) sehingga cocok ke sembarang model (`test_05`).
  2. `code/ace_autonomy/budget.py` (`BudgetUsage.from_dict`): `retries_by_step` bernilai non-dict (mis. list) memicu `AttributeError` mentah (`test_29`).
- **D3 (1 bug):**
  3. `code/ace_self_dev/fenced_store.py` (`_active`): `now=NaN` membuat perbandingan `row[3] <= now` bernilai `False`, meloloskan lease kedaluwarsa (`test_07`).
- **D4 (8 bug):**
  4. `code/ace_smt/dpllt_solver.py:758-762` (`Eq` hanya mengodekan `left <= right`, menghilangkan `left >= right`, `test_10`).
  5. `code/ace_smt/dpllt_solver.py:735-768` (`Ne` masuk tuple kondisi L735 lalu melempar `ValueError: Unsupported condition`, `test_11`).
  6. `code/ace_conformal/conformal_risk.py:131` (`lambda_candidates=[]` memicu `IndexError` mentah alih-alih `ValueError`, `test_15`).
  7. `code/ace_pac_bayes/pac_bounds.py:162` (`ProgramEnsembleDistribution` kosong memicu `ZeroDivisionError`, `test_21`).
  8. `code/ace_game_theory/minimax_synthesizer.py:124-141` (`HedgePlayer.compute_regret` masih menyisakan stub `pass` dan memakai strategi akhir alih-alih akumulasi historis `sum_t <p_t, loss_t>`, `test_25`).
  9. `code/ace_game_theory/minimax_synthesizer.py:161` (`MinimaxCoEvolution.solve(rounds=0)` memicu `ZeroDivisionError` mentah alih-alih `ValueError`, `test_26`).
  10. `code/ace_abstraction/wake_sleep.py:29` (`TypedASTNode('len')` mengompilasi `'len(word)'`, gagal dievaluasi oleh `DiscoveredPrimitive.evaluate` karena sandbox `{'__builtins__': None}` tidak menyertakan `len`, `test_30`).
  11. `code/ace_automata/lstar.py:54` (`DFA.to_python_code` mematok `state = 0`, mengabaikan `self.initial_state != 0`, `test_34`).
- **D5 (4 bug):**
  12. `code/ace_mission/schema.py:4,88-89` (`deadline` menerima string non-ISO sembarang tanpa melempar `MissionSchemaError`, `test_02`).
  13. `code/ace_indo_nlp/discourse.py:177,205,219` (regex `(?:artinya|maknanya)?` menangkap kata `"artinya"` pada `"artinya apa?"` karena `"artinya"` absen dari `skip_words`, membuat cabang anafora `pending_word` tidak terjangkau, `test_15b`).
  14. `code/ace_indo_nlp/discourse.py:320` (slang terima kasih `"mksh"`, `"mksih"`, `"thx"` ternormalisasi ke `"terima"` sehingga gagal pada `is_thanks`, `test_17`).
  15. `code/ace_report/mobile_report.py:38` (selisih negatif kondisi C terhadap B dicetak `"+-15.0%"` alih-alih `"-15.0%"`, `test_28`).

## Batas Wilayah Terlarang yang Dijaga

- Tidak ada sentuhan ke `code/ace_operational/evo0007_run.py`, seluruh instrumen ukur/verdict (`ace_evaluator/*`, `abc_v3_scorer`, `round2_instrument`, `g*_instrument`), jalur tulis memory store (`memory_writeback.py`, `cognitive_memory.py`), korpus beku `handover/`, ataupun direktori stage Ian.
- Auditor D6 (`tools/coverage_and_flaky_audit.py`) mengecualikan `24` berkas terlarang tersebut secara statis sebelum pemindaian AST dan menolak eksekusinya via runner flaky.

## Usulan Tranche 2 untuk Garis D (Bernomor)

1. **D-T2-1 · Perbaikan 15 bug `code/` terverifikasi:** Ajukan PR perbaikan terisolasi di bawah supervisi engineer utama untuk ke-15 `@unittest.expectedFailure` di `D2`–`D5` sekaligus mencabut dekoratornya setelah lulus.
2. **D-T2-2 · Penutupan 40 modul yatim tes hasil D6:** Prioritaskan penambahan tes unit awal untuk `tools/ace_autonomous_daemon.py` (`7` simbol), `ace_research_generations/mechanisms.py` (`7` simbol), dan `ace_host_controller/isolated_worker.py` (`4` simbol).
3. **D-T2-3 · Integrasi gate flaky 3-run ke skrip prapush:** Sambungkan `tools/coverage_and_flaky_audit.py --runs 3` ke alur uji berkala non-verdict agar tes yang mengotori working tree atau bervarians tinggi tertolak otomatis sebelum review.

**SELESAI** — Seluruh butir Garis D (`D1`–`D6`, PR #359–#364) dan akuntansi penutup selesai; suite gabungan 423 tes lulus sesuai kontrak (`expected failures=15`, `0` unexpected failure/error).  
**TERSISA** — Antrean berikutnya pada **Garis E s.d. I**.  
**PENGHAMBAT** — Nihil.
