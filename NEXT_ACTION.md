# Aksi berikutnya untuk Work atau Codex

1. Baca [status](CURRENT_STATE.md), [bukti selection](evidence/e13/selection_summary_v1.json), [desain E1.3](design/e1.3/E13_DESIGN_v0.1.md), dan [pekerjaan GitHub #1](https://github.com/dianzherdiana25-hash/ACE/issues/1). Verifikasi kepala branch `research/e1.3-design` sebelum bekerja.
2. Lakukan analisis daya berbasis blok aturan berpasangan dan dua keluarga. Catat asumsi variasi, efek minimum +10 poin, jumlah blok, seed, jumlah pengulangan, dan risiko pilot kecil. Gunakan bukti development dan sensitivitas asumsi. Tahan konfirmasi bila daya atau biaya tidak memadai.
3. Verifikasi reproduksi selection dalam pekerjaan teknis terpisah dari implementasi kandidat menggunakan paket evaluator privat. Pertahankan kandidat beku `2d9d86c`, B* beam, digest bank, dan kegagalan yang dicatat. Perubahan kode solver yang memengaruhi kontras harus memicu pemeriksaan versi sebelum penggunaan bank lagi.
4. Kunci kontras primer, ukuran sampel, urutan dan seed, aturan biaya/kegagalan, analisis bootstrap dan audit. Siapkan split konfirmatori dengan motif baru serta kustodi evaluator yang terpisah dari selection. Jalankan konfirmasi hanya ketika seluruh gerbang lulus.

Gunakan CPU lokal, anggaran Rp0, dan kontrak checkpoint pada [piagam](PROJECT_CHARTER.md).
