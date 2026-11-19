# Audit ketahanan slate dan organ WS-6

Basis source `95cee1209265286df250bebb8a0fea7ae0bcb422`. Slate lokal
dibaca dari [rekaman deployment](../../handover/BRAIN_SLATE_V2_DEPLOYMENT_20261116.md)
dan [kode routing](../../code/ace_operational/brain_endpoints.py). Bridge
merujuk draf #319 pada `0ae6d76de642cf59db9756bdfd03bf1fb8c8f956`.
Kesehatan host, kredensial, kuota tersisa, dan rute yang sedang aktif TIDAK TAHU.

| Jalur | Titik gagal tunggal atau asumsi | Tindakan yang diusulkan untuk review |
|---|---|---|
| Proposer dan validator lokal | Pasangan kode dan bahasa berbagi front/coder secara silang. Hilangnya salah satu menghentikan ratifikasi kedua jenis. | Sediakan pemeriksaan silang identitas organ saat preflight dan pertahankan hasil gagal yang dapat dibedakan dari penolakan judge. |
| Recall semantik | Role embedding dan recall mengarah ke organ sama. Layanan tidur memerlukan health, izin wake, dan keberhasilan start. | Lacak alasan unavailable terpisah untuk health, start, dan timeout. Tetapkan aturan abstain untuk tahap yang membutuhkan embedding. |
| Organ deep | Start eksplisit, bergantung pada kapasitas host yang sama. | Catat ketersediaan sebagai prasyarat gerbang manusia. Jalankan drill papan kerja dengan health dan scheduler tiruan. |
| Host lokal | Rekaman deployment memasang layanan dan watchdog pada satu host. Jadwal idle dan keep-alive bergantung pada host yang sama. | Dokumentasikan prosedur boot dan pemulihan setelah suspensi yang diuji offline. |
| Konfigurasi endpoint | Override per role dibaca saat pemanggilan. Pasangan nama role berbeda masih dapat diarahkan ke endpoint sama. | Periksa benturan alamat secara lokal dengan menampilkan kode temuan, tanpa menyalin nilai konfigurasi. |
| Bridge draf | Relay lokal, spool, koneksi keluar pump, vault dan governor membentuk rantai serial. Header `brain_bridge.py` mendeskripsikan reverse tunnel, sedangkan header pump/relay mendeskripsikan store-and-forward. | Tetapkan satu dokumen transport yang berlaku dan uji spool backlog, timeout, respons terlambat, serta pemulihan pump dengan fixture. |
| Model discovery bridge | Header relay menyatakan health dan daftar model dapat dilayani lokal dari cache untuk kontrak discovery. | Bedakan readiness relay dari ketersediaan upstream dalam runbook dan tes kegagalan. |

Tes yang dijalankan pada basis di atas

```sh
PYTHONPATH=code:. python3 -m unittest ace_operational.test_brain_endpoints.RoutingTests ace_operational.test_brain_endpoints.WakeTests ace_operational.test_brain_endpoints.ParseTests ace_operational.test_brain_registry.RegistryTests -q
```

SELESAI — 16 tes lokal lulus untuk routing, wake tiruan, parsing, dan registry
fixture. Audit draf bridge menggunakan source pada commit terpin.

TERSISA — usulan isi ulang berupa drill dengan relay dan vault tiruan serta
rekonsiliasi dokumentasi transport.

PENGHAMBAT — transisi konfigurasi, pilihan failover, dan pemeriksaan host
aktif tetap berada pada operator yang berwenang.
