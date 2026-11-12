# ACE Ω — Addendum 12, 2026-11-12: OMEGA-11 Lab Penalaran & Hasil Eksperimen Kontras

Paket terakhir Fase 1. Bergantung pada OMEGA-03, OMEGA-06, OMEGA-09 —
semua terpenuhi.

## Yang dibangun (PR #114, draft, bertumpuk di atas #113)

`code/ace_operational/reasoning_lab.py` — harness kontras formal untuk
tugas OMEGA-10, tiga strategi perbaikan di bawah anggaran evaluasi yang
IDENTIK:

- **grammar**: komposisi operator edit AST yang diauthor (flip batas di
  konstanta yang disebut spec, tukar basis ke variabel akumulator,
  geser konstanta), digabung greedy menaiki kasus shown.
- **token-search**: proposal representasi yang dikontraskan — kode
  sebagai aliran token, operator substitusi satu token, pencarian
  best-first. Tidak ada katalog defek yang diauthor ke dalamnya.
- **random**: kontrol substitusi token acak, anggaran sama.

Aturan ditegakkan harness, bukan kepercayaan: solver hanya melihat
kasus shown (Budget dibangun dari data shown saja — jawaban holdout
tidak pernah masuk dunia solver); skor utama adalah verifier OMEGA-10
atas semua kasus, dihitung harness (evaluasi independen); pelanggar
anggaran ABSTAIN; hipotesis + aturan keputusan dinyatakan sebelum run,
dengan SUPPORTED / FALSIFIED / INCONCLUSIVE sebagai hasil kelas-satu.

## Hasil eksperimen nyata (evidence: omega11_contrast_experiment.json)

Dua keluarga, level 1–3, seed 1–10, anggaran 200:

- **Holdout (20 tugas)**: grammar 14, token-search 13, ablated 13,
  random 6 → hipotesis "token-search >= grammar" **INCONCLUSIVE**
  (selisih −1, di dalam margin 2).
- **Train (40 tugas)**: grammar 25, token-search 18 → hipotesis
  **FALSIFIED** (grammar unggul 7 ≥ margin).
- Per keluarga: pricing praktis tuntas oleh kedua solver sungguhan
  (holdout 11–12/12; train 18/18); shipping keluarga keras —
  token-search 0/22 di train shipping, grammar 7/22.

Bacaan jujur: pada semesta tugas ini, grammar yang diauthor menyamai
atau mengalahkan proposal generik; klaim kebaruan/generalisasi tetap
**NOT_ASSESSED** sesuai gerbang OMEGA-11 (`promote_claims` menolak
promosi tanpa bukti custody + transfer). Baseline acak (6/20) membuktikan
tugas-tugasnya tidak trivial untuk dicari.

## Cacat lintas paket ditemukan & diperbaiki (OMEGA-10)

Run pertama eksperimen memberi skor 0 untuk SEMUA solver: kasus shown
OMEGA-10 adalah dua kasus grid pertama, yang di kedua keluarga berupa
input nol degenerat — sinyal fitness jenuh sejak lahir, tak ada solver
yang bisa melihat defeknya. `curriculum_lab.py` kini memilih kasus
shown yang informatif (minimal satu mengekspos defek). Cacat ini
ditemukan karena OMEGA-11 *memakai* OMEGA-10 — loop umpan-balik lab
bekerja sebagaimana mestinya.

9 test harness lulus; sapuan paket penuh **183 test OK (10 skip)**.

---

# Ringkasan Penutup Fase 1 — Status per Paket (2026-11-12)

| Paket | Status | Bukti |
|---|---|---|
| OMEGA-00 Probe lingkungan | ✓ | laporan probe VM |
| OMEGA-01 Local fabric (fail-closed) | ✓ | PR #104 |
| OMEGA-02 Pengetahuan repo | ✓ | reproduksi OMEGA-06 cocok persis |
| OMEGA-03 Agen coding umum | ✓ terdegradasi | patch model 6/6 test tertahan (isolasi terdegradasi, tanpa bwrap) |
| OMEGA-04 Workflow durable | ✓ | probe crash/resume lintas proses PASS |
| OMEGA-05 Sandbox | **BLOCKED_ENVIRONMENT** | bwrap tidak tersedia di host ini |
| OMEGA-06 Kernel eksperimen & bukti | ✓ | PR #109 + verifikasi ulang independen (Addendum 6/8) |
| OMEGA-07 Memori kognitif persisten | ✓ | PR #110 |
| OMEGA-08 Arsip populasi & lineage | ✓ | PR #108 + demo gerbang |
| OMEGA-09 Mutasi/rekombinasi/diversitas | ✓ | PR #111 |
| OMEGA-10 Lingkungan & kurikulum | ✓ | PR #113 (+ perbaikan dari OMEGA-11) |
| OMEGA-11 Lab penalaran/representasi | ✓ | PR #114 + eksperimen kontras nyata |

Kejujuran ilmiah, tidak berubah oleh selesainya paket-paket ini:
**G0 PASS hanya lingkup sesi; G1–G5 NOT_ASSESSED; OAIE belum terbukti
(`oaie_proven=false`).** Yang selesai di Fase 1 adalah *infrastruktur
yang terverifikasi dan klaim-klaim kecil yang teruji* — bukan gerbang
ilmiah PRD, yang menuntut pilot A/B/C pada tugas tertahan dengan kustodi
penuh. Kejutan jujur yang berulang di tiga titik (OMEGA-03, 08, 11):
pada semesta kecil ini, baseline deterministik/grammar menyamai model
dan proposal generik — data, bukan kekalahan; itulah gunanya mengukur.

Keputusan yang tetap milik pemilik: merge tumpukan PR #103–#114 ke
main (atau sebagian), publikasi, dan pengeluaran apa pun. Menurut
aturan urutan pemilik sendiri, selesainya Fase 1 membuka Fase 2 (loop
otomatisasi Research Director lokal) sebagai tahap berikutnya.
