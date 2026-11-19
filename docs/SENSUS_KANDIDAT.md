# Sensus Kandidat Corpus ACE

> Dihasilkan secara baca-saja oleh `tools/candidate_census.py` (`ace.candidate-census.v1`).

| Berkas | Baris Valid | `task_kind` | Sebaran Kendala | Duplikat ID | Duplikat Instruksi | Verdict Kesiapan |
| --- | ---: | --- | --- | ---: | ---: | --- |
| `handover/EVO_0003_CORPUS_TAIL_V1.jsonl` | 16/16 | (missing):8, code:4, language:4 | 2:12, 3:2, 4:2 | 0 | 0 | **BELUM_LAYAK** |
| `handover/EVO_0005_CORPUS_V1.jsonl` | 16/16 | code:8, language:8 | 2:12, 3:3, 4:1 | 0 | 0 | **LAYAK** |
| `handover/EVO_0006_CORPUS_CANDIDATES_V1.jsonl` | 24/24 | code:12, language:12 | 1:1, 2:11, 3:9, 4:2, 5:1 | 0 | 0 | **LAYAK** |
| `handover/EVO0007_KANDIDAT_PABRIK.jsonl` | 24/24 | code:12, language:12 | 0:10, 1:9, 2:2, 3:1, 4:1, 5:1 | 0 | 0 | **BELUM_LAYAK** |
| `handover/KANDIDAT_PABRIK_0007_BEKU.jsonl` | 24/24 | code:12, language:12 | 0:6, 1:5, 2:6, 3:3, 4:4 | 0 | 0 | **BELUM_LAYAK** |

## `handover/EVO_0003_CORPUS_TAIL_V1.jsonl`

- **Verdict Kesiapan:** `BELUM_LAYAK`
- **Statistik Kendala:** min=2, median=2.0, mean=2.375, max=4, nol-kendala=0
- **Alasan Verdict:**
  - Terdapat 8 pelanggaran skema wajib (contoh: baris 1 missing_task_kind).
  - Terdapat 16 ketidaksesuaian skema corpus episode baku (contoh: unexpected_kind).

## `handover/EVO_0005_CORPUS_V1.jsonl`

- **Verdict Kesiapan:** `LAYAK`
- **Statistik Kendala:** min=2, median=2.0, mean=2.312, max=4, nol-kendala=0
- **Alasan Verdict:**
  - Seluruh pemeriksaan skema, keunikan id/instruksi, dan keberadaan kendala terpenuhi.
- **Catatan Tambahan:**
  - Terdapat 3 benturan awalan 60 karakter antar kandidat meski instruksi lengkap berbeda.

## `handover/EVO_0006_CORPUS_CANDIDATES_V1.jsonl`

- **Verdict Kesiapan:** `LAYAK`
- **Statistik Kendala:** min=1, median=2.5, mean=2.625, max=5, nol-kendala=0
- **Alasan Verdict:**
  - Seluruh pemeriksaan skema, keunikan id/instruksi, dan keberadaan kendala terpenuhi.

## `handover/EVO0007_KANDIDAT_PABRIK.jsonl`

- **Verdict Kesiapan:** `BELUM_LAYAK`
- **Statistik Kendala:** min=0, median=1.0, mean=1.042, max=5, nol-kendala=10
- **Alasan Verdict:**
  - Terdapat 48 ketidaksesuaian skema corpus episode baku (contoh: missing_kind).
  - Terdapat 10 kandidat tanpa kendala terdeteksi (risiko soal hampa/tidak diskriminatif).

## `handover/KANDIDAT_PABRIK_0007_BEKU.jsonl`

- **Verdict Kesiapan:** `BELUM_LAYAK`
- **Statistik Kendala:** min=0, median=2.0, mean=1.75, max=4, nol-kendala=6
- **Alasan Verdict:**
  - Terdapat 6 kandidat tanpa kendala terdeteksi (risiko soal hampa/tidak diskriminatif).
