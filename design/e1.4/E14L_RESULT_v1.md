# E1.4l — pemeringkatan lolos, ambang biaya dan cakupan selektif tertahan

**Ranking GO · Budget HOLD · Selective HOLD · NATURAL_HOLD untuk transfer.** Ketiga strategi melihat calon pertanyaan yang sama ketika riwayat labelnya sama. Perbandingan mengisolasi pemeringkatan dan pilihan untuk tidak membeli label.

[Pembekuan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/904dcc62d94bcbfdd6070437af434ec7cce25730) · [Hasil mentah](../../evidence/e14/e14l_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14l_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14l_verification_v1.json)

- **Ranking GO.** Dengan satu label di kasus packable aturan panjang, pemeringkat manfaat per biaya memperoleh 5/5 diagnosis simbol dan 3/5 graf. Minimax memperoleh 5/5 dan 2/5. Keuntungan berasal dari satu kasus graf. Pada batas dua label, minimax justru memperoleh 4/5 pada graf yang sama, dibanding 3/5 untuk pemeringkat manfaat. Gerbang hanya mendukung kelanjutan uji pemeringkatan satu-label.
- **Budget HOLD.** Ambang menolak banyak pembelian label. Pada simbol alami, ia mempertahankan 7/12 diagnosis dan 95/96 probe tepat dengan 30 kejadian dan enam label, dibanding 150 kejadian dan 16 label untuk minimax. Namun pada gabungan strata dalam model, diagnosis yang dipertahankan hanya 17/20 pada simbol dan 12/20 pada graf, di bawah ambang 90% per keluarga. Seluruh graf packable dan seluruh kasus ceiling berhenti tanpa membeli label pada lengan ambang.
- **Selective HOLD.** Di dalam model, tidak ada prediksi selektif yang salah. Cakupan lengan ambang hanya 96/256 pada simbol dan 131/256 pada graf, sehingga simbol gagal ambang 50%. Prediksi fallback juga lebih sering keliru positif ketika diagnosis ditunda. Jumlahnya naik dari 5 ke 7 pada simbol dan dari 4 ke 14 pada graf dibanding minimax, dengan cakupan fallback yang berbeda.
- **Kesepakatan di luar model dapat keliru.** Pada delapan dunia target tujuh kejadian, lengan ambang menerima 32 dari 64 probe dan semua 32 yang diterima salah. Ini uji tekanan yang sengaja dibangun agar prediksi negatif dalam model bertentangan dengan target positif. Angkanya menggambarkan konstruksi tersebut. Semua lengan masih menyisakan kandidat dalam model pada akhir run. Minimax bahkan memberi satu diagnosis kelas graf yang salah. Nol kesalahan selektif dalam model bergantung pada target berada dalam himpunan hipotesis.
- **Verifikasi.** 52 blok, 72 dunia, dan 2.080 input baru dibanding 14.926 fingerprint. Setiap penilaian memakai 433 worker, 7.974.240 perbandingan kecocokan, dan 3.097 evaluasi oracle. Enam pemeriksaan isolasi lulus. Audit menghitung ulang kecocokan, cakupan, risiko, label, dan peringkat serta memeriksa kesetaraan proposal pada riwayat yang sama. Replay cocok pada 72 kasus dan resume dari ledger selesai identik byte. Tes pra-penilaian lulus 4/4 dan regresi dari sumber yang dapat dipulihkan lulus 95/95.

| Dalam model, batas dua label | Strategi | Diagnosis tepat / 32 | Label | Kejadian dibeli | Probe tepat / 256 | Cakupan selektif / 256 | Salah di antara prediksi diterima |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Simbol | Minimax | 20 | 45 | 484 | 223 | 128 | 0 |
| Simbol | Manfaat per biaya | 20 | 45 | 345 | 219 | 120 | 0 |
| Simbol | Ambang pembelian | 17 | 17 | 155 | 208 | 96 | 0 |
| Graf | Minimax | 20 | 39 | 433 | 205 | 148 | 0 |
| Graf | Manfaat per biaya | 18 | 38 | 274 | 201 | 151 | 0 |
| Graf | Ambang pembelian | 12 | 1 | 5 | 193 | 131 | 0 |

E1.4m akan menguji pertanyaan yang sengaja mencari bukti untuk menggugurkan seluruh kelas yang tersedia. Bandingkan kemampuan mendeteksi aturan di luar model, biaya label, dan penolakan keliru pada data yang masih sesuai model.
