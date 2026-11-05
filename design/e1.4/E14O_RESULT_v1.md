# E1.4o — loop aktif berjalan, pemulihan graf tertahan

**Autonomous repair HOLD · Rare HOLD · NATURAL_HOLD.** Pada distribusi baru dengan event berkelompok, semua metode memakai detektor yang sama. Metode aktif memilih sendiri label pembeda sesudah kontradiksi. Gerbang mewajibkan pemulihan lengkap minimal 5/9 per keluarga dalam empat label.

[Pembekuan](https://github.com/dianzherdiana25-hash/ACE/commit/0af0240948a059e5ece3e8ebd1fa167ead9dead0) · [Bukti](../../evidence/e14/e14o_verification_v1.json)

| Strata terjangkau | Aktif, deteksi | Aktif, pulih penuh | Pasif, pulih penuh | Acak, pulih penuh | Label aktif / pasif / acak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Simbol | 9/9 | 8/9 | 1/9 | 1/9 | 30 / 20 / 33 |
| Graf | 8/9 | 1/9 | 0/9 | 0/9 | 36 / 27 / 36 |

- Aktif menambah cakupan terhadap pasif dari 49 ke 70 dari 72 probe simbol dan 21 ke 39 dari 72 probe graf. Tidak ada kesalahan di antara prediksi yang diterima pada bank ini. Enam kasus langka luput dan tidak ada pemicu keliru pada 24 dunia dalam model per strategi.
- Tujuh dari delapan graf terdeteksi pada label ketiga, dengan lima atau enam kandidat perluasan dan satu label tersisa. Untuk graf rantai, satu query hanya memberi hasil kosong atau total biaya jalur. Satu jawaban biner tidak bisa menjamin pemilihan dari lima atau enam kandidat. Ini batas kasus terburuk. Sebagian keluaran atau probe tetap bisa disepakati tanpa identifikasi penuh.
- Pemulihan dari timeout diuji pada run penilaian. Tiga dunia disimpan, proses berakhir TIMEOUT, lalu ledger yang sama diteruskan hingga 48 dunia. Hasil deterministik cocok dengan replay baru. Audit merekonstruksi setiap query, kontradiksi, ruang hipotesis dan probe. Run lengkap memakai 668 worker terisolasi dan 2.444 evaluasi oracle. Regresi dari sumber yang dipulihkan lulus 105/105.
- Penyelesaian simbol mendukung loop terbatas pada distribusi terjangkau. Keunggulan graf belum memenuhi ambang. E1.4p menguji jalur pewarisan terpisah dengan pendahulu yang menerima bukti terjadwal dan penerus pada graf bercabang. Hasil E1.4p tidak dapat menggantikan gerbang E1.4o.
