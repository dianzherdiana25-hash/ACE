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
| 9 | `api_connector_builder.py` | Subset OpenAPI GET menjadi kontrak konektor JSON bertipe |
| 10 | `connector_sandbox.py` | Exchange fixture offline dan pengujian bentuk respons |
| 11 | `web_scheduler.py` | Slot UTC dan catch-up dengan receipt terminal |
| 12 | `consent_handler.py` | Rencana kontrol consent opsional yang bertumpu pada pilihan operator |
| 13 | `captcha_escalator.py` | Deteksi penanda challenge, posisi bukti, dan handoff operator |
| 14 | `evidence_shooter.py` | Capture PNG Chromium setelah assertion, dengan hash dan dimensi |
| 15 | `cross_site_comparator.py` | Bandingkan SKU tersesuaikan dan laporkan stok, umur serta biaya yang tidak lengkap |
| 16 | `cart_preparer.py` | Simulasi kontrol keranjang loopback, anggaran dan pagar checkout |
| 17 | `booking_agent.py` | Seleksi slot reversible dan undo fixture berbasis hash |
| 18 | `web_messenger.py` | Draf di thread loopback, izin terikat isi, dan verifier nilai tanpa send |
| 19 | `web_task_queue.py` | Transaksi antrean banyak situs dengan lease dan penahanan setelah expiry |
| 20 | `site_reliability_tracker.py` | Keandalan per situs dengan denominator yang memisahkan receipt absen |
| 21 | `session_recoverer.py` | Resume baca dengan checkpoint yang diverifikasi ulang dan tanpa replay perubahan |
| 22 | `search_reader.py` | Ekstrak serta ringkas hasil pencarian tersimpan dengan pointer |
| 23 | `fact_verifier_web.py` | Cocokkan nilai dan grup sumber independen dari registry serta snapshot |
| 24 | `page_proof_keeper.py` | Bekukan HTML dan locator, lalu periksa hash manifest serta isi |
| 25 | `phishing_detector.py` | Indikator defensif dari snapshot dengan posisi dan redaksi URL |
| 26 | `politeness_guard.py` | Gerbang robots, interval, kuota per jam dan Retry-After sebelum transport |
| 27 | `dashboard_operator.py` | Inspeksi tab atau filter yang terdaftar serta verifikasi tampilan |
| 28 | `web_sheet_filler.py` | Pemetaan matriks ke alamat A1 dan verifikasi isi grid tanpa submit |
| 29 | `account_exporter.py` | Ekspor snapshot akun sendiri dengan grant, proyeksi field dan TTL |
| 30 | `web_ops_bench.py` | Chromium pada tujuh tugas tertutup dan arsip hash per kasus |
| 31 | `shop_operator.py` | Audit stok dashboard dengan verifikasi toko dan bukti per SKU |
| 32 | `catalog_manager.py` | Revisi snapshot dan retire produk dengan preimage per SKU |
| 33 | `content_uploader.py` | Paket draft terjadwal, validasi byte aset dan preflight lokal |
| 34 | `comment_drafter.py` | Draf berkategori dan berbahasa dengan sumber fakta terverifikasi |
| 35 | `mention_watcher.py` | Alias terdaftar, kecocokan Unicode, jendela dan dedup snapshot |
| 36 | `review_collector.py` | Normalisasi rating lintas skala dengan dedup serta konflik eksplisit |
| 37 | `spec_comparator.py` | Perbandingan field berbasis unit, toleransi Decimal dan sumber |
| 38 | `report_submitter.py` | Rekap periode bersumber dan rehearsal pengisian tanpa submit |
| 39 | `multi_account_guard.py` | Marker profil terpisah, origin bound, symlink dan profil silang ditahan |
| 40 | `tos_watcher.py` | Jejak perubahan klausul berlabel dan selisih kata |
| 41 | `thread_archiver.py` | Arsip utas yang disetujui dengan redaksi dan reply chain |
| 42 | `price_research_runner.py` | Slot UTC riset harga dan delta dari snapshot yang ada |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_web_operator -t code -q
```

Semua perintah memakai `--expect-sha256` dari JSON terkanonisasi
menurut `_contracts.identity`. Receipt mengacu ke konfigurasi, snapshot
atau observasi yang dipakai oleh operasinya.
