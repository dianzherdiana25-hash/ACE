# Eksekusi sprint ACE

Checkout operasional dipulihkan dari GitHub dengan pencocokan Git blob, tree, dan commit. HEAD pemulihan `2438eeb` memiliki 286 berkas terlacak. Riwayat lokal pada checkout pemulihan memiliki batas shallow di pembekuan `fb9ac72`. Bukti dan status pemulihan dua host sebelumnya tetap historis.

Untuk memeriksa worker E1.4n pada checkout terkini:

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 15 --heartbeat 5 --log WORK/preflight.log -- python3 tools/ace_sprint_preflight.py
```

Runner sprint membungkus runner beku. `COMPLETE` berarti keluar nol. `FAILED` berarti perintah gagal. `TIMEOUT` berarti batas waktu habis dan grup proses dihentikan. `BLOCKED_ENV` berarti peluncuran gagal karena jalur atau izin lingkungan. `BLOCKED_APPROVAL` hanya dicatat bila platform sungguh mensyaratkan persetujuan. Tidak ada retry otomatis. Gunakan ledger yang sama setelah kegagalan parsial dan ledger berbeda untuk replay.

Freeze historis memakai status `OK` yang setara dengan `COMPLETE`. Log terminal mentah dipertahankan pada bukti. Model worker menggunakan input DSL bertipe, bukan kode kandidat. Protokol publik tidak mengubah data tersegel.
