# ACE E1.4 — hasil pilot diagnosis representasi

**GO untuk pilot lanjutan tentang pemilihan pertanyaan.** Hasil saat ini mendukung diagnosis terbatas ketika demonstrasi memuat saksi pembeda. Pada demonstrasi ambigu, kebijakan yang sama masih menerima representasi hitung yang cocok dan dapat salah pada probe baru.

Desain dan kode dibekukan sebelum penilaian pada [checkpoint `8b3975a`](https://github.com/dianzherdiana25-hash/ACE/commit/8b3975a9f3d76f02aced95fc090849a38b9cbc6e). Pilot menggunakan 18 episode publik baru dalam dua keluarga, empat kebijakan, dan 72 arm terisolasi. Replay mencocokkan semua baris pada bidang deterministik. Semua fit dan prediksi berada dalam plafon. [Protokol](E14_ROUTING_PILOT_v1.md) · [Bukti per arm](../../evidence/e14/routing_pilot_v1.json)

| Strata | Adaptif | Hitung | Urutan | Beam |
| --- | ---: | ---: | ---: | ---: |
| Hitung | 42/48 | 42/48 | 16/48 | 22/48 |
| Urutan dengan saksi | 48/48 | 24/48 | 48/48 | 28/48 |
| Urutan ambigu | 22/48 | 22/48 | 26/48 | 22/48 |

Kandidat adaptif berpindah ke urutan pada keenam episode bersaksi dan bertahan pada hitung untuk keenam episode hitung. Pada keenam episode ambigu, kecocokan hitung di demonstrasi menghentikan pencarian. Di keluarga graf pada strata hitung, adaptif benar 18/24. Kecocokan di demo belum memastikan model benar di probe. Perbandingan ini bergantung pada kasus yang sengaja disusun untuk diagnosis, pola pendek, dan dua keluarga mesin terbatas. Dua kebijakan tidak dibedakan secara inferensial dari pilot kecil ini.

## Hipotesis berikutnya

Saat beberapa representasi cocok, pengendali yang memilih pertanyaan berdasarkan ketidaksepakatan prediksi dapat memperoleh contoh lebih informatif daripada pengambilan acak dengan biaya label yang sama. Buat bank development baru sebelum penilaian, termasuk kasus tanpa pertanyaan pembeda dan kasus saat kedua model salah. Bandingkan satu label aktif, satu label acak, dan fit awal. Pencarian pertanyaan menggunakan masukan tanpa label. Oracle hanya menjawab pertanyaan terpilih. Probe akhir berada di luar kumpulan pertanyaan.
