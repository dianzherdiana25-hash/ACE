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
| 43 | `bulk_downloader.py` | Unduh dataset fixture berlisensi dengan resume dari objek terverifikasi |
| 44 | `link_validator.py` | Uji fragment snapshot dan status dari probe yang telah disimpan |
| 45 | `heavy_js_extractor.py` | Capture DOM dinamis dengan penanda siap dan field terverifikasi |
| 46 | `scroll_handler.py` | Traversal halaman/gulir dengan dedup, penanda akhir dan batas putaran |
| 47 | `form_state_keeper.py` | Checkpoint field biasa dengan versi, scope dan expiry |
| 48 | `site_health_checker.py` | Probe status, media, isi dan latency lokal berbatas |
| 49 | `analytics_operator.py` | Filter dashboard, snapshot DOM dan rekap kelompok bertambat |
| 50 | `failed_task_escalator.py` | Triage dari receipt, efek dan batas retry sebelum telaah operator |
| 51 | `skill_absorber.py` | Paket kutipan, tujuan dan latihan lokal dengan commitment held-out terpisah |
| 52 | `skill_verifier.py` | Verifier per tujuan dan pengecekan kontaminasi latihan |
| 53 | `skill_registry.py` | Revisi registry dari verifier ulang dan kebijakan atestasi eksternal |
| 54 | `skill_path_builder.py` | Jalur belajar deterministik dengan prasyarat, gap dan anggaran |
| 55 | `skill_composer.py` | Komposisi skill dari port bertipe, versi dan prasyarat terverifikasi |
| 56 | `skill_retention_probe.py` | Perbandingan retensi per tujuan atas suite controlled yang berbeda |
| 57 | `skill_staleness.py` | Usia bukti, perubahan versi dan penurunan retensi |
| 58 | `curriculum_importer.py` | Impor blob dari commit lokal terpin dengan lisensi dan hash |
| 59 | `source_quality_gate.py` | Mutu sumber dari byte aktual, umur, kata, topik dan duplikasi sebelum penyerapan |
| 60 | `skill_board.py` | Papan roadmap, custody registry dan bukti staleness per skill |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_web_operator -t code -q
```

Semua perintah memakai `--expect-sha256` dari JSON terkanonisasi
menurut `_contracts.identity`. Receipt mengacu ke konfigurasi, snapshot
atau observasi yang dipakai oleh operasinya.

## Bukti bench dan roadmap

`fixtures/web_operator_bench.json` menetapkan tujuh tugas loopback.
`fixtures/operator_bench_evidence/operator_bench_report.json` menunjuk
manifest per tugas, request log, receipt workflow dan snapshot dari satu
run Chromium. Verifier membandingkan kembali hash dan ukuran tiap berkas.
Port fixture ephemeral, sehingga receipt dari run baru boleh berbeda
sambil mempertahankan hasil ukur yang sama.

`fixtures/evo0055_skill_roadmap.json` memuat 40 klaster dan 400 kandidat
yang diminta rancangan. Runner penyerapan membangun paket dari materi
yang sudah ada, sedangkan verifikasi memakai data jawaban yang
diberikan. `skill_registry` hanya memberi status `ACQUIRED` untuk
receipt controlled yang dihitung ulang dan ditambatkan pada daftar
atestasi terpisah. Tes fixture memeriksa aturan tersebut.

## Integrasi baca-saja

`ACE_EVO0055_SKILL_BOARD=1` mengalihkan langkah capability report
ke ringkasan papan yang membaca `evo0055_skills/board.json`
pada workspace. `ACE_EVO0055_BOARD_SHA256` adalah hash byte eksternal.
Bundel `ace.web.skill-board-bundle.v1` memuat `plan`, `roadmap`,
`registry`, dan `staleness`. Gerbang mati secara bawaan.
