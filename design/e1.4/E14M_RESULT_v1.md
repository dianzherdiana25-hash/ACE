# E1.4m — kontra-contoh menggugurkan seluruh hipotesis pada kondisi terjangkau

**Reachable GO · Rare HOLD · NATURAL_HOLD untuk transfer.** Sistem merangkai pertanyaan dari bagian-bagian yang telah diberi label negatif. Jika seluruh hipotesis memprediksi jawaban negatif dan label yang dibeli justru positif, evaluator mencatat bahwa tidak ada lagi hipotesis yang cocok.

[Pembekuan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/835016481e61261386a02ae4867ece580d4cd1cd) · [Hasil mentah](../../evidence/e14/e14m_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14m_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14m_verification_v1.json)

| Kasus di luar model | Keluarga | Falsifikasi terarah, deteksi / kasus | Adjudikasi | Acak | Label terarah / adjudikasi / acak |
| --- | --- | ---: | ---: | ---: | ---: |
| Terjangkau | Simbol | 8/8 | 0/8 | 0/8 | 17 / 32 / 32 |
| Terjangkau | Graf | 7/8 | 0/8 | 0/8 | 23 / 32 / 32 |
| Langka | Simbol | 0/8 | 0/8 | 0/8 | 28 / 32 / 32 |
| Langka | Graf | 0/8 | 0/8 | 0/8 | 32 / 32 / 32 |

- **Cakupan keberhasilan.** Target terjangkau sengaja diambil dari pola tujuh kejadian yang kedua bagian enam kejadiannya terlihat pada demo negatif. Semua pertanyaan berisi sembilan kejadian dan setiap metode punya batas empat label. Falsifikasi membeli 40 label untuk 16 kasus terjangkau, dibanding 64 per pembanding. Lengan berhenti segera ketika model gugur. Nol dari 40 kasus dalam model ditolak pada masing-masing dari tiga lengan. Pada delapan kontrol berpasangan per keluarga, worker memulai dari demo dan label yang sama dengan target luar model terjangkau.
- **Satu kegagalan pemilihan.** Pada graf terjangkau yang luput, kandidat dengan target berada dalam pool pada putaran ketiga dan keempat, tetapi peringkat jumlah jendela baru memilih kandidat lain. Empat label habis tanpa kontra-contoh. Ini audit atas tawaran yang tersimpan. Label alternatif tersebut tidak dibeli dalam run.
- **Batas pada kasus langka.** Strategi hanya merangkai jendela enam kejadian yang sudah diamati negatif. Kedua jendela dari target langka sengaja belum terlihat. Dengan empat pertanyaan sembilan kejadian, cabang sebelum aktivasi dapat mencakup paling banyak 12 kandidat tujuh kejadian. Dalam bank langka ada 2.100–2.109 target potensial per kasus simbol dan 79–94 per kasus graf. Jika target seragam bersyarat pada bentuk demo dan kebijakan hanya melihat bentuk dan label, batas atas peluang memicu target adalah 0,58% pada simbol dan 15,2% pada graf. Ini batas peluang aktivasi dalam konstruksi tersebut. Satu pembelian acak pada graf langka memperoleh label aktif, tetapi masih kompatibel dengan sedikitnya satu hipotesis lama.
- **Prediksi selektif.** Pada lengan falsifikasi, cakupan prediksi di kedua strata luar model adalah nol. Karena itu nol kesalahan pada strata tersebut tidak menunjukkan prediksi yang aman atau akurat. Pada kasus dalam model, cakupan lengan ini hanya 39/160 pada simbol dan 96/160 pada graf, tanpa kesalahan di antara prediksi yang diterima. Deteksi kontradiksi, cakupan, dan risiko di antara prediksi yang diterima diukur terpisah.
- **Verifikasi.** 56 blok, 72 dunia, dan 2.240 input mentah baru dibanding 17.006 fingerprint. Setiap run memakai 981 worker, 18.039.120 perbandingan kecocokan dan 3.645 evaluasi oracle. Enam pemeriksaan isolasi lulus. Audit menghitung ulang hipotesis, pilihan query, label yang dibeli, dan prediksi selektif. Replay cocok pada 72 kasus dan resume ledger terminal identik byte. Regresi dari sumber yang dapat dipulihkan lulus 99/99.

Tahap E1.4n akan menguji apakah sistem dapat mengusulkan perluasan representasi yang terbatas setelah hipotesis lama gugur, lalu memeriksa usulan itu pada probe baru. Temuan E1.4m mendukung deteksi terkontrol. Pemulihan dan transfer masih terbuka.
