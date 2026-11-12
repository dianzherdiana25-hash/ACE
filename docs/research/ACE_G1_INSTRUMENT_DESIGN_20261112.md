# Instrumen Pengukuran G1 — Desain dan Penerapan Pertama (Tahap H, 2026-11-12)

## Definisi (PRD v0.1)

**G1 — Operasional:** menjalankan satu eksperimen digital dari
tugas sampai laporan dengan catatan lengkap dan kemampuan
melanjutkan setelah terputus.

G1 lama berstatus NOT_ASSESSED dengan alasan tunggal yang tercatat
di agenda direktur (siklus #3, proposal peringkat 1): belum ada
instrumen pengukuran yang disepakati. Dokumen ini adalah instrumen
itu; implementasinya `ace_operational/g1_instrument.py`.

## Instrumen

Penilaian dilakukan terhadap **dossier berkas bukti tersegel**
(bukan klaim), mekanis dan fail-closed — item yang hilang atau tak
terbaca adalah kegagalan bernama, bukan lolos bawaan:

- **C1 — busur tugas→laporan:** laporan eksperimen memuat hash
  pra-registrasi dan audit kernel.
- **C2 — catatan lengkap:** audit CLEAN, rantai hash tanpa putus,
  ≥1 hasil terverifikasi, tanpa masalah audit.
- **C3 — lanjut setelah terputus:** probe pada mesin store yang
  sama menunjukkan keadaan dibuat di satu proses OS, dimajukan di
  proses kedua, diverifikasi di proses ketiga (atau rekaman
  multi-proses setara), dengan verdict PASS dan state checkpoint
  yang nyata.

## Penerapan pertama (bukti yang sudah ada, tanpa run baru)

- Eksperimen unggulan: **pilot-abc-v1** — protocol hash
  `bce010ab273183f3…`, audit CLEAN, 4 hasil terverifikasi,
  4 entri ledger terverifikasi → C1 PASS, C2 PASS.
- Probe resume: **OMEGA-04** — tiga proses OS terpisah
  (create → restart+advance → restart+verify), verdict PASS →
  C3 PASS.
- **Hasil instrumen: G1 DEMONSTRATED** (berkas penilaian:
  `evidence/g1_assessment.json` di harness operator).

## Kualifikasi dan eksperimen penutup

C3 membuktikan kemampuan resume *substrat* tempat eksperimen
unggulan berjalan — bukan interupsi atas run unggulan itu sendiri.
Karena itu status yang dicatat direktur adalah **G1 MEASURED —
DEMONSTRATED dengan kualifikasi tersebut**, bukan PASS tanpa
syarat. Eksperimen penutup yang mengangkat kualifikasinya sudah
bernama: **latihan resume** (resume drill) — sebuah run unggulan
yang sengaja diinterupsi di tengah jalan (proses dibunuh), lalu
dilanjutkan sampai laporan dari state tersimpan, dengan rantai
bukti yang tidak putus melintasi interupsi. Desainnya sejajar
dengan latihan pemecatan otak Tahap G dan masuk antrean program.
