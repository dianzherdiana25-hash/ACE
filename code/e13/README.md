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
- Worker memakai namespace jaringan baru, lingkungan bersih, direktori sementara, runtime sistem hanya-baca, dan salinan lima modul solver yang dipilih eksplisit. Checkout, kode bank, kredensial dari lingkungan, dan data evaluator berada di luar mount worker. Batas fit 1 detik CPU, 3 detik wall, dan 128 MiB ruang alamat. Ringkasan menampilkan CPU worker, wall peluncuran hingga respons, dan RSS puncak worker. Anggaran penilaian dan biaya total studi masih harus diukur.
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
