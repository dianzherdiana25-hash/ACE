# Eksekusi sprint ACE

Checkout operasional dipulihkan dari GitHub dengan pencocokan Git blob, tree, dan commit. HEAD pemulihan `2438eeb` memiliki 286 berkas terlacak. Riwayat lokal pada checkout pemulihan memiliki batas shallow di pembekuan `fb9ac72`. Bukti dan status pemulihan dua host sebelumnya tetap historis.

Untuk memeriksa worker E1.4n pada checkout terkini:

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 15 --heartbeat 5 --log WORK/preflight.log -- python3 tools/ace_sprint_preflight.py
```

Runner sprint membungkus runner beku. `COMPLETE` berarti keluar nol. `FAILED` berarti perintah gagal. `TIMEOUT` berarti batas waktu habis dan grup proses dihentikan. `BLOCKED_ENV` berarti peluncuran gagal karena jalur atau izin lingkungan. `BLOCKED_APPROVAL` hanya dicatat bila platform sungguh mensyaratkan persetujuan. Tidak ada retry otomatis. Gunakan ledger yang sama setelah kegagalan parsial dan ledger berbeda untuk replay.

Freeze historis memakai status `OK` yang setara dengan `COMPLETE`. Log terminal mentah dipertahankan pada bukti. Model worker menggunakan input DSL bertipe, bukan kode kandidat. Protokol publik tidak mengubah data tersegel.

## Regresi publik dari snapshot bersih

Sebagian fixture historis E1.4d–f ada dalam arsip terverifikasi di Git, sehingga discovery langsung hanya mencakup tes yang tersimpan sebagai berkas Python. Untuk memulihkan suite historis, jalankan ini dari checkout branch penelitian dengan Python 3.12 dan Bubblewrap yang sudah melewati preflight. Pilih direktori log yang berada di luar snapshot.

```bash
set -euo pipefail
ace_root="$PWD"
ace_snapshot=$(mktemp -d)
ace_logs=$(mktemp -d)
git archive HEAD | tar -x -C "$ace_snapshot"
python3 tools/ace_sprint_runner.py --timeout 20 --heartbeat 5 --log "$ace_logs/restore.log" -- python3 tools/ace_restore_public_regression.py "$ace_snapshot" | tee "$ace_logs/restore.terminal.json"
cd "$ace_snapshot"
PYTHONPATH=code python3 "$ace_root/tools/ace_sprint_runner.py" --timeout 210 --heartbeat 20 --log "$ace_logs/regression.log" -- python3 -m unittest discover -s code/e14 -t code -v | tee "$ace_logs/regression.terminal.json"
```

Pemulihan hanya menyalin anggota arsip publik yang diizinkan ke snapshot sementara dan memeriksa berkas yang sudah ada sebelum menulis. Tiga belas hasil pemulihan sama byte demi byte dengan lingkungan regresi sprint. Log tiap tahap tersedia di [bundel regresi](../evidence/e14/ace_sprint_regression_logs_v1.json.gz).
