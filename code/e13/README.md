# E1.3 development

Dua fixture publik menguji alur `fit → predict → score` untuk transformasi simbolik (S) dan graf beratribut (G). Pembanding memilih satu dari tiga AST tetap per keluarga dengan membandingkan demonstrasi target. Demonstrasi sumber menjadi pemutus seri. Operasi target fixture tersedia di katalog agar kedua fixture dapat menguji mekanik harness.

Jalankan dari root repositori. Uji unit awal memerlukan Python 3.10+. Jalur isolasi memerlukan Linux dengan namespace user dan jaringan yang aktif, `/usr/bin/python3`, Bubblewrap yang mendukung `--disable-userns`, serta `unshare` dan `prlimit` dari util-linux.

```bash
PYTHONPATH=code python3 -m unittest -v e13.test_development e13.test_isolation
PYTHONPATH=code python3 -m e13.development
python3 verify_handoff.py
(cd code/e12 && python3 -m unittest -q test_e12.py)
```

## Kontrak JSON v1

| Objek | Field dan batas |
| --- | --- |
| Request `fit` | `version` bernilai 1, `task_id` 32 karakter hex huruf kecil, `family` S atau G, `seed` uint32, `fuel` 1–100.000, `source` dan `target` masing-masing 1–16 demonstrasi `{input, output}`. Maksimum 32 KiB. Seed dicatat dan enumerator berurutan deterministik. |
| I/O S | Array maksimal 64 token bilangan bulat 0–15. `pair_flags` mengeluarkan 0 atau 1 untuk setiap pasangan bersebelahan. |
| Input G | Graf berarah dengan `nodes` 1–16, `start` dan `goal` sebagai indeks simpul, serta hingga 64 sisi `[awal, akhir, label, biaya]`. Label 0–3 dan biaya 0–15. |
| Output G | Biaya lintasan minimum atau `null` jika tak terjangkau. |
| AST S | `{"family":"S","ast":{"op":"pair_flags","rule":{"op":"lt"}}}`. Pilihan aturan `eq`, `lt`, `gt`. |
| AST G | `{"family":"G","ast":{"op":"path_cost","rule":{"op":"different"}}}`. Pilihan aturan `any`, `different`, `same`. |
| Input `predict` | Satu JSON I/O tanpa label, maksimum 4 KiB, plus AST kanonis maksimum 1 KiB dengan SHA-256. |

Parser menolak field tambahan, kunci ganda, tipe salah, dan operasi di luar katalog. Interpreter menghitung langkah awal, setiap pasangan token, serta setiap sisi yang disiapkan, entri antrean yang diambil, dan sisi yang diperiksa pada graf. Fit memakai satu anggaran untuk seluruh katalog. Probe satu fixture berbagi anggaran prediksi tersendiri.

## Pemisahan development

- `public_bank.py` memiliki dua oracle publik dan membentuk request sebelum memanggil kandidat. Kode dan label bank berada di sisi evaluator. Worker memulai proses baru per episode, menerima satu request melalui stdin, dan mengirim satu AST bertipe serta metrik melalui stdout. Evaluator memvalidasi AST, menghitung hash, memprediksi, dan menilai setelah fit berakhir.
- Worker memakai namespace jaringan baru, lingkungan bersih, direktori sementara, runtime sistem hanya-baca, dan salinan modul solver yang dipilih eksplisit. Checkout, kode bank, kredensial dari lingkungan, dan data evaluator berada di luar mount worker. Batas fit 1 detik CPU, 3 detik wall, dan 128 MiB ruang alamat. Ringkasan menampilkan CPU worker, wall peluncuran hingga respons, dan RSS puncak worker. Anggaran penilaian dan biaya total studi masih harus diukur.
- `split_audit.py` menolak tabrakan lintas split dalam satu keluarga berdasarkan bentuk aturan yang dinormalisasi oleh benchmark, perilaku pada rangkaian probe yang sama, atau payload tugas tanpa metadata. Kecocokan perilaku pada probe terbatas adalah alasan menahan blok untuk diperiksa. Pembuktian ekuivalensi fungsi, normalisasi khusus grammar, dan pemeriksaan bank nyata tetap pekerjaan evaluator.
- Uji development memeriksa akses ke file sintetis evaluator, kredensial canary, koneksi loopback host, label probe, ID opak, batas proses, respons worker tidak valid, serta tiga jenis tabrakan split. Smoke menghasilkan **6/6 probe publik** dengan SHA AST dan langkah fit yang sama seperti checkpoint awal. Hasil ini menguji jalur engineering untuk solver tetap dan AST terbatas.

## Pemulihan 4 November 2026

Tiga tree di GitHub identik dengan tree checkpoint lokal. Branch penelitian berawal dari commit awal GitHub, sehingga commit hasil impor memiliki SHA baru dengan trailer `ACE-Source-Commit`. Tag sumber E1.2 tetap tersedia pada bundle asli.

| Tahap | Commit sumber | Commit GitHub |
| --- | --- | --- |
| Bukti sampai E1.2 | `38afa3b5cf3e5b5529157fc0cc71e039189a2098` | `8b3546a26a40bc96111f5375282da8fa31660d92` |
| Desain E1.3 | `11ad689e31b320dbe7edc00adcccc7d97ed00e48` | `c28c89f729fb1b285e90aa00b395b1c5f08255e8` |
| Harness awal | `f7f0d391901d550ffa0c8e571916847601a860c3` | `77c8ef0c31dca700dd043a2c42e28069c16c7e88` |

`git fsck --full --strict` lulus, manifest historis cocok **45/45**, dan regresi unit E1.2 lulus **14/14** tanpa menjalankan ulang eksperimen lama.

## Gerbang berikutnya

Bangun bank aturan development/selection dan oracle evaluator di jalur terpisah, lalu jalankan audit split pada bank itu. Lanjutkan kontrol kuat, pilot, pemilihan B*, dan penguncian sebelum evaluasi konfirmatori. Set konfirmatori dan audit reproduksi terpisah masih terbuka. Status tetap development. Lihat [desain E1.3](../../design/e1.3/E13_DESIGN_v0.1.md).

## Bank development

```bash
PYTHONPATH=code python3 -m e13.evaluator.bank
PYTHONPATH=code python3 -m unittest discover -s code -p 'test_*.py' -v
```

Bank publik seed 1304 membangun 12 episode simbolik dan 12 episode graf, seimbang antara target terkait dan tidak terkait. Tiap keluarga memiliki dua kelompok aturan, masing-masing berisi sumber, target terkait, dan target tidak terkait. Tiap episode memiliki enam probe per ukuran, yaitu **288 probe** seluruhnya. SHA-256 bank adalah `76c7c3a486a57f47a22a74c35de7b757e12a692dbdd6ef4bfcb8ad0f4a7a07a2`.

Oracle berdiri sendiri di `evaluator/oracle.py`. Untuk graf, oracle menggunakan relaksasi sinkron pada graf keadaan, termasuk siklus dan sisi biaya nol. Struktur terkait membutuhkan jarak edit pohon terurut positif dan subpohon identik yang terdiri dari lebih dari satu node. Target tidak terkait memiliki jarak positif tanpa subpohon tersebut. Pembeda semantik memakai 121 urutan simbol dan 127 rantai graf pada domain kecil. Demonstrasi harus menyingkirkan aturan saingan dalam katalog publik. Pemeriksaan ini terbatas pada saingan dan domain yang dicakup.

Audit lintas split menolak bentuk aturan, sidik perilaku, tugas, dan input yang sama. Sisi graf diurutkan dan urutan demo/probe tidak menentukan hash tugas. Audit belum mengkanonisasi isomorfisme graf atau membuktikan kesetaraan semantik umum. Tes injeksi salinan lulus. Bank berisi split development saja dan modul evaluator berada di luar daftar staging worker. Bank selection terpisah tetap gerbang terbuka.

## Pilot development v0.1

Jalankan perintah berikut dari [checkpoint v0.1](https://github.com/dianzherdiana25-hash/ACE/commit/b3ca7be433668c1bf429116a61f3fa2abee61105).

```bash
PYTHONPATH=code python3 -m e13.evaluator.pilot > /tmp/ace-e13-pilot.json
```

Katalog awal tetap tersedia melalui worker. Pembanding buta menginferensi transduser simbolik dari jejak demonstrasi target, dan mengenumerasi mesin penghitung event serta keadaan penerima untuk graf. Ia tidak memuat nama aturan atau oracle. AST menggunakan tabel bertipe dengan satu sampai empat keadaan, keadaan awal nol, dan tiga event. Untuk simbol, event berasal dari perbandingan naik, sama, turun. Untuk graf, event adalah label pertama, label sama, dan label berbeda. Tabel graf dapat menolak transisi. Semua prediksi melalui interpreter berbatas langkah. Sebagai kontrol target-only, pembanding baru mengabaikan demonstrasi sumber.

| Pembanding | Simbol biasa | Simbol ekstrapolasi | Graf biasa | Graf ekstrapolasi | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Katalog | 31/72 | 20/72 | 26/72 | 32/72 | 109/288 |
| Inferensi simbol + enumerasi graf | 72/72 | 57/72 | 68/72 | 72/72 | 269/288 |

[Data v0.1](../../evidence/e13/development_pilot_v0.1.json) mencatat 48 eksekusi berpasangan, hash, langkah, CPU worker, RSS, waktu wall fit dan CPU penilai. Dua run cocok pada skor, hash AST, status dan hitungan langkah. Waktu dan RSS merupakan observasi mesin. CPU worker dan evaluator dicatat terpisah. Akuntansi CPU launcher dan satu batas CPU gabungan fit/prediksi masih terbuka untuk konfirmasi. Angka pilot ini menguji rekayasa pada aturan yang diketahui penulis benchmark. Bank selection, kontrol C, dan evaluasi konfirmatori belum tersedia.

## Pilot development v0.2

Jalankan perintah berikut dari [checkpoint v0.2](https://github.com/dianzherdiana25-hash/ACE/commit/9128bbf8c272bc1a9aec6be75b4e5e5efaea9154). Replay terikat pada hash kode di checkpoint itu.

```bash
PYTHONPATH=code python3 -m e13.evaluator.pilot --verify evidence/e13/development_pilot_v0.2.json > /tmp/ace-e13-pilot-v02.json
PYTHONPATH=code python3 -m e13.evaluator.capacity > /tmp/ace-e13-capacity.json
cmp evidence/e13/development_capacity_v0.1.json /tmp/ace-e13-capacity.json
```

Fixed memakai satu metode konstan per keluarga. Beam menjelajah mutasi lokal tabel dengan lebar 4, enam putaran, dan plafon 160 proposal. Semua fit memakai worker terisolasi, kontrak input yang sama, serta plafon 30.000 langkah per episode. Fit dan prediksi masih memiliki plafon terpisah. Status `fit` berarti pencarian berakhir dengan AST valid. Jumlah demo yang cocok dan generalisasi dapat berbeda menurut kebijakan.

| Pembanding | Simbol biasa | Simbol ekstrapolasi | Graf biasa | Graf ekstrapolasi | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed | 2/72 | 0/72 | 34/72 | 41/72 | 77/288 |
| Katalog | 31/72 | 20/72 | 26/72 | 32/72 | 109/288 |
| Inferensi simbol + enumerasi graf | 72/72 | 57/72 | 68/72 | 72/72 | 269/288 |
| Beam | 44/72 | 25/72 | 45/72 | 51/72 | 165/288 |

[Data pilot v0.2](../../evidence/e13/development_pilot_v0.2.json) memiliki 96 baris. Replay memeriksa seluruh bidang deterministik, termasuk hash kode dan bank, dan mengizinkan perbedaan waktu/RSS. Akurasi, biaya, kegagalan dan skor per strata dicatat untuk setiap kebijakan. `B*` memerlukan bank selection dan pembanding lengkap.

[Audit kapasitas](../../evidence/e13/development_capacity_v0.1.json) terpisah memakai label publik untuk penyempurnaan dengan contoh tandingan. Untuk masing-masing dari 12 aturan, ditemukan AST hingga empat keadaan yang cocok pada seluruh 145–176 saksi yang diperiksa untuk aturan itu. Auditor tidak mengubah kebijakan pilot. Cakupan ini mengikat saksi publik dan tidak membuktikan ekuivalensi untuk seluruh input atau ketiadaan kapasitas baru pada bank lain.

## Diagnostik batas representasi

```bash
PYTHONPATH=code python3 -m e13.evaluator.boundary > /tmp/ace-e13-boundary.json
cmp evidence/e13/development_representation_boundary_v0.1.json /tmp/ace-e13-boundary.json
```

Dua kasus publik yang terpisah dari pilot menguji batas formal yang sempit. Pada simbol, keluaran menandai setiap penurunan kelima. Lima prefiks dengan 0–4 penurunan berakhir pada simbol yang sama. Untuk setiap pasang prefiks ada kelanjutan identik yang membedakan keluaran mereka. Empat keadaan deterministik tidak cukup karena sekurangnya dua dari lima prefiks harus berbagi keadaan. Pada graf, pertanyaannya adalah biaya minimum lintasan dengan tepat lima sisi. Pada rantai dengan label tetap, lima prefiks nonkosong dari rantai lima sisi semuanya bisa mencapai penerimaan. Setiap pasang bisa dibedakan dengan meneruskan keduanya menggunakan jumlah sisi yang sama hingga hanya satu berjumlah lima. Label sebelumnya sama pada kedua prefiks, dan keadaan tolak tidak bisa mewakili prefiks yang masih dapat diterima.

[Data diagnostik](../../evidence/e13/development_representation_boundary_v0.1.json) menyimpan 20 pasang saksi dan dua AST diagnostik buatan manual. Interpreter dapat mengaktifkan 5–8 keadaan melalui parameter eksplisit pada jalur evaluator. Worker dan evaluator pilot tetap memakai batas default empat. Bukti ini memisahkan daya ekspresi dalam dua kelas mesin pada kontrak saat ini. Eksperimen berikutnya perlu menguji apakah ACE dapat menyintesis serta mewariskan perluasan dari contoh dan mengungguli kontrol.

## Pilot sintesis dan pewarisan v0.1

Jalankan replay hash kode dari [checkpoint pilot](https://github.com/dianzherdiana25-hash/ACE/commit/cad0a457b4dc6e1e80d47dc570e92bf2c4245bba).

```bash
PYTHONPATH=code python3 -m e13.evaluator.transfer_pilot --verify evidence/e13/development_transfer_pilot_v0.1.json > /tmp/ace-e13-transfer.json
PYTHONPATH=code python3 -m unittest discover -s code -p 'test_*.py' -q
```

Solver mengusulkan definisi transisi umum dari subset event dan tabel siklus atau saturasi. Demo sumber menentukan definisi yang diprioritaskan untuk target. Readout target dipelajari kembali dari demo target. Artefak bertipe menyimpan tabel transisi, keluarga dan versi. Hash mendeteksi perubahan dan mengikat proposal ke definisi induk. Penerus menerima JSON artefak dan demo target melalui worker terisolasi baru. Schema v1 memakai satu salinan demo target untuk memenuhi field sumber. Contoh sumber asli tidak dikirim.

Keempat kondisi memakai plafon fit yang sama dan membagi bahan bakar menjadi separuh sumber dan separuh target. Kontrol tanpa perluasan membatasi tabel pada empat keadaan. Kontrol tanpa warisan mengulang pekerjaan sumber dan memulai target tanpa definisi sumber. Sham menggeser skor secara siklik tanpa titik tetap jika ada lebih dari satu kandidat. Nilai asli dan geseran dapat diperiksa, termasuk saat skor seri membuat perlakuan tidak informatif. Fit berhenti pada kandidat pertama yang cocok dengan semua demo target atau saat anggaran habis. Biaya proposal aktual dapat berbeda. Prediksi tetap memiliki plafon langkah tersendiri dan CPU evaluator diukur terpisah.

| Kebijakan | Kapasitas | Terkait | Tak terkait |
| --- | ---: | ---: | ---: |
| C_EXTEND | 32/32 | 29/32 | 7/32 |
| C_NO_EXTEND | 3/32 | 2/32 | 24/32 |
| C_NO_TRANSFER | 19/32 | 1/32 | 29/32 |
| C_SHAM | 19/32 | 3/32 | 23/32 |
| Beam | 3/32 | 10/32 | 29/32 |

[Bukti lengkap](../../evidence/e13/development_transfer_pilot_v0.1.json) berisi 96 fit, hasil per probe, AST beku, langkah, CPU, RSS, saksi demo, dan 24 replay di worker baru. Jejak proposal menyimpan indeks dari `proposal_sha256_by_index` dan skor asli. Kedua kebijakan pembanding lain dari pilot lama juga dicatat bersama fixed dan beam. Dibanding C_NO_TRANSFER, pewarisan memperbaiki 28 probe terkait dan merugikan 22 probe tak terkait tanpa perubahan berlawanan di kedua kelompok. Angka tersebut berkelompok pada empat episode per rezim.

Kasus terkait memakai variasi readout dari motif sumber, sehingga gerbang motif baru di desain utama masih terbuka. Demo target yang sedikit sengaja membuat pemilihan ambigu di diagnostik ini. Hasil memeriksa implementasi sintesis, penggunaan ulang dan risiko prioritas yang salah pada grammar event terbatas. Ekuivalensi semantik program terpelajar tetap `UNKNOWN`. Bank ini seluruhnya publik dan tidak digunakan untuk memilih B*.

## Pilot pembanding terpisah

```bash
PYTHONPATH=code python3 -m e13.evaluator.comparator_pilot --verify evidence/e13/development_closed_comparators_v0.1.json > /tmp/ace-e13-comparators.json
```

Terstruktur menginferensi transisi dan keluaran dari jejak simbolik. Pada graf, setiap struktur transisi menghasilkan kendala pada keadaan penerima berdasarkan biaya demo, lalu solver mencari readout yang memenuhi kendala tersebut. Enumeratif menjelajah readout simbolik menurut jumlah bit aktif dan menghapus duplikat perilaku pada demo. Pada graf, enumeratif menguji subset keadaan penerima dari tabel transisi yang sama. Beam memakai mutasi lokal dan skor demo. Ketiganya tetap dalam batas empat keadaan.

| Pembanding | Development S | Development G | Diagnostik S | Diagnostik G |
| --- | ---: | ---: | ---: | ---: |
| Terstruktur | 129/144 | 140/144 | 16/48 | 17/48 |
| Enumeratif | 71/144 | 140/144 | 16/48 | 17/48 |
| Beam | 69/144 | 96/144 | 16/48 | 26/48 |

[Bukti](../../evidence/e13/development_closed_comparators_v0.1.json) memuat 108 fit serta ukuran CPU worker, CPU penilai, langkah, dan hasil per probe. Enam fit enumeratif mencapai plafon langkah. Dua fit terstruktur memakai AST cadangan setelah tidak menemukan kecocokan lengkap. AST yang valid tetap dinilai. Bank publik memberikan peringkat berbeda. Pemilihan B* dan penguncian biaya menunggu bank selection.

## Protokol selection evaluator

Gerbang ini menerima 12 episode dengan satu blok target per episode dan tiga episode per keluarga dan rezim. Setiap target memiliki empat probe biasa dan empat ekstrapolasi. Bentuk aturan menghilangkan literal dan nama insidental. Target terkait harus berbeda secara struktur sambil berbagi subpohon operasi nontrivial. Target tak terkait harus berbeda dan tidak berbagi subpohon itu. Audit membandingkan bentuk, perilaku pada saksi terbatas, input dengan sisi terurut, dan kecukupan demo terhadap dua bank development dan fixture publik. Ekuivalensi di luar saksi berstatus `UNKNOWN`. Isomorfisme graf umum belum diperiksa.

Jalur evaluator menyimpan generator, oracle, dan label di luar checkout. Worker menerima fit JSON tanpa nama aturan atau label probe. Interpreter evaluator menilai AST beku. Tiga kebijakan tertutup dijalankan dengan urutan acak deterministik. Anggaran per arm 75.000 langkah fit dan 100.000 langkah total, dengan prediksi memakai sisa langkah. CPU fit worker ditambah CPU prediksi dibatasi 1 detik. Wall fit dan prediksi dibatasi 3 detik. Batas memori fit tetap 128 MiB ruang alamat. Waktu CPU proses launcher dan biaya audit/generator terpisah dari skor arm. Probe yang berhenti karena cap tetap dalam denominator. Kegagalan infrastruktur menahan keputusan.

Peringkat memakai akurasi rata-rata berbobot sama untuk simbol dan graf, lalu CPU total yang lebih rendah, lalu ID leksikografis. Catat skor ketiga kebijakan, cap dan fallback, digest bank dan sumber evaluator. Akurasi ini memilih pembanding untuk bank selection. Kontras kausal, ukuran sampel dan penguncian konfirmatori adalah gerbang tersendiri.

### Keputusan selection v1

Pembanding dibekukan pada [`2d9d86c`](https://github.com/dianzherdiana25-hash/ACE/commit/2d9d86c1d7a142f985ea1188532508bca077522c) sebelum generator evaluator ditulis di direktori terpisah. Penulis berasal dari konteks proyek yang sama. Audit 12 blok target meliputi 344 input simbolik dan 393 graf publik yang dicatat, ditambah suite saksi kecil. Canary worker gagal membaca sumber evaluator sesuai batas isolasi. Audit memeriksa ekuivalensi pada domain terbatas.

| Kebijakan | Simbol | Graf | Total |
| --- | ---: | ---: | ---: |
| Beam | 22/48 | 28/48 | 50/96 |
| Enumeratif | 25/48 | 23/48 | 48/96 |
| Terstruktur | 23/48 | 19/48 | 42/96 |

**B* selection internal adalah beam.** Replay dari checkout beku kedua menghasilkan urutan akurasi sama dan mencocokkan seluruh 36 arm pada bidang deterministik. Tiga fit enumeratif mencapai plafon langkah dan enam fit menggunakan AST cadangan karena belum mencapai kecocokan demo lengkap. Seluruh AST valid tetap dinilai. Pada run asli, arm terberat memakai 75.138 langkah total dan sekitar 111 ms CPU fit + prediksi. Seluruh arm berada dalam batas yang dipilih.

[Bukti agregat](../../evidence/e13/selection_summary_v1.json) memuat digest bank, oracle dan kode, peringkat, serta cap. Generator, label dan log per episode tetap di paket evaluator. Paket itu memuat instruksi replay dari checkpoint beku. Selisih dua probe menentukan urutan pada bank internal ini. Evaluasi konfirmatori memiliki split, analisis daya dan penguncian tersendiri.

## Daya dan analisis sebelum konfirmasi

[Rancangan prelock](../../design/e1.3/E13_PRELOCK_v0.1.md) menjelaskan pairing, perlakuan kegagalan, rencana 48 blok, dan kondisi HOLD. Untuk menghitung ulang simulasi dengan NumPy 2.3.5:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=code python3 -m e13.evaluator.power evidence/e13/public_resource_profile_v1.json > /tmp/ace-e13-power.json
cmp evidence/e13/preconfirm_power_v1.json /tmp/ace-e13-power.json
```

Untuk mengulang profil, gunakan `PYTHONPATH` yang menunjuk `code/` dari checkout beku `2d9d86c`, lalu jalankan `python3 code/e13/evaluator/public_resource_profile.py` dari checkpoint perencanaan. CPU dan wall adalah pengukuran yang dapat berubah. Reproduksi selection menggunakan paket evaluator privat dan checkout beku yang sama, dengan [hasil verifikasi](../../evidence/e13/selection_reproduction_v1.json) sebagai pembanding.

## Checkpoint arm evaluator

```bash
PYTHONPATH=code python3 -m unittest e13.test_run_ledger -v
```

Ledger evaluator menyimpan arm terminal secara transaksional dan memakai kunci unik berdasarkan keluarga, rezim, blok, episode, slot seed dan kebijakan. Digest rencana mengikat kunci, urutan, kandidat, bank, oracle dan protokol. Runner kedua ditolak selama ledger aktif. Pada gangguan, arm tanpa catatan terminal tetap menunggu. Kegagalan kandidat yang diklasifikasikan adapter disimpan dengan skor nol dan denominator tetap. Gangguan yang belum diklasifikasi menghentikan run dan dicatat tanpa mengarang skor.

Tes pada fixture publik menjalankan satu arm dalam worker, menyimulasikan interupsi, lalu menyelesaikan tiga arm yang tersisa. Pemanggilan ulang melewati semua arm terminal. Ledger belum mengizinkan atau membuka bank konfirmatori. Adapter, penguncian dan pemeriksaan sumber daya harus lulus sebelum penggunaan itu.

## Runner terkunci dan uji urutan publik

```bash
PYTHONPATH=code python3 -m unittest e13.test_locked_runner -v
```

Dry-run menilai 54 arm dari sembilan kebijakan. Runner mencocokkan digest lock yang diberikan kustodian dengan evaluator, rencana, audit dan ukuran anggaran. Mode konfirmatori menolak bank kecil dan memerlukan bukti audit tersendiri. AST invalid pada respons valid dan timeout setelah marker masuk fase kandidat dapat diklasifikasikan sebagai kegagalan kandidat. Transport rusak, sandbox gagal sebelum marker, atau exit yang tidak dapat diatribusikan menahan run. Profil dry-run hanya mencakup fixture publik, dengan komitmen evaluator nyata tetap berada di luar kandidat.

Pembanding berinformasi menerima kelas hipotesis di sandbox tersendiri. Ia mengurutkan hipotesis secara deterministik, memilih memakai demo target, dan mengembalikan AST beku. Oracle evaluasi membandingkan prediksi terhadap probe di luar worker. Hasil dan keterbatasan ada di [keputusan E1.3](../../design/e1.3/E13_DECISION_v1.md).
