# ACE Ω — Addendum 19, 2026-11-12: OMEGA-05 Selesai Secara Substantif di Host Ini

Backend sandbox v2 terbangun dan **lulus daftar uji live OMEGA-05
yang asli di host ini**. PR #121 (draft, bertumpuk di atas #120).

## Implementasi (`local_sandbox_v2.py`)

Kontrak resi dan program probe/runner **persis** milik v1 (diimpor,
bukan ditulis ulang) — yang diganti hanya peluncurnya, disusun dari
mekanisme yang dibuktikan probe Addendum 18:

- namespace user+mount+pid+net via `unshare` (payload = PID 1);
- rootfs pivot_root dari bind read-only (Python sistem, stdlib,
  lib platform, /candidate & /evaluator read-only, tmpfs /tmp
  terbatas, empat berkas device) — jalur host tidak ada di dalam;
- denylist seccomp yang sama dengan v1 (nomor syscall terverifikasi
  ke header host), dipasang lewat **syscall seccomp(2)** karena jalur
  prctl dicegat profil luar;
- rlimit, anggaran keluaran, dan disiplin kill sisi-host ala v1.

## Hasil penerimaan (ACE_RUN_SANDBOX_TESTS=1, di host ini)

9/9 test v2 lulus, termasuk seluruh daftar live: probe isolasi
semua hijau (host tersembunyi, env bersih, PID namespace privat,
tanpa antarmuka jaringan, socket & fork ditolak EPERM, kedua pohon
read-only), digest input tidak berubah, kegagalan nyata terlaporkan,
flood/hang berhenti dengan alasan anggaran yang benar, penjaga
no-tests dan early-exit utuh. Sapuan paket penuh: **208 test OK**.

Status paket: **OMEGA-05 tuntas secara substantif di host ini**
(vonis BLOCKED_ENVIRONMENT Fase 1 tertutup oleh bukti, bukan oleh
penurunan standar — daftar ujinya sama). Yang sengaja belum
dilakukan: `LocalRepoWorkflow` masih memakai kelas v1 sebagai
bawaan; pengalihan ke v2 dan menjalankan ulang OMEGA-03 di bawah
isolasi sungguhan adalah tahap integrasi tersendiri.
