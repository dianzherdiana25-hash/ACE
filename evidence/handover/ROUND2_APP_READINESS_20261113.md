# DAFTAR PERIKSA KESIAPAN FASE APLIKASI GERBANG ROUND-2

Ian, 2026-11-13 (pekerjaan meja, paralel run v3).
Peluncuran TIDAK dilakukan — fase aplikasi tetap menunggu
finalisasi v3 sesuai antrean penentu. Semua butir
diverifikasi langsung di VM hari ini.

## Hasil per butir

1. **Driver hadir dan utuh — LULUS.**
   `round2_gate_run.py` (fase guard1/guard2/guard3/app/
   finalize via argv) + `round2_submit.py` lolos
   py_compile. JSON guard tercermin di `round2-gate-run/`
   dan ketiganya `pass: true` (guard1 exact_match,
   guard2 coverage 1.0, guard3 10/10 checks).
2. **Lift manifest cocok dengan konstruksinya — LULUS.**
   `compute_lift_manifest()` (statement_ops.py, konstruksi
   §2: tiga berkas + MANIFEST_PARAMS + digest freeze
   substrat, tanpa pemisah) = `f36218cd…` persis.
   Ekstensi enam komponen teks terkunci (+ byte
   statement_ops.py) = `47a5afc4…` persis. sha256
   statement_ops.py = `95053147…` persis. Konstanta modul
   cocok dengan catatan program (digest freeze B-3
   terverifikasi dari dokumen lineage B-3).
3. **Teks praregistrasi terkunci ada di remote — LULUS.**
   PR #161 head `4fb517c`; `git show` pada tip branch =
   sha256 `89dbb6f1…`, cocok dengan salinan terkunci
   lokal (wt-r2lift).
4. **Band dan aturan penilaian sesuai teks terkunci —
   LULUS.** Driver app(): band `range(72000, 72100)`,
   pool 10 pertama, evaluasi 30 berikutnya. Fixture
   submission: target_band [72000, 72099], pool 10,
   evaluation 30, score_call_cap 4000, wall 60 dtk.
   Aturan lulus: `round2_index` gte 0, protokol kernel
   `743a2e9c…`. sha256 round2_instrument.py =
   `e08c1586…` = evaluator_digest di record submission.
5. **Jalur finalisasi dosier — CACAT DITEMUKAN,
   DIPERBAIKI, GLADI HIJAU.**
   - Pra-periksa kustodi: sha256 artefak finalize driver
     = `7cf3b62a…` = candidate_digest_kernel di record
     submission — byte-identik, pagar kustodi aman.
   - Gladi karantina (rehearsal-r2-20261113/, submission
     karantina mereproduksi record resmi PERSIS: protokol
     743a2e9c…, candidate 7cf3b62a…, baseline 2652adaf…,
     evaluator e08c1586…, fixture 7b3af96c…) dengan
     app.json SINTETIS berlabel: lari pertama CRASH —
     `ModuleNotFoundError: ace_operational.round2_instrument`.
     Akar masalah: driver mengimpor paket ace_operational
     dari wt-r2lift di level modul; instrumen hanya ada di
     wt-r2gate, dan paket yang sudah ter-cache membuat
     impor di finalize() buta ke sana. Finalisasi resmi
     akan crash persis sama di garis finis.
   - Perbaikan (round2_gate_run.py, hanya finalize()):
     instrumen dimuat via jalur berkas eksplisit
     (importlib) — instrumen mandiri (hanya json/pathlib);
     impor experiment_kernel tidak berubah (lineage
     wt-r2lift, sama dengan submission).
   - Gladi ulang HIJAU ujung-ke-ujung: record kernel
     sukses, audit CLEAN, dosier tersusun, assess_round2
     mengembalikan LIFT_DEMONSTRATED atas data sintetis
     (putusan gladi, BUKAN hasil gerbang).
   - Keadaan resmi terverifikasi tak tersentuh: kernel
     round2-gate-kernel results.jsonl tetap 0 byte; tidak
     ada evidence/round2_gate_run.json, app.json, atau
     dossier resmi.

## Catatan pra-peluncuran (bukan kegagalan butir)

- Fase app berat CPU; tempat menjalankannya (VM sesudah
  v3, atau sandbox via shell nyata) diputuskan saat
  gilirannya — kanal MCP sandbox tidak bisa (dinding
  30 CPU-detik).
- Bila app dijalankan BUKAN di VM, finalize membaca
  guard1/2/3.json + app.json dari `round2-gate-run/` di
  VM — file-file itu harus tercermin lebih dulu (guard
  sudah tercermin; app.json menyusul dari tempat app
  berjalan).
