# Akuntansi Penutup Garis F — Penyambungan & Integrasi Aman (Gravity)

> **Status:** Draft PR penutup Garis F (`F1–F3`). Seluruh pekerjaan dilakukan pada branch `gravity/*`, berbasiskan `origin/main` (`478848d`), tanpa menyentuh `evo0007_run.py`, instrumen judge/scorer, jalur tulis `memory_writeback`/`cognitive_memory`, maupun direktori staging aktif EVO 0007.

## 1. Daftar Serahan & Status PR

| Butir | Branch | Commit | Draft PR | Ringkasan Serahan |
| --- | --- | --- | --- | --- |
| **F1** | `gravity/f1-wiring-audit` | `2c0fef9` | [#371](https://github.com/dianzherdiana25-hash/ACE/pull/371) | `tools/wiring_audit.py` + `tools/test_wiring_audit.py` + `docs/research/ACE_WIRING_AUDIT.md` (auditor AST statis 363 modul non-tes tanpa eksekusi impor). |
| **F2** | `gravity/f2-ops-digest-pipeline-wiring` | `480be03` | [#372](https://github.com/dianzherdiana25-hash/ACE/pull/372) | Wiring 8 perkakas aman (`storage_debt`, `repo_status_dashboard`, `repo_index`, `stage_verify`, `royalty_track`, `kbm_schedule`, `ruleset_readiness` offline snapshot, `self_send_audit_view`) ke `tools/daily_digest.py` dan `tools/repo_status_dashboard.py` + `tools/test_f2_ops_wiring.py`. |
| **F3** | `gravity/f3-kbm-migration-pack-wiring` | `4ca8e87` | [#373](https://github.com/dianzherdiana25-hash/ACE/pull/373) | Wiring `cover_check`, `pack_evidence`, `portability_pack` ke `tools/kbm_pipeline.py` serta gerbang isolasi `instance_kit` ke `tools/portability_pack.py` + `tools/test_f3_kbm_portability_wiring.py`. |

## 2. Dampak Keterhubungan (`ace.wiring-audit.v1`)

Pengukuran di worktree overlay gabungan `F1..F3` (`/tmp/garis_f_combo` sebelum dibersihkan):

- **Baseline `main` (`F1`)**: `total_modules=363`, `wired=234`, `cli_standalone=65`, `orphan=42`, `menunggu_engineer_utama=22`, `tools_unwired_safe=46`.
- **Setelah overlay `F1..F3`**: `total_modules=363`, `wired=246` (**+12 modul tersambung**), `cli_standalone=53` (**-12**), `orphan=42`, `menunggu_engineer_utama=22` (utuh tidak tersentuh), `tools_unwired_safe=34` (**-12**).
- 12 perkakas yang berpindah dari `CLI_STANDALONE` menjadi `WIRED`:
  1. `tools/cover_check.py`
  2. `tools/instance_kit.py`
  3. `tools/kbm_schedule.py`
  4. `tools/pack_evidence.py`
  5. `tools/portability_pack.py`
  6. `tools/repo_index.py`
  7. `tools/repo_status_dashboard.py`
  8. `tools/royalty_track.py`
  9. `tools/ruleset_readiness.py`
  10. `tools/self_send_audit_view.py`
  11. `tools/stage_verify.py`
  12. `tools/storage_debt.py`

## 3. Hasil Uji Gabungan Worktree Overlay

Perintah dijalankan langsung di `/tmp/garis_f_combo` (`Cwd="/tmp/garis_f_combo"`, lalu worktree sementara langsung dihapus):

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/garis_f_combo/code:/tmp/garis_f_combo \
  python3 -m unittest tools.test_wiring_audit tools.test_f2_ops_wiring \
  tools.test_f3_kbm_portability_wiring tools.test_daily_digest \
  tools.test_repo_status_dashboard tools.test_storage_debt tools.test_stage_verify \
  tools.test_royalty_track tools.test_kbm_schedule tools.test_ruleset_readiness \
  tools.test_repo_index tools.test_self_send_audit_view tools.test_kbm_pipeline \
  tools.test_portability_pack tools.test_cover_check tools.test_pack_evidence \
  tools.test_instance_kit tools.test_kbm_split tools.test_kbm_pack_check --buffer
----------------------------------------------------------------------
Ran 59 tests in 1.987s

OK
```

- `PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_sources.py`: `PASS: 25 imported files match their recorded Git blob IDs (offline)`.

## 4. Daftar Modul `"MENUNGGU_ENGINEER_UTAMA"` (22 Berkas — Tidak Disentuh)

Sesuai kontrak wilayah terlarang, seluruh modul di bawah ini tetap diklasifikasikan `MENUNGGU_ENGINEER_UTAMA` agar disambungkan hanya oleh Engineer Utama (Ian):

1. Wilayah instrumen / evaluator / memory terlarang (14 berkas):
   - `code/ace_evaluator/cheat_detection.py`
   - `code/ace_evaluator/sealed_generator.py`
   - `code/ace_evaluator/task_families.py`
   - `code/ace_operational/abc_v3_scorer.py`
   - `code/ace_operational/cognitive_memory.py`
   - `code/ace_operational/g1_instrument.py`
   - `code/ace_operational/g3_instrument.py`
   - `code/ace_operational/g4_instrument.py`
   - `code/ace_operational/g5_instrument.py`
   - `code/ace_operational/memory_writeback.py`
   - `code/ace_operational/round2_instrument.py`
   - `tools/abc_v3_run.py`
   - `tools/memory_writeback.py`
   - `tools/round2_gate_run.py`
2. Perkakas aman yang titik panggil targetnya berada di jalur EVO 0007 / evaluator (8 berkas):
   - `tools/corpus_lint.py`
   - `tools/corpus_registry.py`
   - `tools/corpus_tag.py`
   - `tools/curriculum_gen.py`
   - `tools/four_arm_report.py`
   - `tools/pattern_distill.py`
   - `tools/screen_census.py`
   - `tools/verify_f13_f14.py`

## 5. Kepatuhan Wilayah Terlarang

- Tidak ada perubahan pada `code/ace_operational/evo0007_run.py`, `code/ace_evaluator/*`, `*_instrument.py`, `abc_v3_scorer.py`, `memory_writeback.py`, `cognitive_memory.py`, maupun `handover/*`.
- Tidak ada pembacaan/penulisan ke direktori staging aktif EVO 0007 maupun panggilan jaringan HTTP langsung (`0` koneksi jaringan).

## 6. Usulan Tranche 2 Garis F (Bernomor)

1. **F4 — Wiring `tools/bench_table.py`, `tools/evo_scaffold.py`, dan `tools/fuzz_parsers.py` ke satu runner QA pra-review:** mengemas keluaran tabel benchmark dan hasil fuzz non-instrumen ke bundel laporan statis satu perintah.
2. **F5 — Audit & penyambungan modul riset `code/` `ORPHAN` (sebagian dari 34 modul) melalui adapter CLI eksperimen non-verdict:** mis. menyambungkan `code/ace_mission/proposers.py`, `code/ace_operational/catalog_artifact.py`, `code/ace_operational/citation_validator.py`, dan `code/ace_report/mobile_report.py` ke pipeline laporan offline tanpa menyentuh evaluator aktif.
3. **F6 — Pengesahan penyambungan `corpus_*` / `pattern_distill` oleh Engineer Utama:** menunggu Ian memutuskan titik kait di runner evaluasi/evolusi aktif setelah masa inkubasi EVO 0007 selesai.
