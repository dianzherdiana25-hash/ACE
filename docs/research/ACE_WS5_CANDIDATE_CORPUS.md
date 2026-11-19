# Paket kandidat corpus WS-5

Pabrik menggabungkan template kode dan bahasa yang sudah ada menjadi JSONL
`{id, kind, task_kind, instruction}`. Gunakan direktori keluaran baru.

```sh
python3 -m tools.candidate_corpus_batch generate /tmp/ace-future-candidates
python3 -m tools.candidate_corpus_batch validate /tmp/ace-future-candidates/episodes.jsonl
PYTHONPATH=code:. python3 -m unittest tools.test_candidate_corpus_batch tools.test_corpus_lint tools.test_corpus_factory_code tools.test_corpus_factory_lang -q
```

Direktori berisi episode, sidecar spesifikasi dan jawaban sampel bahasa, serta
laporan kualitas yang ditulis terakhir. Simpan jawaban sampel terpisah dari
masukan pembelajaran. Semua keluaran dapat dibuat ulang dengan seed dan jumlah
yang sama. Prefix pada ID menunjukkan jenis tugas.

Batch default menghasilkan 224 kandidat dengan 224 awalan instruksi yang
berbeda setelah normalisasi dan 96 sampel bahasa yang lulus pemeriksaan
kendala. Hitungan keluarga, sebaran domain, dan SHA-256 ada di
[receipt kualitas](../../evidence/candidate_corpus_batch/quality.json).
Ini ukuran mekanis. Validasi jawaban kode, kemiripan semantik, dan overlap
dengan korpus beku belum dinilai. Kapasitas dibatasi pool template yang tersedia.
Kegagalan saat menulis dapat menyisakan direktori parsial tanpa receipt.

SELESAI — generator, validator, receipt, dan 31 tes lokal lulus pada perintah di atas.

TERSISA — usulan isi ulang berupa cek overlap pada korpus pembanding yang
ditunjuk hub dan kalibrasi independen atas rubrik tugas.

PENGHAMBAT — pemilihan korpus pembanding dan keputusan pemakaian berada pada hub.
