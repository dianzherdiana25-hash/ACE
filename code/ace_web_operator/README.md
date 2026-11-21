# EVO 0055 · Operator web lokal

Basis `main` `b7dbafb`. Program dibangun dan diuji dengan situs
loopback dan snapshot fixture. Rute serta origin diberikan melalui
kontrak data. Chromium, Node dan Playwright digunakan bila sudah
tersedia lokal.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `browser_engine.py` | Chromium aktual dengan kontrak aksi, penolakan rute lain dan receipt tanpa isi |
| 2 | `workflow_runner.py` | Prasyarat topologis dan stop pada kegagalan dalam satu sesi |
| 3 | `form_filler.py` | Isi kontrol terdaftar tanpa menyertakan nilai di receipt atau submit |
| 4 | `page_extractor.py` | Ekstraksi field HTML bertipe, posisi sumber, dan laporan baris ambigu |
| 5 | `site_explorer.py` | BFS tautan loopback, prefix scope dan frontier yang belum dicakup |
| 6 | `session_manager.py` | Handle vault opak dengan batas waktu, cap dan verifikasi login |
| 7 | `page_watcher.py` | Perbandingan snapshot terikat hash dan perubahan blok terlacak |
| 8 | `web_archiver.py` | Capture loopback berizin, dedup objek dan verifier ZIP |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_web_operator -t code -q
```

Semua perintah memakai `--expect-sha256` dari JSON terkanonisasi
menurut `_contracts.identity`. Receipt mengacu ke konfigurasi, snapshot
atau observasi yang dipakai oleh operasinya.
