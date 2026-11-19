# Audit Git untuk checkpoint self-dev dan branch kerja

`tools/self_dev_git_audit.py` membaca objek Git lokal dan mencetak JSON.
Masukan checkpoint berupa berkas JSON dalam commit yang dipilih.
Gunakan jalur dan revisi checkpoint yang sudah diizinkan untuk diperiksa.
Laporan memuat nama field, tipe, dan identitas commit. Perlakukan nama
field sebagai informasi sumber saat membagikan laporan.

## Perubahan checkpoint

```sh
python3 tools/self_dev_git_audit.py diff fixtures/checkpoint.json \
  --before BASE --after TIP
```

Pilih `BASE` dan `TIP` sebagai ref atau ID commit lokal. Perintah
menghasilkan hitungan dan daftar penambahan, penghapusan, serta perubahan
field. Field memakai JSON Pointer. Objek dinilai rekursif, sedangkan
perubahan array dilaporkan pada pointer array. Representasi angka yang
ekuivalen dan pengurutan kunci objek tidak menambah hitungan. Pointer
kosong mewakili akar. Penambahan atau penghapusan satu subtree dihitung
satu perubahan pada pointer subtree itu.

## Riwayat sebuah field

```sh
python3 tools/self_dev_git_audit.py history fixtures/checkpoint.json \
  --base BASE --tip TIP --field /cycle/status
```

Riwayat membandingkan snapshot berurutan dari base eksklusif sampai
tip inklusif pada jalur induk pertama. Perubahan dari branch samping
muncul ketika terlihat pada commit merge. Peristiwa menyertakan ID
commit dan tanggal committer pada Git. Pointer field dapat memakai
indeks array seperti `/cycles/0/status`. Field hilang dan field dengan
nilai JSON null menghasilkan status yang berbeda. Pergantian nama
berkas terlihat sebagai penambahan atau penghapusan di jalur yang
diperiksa.

## Pemeriksaan commit branch

```sh
python3 tools/self_dev_git_audit.py guard \
  --base BASE --tip TIP --expect HASH_KERJA_1 --expect HASH_KERJA_2
```

Catat ID penuh commit yang disetujui untuk pekerjaan, lalu berikan satu
`--expect` per commit. Untuk branch yang baru dibuka, daftar kosong
menyatakan belum ada commit kerja. Base harus leluhur tip. Semua induk
ditelusuri agar commit yang ikut masuk lewat merge juga diperiksa.
Hasil memuat ID di luar ekspektasi dan ekspektasi yang tidak muncul.
Gunakan ID base terpin dan repo lokal dengan riwayat lengkap untuk
pemeriksaan yang dapat diulang.

Kode keluar `0` menandai audit selesai dan penjaga branch bersih.
Kode `1` menandai temuan penjaga branch. Kode `2` menandai input
atau objek Git yang gagal diperiksa.

## Tes

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q tools.test_self_dev_git_audit
```

Tes membangun repo sintetis di direktori sementara dengan checkpoint,
branch samping, peristiwa merge, dan daftar ekspektasi. Semua perintah
audit dijalankan terhadap fixture itu.
