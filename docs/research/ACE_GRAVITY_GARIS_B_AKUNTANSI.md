# Akuntansi Garis B · Korpus, Kandidat, dan Evaluasi

Serahan Garis B disusun oleh Antigravity di atas `origin/main` (`478848d`) sebagai PR draf terpisah per butir untuk penyaringan Ian. Pekerjaan utang akuntansi ronde 2 sebelumnya dikirimkan terpisah di [PR #340](https://github.com/dianzherdiana25-hash/ACE/pull/340) di atas `codex/round2-accounting`.

| Butir | Status | PR & Commit | Modul & Ringkasan |
| --- | --- | --- | --- |
| B1 · Pabrik kandidat v2 | Selesai | [PR #341](https://github.com/dianzherdiana25-hash/ACE/pull/341) (`gravity/b1-candidate-factory-v2`, `0d53c0c`) | `tools/candidate_factory_v2.py`: prefix baru (`grav_lang_id_`, `grav_lang_ml_`, `grav_code_v2_`), kendala bertingkat 2–6 lapis, gelombang Indonesia baru + multibahasa 5 bahasa (`>= 4` bahasa wajib), kode komposit (algoritma + kompleksitas + larangan alat + format persis), gerbang fail-closed, dan sensus kesiapan per gelombang. 7 tes baru lulus (`24` total dgn `corpus_lint`). |
| B2 · Analisis kejenuhan judge | Selesai | [PR #342](https://github.com/dianzherdiana25-hash/ACE/pull/342) (`gravity/b2-saturation-scan`, `6acb600`) | `tools/saturation_scan.py`: memindai JSONL/JSON/`.json.gz` hasil saring/ukur → pasangan tugas jenuh (`always_pass`, `always_fail`, `split`), pita skor berhenti membedakan (`CEILING_SATURATED`, `FLOOR_SATURATED`, `ZERO_SPREAD_PILEUP`, `LOW_SEPARATION`), dan rekomendasi per kelompok (`RETIRE_EASY`, `HARDEN`, `RECALIBRATE_OR_RETIRE_FAILING`, `KEEP_CALIBRATED`). 4 tes lulus (termasuk arsip baca-saja `evo0006`). |
| B3 · Tata kelola korpus | Selesai | [PR #343](https://github.com/dianzherdiana25-hash/ACE/pull/343) (`gravity/b3-corpus-governance`, `4abb70e`) | 3 perkakas baru: `tools/frozen_corpus_registry.py` (+ `--check` drift `ADDED`/`MODIFIED`/`REMOVED`), `tools/corpus_freeze_packer.py` (kandidat terpilih → korpus beku + entri registry + catatan pembekuan), dan `tools/corpus_lint_v2.py` (skema + kendala mekanis + near-duplicate Jaccard lintas berkas). 4 tes baru lulus (`25` total dgn `test_corpus_registry` & `test_corpus_lint`). |
| B4 · Bench evaluasi berdiri | Selesai | [PR #344](https://github.com/dianzherdiana25-hash/ACE/pull/344) (`gravity/b4-standalone-eval-bench`, `387e11f`) | `tools/eval_bench.py`: (a) QA introspektif `handover/` dengan pointer sumber wajib, (b) konsistensi lintas organ offline + laporan ketidaksepakatan, (c) regresi format 6 perkakas program di `main`. 4 tes lulus. |

## Hasil Suite Gabungan Garis B

Pada overlay sementara seluruh modul B1–B4 di atas `main` (`478848d`):

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tools.test_candidate_factory_v2 tools.test_saturation_scan \
  tools.test_corpus_governance tools.test_eval_bench \
  tools.test_corpus_lint tools.test_corpus_registry
python3 tools/verify_sources.py
```

- **Suite gabungan B1–B4 + regresi lint/registry**: **40 tests — OK** (0.864s, tanpa error/skip).
- **`tools/verify_sources.py`**: `PASS: 25 imported files match their recorded Git blob IDs (offline)`.

## Usulan Tranche 2 untuk Garis B (bernomor)

1. **B-T1 · Sinkronisasi penanda bab/kode eksekusi nyata pada kandidat komposit**: tambahkan runner sandbox uji unit offline atas contoh solusi referensi kandidat `code_composite` agar kepatuhan signature, larangan impor AST, dan perilaku kasus tepi terbukti tereksekusi selain pemeriksaan teks instruksi.
2. **B-T2 · Audit overlap semantik & kesamaan lintas-bahasa antara kandidat v2 (`id`/`en`/`es`/`de`/`fr`) dan seluruh arsip historis (`evidence/evo0003`–`0006`)** guna memverifikasi tidak ada kebocoran pola kalimat.
3. **B-T3 · Kalibrasi pita tengah `45–75` berbasis keluaran model 7B/API** setelah diizinkan Ian berjalan di atas paket kandidat v2, memetakan profil kesulitan per lapis kendala (2..6) melalui `saturation_scan.py`.
4. **B-T4 · Ekspansi paket QA `handover/` berversi dan matriks regresi format seluruh perkakas `tools/` tambahan** setelah PR Garis A/B/C mulai diratifikasi ke `main`.

**SELESAI** — utang akuntansi ronde 2 (#340) serta B1–B4 (#341–#344) dan penutup Garis B ini selesai tanpa menyentuh instrumen ukur, jalur tulis memory store, korpus beku `handover/`, maupun direktori stage EVO 0007.  
**TERSISA** — penyaringan PR oleh Ian; kelanjutan langsung antrean ke **Garis C (Memori & Lapis 3)**.  
**PENGHAMBAT** — nihil.
