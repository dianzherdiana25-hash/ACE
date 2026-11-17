# EVO 0006 — KONSOLIDASI (Ian, 2026-11-17 pagi)
## Vonis: INSTRUMEN_TIDAK_CUKUP (probe set 1 < 8) — gerbang paket bekerja sebagaimana diratifikasi

## 1. Yang diuji dan yang terjadi

Klaim inheritance (PR #251): instans segar di-seed store
penuh program mengungguli instans segar dari nol pada
probe set terkalibrasi, lewat jalur recall yang sama
dengan 0005. Store penuh dibangun persis definisi paket:
snapshot = salinan utuh root store akumulasi (10 record
unik: 2 seed + 8 verdict_sealed), terverifikasi memuat
store live (2 record) sebagai subset byte-identik;
log-rantai snapshot sha256 14b5e7ab0a585c23d8d91dcc2
8347a38955aad345f97dfd0336dcfdc955beb. Store live tidak
diubah. Engine dijeda selama jendela, hidup lagi
sesudahnya (Ss terverifikasi).

Lengan SEEDED vs KOSONG TIDAK berjalan: layar kalibrasi
tidak menyediakan probe set yang cukup, dan paket
memerintahkan berhenti di gerbang tanpa vonis paksa.

## 2. Hasil layar terkoreksi (semua baris terukur asli)

Korpus kandidat beku 24 (sha 1d09d590…), masing-masing
2× kondisi kosong; masuk probe hanya vonis-belah:

| jenis | selalu-lolos | selalu-gagal | belah |
|---|---|---|---|
| code (12) | 9 | 2 | 1 (cd-code-010) |
| language (12) | 12 | 0 | 0 |

Probe set = 1 episode. Pasangan A/B sepakat pada 23
dari 24 episode: vonis pasangan organ per episode
nyaris deterministik pada sampling bawaan — layar
belah tidak bisa mengisi probe set pada jumlah kandidat
ini. Itu temuan tahap instrumen 0006, dan vonis
INSTRUMEN_TIDAK_CUKUP adalah keluaran sah paketnya:
klaim inheritance TIDAK teruji, bukan gugur.

## 3. Insiden outage + koreksi (preseden 0005)

ace-front mati dua kali selama layar (pola OOM cap
6 GiB; NRestarts 5 → 8 malam itu): sekali di layar code
(baris cd-code-006 run A) dan sekali di awal layar
language — yang membakar 20 dari 24 baris language
menjadi baris error (BrainUnavailable) sebelum
terdeteksi. Baris mentah pertama sempat terbaca sebagai
in-band language 4 — artefak, dinyatakan tidak sahih.
Koreksi ter-ratifikasi hub: 21 baris error DIPERTAHANKAN
sebagai berkas invalid terpisah (screen_code_invalid:
1 baris; screen_language_invalid: 20 baris), pasangan
hilang diukur ulang dengan front sehat (code 1 run:
cd-code-006 A = True asli, mengubah 006 menjadi
selalu-lolos; language 20 run). Semua angka §2 berasal
dari baris terukur asli saja. Perbaikan runner dari
insiden ini — fase layar berhenti pada baris error
pertama — ter-ratifikasi hub sebagai aturan instrumen
tetap.

## 4. Pelajaran desain untuk paket berikutnya

Definisi pita "vonis belah 1/2" terlalu sempit untuk
pasangan organ yang nyaris deterministik. Kandidat arah
(belum diputuskan, bukan bagian misi ini): pita berbasis
margin judge (alasan penerimaan/penolakan nyaris-batas),
jumlah kandidat jauh lebih besar, atau kalibrasi adaptif
— kesulitan dinaikkan bertahap sampai belah muncul —
dibekukan di praregistrasi berikutnya sebelum lari.

## 5. Bukti

evidence/evo0006/: screen_code.jsonl,
screen_language.jsonl, screen_code_invalid.jsonl,
screen_language_invalid.jsonl, probe_set.json,
evo0006_verdict.json, evo0006.log. Praregistrasi:
PR #251. Snapshot store: staging sandbox
evo0006-stage/store_full (sha di §1).
