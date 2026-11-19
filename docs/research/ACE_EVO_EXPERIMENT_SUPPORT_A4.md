# Infrastruktur eksperimen A4

Ketiga CLI membaca berkas lokal. Templat, tabulasi, dan perbandingan dicetak
ke stdout. Pengemas menulis satu salinan baru di lokasi yang dipilih operator.

## Templat praregistrasi dari rancangan

```sh
python3 tools/evo_prereg_draft.py /path/rancangan.md
```

Rancangan memakai judul `# RANCANGAN EVO NNNN`. Generator membuat bagian
§0–§5 sesuai susunan templat EVO yang sudah ada. Ia menyalin bagian dengan
judul yang dikenali, seperti Hipotesis, Kalibrasi, dan Sketsa lengan,
sebagai kutipan bernomor baris. SHA-256 mengikat kutipan ke revisi masukan.
Isian keputusan tersedia di setiap bagian untuk diperiksa dan diisi dalam
review. Hasil berstatus DRAF.

## Bundel run offline

```sh
python3 tools/seal_run.py pack /path/salinan-run /path/bundel-baru
python3 tools/seal_run.py verify /path/bundel-baru --manifest-sha256 HASH
```

`pack` memerlukan sumber reguler yang sudah berhenti berubah, tanpa
`manifest.json` pada akar. Direktori tujuan harus baru, dengan induk yang
sudah ada dan berada di luar pohon sumber. Mode ini menyalin berkas lalu
memakai skema `ace.evidence-bundle.v1` dari `pack_evidence.py`.
Manifest mencatat path, ukuran, dan SHA-256 tiap berkas. Pin manifest untuk
verifikasi diperoleh dari field `manifest_sha256` pada keluaran `pack`
dan disimpan secara independen.

`verify` memeriksa berkas hilang, berkas tambahan, perubahan ukuran atau
digest, dan struktur manifest. Ketidakcocokan keluar dengan status 2.
Verifikasi tanpa pin memeriksa konsistensi terhadap manifest lokal.
Pengemasan dan verifikasi mengasumsikan direktori yang tenang tanpa
penulisan serentak.

## Tabel vonis lintas paket

```sh
python3 tools/evo_results.py verdicts \
  handover/EVO_0004_KONSOLIDASI_20261116.md \
  handover/EVO_0005_KONSOLIDASI_20261116.md \
  handover/EVO_0006_KONSOLIDASI_20261117.md
```

Judul tingkat satu memberi ID EVO. Parser mendukung judul vonis eksplisit
tingkat paket dan judul bernama seperti `## Gate G2 — Vonis: NOL`,
`## Blok B — audit (PASS)`, dan `### B4 — audit: ERROR (probe)`.
Hasil mencantumkan berkas dan baris untuk pemeriksaan ulang.
Judul gate tanpa vonis yang dikenali ditandai TIDAK TAHU. Gunakan
`--json` untuk membaca baris terstruktur dan bagian yang belum terbaca.
Label dalam prosa di luar judul perlu diperiksa secara manual.

## Delta metrik bernama

```sh
python3 tools/evo_results.py compare /path/sebelum.md /path/sesudah.md \
  --metrics /path/selector.json
```

Setiap entri selector menyebut metrik, satuan, dan letak angka eksplisit
di kedua revisi. Baris dan kolom mulai dari satu. Contoh sintetis berikut
mengambil desimal dari sel seperti `3/8 = 0.375`.

```json
[
  {
    "name": "rasio_lolos",
    "unit": "proporsi",
    "before": {"line": 20, "column": 4, "format": "equals_decimal"},
    "after": {"line": 26, "column": 5, "format": "equals_decimal"}
  }
]
```

Format `decimal` adalah default. `decimal_comma` menerima koma sebagai
pemisah desimal. Tanpa kolom, selector membaca angka pada satu baris penuh.
Gunakan `null` pada sisi yang belum punya angka. Keluaran mencatat
`line_sha256` untuk mengunci selector ke baris yang sudah diperiksa.
Delta adalah nilai sesudah dikurangi nilai sebelum dalam satuan yang
ditetapkan pemeriksa. Pemeriksa tetap mencocokkan definisi populasi dan
satuan metrik sebelum membandingkan.

## Tes

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q \
  tools.test_evo_experiment_support tools.test_pack_evidence tools.test_evo_scaffold
```
