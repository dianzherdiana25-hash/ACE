# E1.4n — pemulihan bersyarat setelah kontra-contoh

**Repair GO · Rare HOLD · NATURAL_HOLD.** Bank publik membuktikan pemulihan bersyarat dalam grammar motif kontigu yang telah dibatasi. Worker mulai dengan panjang 5–6. Setelah observasi menggugurkan seluruh kelas awal, pencarian terarah menyaring calon panjang 7–9 dari label positif pertama dan memeriksa semua bukti terlihat.

[Pembekuan](https://github.com/dianzherdiana25-hash/ACE/commit/fb9ac72c9c6b039f402a1905b3635f2a4efbecdb) · [Penilaian](../../evidence/e14/e14n_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14n_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14n_verification_v1.json)

| Keluarga pada strata repair | Terarah, semua 8 probe benar | Panjang tetap 7 | Enumerasi 7–9 | Kandidat terarah / enumerasi | Perbandingan label terarah / enumerasi |
| --- | ---: | ---: | ---: | ---: | ---: |
| Simbol | 9/9 | 3/9 | 9/9 | 90 / 852.930 | 3.078 / 855.918 |
| Graf | 9/9 | 3/9 | 9/9 | 450 / 26.880 | 15.234 / 41.664 |

- Pada seluruh 72 dunia dan semua langkah, pencarian terarah dan enumerasi mempertahankan himpunan kandidat yang identik. Penyaringan menambah 450 pemeriksaan jendela anchor per keluarga pada strata repair. Biaya yang dicatat mencakup pencarian ulang pada setiap prefix bukti, bukan komputasi kumulatif yang sudah dicache.
- Setelah kontra-contoh pertama, 0/18 dunia repair sudah mencakup delapan probe. Penyelesaian 18/18 memakai 60 label tambahan yang dijadwalkan evaluator, termasuk kontra-contoh. Maka hasil ini memisahkan deteksi dari pemulihan dan belum mengukur kemampuan memilih sendiri bukti pemulihan.
- Pada enam kasus ambigu, pencarian terarah menerima 17/48 prediksi tanpa salah. Pembanding panjang tetap menerima 28/48 dengan empat kesalahan, seluruhnya pada simbol. Di delapan kasus panjang 10, seluruh perluasan tetap kosong dan sistem menahan prediksi. Pada 32 kontrol sesuai model dan delapan target di luar model tanpa kontra-contoh, tidak ada perluasan yang dipicu.
- Penilaian dan replay memakai snapshot beku dengan tree identik. Audit oracle cocok pada 72 dunia, resume identik byte, dan verifikasi arsip historis lulus 45/45. Pengujian native mencakup worker aktual, mount hanya baca, akses evaluator dan jaringan ditolak, serta batas CPU 1 detik dan alamat virtual 128 MiB. Provenance tanda tangan distribusi binary belum diperiksa. Tidak ada sandbox tiruan dalam penilaian ini.
- Ini bukti pemulihan untuk keluarga simbol dan graf pada grammar yang ditentukan manusia dan urutan label yang sengaja memisahkan kandidat. Transfer, penciptaan operator baru, dan pemilihan bukti secara otonom tetap terbuka.
