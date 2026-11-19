# Standar Uji Fuzz Parser ACE

Dokumen ini menetapkan standar pengerasan fuzz deterministik untuk seluruh parser dan pembaca berkas non-verdict di `tools/` dan modul pembantu aman di `code/`.

## Kriteria Penerimaan Wajib

Setiap PR parser atau pengubah format masukan baru di `tools/` wajib lulus uji matrix fuzz ringan:

- **Seed standar:** `20261117`, `20261118`, `20261119` (3 seed berbeda)
- **Iterasi minimum:** `300` iterasi per target per seed (`900` eksekusi ter-seed per target)
- **Ambang crash tak tertangani:** `0` (`total_crashes == 0`, status `"passed": true`)

Exception kontrak yang terdokumentasi eksplisit (mis. `ValueError`, `*InputError`, `JSONDecodeError`, `OSError`) diterima sebagai penolakan masukan korup yang terkendali; exception tak terduga seperti `TypeError`, `KeyError`, `AttributeError`, atau `IndexError` dihitung sebagai crash yang wajib diperbaiki pada parser pemilik.

## Target Aktif & Opsional (33 Target pada Garis D1)

1. **Target `tools/` inti (selalu aktif — 3 target):**
   - `ace_mobile_dashboard.parse_logs_to_stories`
   - `ace_ai_diagnostic.audit_consultations`
   - `dashboard_state_build.rp_to_int`
2. **Target `code/` non-verdict aman (selalu aktif — 6 target):**
   - `code.ace_visual_bridge.cli.process`
   - `code.ace_host_exchange.contracts.verify`
   - `code.ace_autonomy.policy.BudgetCeiling`
   - `code.ace_code_agent.read_failure_history`
   - `code.ace_code_agent.verify_receipt`
   - `code.ace_indo_nlp.syllabify_and_morphology`
3. **Target `tools/` opsional (aktif bila modul hadir di branch kerja — 24 target):**
   - `corpus_lint.lint_file`, `screen_census.compute_census`, `corpus_registry`, `stage_verify.verify_stage`, `bench_table.summarize_bench`, `pack_evidence.verify_evidence`
   - `pattern_distill.distill_evidence`, `four_arm_report.analyze_four_arms`, `corpus_tag.tag_corpus`
   - `cover_check.check_cover`, `royalty_track.summarize_royalties`, `kbm_schedule.build_schedule`
   - `kbm_split.split_manuscript`, `kbm_pack_check.check_package`, `kbm_pipeline.run_pipeline`
   - `curriculum_gen.generate_curricula`, `portability_pack.verify_bundle`, `instance_kit.validate_isolation`
   - `ruleset_readiness.check_repo_readiness`, `opportunity_register.generate_proposals`, `repo_status_dashboard.collect_and_render`
   - `self_send_audit_view.inspect_audit_files`, `repo_index.build_and_render`, `daily_digest.build_daily_digest`

## Perintah Standar

```bash
python3 tools/fuzz_parsers.py --seeds 20261117,20261118,20261119 --iterations 300
python3 -m unittest -v tools.test_fuzz_parsers
```

## Kebijakan Wilayah Terlarang

- Harness fuzz **tidak boleh** diarahkan ke instrumen verdict, penilai aktif (`ace_evaluator`, `abc_v3_scorer`, `round2_instrument`, `g*_instrument`, `evo0007_run`), maupun jalur tulis store (`memory_writeback`, jalur tulis `cognitive_memory`).
- Jika pengujian fuzz menemukan bug pada modul `code/` yang berada di luar cakupan tugas aktif, catat temuan secara eksplisit melalui laporan atau `@unittest.expectedFailure` tanpa memodifikasi berkas target secara diam-diam.
