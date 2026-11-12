# ACE Ω — Addendum 11, 2026-11-12: OMEGA-10 Lab Lingkungan & Kurikulum

Bergantung pada OMEGA-06 (kernel bukti ✓) dan OMEGA-08 (arsip ✓).

## Yang dibangun (PR #113, draft, bertumpuk di atas #112)

Modul baru `code/ace_operational/curriculum_lab.py`:

- **Generator tugas dengan validitas yang teruji**: setiap tugas
  dibuktikan saat lahir — kode buggy WAJIB gagal verifier-nya, solusi
  referensi WAJIB lulus, dan label kesulitan WAJIB cocok dengan hitungan
  ulang dari set defek aktual. Tugas "gaming" yang sudah selesai sejak
  lahir ditolak, bukan masuk benchmark.
- **Verifier independen**: ekspektasi dibekukan dari referensi atas grid
  kasus; hanya 2 kasus publik, sisanya holdout yang tak pernah dilihat
  kandidat.
- **Taksonomi kesulitan L1–L4** dari jumlah/subtilitas defek + dressing
  adversarial (L4 menyelipkan instruksi palsu di spec — tema README
  beracun dari OMEGA-03).
- **Pemisahan train/holdout**: split deterministik dari bentuk ternormalisasi
  yang invarian-renaming (penamaan ulang konsisten ala de Bruijn —
  rename menyeluruh berbagi bentuk, tukar satu variabel tidak);
  klaster duplikat tidak bisa menyeberangi split, ditegakkan cek integritas.
- **Cek kebocoran** pada bundel publik: kode referensi, nama defek,
  jawaban holdout.
- **Audit benchmark** menandai inflasi: non-tugas (keadaan buggy lulus
  seluruh verifier), label salah, duplikat nyaris.
- **Scheduler kurikulum**: batch di level frontier, naik hanya bila
  mastery terbukti, campuran review + probe, holdout hanya di mode
  eval, probe transfer lintas keluarga. Dua keluarga tugas (pricing,
  shipping) agar transfer benar-benar teruji.

## Pengujian (daftar uji dokumen OMEGA-10)

16 test lulus: validitas generasi (dua keluarga), problem invalid,
gaming tugas trivial, label kesulitan digelembungkan, kebocoran solusi
referensi, jawaban holdout, determinisme split, duplikat hasil rename,
klaster menyeberangi split, audit inflasi (set sehat vs set dipalsukan),
frontier scheduler, holdout hanya di eval, transfer keluarga.
Sapuan paket penuh: **174 test OK (10 skip)**.

Tiga cacat ditemukan dan diperbaiki selama pengujian, dicatat jujur:
(1) normalisasi penghapus-identifier menyembunyikan defek tukar-variabel
— diganti penamaan konsisten de Bruijn; (2) metrik trivialitas awal
menyamakan defek sempit-yang-sulit dengan non-tugas — definisi trivial
diperbaiki menjadi "buggy lulus seluruh verifier"; (3) cek kebocoran
membandingkan teks yang sudah ter-escape JSON — diganti pemeriksaan
per-field.

## Pemisahan rekayasa vs ilmiah

Lab ini menghasilkan tugas yang terbukti valid dan kurikulum yang
jujur; ia bukan bukti bahwa kandidat mana pun belajar lebih baik.
**G1 tetap NOT_ASSESSED, OAIE tetap belum terbukti**.

## Sisa Fase 1

Tinggal OMEGA-11 (lab penalaran/representasi/algoritma; bergantung
03+06+09 — semua terpenuhi). Sesudahnya paket Fase 1 lengkap dan
ringkasan penutup Fase 1 akan disusun untuk pemilik.
