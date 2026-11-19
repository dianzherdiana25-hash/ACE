# Daftar periksa migrasi dan instans WS-7

1. Pilih berkas yang sudah ditinjau dan buat bundle dengan `portability_pack`.
   Simpan digest manifest dari sumber tepercaya secara terpisah. Hindari
   rahasia, ledger, state aktif, database terbuka, dan bukti tersegel.
2. Siapkan konfigurasi source dan target dengan `instance_kit`, keduanya
   berstatus fondasi nonaktif. Pilih direktori, port dan namespace lock
   terpisah. Buat direktori workspace target yang dimiliki operator.
3. Jalankan drill terhadap bundle yang disetujui. Periksa digest pada receipt
   dan pastikan preview telah dibersihkan. Ulangi jika pilihan file berubah.
4. Penyalinan nyata dilakukan sebagai tugas terpisah setelah tinjauan isi,
   backup, penilaian toolchain dan uji akses. Aktivasi membutuhkan keputusan
   operator dan pengukuran kapasitas target.

```sh
python3 -m tools.migration_rehearsal bundle.tar.gz source.json preview.json \
  --manifest-sha256 "$APPROVED_SOURCE_MANIFEST_SHA"
PYTHONPATH=code:. python3 -m unittest tools.test_migration_rehearsal tools.test_portability_pack tools.test_instance_kit -q
```

Pemeriksa menggabungkan verifikasi byte, pin manifest dan pemeriksaan isolasi,
lalu melakukan restore sementara dalam workspace target tanpa memodifikasi
berkas di luarnya. Pakai bundle lokal yang sudah ditinjau. Pembaca bundle
memuat payload ke memori. Uji ini tidak menilai database hidup, kapasitas
host, proses berbagi target workspace, atau aktivasi layanan.

SELESAI — 8 tes lokal lulus, termasuk fixture direktori dan arsip, bundle
keliru meskipun konsisten internal, konflik port, dan konfigurasi aktif.

TERSISA — usulan isi ulang berupa checklist backup/restore SQLite yang
dipisah dari state pengukuran dan uji platform target pilihan hub.

PENGHAMBAT — pin bundle produksi, verifikasi lokasi, dan jadwal aktivasi
perlu masukan operator untuk instans nyata.
