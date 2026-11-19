# C5 · Generator Laporan-Diri Berkala (`tools/periodic_self_report.py`)

Menghasilkan laporan berkala siap-pemilik (Markdown & JSON) atas gerbang,
vonis terbaru, antrean aktif, dan utang bukti bernama dari sumber model-diri (C1).

## Prinsip Kejujuran
- Strictly read-only terhadap repositori maupun snapshot memori.
- Setiap baris gerbang, vonis, antrean, dan utang bukti wajib menunjuk berkas sumber + SHA-256.
- Berkas operasional yang belum ada di disk dicatat eksplisit `SOURCE_NOT_PRESENT` (nol nilai karangan).

## Pengujian
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_periodic_self_report
python3 tools/verify_sources.py
```
