# Pemeliharaan Indeks Dokumen — 2026-11-19 (E8)

## Kenapa
Enam tes `test_03_live_repo_*` gagal di `main` karena dokumen turunan (hasil generator deterministik) tertinggal dari isi repo. Dokumen ini mencatat penyegaran dan hasil audit tautan. Tidak ada berkas yang dibuat ulang atau dihapus untuk menutup tautan.

## Dokumen yang disegarkan (dihasilkan ulang oleh generator masing-masing)
| Dokumen | Generator |
| --- | --- |
| `docs/HANDOVER_INDEX.md` | `tools/handover_index.py` |
| `docs/REPO_CARTOGRAPHY.md` | `tools/repo_cartography.py` |
| `docs/PROGRAM_GLOSSARY.md` | `tools/program_glossary.py` |
| `docs/BUILDER_ONBOARDING_PACK.md` | `tools/builder_onboarding_pack.py` |
| `docs/research/ACE_PLATFORM_REQUIREMENTS_SUMMARY.md` | `tools/platform_requirements_summary.py` |
| `docs/research/ACE_HANDOVER_DECISIONS_EXTRACTED.md` | `tools/handover_decision_extractor.py` |

Cara memeriksa kesegaran: jalankan tiap generator dengan `--root . --check <berkas>`; exit 0 berarti mutakhir.

## Audit tautan markdown relatif (`docs/` dan `handover/`)
Ditemukan 7 tautan relatif yang targetnya tidak ada. Semuanya DIBIARKAN apa adanya (keputusan minimal; perbaikan tautan di dokumen riset dicatat untuk engineer utama).

| Dokumen sumber | Target tautan | Catatan |
| --- | --- | --- |
| `docs/research/ACE_A1_TRANCHE2_CATALOG_COMPAT.md` | `ACE_GARIS_A_AKUNTANSI.md` | Berkas tidak ada. Berkas bernama mirip: `docs/research/ACE_CODEX_GARIS_A_AKUNTANSI.md`. |
| `docs/research/ACE_A2_TRANCHE2_CLOSURE.md` | `ACE_GARIS_A_AKUNTANSI.md` | idem |
| `docs/research/ACE_A3_TRANCHE2_PROSE_SHAPES.md` | `ACE_GARIS_A_AKUNTANSI.md` | idem |
| `docs/research/ACE_A3_TRANCHE2_PROSE_SHAPES.md` | `../code/ace_operational/store.py` (2 kali) | Kedalaman jalur salah; yang benar `../../code/ace_operational/store.py`. |
| `docs/research/ACE_A4_TRANCHE2_BUNDLE_AND_SCOPE.md` | `ACE_GARIS_A_AKUNTANSI.md` | idem |
| `docs/research/ACE_A5_TRANCHE2_PREREVIEW.md` | `ACE_GARIS_A_AKUNTANSI.md` | idem |
