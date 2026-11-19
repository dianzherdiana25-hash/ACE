# Katalog pola berversi

`tools/pattern_catalog.py` menerima berkas JSONL `pattern_distilled` keluaran distiler. Pilih berkas historis yang sudah dialokasikan untuk pekerjaan ini. Semua subperintah membaca masukan dan menulis ke stdout.

```sh
python3 tools/pattern_catalog.py build a.jsonl b.jsonl > catalog-v1.json
python3 tools/pattern_catalog.py export catalog-v1.json > combined-v1.jsonl
python3 tools/pattern_catalog.py build a.jsonl c.jsonl --previous catalog-v1.json > catalog-v2.json
python3 tools/pattern_catalog.py diff catalog-v1.json catalog-v2.json > changes.json
```

## Identitas dan asal pola

Kunci identitas adalah pasangan `source_episode` dan `provenance.output_sha256`, yang juga dipakai distiler dan pengusul kurikulum. Dua pola dengan identitas sama digabung jika isi sama setelah lokasi `evidence_file` dan `entry_index` dikesampingkan. Snapshot menyimpan semua rujukan berkas dan baris katalog. Rekaman untuk ekspor dipilih menurut kelengkapan rujukan, lalu urutan JSON kanonik. Jika isi berbeda, seluruh varian identitas dicatat sebagai konflik bersama SHA-256 isi dan rujukan baris. Ekspor berisi identitas yang bebas konflik dalam format JSONL yang dapat dibaca `curriculum_propose.py`.

## Skor kelengkapan

Skor 0–100 dihitung dari tiga bagian. Ukuran tercatat pada entri pola sehingga tiap komponen bisa dihitung ulang.

| Bagian | Maksimum | Perhitungan |
| --- | --- | --- |
| Provenance | 40 | Delapan poin masing-masing untuk nama berkas bukti, nomor entri positif, jenis tugas yang sama, SHA-256 keluaran, dan SHA-256 instruksi. Hash keluaran wajib untuk identitas. |
| Panjang | 20 | Dua puluh poin jika panjang JSON kanonik dalam karakter Unicode tidak melebihi `--max-chars`, default 2048. |
| Ciri tugas | 40 | Sepuluh poin untuk jenis tugas yang diketahui, sepuluh untuk signature berisi ciri, dan dua puluh jika minimal ada satu kata kunci atau penanda kendala. Jumlah kata kunci dan kendala unik dilaporkan. |

Skor menunjukkan kelengkapan struktural. Rujukan provenance diperiksa bentuknya. Arsip yang dirujuk dan efektivitas pola memerlukan verifikasi terpisah.

## Rekam versi

Snapshot pertama bernomor 1. Opsi `--previous` mengambil nomor versi sebelumnya dan menambah satu, lalu menyimpan SHA-256 snapshot sebelumnya. Hash dihitung atas JSON dengan kunci terurut, karakter Unicode asli, dan spasi standar Python, tanpa newline penutup. Masukkan seluruh berkas yang diinginkan pada setiap build. Snapshot sebelumnya memberi nomor dan tautan hash. Diff menampilkan penambahan, penghapusan, dan perubahan per identitas untuk pola serta konflik, dengan daftar field yang berubah.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest tools.test_pattern_catalog tools.test_pattern_distill
```
