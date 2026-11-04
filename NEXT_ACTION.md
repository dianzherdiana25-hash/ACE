# Aksi berikutnya untuk Work atau Codex

1. Mulai dari kepala `research/e1.3-design`. Baca [status](CURRENT_STATE.md), [desain E1.3](design/e1.3/E13_DESIGN_v0.1.md), dan [pekerjaan GitHub #1](https://github.com/dianzherdiana25-hash/ACE/issues/1). Jalankan regresi, [replay pilot](code/e13/README.md#pilot-development-v02), dan [diagnostik batas](code/e13/README.md#diagnostik-batas-representasi).
2. Implementasikan `C_EXTEND` yang mencari perluasan dari contoh, menggunakan prototipe AST diagnostik hanya sebagai permukaan uji. Simpan definisi reusable dengan hash induk, saksi, jejak seleksi, dan replay oleh penerus yang baru. Terapkan `C_NO_EXTEND`, `C_NO_TRANSFER`, dan `C_SHAM` dengan kesempatan yang sebanding. Pertahankan status `UNKNOWN` untuk ekuivalensi yang belum lengkap.
3. Pisahkan pembanding struktural dan enumerasi di kedua keluarga. Rekonsiliasi biaya fit, prediksi dan evaluator. Jalankan seluruh kontrol pada development, termasuk diagnostik yang lebih kuat.
4. Siapkan bank selection dalam jalur evaluator terpisah dan audit tumpang tindih terhadap development. Pilih B* setelah kontrol dan akuntansi biaya siap. Tahan konfirmasi sampai penguncian dan audit reproduksi teknis terpenuhi.

Gunakan CPU lokal, anggaran Rp0, dan kontrak checkpoint pada [piagam](PROJECT_CHARTER.md).
