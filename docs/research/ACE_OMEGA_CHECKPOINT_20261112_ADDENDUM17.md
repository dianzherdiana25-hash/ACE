# ACE Ω — Addendum 17, 2026-11-12: Siklus Direktur #2 & Diagnosis Residu

## Siklus direktur #2 (evidence: director_cycle2.json)

Observasi pasca-pilot (16 fakta) dibaca Qwen3-8B dalam 478 detik;
server on-demand dimatikan sesudahnya (terverifikasi 0 proses).
Hasil: **ACCEPTED — 5 proposal**, tercatat sebagai siklus 2 pada
agenda append-only yang sama (siklus 1 tetap utuh), 5 record memori
tebakan-model baru. Agenda peringkat harness:

1. Mengatasi celah sandbox untuk OMEGA-05 (engineering, 5/4)
2. Mengembangkan keluarga tugas ketiga seperti MiniGrid (measurement, 5/4)
3. Mengidentifikasi defek berinteraksi dalam kasus shown OMEGA-10 (experiment, 5/4)
4. Mengembangkan semesta tugas yang lebih luas (measurement, 5/5)
5. Menggabungkan tumpukan PR draft — *reserved pemilik*, diusulkan saja.

Penilaian pelaksana atas agenda: urutannya dapat dipertahankan,
dengan satu catatan praktis — item #1 adalah penghalang lingkungan,
bukan pekerjaan kode; perlakuan yang benar adalah satu probe
lingkungan segar untuk memastikan tidak ada jalur isolasi yang
terlewat (namespace pengguna, landlock, seccomp via ctypes), lalu
blokirnya dinyatakan ulang dengan bukti baru bila memang tidak ada.
Item #3 adalah pembangunan terkecil dengan daya ungkit terbesar
karena diagnosisnya sudah selesai (di bawah) dan ia membuka jalan
bagi #4 dan #2.

## Diagnosis residu pilot (PR #119, diringkas)

Dugaan "dataran fitness untuk pencarian greedy" yang tertulis di
Addendum 16 **terbukti keliru mekanismenya** (kesimpulan pilotnya
tetap sah: residu tidak terpecahkan ketiga lengan). Probe beam
(0/15, sama seperti greedy) memaksa diagnosis per-tugas, dan
mekanisme sebenarnya adalah **jebakan shown**: di 15/15 tugas
residu, perbaikan satu-defek sempurna pada 2 kasus shown tetapi
salah pada holdout. Solver greedy yang identik memecahkan 15/15
dengan 4 kasus shown pengekspos. Akar masalah: kriteria pemilihan
kasus shown OMEGA-10 tidak menjamin identifiabilitas defek
berinteraksi.

## Urutan tahap berikutnya (dalam mandat)

1. Probe isolasi segar untuk OMEGA-05 (verifikasi, murah, menutup
   item direktur #1 dengan bukti mana pun hasilnya).
2. Amendemen identifiabilitas OMEGA-10: pemilihan shown wajib
   mengalahkan setiap perbaikan parsial sejati; validator
   kurikulum menegakkannya saat generasi (item direktur #3).
3. Keluarga tugas ketiga bergaya grid + semesta lebih keras v2
   (item direktur #2 dan #4), lalu pilot A/B/C v2 dapat
   dipra-registrasi di atas semesta yang punya ruang kepala.
