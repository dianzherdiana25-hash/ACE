# Antrean produksi lokal KBM WS-1

`tools.kbm_production_queue` memecah naskah Markdown, memeriksa bab dan
sampul dengan jalur ketat WS-3, lalu menyimpan manifest dan byte paket
dalam satu transaksi SQLite. Status awal adalah `WAITING_FOR_HUMAN_REVIEW`.
Percobaan ulang dengan isi sama mempertahankan satu entri. Isi berubah
membuat entri baru. Direktori dan berkas antrean dikelola operator lokal.

```sh
python3 -m tools.kbm_production_queue --queue /path/local/queue.sqlite3 enqueue naskah.md cover.png
python3 -m tools.kbm_production_queue --queue /path/local/queue.sqlite3 list
python3 -m tools.kbm_production_queue --queue /path/local/queue.sqlite3 export-review "$ITEM_ID" /path/local/review-new
PYTHONPATH=code:. python3 -m unittest tools.test_kbm_production_queue tools.test_kbm_pipeline tools.test_kbm_cover_wiring tools.test_kbm_pack_check tools.test_kbm_split -q
```

Gunakan parent direktori antrean yang privat. Ekspor memverifikasi manifest
dan isi, lalu menyalin paket ke direktori lokal baru berizin privat. Review
editorial, verifikasi aturan platform, dan keputusan publikasi adalah gerbang
manusia. Pemeriksaan sampul memakai header gambar, dimensi, rasio dan ukuran
berkas. Ambang kata/byte dapat disetel untuk fixture dan perlu dicocokkan
dengan kebijakan operator pada naskah nyata.

SELESAI — alur naskah sampai antrean lokal dan ekspor review. Sebanyak
23 tes lokal lulus, termasuk retry paralel, hash paket, penolakan cover/
bab gagal, file korup, dan perlindungan direktori ekspor yang sudah ada.

TERSISA — usulan isi ulang berupa kurasi checklist editorial dari
kebijakan terverifikasi dan latihan reviewer pada naskah yang diizinkan.

PENGHAMBAT — input editorial nyata dan izin publikasi berada pada operator.
