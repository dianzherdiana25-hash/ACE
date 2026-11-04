# E1.4h — pemilihan grammar dari kecocokan demo

**ROUTING_DEVELOPMENT_GO** pada bank yang dirancang untuk menguji peralihan. Pemilih mendapat 32 demo dan dua grammar yang tersedia. Ia beralih dari lima ke enam kejadian hanya ketika grammar lima memiliki kesalahan dan grammar enam cocok dengan semua demo. Pemilih mengambil satu label setelah menentukan grammar. Panjang aturan sebenarnya disimpan evaluator.

[Pembekuan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/d6db8d065104ada75e676801bed62daa26cf094a) · [Hasil mentah](../../evidence/e14/e14h_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14h_replay_v1.json.gz) · [Audit](../../evidence/e14/e14h_verification_v1.json)

| Distribusi | Keluarga | Panjang | Grammar dipilih benar | Lima tetap | Enam tetap | Adaptif tanpa label | Adaptif satu label | Acuan tahu panjang |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Alami sintetis | S | 5 | 6/6 | 48/48 | 48/48 | 48/48 | 48/48 | 48/48 |
| Alami sintetis | S | 6 | 1/6 | 46/48 | 48/48 | 47/48 | 47/48 | 48/48 |
| Alami sintetis | G | 5 | 6/6 | 48/48 | 41/48 | 48/48 | 48/48 | 48/48 |
| Alami sintetis | G | 6 | 6/6 | 38/48 | 48/48 | 48/48 | 48/48 | 48/48 |
| Diperkaya peluang | S | 5 | 6/6 | 96/96 | 48/96 | 48/96 | 96/96 | 96/96 |
| Diperkaya peluang | S | 6 | 6/6 | 48/96 | 96/96 | 48/96 | 96/96 | 96/96 |
| Diperkaya peluang | G | 5 | 6/6 | 96/96 | 48/96 | 48/96 | 96/96 | 96/96 |
| Diperkaya peluang | G | 6 | 6/6 | 48/96 | 96/96 | 48/96 | 96/96 | 96/96 |

- Di bank peluang, setiap keluarga mencapai 192/192 jika kedua panjang digabungkan, dibanding 144/192 untuk masing-masing grammar tetap. Keduanya mendapat satu label tambahan. Pemilih adaptif membandingkan dua fit awal, sehingga biayanya lebih besar dari satu kontrol tetap. Tidak ada dunia dengan skor adaptif di bawah grammar lima.
- **Keterbatasan utama.** Pada lima dari enam blok S alami dengan aturan panjang enam, kedua grammar sama-sama cocok dengan 32 demo. Aturan peralihan tetap memilih lima. Audit deskriptif setelah penilaian mencakup keenam blok. Kata target enam kejadian muncul pada dua demo di satu blok, dan tidak muncul pada 48 item pool maupun 48 probe di strata tersebut. Skor 47/48 dapat muncul sambil gagal mengenali panjang karena seluruh probe berlabel negatif. `NATURAL_HOLD` tetap berlaku untuk transfer.
- **Cakupan bukti.** Bank baru memiliki 2.304 input mentah, 48 blok, dan 72 dunia. Bentuk trace dan beberapa motif diagnostik dapat terulang. Setiap penilaian menggunakan 360 worker terisolasi dan 2.989 evaluasi oracle. Semua lima canary lulus, dua tes pra-penilaian lulus, auditor menghitung ulang hasil 72 dunia, replay deterministik cocok, dan resume ledger terminal menghasilkan byte identik. Tidak ada kasus ketika kedua grammar gagal mencapai kecocokan sempurna di bank ini.
- **Implikasi.** E1.4h menguji diagnosis terbatas dengan dua representasi buatan manusia. Tahap berikutnya perlu menguji cara mencari pertanyaan yang membedakan dua grammar ketika keduanya cocok dengan demo. Ukur ketersediaan saksi, tingkat abstain, dan kemampuan diagnosis secara terpisah. Penemuan representasi baru, transfer, dan visi OAIE tetap menjadi tujuan riset jangka panjang.

Regresi yang dapat dipulihkan dari arsip GitHub, ditambah tes E1.4g/h, lulus 79/79.
