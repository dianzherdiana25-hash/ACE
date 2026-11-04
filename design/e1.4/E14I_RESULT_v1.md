# E1.4i — satu label dapat mengurai ambiguitas bila ada saksi

**WITNESS_DEVELOPMENT_GO** pada pasangan terkontrol. **NATURAL_HOLD** untuk transfer. Saksi adalah input yang akan diberi jawaban berbeda oleh dua grammar yang sama-sama cocok dengan contoh awal.

[Pembekuan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/63aeaf63f1762dc766c13a8188c15a2996316daf) · [Hasil mentah](../../evidence/e14/e14i_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14i_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14i_verification_v1.json)

| Dengan saksi | Diagnosis panjang S | Diagnosis panjang G | Probe tepat S | Probe tepat G | Probe false positive S/G |
| --- | --- | --- | --- | --- | --- |
| Pertanyaan lintas grammar | 12/12 | 12/12 | 96/96 | 96/96 | 0 / 0 |
| Aturan E1.4h | 6/12 | 6/12 | 72/96 | 76/96 | 24 / 20 |
| Acak satu label, ekspektasi | 3/12 | 3/12 | 78/96 | 78/96 | 18 / 18 |
| Tanpa label | 0/12 | 0/12 | 72/96 | 72/96 | 24 / 24 |
| Batas retrospektif | 12/12 | 12/12 | 96/96 | 96/96 | 0 / 0 |

Pada setiap keluarga, pertanyaan lintas grammar mendiagnosis kedua dunia cermin pada 6/6 blok bersaksi. Ketika kedua saksi dikeluarkan, metode menunda keputusan dan memakai nol label pada semua 24 dunia. Prediksi cadangan pada kondisi ini setara dengan kontrol tanpa label, 72/96 per keluarga. Penundaan tidak menghapus false positive jika sistem tetap diwajibkan memberi prediksi. Tiap pasangan memiliki demo, probe, dan enam item pool yang sama.

| Data sintetis alami | Dunia ambigu | Pool dengan TV positif | Bisa didiagnosis dengan satu label | Probe tepat lintas grammar | Probe tepat tanpa label |
| --- | --- | --- | --- | --- | --- |
| S panjang 5 | 4 | 2 | 0 | 47/48 | 47/48 |
| S panjang 6 | 4 | 4 | 0 | 46/48 | 46/48 |
| G panjang 5 | 2 | 1 | 1 | 48/48 | 48/48 |
| G panjang 6 | 2 | 2 | 1 | 48/48 | 48/48 |

Pemilih memakai sembilan label di 12 dunia alami ambigu. Dua label menyelesaikan diagnosis dan tujuh tidak. Tidak ada perbaikan akurasi probe dari satu label, bahkan dengan pilihan retrospektif. Pada S panjang lima, aturan E1.4h menebak panjang lima dengan benar pada enam dunia, sedangkan metode baru hanya menyatakan dua diagnosis dan menunda empat keputusan. Lihat tabel lengkap untuk membedakan skor diagnosis, abstain, dan prediksi.

**Audit analitis pasca-penilaian.** Dalam dua kasus alami, pool memiliki input dengan himpunan jawaban kedua grammar yang saling lepas. Keduanya dipilih. Pada enam kasus simbol alami, kedua grammar memiliki lebih banyak kata yang masih cocok daripada jendela yang dapat dicakup satu input sah. Apa pun input yang dibuat, masih ada setidaknya satu kata per grammar yang menghasilkan jawaban kosong. Dengan demikian satu label tidak dapat **menjamin** pemisahan pada enam kasus itu, meskipun jawaban tertentu bisa saja informatif. Untuk enam kasus tersebut, batas bawah terhitung adalah dua pertanyaan pada lintasan jawaban kosong. Jumlah yang cukup belum diketahui. Audit ini deskriptif dan tidak mengubah protokol atau keputusan. [Perhitungan](../../code/e14/e14i_capacity.py).

**Bukti dan biaya.** Bank berisi 36 blok, 72 dunia, 1.752 input mentah baru dibanding inventaris 8.950 fingerprint, dan 576 cabang satu-label. Setiap run memakai 1.368 worker, 12.610.944 perbandingan kecocokan dan 3.456 evaluasi oracle. Angka oracle menghitung ulang contoh yang sengaja dibagi antarkondisi. Kebijakan hanya mendapat satu label query jika mengajukannya. Enam pemeriksaan isolasi lulus. Replay dengan ledger baru cocok, auditor menghitung ulang semua 72 dunia, dan pengulangan ledger selesai menghasilkan byte identik. Tes pra-penilaian 4/4 dan regresi sumber yang dapat dipulihkan 83/83.

Langkah berikutnya menguji pembuatan saksi dari hipotesis yang masih cocok, dengan jalur lebih dari satu pertanyaan atau abstain jika batas bawah menuntutnya. Bukti ini berlaku untuk dua grammar yang tersedia di bank publik. Transfer dan penemuan representasi baru masih terbuka.
