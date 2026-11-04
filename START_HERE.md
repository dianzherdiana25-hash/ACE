# Mulai di sini — ACE Work + Codex

Proyek: **Autonomous Capability Evolution (ACE)**. Dokumen ini adalah titik masuk yang dapat digunakan tanpa membaca ulang percakapan panjang.

## Status dan instruksi terpenting
- Snapshot terakhir: **E1.2 selesai sebagai eksperimen DSL internal**, kemampuan menciptakan primitive fundamental dan AI otonom umum **belum terbukti**.
- Langkah berikut: **E1.3 DESAIN**, bukan mengeksekusi set konfirmatori tanpa prapenguncian.
- Baca terlebih dahulu `ACE_RESEARCH_MASTER_RECORD_v1.0.md`, lalu `docs/PRD_ACE_v0.1.md`, `docs/ACE_Research_Execution_Spec_v0.1.md`, dan `docs/E12_Research_Report_v0.1.md`.
- Folder `evidence/` berisi ZIP penelitian historis utuh; `code/e12/` berisi salinan kode E1.2 untuk orientasi; jangan menimpa output lama.
- Validasi snapshot menggunakan `MANIFEST_SHA256.json` dan `python verify_handoff.py`.
- **Jangan gunakan repositori Tod.** Saat inventarisasi GitHub hanya Tod yang tersedia; buat repositori ACE baru secara privat bila pengguna memilih memublikasikan repositori hasil kerja ini.
- Asisten Work bisa menggunakan paket ini untuk koordinasi, Codex untuk coding di repo ACE, Colab untuk replikasi. Tidak ada keterhubungan Work/Codex yang sudah diklaim otomatis oleh paket ini.

## Perintah kerja awal untuk Work
> Baca paket ACE ini sebagai sumber kebenaran. Rekonsiliasi artefak E1.2 dan semua laporan sebelumnya. Jangan mulai dari nol, jangan ubah Tod, jangan keluarkan biaya, jangan melakukan konfirmasi E1.3 sebelum protokol dan evaluator terpisah dibekukan. Prioritas: siapkan repo ACE pribadi yang berversi, desain tantangan E1.3 dengan kontrol matematis kuat dan anggaran CPU nyata, serta checkpoint dan audit independen.

## Perintah kerja awal untuk Codex
> Kerjakan hanya di repositori ACE, jangan Tod. Jadikan `code/e12/` pembanding yang tidak diedit. Buat branch eksperimen E1.3; buat evaluator/benchmark terpisah, tes kebocoran, benchmark solver kuat dan metrik biaya aktual. Jangan memakai soal sealed-test untuk tuning. Laporkan commit, test command, bukti, dan keterbatasan.
