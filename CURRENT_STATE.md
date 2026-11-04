# Keadaan ACE saat ini

**Status untuk pembaca umum.** ACE sudah bisa menguji metode kecil dan menemukan kapan pemakaian ulang metode membantu atau merugikan. Pada E1.2, metode yang memakai ulang pengetahuan berhasil pada soal terkait, tetapi pembanding terstruktur juga berhasil seluruhnya. E1.3 sedang menyiapkan uji yang lebih ketat untuk aturan yang disembunyikan dari kandidat.

- **Proyek** [Piagam ACE](PROJECT_CHARTER.md) dan visi OAIE.
- **Branch** [`research/e1.3-design`](https://github.com/dianzherdiana25-hash/ACE/tree/research/e1.3-design). SHA checkpoint terkini adalah kepala branch tersebut. Checkpoint implementasi yang direkonsiliasi adalah [`0bb5c7d`](https://github.com/dianzherdiana25-hash/ACE/commit/0bb5c7d9fcd04abb361fe28b12b1b6c14560d2d9), yang memiliki tree sama dengan sumber lokal `6c1f6e3`. `main` berada di luar alur perubahan.
- **Bukti teknis** Manifest historis 45/45, regresi unit E1.2 14/14, tes E1.3 18/18, smoke publik 6/6. Pemeriksaan mencakup isolasi berkas, lingkungan, dan jaringan worker. Perintah ada di [README E1.3](code/e13/README.md).
- **Status ilmiah** [F5](docs/ACE_F5_Research_Synthesis_and_Decision_v0.1.md) melanjutkan riset dengan batas klaim. [E1.2](docs/E12_Research_Report_v0.1.md) menunjukkan induksi dalam grammar buatan manusia dan transfer negatif pada aturan tidak terkait. E1.3 masih development.
- **Sedang dikerjakan** Bank aturan terbuka, oracle, dan audit per blok aturan. [Desain E1.3](design/e1.3/E13_DESIGN_v0.1.md) mendefinisikan gerbang riset.
- **Gerbang terbuka** Bank selection di bawah kustodi evaluator, kontrol kuat lengkap, pilot selection, penetapan B*, daya, penguncian, dan reproduksi teknis terpisah. Evaluasi konfirmatori tetap ditahan.

Baca [ledger](RESEARCH_LEDGER.md) untuk hasil positif dan negatif, serta [aksi berikutnya](NEXT_ACTION.md) untuk memulai kerja.
