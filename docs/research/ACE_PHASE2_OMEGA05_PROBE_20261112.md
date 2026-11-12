# ACE Fase 2 — Probe Isolasi Segar OMEGA-05: Vonis BLOCKED_ENVIRONMENT Gugur (2026-11-12)

Item agenda Direktur Riset #1 dari siklus #2 (Addendum 17). Empat
ronde probe fungsional di host ini; evidence:
`omega05_isolation_probe.json` (ronde 1) dan
`omega05_isolation_probe_round2/3/4.json`.

## Mengapa vonis lama ada

OMEGA-05 dinyatakan BLOCKED_ENVIRONMENT di Fase 1 karena desain
sandbox mewajibkan `bwrap` + seccomp dan biner `bwrap` tidak
tersedia/diinstal di host ini. Vonis itu tentang *satu alat*, bukan
tentang *kemampuan* yang dibutuhkan desain.

## Yang diuji secara fungsional (bukan sekadar keberadaan biner)

| Mekanisme | Hasil | Bukti |
|---|---|---|
| bwrap | tidak ada | ronde 1 |
| Namespace user+mount+pid (`unshare -Urmpf`) | **berfungsi** | proses di dalam berjalan sebagai root termetakan |
| Rootfs terisolasi (bind + `pivot_root`) | **berfungsi** | berkas rahasia host TIDAK terlihat dari dalam; payload menulis ke /work terisolasi dan hasilnya terverifikasi dari luar |
| Namespace jaringan | **berfungsi** | ronde 1 |
| Seccomp via `prctl(PR_SET_SECCOMP)` | gagal EINVAL | profil sandbox luar mencegat jalur prctl |
| Seccomp via syscall `seccomp(2)` | **berfungsi & menegakkan** | filter terpasang (ret 0); `uname` yang diblokir kembali −1/EPERM |
| Landlock (ABI v8) | **berfungsi & menegakkan** | ruleset + aturan path-beneath terpasang; tulis ke direktori yang diizinkan OK, tulis ke luar diblokir EACCES |

Dua temuan proses dicatat apa adanya: probe ronde pertama sempat
menyimpulkan "seccomp gagal" dari jalur prctl saja — kesimpulan itu
keliru dan dikoreksi ronde berikutnya (ini alasan probe harus
fungsional dan berlapis); dan fixture di `/tmp` musnah di antara
ronde karena `/tmp` memang ephemeral di VM ini, sesuai pelajaran
lama — fixture dipindah ke `~/workspace`.

## Keputusan

**OMEGA-05: BLOCKED_ENVIRONMENT dicabut berdasarkan bukti baru.**
Semua kemampuan yang dituntut desain sandbox tersedia di host ini
melalui jalur lain: namespace + pivot_root untuk isolasi FS/proses,
namespace jaringan untuk isolasi network, Landlock untuk kebijakan
akses berkas, dan seccomp(2) untuk penyaringan syscall. Yang belum
ada adalah *implementasinya*: backend `local_sandbox` v2 yang memakai
jalur-jalur ini menggantikan kewajiban bwrap, diuji dengan daftar
uji OMEGA-05 yang asli (isolasi network, batas sumber daya, mutasi
evaluator terblokir, pembersihan proses). Itu tahap pembangunan
berikutnya; status OMEGA-05 sampai saat itu: **TERBUKA — jalur
terverifikasi, implementasi tertunda**, bukan lagi terblokir
lingkungan.
