# ACE E1.4b — hasil pilot pertanyaan pembeda

**GO ke replikasi development publik.** Pada strata yang dirancang memuat saksi, pilihan berdasarkan ketidaksepakatan menang di keenam episode dan mengungguli kontrol satu label acak di kedua keluarga. Pemilihan label hanya membantu bila pool mengandung informasi yang dapat dipakai dan basis representasi dapat memuat jawaban.

[Protokol dan kode dibekukan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/2391caf2c49d8837dd8cd6eced2626ab8bd1e6d4). [Bukti per arm](../../evidence/e14/query_pilot_v1.json)

| Strata | Tanpa label tambahan | Satu label acak, nilai harapan | Satu label aktif |
| --- | ---: | ---: | ---: |
| Pool bersaksi | 24/48 | 30/48 | 48/48 |
| Kurang informasi | 24/48 | 24/48 | 24/48 |
| Di luar basis | 22/48 | 22,5/48 | 24/48 |

Pada pool bersaksi, dua dari delapan pertanyaan sengaja berupa saksi. Pemilih menemukan ketidaksepakatan pada seluruh enam episode dan memilih salah satu saksi. Pada kedua strata lain, pemilih kembali ke acak karena kedua model sepakat. Selisih pada strata di luar basis muncul dari pilihan acak itu. Audit atas seluruh tabel hitung dan kata urutan menunjukkan keduanya tidak bisa membedakan keempat pasangan pada keenam episode di luar basis. Masing-masing keluarga DSL memiliki plafon 4/8 pada pasangan itu, berapa pun label yang ditambahkan selama basis tetap sama.

Seluruh 198 fit berada dalam batas fase. CPU solver dan pemilih tertinggi untuk jalur aktif sekitar 146 ms pada mesin uji. Nilai harapan acak dihitung dengan menjalankan tiap kemungkinan cabang satu-label secara independen. Tiap hasil aktif berpasangan dengan cabang kontrol yang menerima label persis sama. Seluruh 18 episode dan hasil deterministik cocok pada replay. Pemeriksaan awal salah membandingkan tuple di memori dengan array JSON. Dua laporan dari kode beku cocok setelah serialisasi yang sama. Perbaikan verifier hanya mengubah pembandingan dan mempertahankan hasil skor asli.

## Reproduksi

Jalankan `PYTHONPATH=code python3 -m e14.query_pilot > /tmp/ace-query-replay.json` pada checkout freeze `2391caf`. Pada checkout yang memuat verifier hasil, jalankan `PYTHONPATH=code python3 -m e14.query_pilot --compare evidence/e14/query_pilot_v1.json /tmp/ace-query-replay.json`. Pengukuran waktu dan RSS boleh berbeda.

Pilot ini menguji pool rekayasa kecil dan graf rantai. Langkah selanjutnya menguji pool yang dibangkitkan tanpa memilih pertanyaan berdasarkan label atau prediksi kandidat.
