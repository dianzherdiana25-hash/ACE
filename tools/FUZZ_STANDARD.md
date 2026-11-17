# Standar Uji Fuzz Parser ACE

Dokumen ini menetapkan standar pengerasan fuzz deterministik untuk seluruh parser dan pembaca berkas non-verdict di `tools/` dan modul pembantu aman di `code/`.

## Kriteria Penerimaan Wajib

Setiap PR parser atau pengubah format masukan baru di `tools/` wajib lulus uji matrix fuzz ringan:

- **Seed standar:** `20261117`, `20261118`, `20261119` (3 seed berbeda)
- **Iterasi minimum:** `300` iterasi per target per seed (`900` eksekusi ter-seed per target)
- **Ambang crash tak tertangani:** `0` (`total_crashes == 0`, status `"passed": true`)

Exception kontrak yang terdokumentasi eksplisit (mis. `ValueError`, `*InputError`, `JSONDecodeError`, `OSError`) diterima sebagai penolakan masukan korup yang terkendali; exception tak terduga seperti `TypeError`, `KeyError`, `AttributeError`, atau `IndexError` dihitung sebagai crash yang wajib diperbaiki pada parser pemilik.

## Target Aktif & Opsional

1. **Target `tools/` inti (selalu aktif):**
   - `ace_mobile_dashboard.parse_logs_to_stories`
   - `ace_ai_diagnostic.audit_consultations`
   - `dashboard_state_build.rp_to_int`
2. **Target `code/` non-verdict aman (selalu aktif di `main`):**
   - `ace_visual_bridge.cli.process`
   - `ace_host_exchange.contracts.verify_request_and_candidate`
   - `ace_autonomy.policy.BudgetCeiling.from_dict`
   - `ace_code_agent.codebase_reader.read_failure_history`
3. **Target `tools/` opsional (aktif bila modul hadir di branch kerja):**
   - `corpus_lint.lint_file`, `screen_census.compute_census`, `corpus_registry`, `stage_verify.verify_stage`, `bench_table.summarize_bench`, `pack_evidence.verify_evidence`
   - `pattern_distill.distill_patterns`, `four_arm_report.build_report`, `corpus_tag.tag_corpus`
   - `cover_check.decode_image_dimensions`, `royalty_track.parse_decimal_amount`, `kbm_schedule.build_schedule`
   - `kbm_split.split_manuscript`, `kbm_pack_check.check_package`

## Perintah Standar

```bash
python3 tools/fuzz_parsers.py --seeds 20261117,20261118,20261119 --iterations 300
python3 -m unittest -v tools.test_fuzz_parsers
```

## Kebijakan Wilayah Terlarang

- Harness fuzz **tidak boleh** diarahkan ke instrumen verdict, penilai aktif (`ace_evaluator`, `abc_v3_scorer`, `round2_instrument`, `g*_instrument`), maupun jalur tulis store (`memory_writeback`).
- Jika pengujian fuzz menemukan bug pada modul yang berada di luar cakupan tugas aktif, catat temuan secara eksplisit melalui laporan atau `@unittest.expectedFailure` tanpa memodifikasi berkas target secara diam-diam.
