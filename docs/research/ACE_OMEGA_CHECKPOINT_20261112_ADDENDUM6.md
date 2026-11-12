# ACE Ω — Addendum 6, 2026-11-12: OMEGA-06 Evaluasi Independen (re-verifikasi Fase 1)

Sesuai instruksi tahap pemilik: reproduksi/re-verifikasi independen atas
klaim utama Fase 1 dari keadaan bersih sejauh bisa di VM ini, dengan
jalur dan perintah tercatat (`evidence/omega06_reverification.json`,
`omega06_repro_omega02.json`, `omega06_repro_omega03.json`; harness
`omega06_repro.py` dan `omega06_g0.py`). Setiap klaim diberi vonis.

Catatan cakupan yang jujur: dokumen program Ω mendefinisikan OMEGA-06
sebagai *Experiment Protocol and Evidence Kernel* utuh (preregistrasi,
split custody, hash protokol, uji canary/pemalsuan). Tahap ini
mengeksekusi inti yang diarahkan pemilik — reproduksi independen.
**Kernel protokol lengkap belum dibangun dan tidak diklaim di sini.**

## Vonis per klaim

| Klaim | Reproduksi | Vonis |
|---|---|---|
| G0 arah gagal (fail-closed) | Cache model kosong, discovery nyata tanpa mock: `FAILED / NO_LOCAL_MODEL`, teks kosong, `task_verified=false` | **COCOK** |
| G0 arah hidup via server | `success=true`, teks "SIAP" dari Qwen3-8B di 127.0.0.1:8081. Percobaan pertama (anggaran 24 token) justru memicu `THINKING_BUDGET_EXHAUSTED` — kegagalan bernama dari PR #107 terkonfirmasi independen | **COCOK** |
| G0 arah hidup via CLI + digest | `success=true`, receipt memuat `sha256=d98cdcbd…5785` = digest persis file Qwen3-8B-Q4_K_M. Percobaan pertama `INFERENCE_TIMEOUT` pada anggaran bawaan router (~58 dtk) di bawah perebutan CPU — digest sudah melekat; lulus dengan anggaran operator 240 dtk (~103 dtk) | **COCOK** |
| OMEGA-02: indeks 402 file / 4.026 simbol, hit@1 4/5, hit@5 5/5 | Indeks dibangun segar di clone main; ground truth digrep ulang saat lari: **persis sama** (402 / 4026 / 4/5 / 5/5), pola miss yang sama di `CONFIRMED_SEALED` | **COCOK** |
| OMEGA-03 baseline: fixture gagal evaluator 4/6, dev 2/3 | Direproduksi persis pada fixture murni | **COCOK** |
| OMEGA-03 hasil akhir: patch lulus 6/6 + 3/3 | Keadaan akhir asli hidup hanya di `/tmp/g1-candidate3` (copy sekali pakai) dan **musnah oleh penggantian runtime VM**; `fixture-wt` di disk byte-identik dengan fixture buggy. Verifikasi via rekonstruksi: `harga.py` diambil verbatim dari isi patch yang tercatat di evidence attempt-3 → evaluator **6/6 OK**, dev **3/3 OK** | **COCOK via rekonstruksi**; lari generatifnya sendiri **TIDAK BISA DIREPRODUKSI** identik (sampling) — dan ruang kerja kandidat yang tidak durable adalah pelajaran proses: workspace kandidat wajib di bawah `~/workspace`, jangan di `/tmp` |
| Hitungan tes triase: main 113, Ω 58, #102 36, #105 188, #92 6 | `Ran 113 OK`; `Ran 58 OK (skipped=10)`; `Ran 36 OK`; `Ran 188 OK`; `Ran 6 OK` | **COCOK (kelimanya)** |
| PR terbuka = 65; #92 & #102–#107 tetap terbuka | Listing GitHub: 65 terbuka, ketujuh PR tersebut ada di dalamnya | **COCOK** |

## Pemisahan rekayasa vs ilmiah

Semua vonis di atas adalah klaim **verifikasi rekayasa**. Tidak ada
gerbang ilmiah yang berubah oleh tahap ini: **G1 tetap NOT_ASSESSED**,
**OAIE tetap belum terbukti** (`oaie_proven=false`). Reproduksi yang
cocok memperkuat kepercayaan pada catatan Fase 1; ia bukan bukti
kemampuan ilmiah baru.

## Berikutnya

OMEGA-08 (Population and Lineage Archive) bergantung pada OMEGA-06
menurut dokumen program — dependensi itu kini terpenuhi untuk inti
evaluasinya. Sesuai instruksi tetap pemilik (progres tahap tidak
menunggu pemilik; antrean terus diberi makan di bawah mandat),
OMEGA-08 dilanjutkan sebagai tahap berikutnya tanpa menunggu
persetujuan baru, dan dilaporkan dengan cara yang sama.
