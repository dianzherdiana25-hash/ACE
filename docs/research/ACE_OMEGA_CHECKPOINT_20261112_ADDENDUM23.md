# ACE Ω — Addendum 23, 2026-11-12: Tahap A — Rantai Blocker OMEGA-03, Vonis BLOCKED yang Persis, dan Amendemen Arah Pemilik

## Rantai blocker, terukur langkah demi langkah

Jalan-ulang OMEGA-03 lewat alur resmi dijalankan berulang; setiap
putaran menembus satu lapisan dan mengukur lapisan berikutnya:

1. **RAM sesaat** (Addendum 22): admission menolak model pada
   ~0,6 GB tersedia. Probe alokasi membuktikan kemampuan itu
   *transien*: 5,6 GB teralokasi+tersentuh, MemAvailable pulih ke
   7,0 GB. Bukan cacat arsitektur.
2. **Timeout CLI**: batas inferensi per percobaan workflow 240 detik
   melawan cold-load + generasi jalur CLI → INFERENCE_TIMEOUT.
3. **Timeout server**: jalur server (model residen) menghasilkan 493
   token pada ~2,5 token/detik lalu dibatalkan tepat di batas yang
   sama → INFERENCE_TIMEOUT.
4. **Anggaran berpikir**: pada 256 token, seluruh anggaran habis di
   reasoning_content → THINKING_BUDGET_EXHAUSTED. Diperbaiki secara
   terukur oleh PR #126 (disiplin berpikir Qwen3 di kedua jalur):
   jalur server lalu menghasilkan JSON perbaikan sah-skema dalam
   79 detik; ketiga percobaan CLI selesai inferensi di dalam batas.
5. **Gerbang digest**: jawaban jalur server ditolak workflow dengan
   "coding requires digest-identified local model inference" —
   identitas server tidak teratestasi host (sha256 None menurut
   desain resi). Gerbang ini *benar* dan tidak dilonggarkan.
6. **Kualitas keluaran terstruktur model** (lapisan terakhir): di
   jalur CLI yang teratestasi, ketiga percobaan gugur saat parse —
   model menyalin placeholder skema secara harfiah
   (`"symbol": "function_name"`), menyisipkan string Python
   triple-quote ke dalam JSON (tidak valid), dan kode di dalamnya
   pun salah secara substantif.

## Vonis

**BLOCKED — kemampuan yang hilang disebutkan namanya:** model lokal
8B belum mampu menghasilkan keluaran perbaikan terstruktur yang
lolos skema persis pada jalur inferensi teratestasi-digest, di dalam
anggaran alur resmi. Semua komponen ACE berfungsi: baseline
tereksekusi di sandbox v2, inferensi teridentifikasi, loop
umpan-balik 3 percobaan berjalan, verdict FAIL tersegel dengan
jujur. Yang belum ada adalah kemampuan modelnya, dan satu-satunya
jalan pintas yang tersedia (melonggarkan gerbang digest untuk jalur
server) dilarang oleh mandat karena melemahkan jaminan bukti.

**Arsitektur yang diusulkan (desain saja, belum dimandatkan):**
server yang *diluncurkan harness sendiri* dengan digest GGUF yang
dicatat harness saat peluncuran = identitas teratestasi-harness.
Ini mempertahankan maksud gerbang (penulis patch adalah artefak
yang diverifikasi host) tanpa mempercayai server asing. Perubahan
semantik aturan bukti Fase 1 seperti ini memerlukan tahap tersendiri
dengan tinjauan sendiri — tidak diselundupkan lewat tahap ini.

Status OMEGA-03 tidak berubah: LOCALLY_VERIFIED hanya pernah dicapai
varian terdegradasi Fase 1; alur resmi tetap belum terverifikasi.

## Amendemen arah pemilik (2026-11-12) — tercatat resmi

Pemilik memutuskan: **ACE tidak wajib Rp0 selamanya** — "Rp0 adalah
disiplin awal, bukan sumpah; ACE harus mampu mencari finansialnya
sendiri ketika lingkungannya tidak memadai atau ada hal yang perlu
dibeli saat ia sudah mentok."

Perlakuan direktur: (1) amendemen ini dicatat dalam lineage
checkpoint ini; (2) jalur kemampuan **pendanaan mandiri** masuk
backlog riset dengan tahap pertama berupa studi desain —
`docs/research/ACE_SELF_FUNDING_DESIGN_STUDY_20261112.md` (pemicu
terukur, perolehan berbasis kemampuan terverifikasi saja, struktur
kepemilikan/tanda tangan pemilik, pengaman dan batas); (3) **tidak
ada tindakan uang apa pun sekarang** — mencari dana, membuka akun,
berkontrak, dan membelanjakan tetap reserved pemilik sampai mandat
pelaksanaan tersendiri. Disiplin berjalan tidak berubah: exhaust
jalur lokal/gratis dulu, eskalasi kebutuhan sebagai laporan
berbasis bukti.
