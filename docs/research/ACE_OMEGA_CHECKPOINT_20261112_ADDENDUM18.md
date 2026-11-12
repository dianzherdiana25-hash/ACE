# ACE Ω — Addendum 18, 2026-11-12: OMEGA-05 — Vonis BLOCKED_ENVIRONMENT Dicabut

Item direktur siklus #2 nomor 1 ditutup dengan bukti baru. Dokumen:
`ACE_PHASE2_OMEGA05_PROBE_20261112.md` (PR #120); evidence empat
ronde probe di `omega05_isolation_probe*.json`.

## Ringkasnya

Vonis Fase 1 bertumpu pada satu biner yang hilang (`bwrap`). Probe
fungsional berlapis membuktikan kemampuan yang dituntut desain
sandbox **ada semua di host ini** melalui jalur lain:

- namespace user/mount/pid berfungsi; rootfs bind + pivot_root
  menyembunyikan berkas host dari payload (terverifikasi dua arah);
- namespace jaringan berfungsi;
- filter seccomp terpasang dan menegakkan lewat syscall `seccomp(2)`
  (jalur prctl dicegat profil luar — kesimpulan tergesa ronde
  pertama dikoreksi terbuka di dokumen);
- Landlock ABI v8 menegakkan kebijakan path (tulis diizinkan lolos,
  tulis di luar diblokir).

## Status baru

**OMEGA-05: BLOCKED_ENVIRONMENT dicabut → TERBUKA, jalur
terverifikasi, implementasi tertunda.** Tahap pembangunan berikutnya
adalah backend `local_sandbox` v2 (unshare + Landlock + seccomp(2))
yang diuji dengan daftar uji OMEGA-05 asli — termasuk menjalankan
ulang alur OMEGA-03 (yang dulu "isolasi terdegradasi") di bawah
isolasi sungguhan bila backend itu lulus.
