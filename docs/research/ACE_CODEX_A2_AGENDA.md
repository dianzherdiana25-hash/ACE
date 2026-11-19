# Garis A2 — usulan agenda dari aset dan bukti handover

`tools/agenda_candidates.py` menghasilkan JSONL `ace.agenda-proposal.v1` ke stdout. Setiap usulan punya `proposal_id`, `brain_of_origin: codex-proposal`, `kind`, `title`, serta `sources`. Statusnya `proposal_only`, dengan `claim_made: false` dan `requires_human_validation: true`. Keputusan agenda tetap pada engineer utama.

## Kombinasi aset

```sh
python3 tools/agenda_candidates.py assets \
  --assets-file handover/snapshot_assets.json \
  --register-snapshot handover/archived_combinations.jsonl
```

Gunakan snapshot yang disiapkan untuk penelaahan. Aset mengikuti bentuk masukan `tools/opportunity_register.py`, yaitu objek JSON dengan ID aset sebagai kunci dan objek `kind` serta `name` sebagai nilai. Masukan snapshot kombinasi adalah JSONL dengan setidaknya `combination` per objek. Berkas kosong menyatakan snapshot tanpa entri. CLI memerlukan path yang diberikan secara eksplisit dan menyelesaikannya di dalam akar repo. Opsi `--repo` dipasang sebelum subperintah bila akar repo berbeda dari direktori kerja.

Pemindai memakai generator pasangan di `tools/opportunity_register.py` pada aset jenis `tool`, `corpus`, dan `engine`. Ia membentuk semua pasangan ID berbeda dalam tiga jenis tersebut. Jangkar pasangan mencakup setiap aset yang lolos filter, termasuk pasangan dalam jenis yang sama. Pasangan persis yang tercatat di snapshot dikeluarkan tanpa memandang urutan atau statusnya. Entri tiga aset merupakan kombinasi berbeda dari pasangan. Kata *belum tercatat* bergantung pada kelengkapan snapshot. Sumber setiap usulan memuat ID kedua aset dan lokasi snapshot kombinasi.

## Tindak lanjut dari verdict

```sh
python3 tools/agenda_candidates.py failures \
  handover/EVO_0005_KONSOLIDASI_20261116.md \
  handover/EVO_0006_KONSOLIDASI_20261117.md
```

Parser mencari deklarasi `label: TOKEN` pada judul, butir daftar, baris tebal, atau baris berkepala `Verdict:` maupun `Vonis:`. Bentuk judul `Label (VONIS: TOKEN)` juga terbaca. Label generik `Verdict` dan `Vonis` memakai stem nama berkas sebagai pengenal. Blok kode dan kutipan dilewati. Daftar token eksplisit ada di `VERDICTS`, termasuk `NOL`, `NOT_PASSED`, `TIDAK LOLOS`, dan `INSTRUMEN_TIDAK_CUKUP`. Teks naratif dan label di luar konvensi tersebut perlu ditelaah manual.

Usulan mencatat token verdict, path, dan nomor baris berbasis satu. Pengulangan label dan verdict yang sama di satu berkas menjadi satu usulan dengan beberapa rujukan. Bentuk huruf dan tanda baca pada label diabaikan untuk penggabungan. ID mengikuti path, label yang dinormalisasi, dan token kanonis. Pergeseran nomor baris mengubah rujukan sambil mempertahankan ID.

Garis C6 dapat memakai fungsi `scan_failure_documents` dengan pemetaan path relatif repo ke teks Markdown. Fungsi menerima masukan di memori dan mengembalikan usulan dengan kontrak yang sama seperti CLI.

## Prioritas

```sh
python3 tools/agenda_candidates.py prioritize handover/proposals_for_review.jsonl
```

Subperintah menerima satu atau lebih berkas JSONL usulan. Urutannya dimulai dari penghambat pengukuran (`blocked`), diikuti kegagalan eksplisit (`failure`), hasil null (`null`), dan pasangan aset (`asset_pair`). Aturan ini mendahulukan perbaikan prasyarat pengukuran dan tindak lanjut yang sudah memiliki verdict. Di dalam satu jenis, `proposal_id` menaik menjadi pemutus seri. Peringkat dimulai dari satu dan dihitung ulang. Duplikat identik diringkas. ID yang sama dengan isi berbeda menghasilkan galat. Urutan ini adalah usulan jadwal penelaahan.

## Tes lokal

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q \
  tools.test_agenda_candidates tools.test_opportunity_register
```
