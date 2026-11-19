# Pemeriksaan produk direktur

Ketiga CLI membaca blob Git pada commit yang sama. Semua hasil dicetak ke
stdout sebagai JSON dengan SHA commit dan lokasi sumber. `--repo` memilih
checkout dan `--revision` memilih commit. Direktori kerja dan sumber tak
terlacak berada di luar snapshot. Target symlink dilaporkan ambigu dan
tujuannya tidak dibaca.

## Aset

```sh
python3 tools/director_asset_check.py handover/produk.md \
  --revision HEAD --pr-snapshot handover/pr_snapshot.json
```

Produk JSON memuat daftar `assets` dengan pasangan `kind` dan
`target`. Contoh untuk keempat jenis klaim.

```json
{
  "assets": [
    {"kind": "file", "target": "tools/director_asset_check.py"},
    {"kind": "module", "target": "tools.director_asset_check"},
    {"kind": "function", "target": "tools/director_asset_check.py::verify_assets"},
    {"kind": "pr", "target": "#328"}
  ]
}
```

Pada Markdown gunakan literal code seperti `file:tools/director_asset_check.py`,
`module:tools.director_asset_check`, `function:tools/director_asset_check.py::verify_assets`
atau `pr:#328`. Pemeriksa juga mengenali path berakhiran ekstensi umum,
rujukan PR dan label pada baris **Kombinasi aset** atau **Aset rumah dipakai
ulang**. Label bebas yang memerlukan identitas eksplisit berstatus
`ambiguous`. Klaim prosa di luar bentuk tersebut perlu ditandai dahulu.

Modul dicari sebagai berkas Python atau paket di akar repo dan `code/`.
Nama pendek yang ditemukan di beberapa modul bersifat ambigu. Fungsi
memerlukan nama modul atau path Python dan nama deklarasi yang dipisah
`::`. Deklarasi pada modul atau kelas diperiksa dengan AST. Alias dinamis,
import runtime dan kebenaran perilaku fungsi berada di luar cek ini.

Berkas snapshot PR berisi `repository` seperti `demo/repo` dan
`pull_requests` berupa daftar nomor positif. Status `verified` untuk PR
berarti nomor tercatat pada snapshot tersebut. Rujukan ke repo lain atau
tanpa snapshot yang cocok berstatus `ambiguous`. Jika repo cocok tetapi
nomornya absen, alasan `pr_not_listed_in_snapshot` membatasi temuan
`not_found` pada snapshot yang disediakan.

## Angka

```sh
python3 tools/director_value_check.py handover/produk.json --revision HEAD
```

Produk JSON memakai daftar `numeric_claims`. Satu klaim memuat `label`,
`value` sebagai angka, `source` sebagai path JSON repo, dan `pointer`
sebagai JSON Pointer. Pada Markdown, tulis masing-masing klaim dalam satu
baris seperti berikut.

```markdown
- claim: {"label":"jumlah diterima","value":12,"source":"evidence/demo.json","pointer":"/metrics/accepted"}
```

Perbandingan angka bersifat eksak. Desimal dibaca dengan `Decimal` dan
hasilnya dikodekan sebagai teks angka agar presisi dapat ditelusuri.
Status `mismatch` memuat angka sumber yang berbeda. Field atau berkas
absen berstatus `not_found`. Sumber salah format atau bertipe selain
angka berstatus `ambiguous`. Klaim harus menunjuk field yang sudah memiliki
satuan yang benar. Konversi satuan dan pembulatan perlu terjadi di sumber.

## Siklus

```sh
python3 tools/director_cycle_record.py handover/siklus-1.json \
  handover/siklus-2.json --revision HEAD
```

Berkas siklus memakai `cycle` unik dan positif, `status`, `origin`
sebagai label brain-of-origin, dan `decisions` sebagai daftar objek
`id` dan `decision`. Gunakan ID keputusan samaran. Contoh catatan fiktif.

```json
{
  "cycle": 1,
  "status": "accepted",
  "origin": "brain_fixture",
  "decisions": [{"id": "task-example", "decision": "deferred"}]
}
```

Ekspor mengurutkan tiap siklus dengan nomor, menandai asal atau keputusan
yang belum dicatat, dan menyertakan pointer setiap keputusan. Catatan lama
yang hanya berisi proposal tetap bisa dilacak sebagai siklus dengan
keputusan belum tercatat. Keputusan dapat dikosongkan eksplisit dengan
`decisions: []`.

## Tes fixture

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest -v \
  tools.test_director_audit ace_operational.test_director_loop
```
