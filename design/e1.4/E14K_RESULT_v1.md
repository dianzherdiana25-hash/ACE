# E1.4k — pertanyaan majemuk memperluas cakupan dengan biaya input lebih tinggi

**COMPOUND_DEVELOPMENT_GO** pada kondisi terkontrol dengan motif yang dapat digabungkan. **NATURAL_HOLD** untuk transfer. Worker menyusun input 12 kejadian dari motif yang masih konsisten dengan demo. Evaluator hanya mengungkap label untuk input terpilih.

[Pembekuan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/ae73b9c9d69366d5a503fd1529ced1b11c716dd8) · [Hasil mentah](../../evidence/e14/e14k_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14k_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14k_verification_v1.json)

| Packable, batas satu label | Simbol pendek terarah | Simbol panjang acak | Simbol majemuk terarah | Graf pendek terarah | Graf panjang acak | Graf majemuk terarah |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Diagnosis aturan panjang | 0/6 | 0/6 | 6/6 | 0/6 | 0/6 | 4/6 |
| Kandidat pendek gugur pada kasus aturan panjang | 6/18 | 3/18 | 18/18 | 6/18 | 10/18 | 15/18 |
| Diagnosis semua target | 1/12 | 0/12 | 11/12 | 3/12 | 0/12 | 4/12 |
| Probe tepat | 60/96 | 64/96 | 88/96 | 69/96 | 71/96 | 68/96 |
| Label / kejadian yang dibeli, semua target | 12 / 60 | 12 / 144 | 12 / 144 | 12 / 60 | 12 / 144 | 12 / 144 |

- **Biaya dan kekuatan pembanding.** Pertanyaan panjang acak dan majemuk terarah memiliki panjang yang sama. Semua metode menilai paling banyak delapan input per putaran. Dengan batas dua label, metode pendek masih mendiagnosis 0/6 aturan panjang di setiap keluarga packable dan memakai 115 kejadian pada simbol serta 105 pada graf untuk seluruh 12 target per keluarga. Metode majemuk mendiagnosis 6/6 aturan panjang di kedua keluarga pada batas dua label, dengan 156 dan 240 kejadian untuk seluruh target. Diagnosis dapat membaik dengan biaya kejadian lebih tinggi. Pada graf packable, probe tepat majemuk berada di bawah acak pada batas satu maupun dua label. Gerbang menguji diagnosis, sehingga perbedaan skor prediksi tetap dilaporkan.
- **Data alami dan batas cakupan.** Pada simbol alami, majemuk dan pendek sama-sama mendiagnosis 2/12 kasus setelah satu label, dibanding 1/12 tanpa label. Keduanya menggunakan 11 label, tetapi majemuk membeli 132 kejadian dibanding 62. Skor probe keduanya tetap 90/96. Graf alami sudah mendiagnosis 12/12 panjang dari demo dan tidak membeli label, dengan 95/96 probe tepat. Pada kondisi ceiling, majemuk menghasilkan nol diagnosis pada batas satu label di kedua keluarga. Fallback false positive pada kondisi ini naik dari 0 ke 4 di simbol dan dari 11 ke 15 di graf sesudah satu label. Tidak ada diagnosis majemuk yang salah di bank ini.
- **Audit deskriptif kegagalan seleksi.** Pada dua target panjang graf packable yang masih ambigu setelah satu label, kandidat yang mencakup seluruh tiga motif pendek tersedia. Pemeringkat memilih kandidat yang mencakup dua karena estimasi minimax fraksi terkecil yang tersisa lebih rendah. Ini memisahkan masalah pemeringkatan dari ketersediaan kandidat. Hasil label yang akan diperoleh dari kandidat yang tidak dibeli belum diukur dalam run. Kedua kasus terdiagnosis setelah label kedua. [Rincian](../../evidence/e14/e14k_verification_v1.json)
- **Verifikasi.** 48 blok, 72 dunia, dan 1.920 input mentah baru dibanding inventaris 13.006 fingerprint. Setiap run memakai 544 worker, 10.342.344 perbandingan kecocokan, dan 3.208 evaluasi oracle. Enam pemeriksaan isolasi lulus. Audit menghitung ulang fit, cakupan, pilihan, label, dan skor. Replay dengan ledger baru cocok pada 72 kasus, dan resume ledger selesai identik byte. Tes pra-penilaian lulus 4/4 dan regresi dari sumber yang dapat dipulihkan lulus 91/91.

Tahap berikutnya membandingkan aturan pemeringkatan yang mempertimbangkan cakupan dan biaya pada set pertanyaan calon yang sama. Uji risiko ketika sistem memberi prediksi fallback sambil menunda diagnosis. Kemampuan transfer dan penemuan representasi baru masih terbuka.
