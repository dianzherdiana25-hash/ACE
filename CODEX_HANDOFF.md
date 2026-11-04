# Codex Handoff — kontrak tugas berikut

**Misi:** mempersiapkan E1.3 secara ilmiah; implementasi algoritma eksploratif boleh dilakukan setelah repositori ACE terpisah tersedia, tetapi **jangan** menjalankan evaluasi konfirmatori sebelum data/kontras primer dikunci. 

## Checklist implementasi
1. Audit reproduksibilitas E1.2: `python -m unittest -v test_e12.py` dari `code/e12/`; rekonsiliasi hasil dengan laporan E1.2 (tes awal hanya memeriksa sebagian persyaratan).
2. Definisikan antarmuka tugas/agent/evaluator yang membatasi apa yang agen boleh lihat, dan verifikasi tes kebocoran.
3. Desain 2+ keluarga grammar yang dibuat dari spesifikasi terpisah; jangan hardcode grammar target pada agen.
4. Implementasikan dua pembanding kuat yang wajar: solver berbasis struktur ketika struktur diketahui, dan enumerative/beam/program synthesis pada kondisi unknown-grammar.
5. Log *wall time*, CPU time, evaluasi kandidat, biaya eksekusi primitive, memori puncak jika tersedia, seed, versi kode, hash dataset, kegagalan, dan checkpoint.
6. Buat mode penelitian: `development`, `selection`, `sealed_evaluation`; `sealed_evaluation` hanya dapat dipanggil setelah penguncian protokol.
7. Kunci kontras utama, ukuran efek minimum, jumlah seed, metrik kebaruan/transfer, dan analisis statistik sebelum pengujian.
8. Lakukan implementasi & unit test dengan CPU dan tanpa API berbayar; simpan perubahan sebagai commit/PR di repo ACE.

## Larangan metode
- Jangan menyebut peningkatan kecerdasan dari sekadar bertambahnya macro dalam grammar tetap.
- Jangan tuning terhadap seed pengujian lama setelah membuka hasil.
- Jangan menggunakan repo Tod atau mengubah autentikasi, membayar layanan, atau mengeksekusi kode yang tidak dipercaya secara arbitrer.
- Jangan menghapus atau menulis ulang bukti historis.

## Bukti selesai per task
Command yang benar-benar dijalankan; exit status; data/tangkapan hasil; commit hash; berkas baru; tes yang belum dijalankan; ancaman validitas.
