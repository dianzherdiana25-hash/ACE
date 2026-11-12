# Pilot A/B/C v2 — Hasil (Fase 2, tahap 9)

Pra-registrasi: eksperimen `pilot-abc-v2` di kernel bukti baru
(`pilot/kernel-v2`), protocol_hash
`babfd459b35ddaa188f8777bd2e051a8c32cb9f8941cafaf283ae2ce919ed905`,
canary `CANARY-PILOT-ABC-V2`. Bukti mentah:
`evidence/pilot_abc_v2_report.json`. Semesta: kurikulum hasil
amendemen identifiabilitas (Addendum 20), keluarga pricing+shipping,
level 1–4 (termasuk adversarial), 3 repetisi × 50 seed; held-out
220 tugas (pricing 135, shipping 85 — target contoh PRD terpenuhi).

## Angka

| Lengan | Held-out terselesaikan |
|---|---|
| A — Fixed | **220/220 (100%)** |
| B — Adaptive | **220/220 (100%)** |
| C — Evolutionary | **220/220 (100%)** |
| Null (kontrol negatif) | 0/220 |

Audit kernel: **CLEAN**. Δ(C−A) = 0.0pp.

## Interpretasi — hipotesis TIDAK DIDUKUNG, dan langit-langitnya berpindah

Hasilnya nol lagi, tetapi karena alasan yang berlawanan dengan v1.
Di v1 substrat jenuh di 95% dan residualnya adalah perangkap sinyal.
Di v2, amendemen shown (identifiabilitas + jalur gradien) menaikkan
lantai sinyal sampai **lengan tetap pun menyelesaikan seluruh
semesta, termasuk level adversarial**. Perbedaan organisasi pencarian
tidak punya ruang untuk mengekspresikan diri.

Kesimpulan terukur: untuk kelas tugas *perbaikan defek setingkat
ekspresi*, sinyal shown yang teridentifikasi + dapat didaki membuat
perbaikan greedy sederhana bersifat saturatif. Hambatan bukti G2
bukan lagi sinyal — melainkan **kelas tugasnya**. Ruang kepala
(headroom) harus datang dari tugas yang solusinya bukan suntingan
lokal.

## Keluarga grid: lantai terukur

Keluarga ketiga (grid/BFS) terbangun penuh di kurikulum dengan
seluruh mesin validitas + amendemen identifiabilitas berlaku.
Pengukuran asap dengan solver generik yang ada (token-search,
anggaran 400): **0/58 tugas terselesaikan di holdout** — defek BFS
bersifat struktural (konjungsi yang hilang, elemen tuple arah,
empat arah diagonal) dan berada di luar jangkauan substitusi token
tunggal. Keluarga ini adalah kandidat semesta berikutnya, tetapi ia
belum punya substrat perbaikan — operator tingkat pernyataan/struktur
adalah pekerjaan tahap tersendiri, bukan sesuatu yang boleh
diklaim ada.

Status gerbang tidak berubah: G2 tetap MEASURED-null; G1
NOT_ASSESSED; OAIE belum terbukti.
