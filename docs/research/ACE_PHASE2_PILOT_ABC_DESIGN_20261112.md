# ACE Fase 2 — Desain Pilot A/B/C Kustodi Penuh (2026-11-12)

Item agenda Direktur Riset lokal #1 (Addendum 13), dirancang dari
definisi PRD ACE v0.1 §Kelompok pembanding dan §Kontrol adil. Dokumen
ini adalah DESAIN untuk dipra-registrasi di kernel OMEGA-06 sebelum
pilot dijalankan; pilotnya sendiri adalah tahap berikutnya. Selama
pilot belum berjalan dan auditnya belum CLEAN, **G1 tetap
NOT_ASSESSED**.

## Lengan (sesuai PRD)

Substrat bersama: tugas OMEGA-10 (keluarga pricing + shipping), solver
perbaikan kode, anggaran evaluasi identik, verifier OMEGA-10 yang sama.

- **A — Fixed.** Solver grammar versi beku, satu lintasan per tugas,
  tanpa pembelajaran antarsiklus: konfigurasi tidak berubah oleh hasil.
- **B — Adaptive.** Solver boleh mengubah strategi antarsiklus
  berdasarkan memori hasil (OMEGA-07): pilihan/urutan operator dan
  parameter pencarian menyesuaikan per keluarga dari pengalaman —
  tetapi tidak menciptakan operator/kandidat penerus baru.
- **C — Evolutionary.** B ditambah mutasi/rekombinasi OMEGA-09 atas
  genotipe solver (set operator, parameter), dengan silsilah lengkap
  di arsip OMEGA-08; penerus mewarisi kemampuan pendahulu dan beberapa
  cabang dipertahankan.

Di dalam pilot, arah dipilih oleh mekanisme ACE sendiri (aturan
adaptasi B, mutasi+seleksi C). Direktur lokal dan direktur program
berada DI LUAR pilot; mereka hanya mengusulkan agenda antartahap.

## Kontrol adil (PRD §Kontrol adil, diterjemahkan ke mesin Ω)

- Anggaran setara per lengan: batas evaluasi fitness, jumlah percobaan
  per tugas, dan versi verifier yang sama; pelanggaran anggaran =
  ABSTAIN (aturan kernel OMEGA-06).
- Tugas held-out (split OMEGA-10) TIDAK PERNAH dipakai memilih
  kandidat; seleksi/adaptasi hanya memakai split train. Held-out hanya
  disentuh evaluator akhir.
- Kustodi split penuh via kernel: pra-registrasi (hash protokol +
  aturan lulus + baseline) sebelum hasil ada; digest kandidat dan
  evaluator terpisah; semua kegagalan disimpan, bukan hanya run
  terbaik; ledger hasil append-only dapat diaudit ulang.
- Seed: minimal 3 pengulangan per kondisi (target PRD); bila kuota/
  waktu tidak mencukupi, keluaran wajib INCONCLUSIVE.

## Ukuran dan aturan keputusan

- **Utama**: tingkat penyelesaian held-out per keluarga.
- **Pendukung**: transfer lintas keluarga (selisih kinerja keluarga
  bukan-asal), biaya per tugas berhasil (evaluasi terpakai), regresi
  antarsiklus, keberhasilan pewarisan (C).
- **Ambang**: target desain PRD ≥30 tugas held-out per keluarga —
  generator saat ini menghasilkan ±20% held-out, jadi perlu ±150 tugas
  tergenerasi per keluarga (seed diperluas; generasi murah, evaluasi
  solver detik-menit). Selisih ≥10 poin persentase = sinyal eksplorasi
  saja; klaim peningkatan kuat perlu perbandingan berpasangan +
  estimasi ketidakpastian.
- **Pemetaan ke G1**: pilot mendukung penilaian G1 hanya bila audit
  kernel CLEAN dan aturan lulus yang dipra-registrasi terpenuhi;
  hasil C unggul hanya di keluarga asal dicatat sebagai spesialisasi
  (bahasa PRD), bukan generalisasi.

## Confound yang dipra-registrasi (dari pengukuran shipping)

Grammar substrat punya celah operator yang terbukti: tidak ada
operator pemulih pengali (0/10 bahkan di bawah sinyal oracle). Pilot
yang berjalan di atas substrat ini akan mengukur celah itu, bukan
kondisi A/B/C. Keputusan desain: **bekukan solver substrat v2 — dengan
operator pemulih pengali ditambahkan — untuk SEMUA lengan sebelum
pra-registrasi**, dan stratifikasi hasil per set defek tetap
dilaporkan. Penambahan operator dicatat sebagai perubahan substrat,
bukan sebagai hasil pilot.

## Peran LLM pada pilot v1

Tidak ada. PRD sendiri membuka pertanyaan apakah percobaan pertama
perlu LLM; mekanisme seleksi/adaptasi/evolusi dapat diuji murni
algoritmik dengan biaya Rp0 dan determinisme penuh. Varian dengan
direktur lokal sebagai pengusul mutasi adalah tahap lanjutan, dan
hasilnya tidak boleh dicampur dengan pilot v1.

## Risiko dan mitigasi

- Restart VM membunuh proses: setiap siklus pilot checkpoint ke
  ledger kernel di disk (pola OMEGA-04); run dapat dilanjutkan.
- Hanya 2 keluarga tugas: cukup untuk syarat minimal G3 (≥2), tetapi
  sinyal transfer akan tipis; keluarga ketiga (mis. MiniGrid per PRD)
  adalah perluasan masa depan, di luar pilot v1.
- Saturasi generator: parameter keluarga terbatas; perluasan seed
  menghasilkan variasi parameter + kombinasi defek, bukan keluarga
  baru — dicatat sebagai batas validitas eksternal pilot.
