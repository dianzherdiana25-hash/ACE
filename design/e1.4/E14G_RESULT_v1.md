# E1.4g — benchmark yang membedakan manfaat satu label dan batas representasi

**Keputusan pengembangan `BENCHMARK_DEVELOPMENT_GO`.** Distribusi sintetis alami mendapat **`NATURAL_HOLD`**. Hasil memungkinkan pengujian pemilihan representasi pada benchmark yang sengaja mengandung peluang belajar. Transfer kebijakan, generalisasi luas dan penemuan representasi baru masih terbuka.

[Protokol dan sumber beku sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/129b5b8505c6b747efd5f3d4b64a412f16f4c8e2) · [Bukti penilaian](../../evidence/e14/e14g_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14g_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14g_verification_v1.json)

| Distribusi | Keluarga | Panjang | Tanpa label | Tetap, satu label | Acak, ekspektasi | Max-Gini | Minimax | Hindsight | Tahu panjang |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Alami sintetis | S | 5 | 46/48 | 46/48 | 46,25/48 | 48/48 | 48/48 | 48/48 | 48/48 |
| Alami sintetis | G | 5 | 48/48 | 48/48 | 48/48 | 48/48 | 48/48 | 48/48 | 48/48 |
| Alami sintetis | S | 6 | 46/48 | 46/48 | 46/48 | 46/48 | 46/48 | 46/48 | 46/48 |
| Alami sintetis | G | 6 | 41/48 | 41/48 | 40,875/48 | 41/48 | 41/48 | 41/48 | 48/48 |
| Diperkaya peluang | S | 5 | 48/96 | 56/96 | 60/96 | 96/96 | 96/96 | 96/96 | 96/96 |
| Diperkaya peluang | G | 5 | 48/96 | 56/96 | 60/96 | 96/96 | 96/96 | 96/96 | 96/96 |
| Diperkaya peluang | S | 6 | 48/96 | 48/96 | 48/96 | 48/96 | 48/96 | 48/96 | 96/96 |
| Diperkaya peluang | G | 6 | 48/96 | 48/96 | 48/96 | 48/96 | 48/96 | 48/96 | 96/96 |

- **Peluang belajar yang terukur.** Di masing-masing keluarga panjang lima, hindsight mengungguli tanpa label pada 6/6 blok. Max-Gini dan minimax mengungguli acak pada 6/6 blok dan keduanya mengungguli kontrol tetap pada agregat. Label tambahan yang dipilih dengan tepat memisahkan dua hipotesis yang kompatibel dengan demo.
- **Keterbatasan representasi.** Ketika aturan membutuhkan enam kejadian, bahkan pemilih retrospektif dengan grammar lima berhenti pada 48/96 per keluarga. Acuan yang diberi panjang grammar mencapai 96/96 dan mengungguli hindsight di 6/6 blok per keluarga. Ia mendapat satu label tambahan dengan ukuran pencarian berbeda.
- **Distribusi alami.** Pada panjang lima, peluang hindsight hanya 1/6 S dan 0/6 G, di bawah ambang 3/6 masing-masing. G sudah mencapai plafon tanpa label. Tugas panjang enam dilaporkan deskriptif. Pada G panjang enam, pemilihan acak eksak sedikit merugikan dan kandidat terinformasi unggul. Komite bulat pada seluruh enam pool G panjang enam meskipun representasi lima masih salah pada tujuh probe. Jadi kesepakatan komite saja belum cukup untuk mendeteksi batasnya.
- **Unit bukti dan biaya.** 48 blok independen menurut rancangan, 72 dunia, 576 cabang satu-label, 2.304 input mentah baru terhadap inventaris 4.342 fingerprint publik. Dunia cermin dan pengulangan saksi dalam satu blok tidak menambah unit independen. Penilaian membutuhkan 3.456 evaluasi oracle dan 864 worker, masing-masing diulangi dalam replay. Seluruh pemilih satu-label menerima 32 label demo dan satu label query saat fit. Bank alami dan bank diperkaya berbeda di demo, pool dan probe. Perbandingan antardistribusi tidak mengisolasi efek pool.
- **Isolasi dan audit.** Native Bubblewrap 0.12.0 melewati lima canary evaluator dan batas 1 detik CPU, 3 detik wall serta 128 MiB per proses. Canary menguji berkas label privat, ketiadaan modul evaluator, lingkungan credential, mount hanya-baca, dan jaringan host. Bukti ini berlaku untuk jalur worker publik yang diuji. Asal paket binary belum dikonfirmasi. Replay dengan ledger baru cocok pada seluruh data deterministik. Auditor terpisah menghitung ulang kecocokan demo, partisi, kebijakan, prediksi, skor, biaya dan keputusan. Pengulangan ledger terminal menghasilkan byte yang sama. Tes pra-penilaian 8/8. Regresi historis E1.4f tetap 84/84 pada catatan asal. Suite yang dapat dipulihkan dari GitHub menghasilkan 69/69 sebelum penambahan delapan tes E1.4g.

Gerbang berikutnya menguji apakah ketidakcocokan demo dapat memicu pencarian grammar yang lebih panjang tanpa mendapat panjang sebenarnya. Gunakan bank publik baru dan pembanding panjang tetap. Penelitian transfer dan konfirmasi tetap berada di jalur terpisah.

Regresi gabungan dari arsip GitHub dan E1.4g lulus 77/77.
