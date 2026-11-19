# PRAREGISTRASI EVO 0007 — POLA TERDISTILASI (RE-SCOPE ORGAN API)

*Status: DRAF FINAL untuk ratifikasi hub atas head PR ini. BUKAN
beku: tidak ada gelombang, tidak ada episode, sebelum hub
meratifikasi teks ini. Fondasi: PR #310 (teratifikasi hub 18 Nov
2026) + keputusan re-scope hub di tanggal yang sama. Desain induk
klaim dan lengan: PR #254.*

## 0. Mengapa dokumen ini berbentuk begini

Praregistrasi 0007 lama menunggu vonis penerus 0006; vonis itu
tidak pernah ada (lari diakhiri perintah pemilik 18 Nov 2026;
klaim warisan lokal tetap **TIDAK TERUJI** dan bukan urusan paket
ini). Fondasi #310 menurunkan slot yang bisa diturunkan dari bukti
kalibrasi penerus; re-scope hub memutuskan sisanya: subjek ukur
paket ini adalah **jalur recall pola ACE** — perlakuan yang diuji
adalah jenis konteksnya — dan organ pelaksananya adalah set organ
API teregistrasi. Dokumen ini menulis keputusan itu sebagai
praregistrasi yang utuh.

## 1. Klaim (eksplisit, dan yang bukan klaim)

**Klaim:** pada set probe terkalibrasi margin, konteks dari record
`pattern_distilled` (pola terdistilasi) mengangkat accept-rate
proposer melampaui konteks receipt bentuk EVO 0005 dan melampaui
tanpa konteks, dengan set organ API teregistrasi sebagai instrumen
pelaksana dan judge.

**Bukan klaim:** bukan klaim warisan antar-generasi, bukan klaim
tentang belajar atau ingatan organ lokal, bukan klaim tentang
organ API itu sendiri. Garis klaim warisan lokal berdiri terpisah
sebagai TIDAK TERUJI, menunggu otak lokal masa depan.

## 2. Instrumen — set organ API teregistrasi

Semua panggilan mencatat brain-of-origin (`<provider>/<model>`)
per panggilan. Pasangan heterogen proposer ≠ validator bersilang
per jenis, mengikuti konvensi penerus:

| Peran | Kode | Bahasa |
|---|---|---|
| Proposer | groq/qwen/qwen3.8-27b | gemini/gemini-2.5-pro |
| Validator | gemini/gemini-2.5-pro | groq/openai/gpt-oss-120b |
| Judge (terskor, semantik judge v3) | gonka/deepseek-ai/DeepSeek-V4-Flash-0731 | sama |
| Pendistilasi pola | gemini/gemini-2.5-pro | sama |

- Judge memakai semantik judge v3: keluaran `{accept, score 0–100,
  reasons}`; mata uang vonis adalah accept; skor hanya untuk
  kalibrasi pita dan bacaan sekunder. Skor tidak sah pada lari
  ber-skor = baris error (fail-closed).
- **Quirk tercatat (PR #309):** judge Gonka mengeluarkan objek
  JSON-nya dua kali tersambung — parser mengambil objek lengkap
  pertama saja. Aturan parse ini bagian dari instrumen.
- **Identitas judge adalah identitas instrumen:** organ judge tetap
  untuk seluruh paket. Kehabisan saldo Gonka (lihat §8) menghenti-
  kan paket sebagai jeda; mengganti judge di tengah paket hanya
  lewat amandemen teratifikasi hub, dengan gelombang kalibrasi
  diulang. Tidak ada pergantian diam-diam.
- Konteks per episode tercatat kelas-satu di setiap lengan
  (context_ids + delivery flag) — pelajaran instrumentasi 0005.

## 3. Gelombang kalibrasi (di dalam paket ini)

Pita [45,75] pada fondasi terikat instrumen lokal; organ baru =
kalibrasi baru. Gelombang ini menyaring kandidat dengan judge
paket ini (2 lari per kandidat; anggota probe = mean ∈ pita).

**Kolam kandidat (beku, bernama):** korpus gelombang-2 (24 baris,
sha256 22b93961…), korpus cadangan gelombang-3 (12 baris bahasa,
sha256 740e8a29…), korpus gelombang-1 (sha256 1d09d590…). Sha
penuh dicatat di berkas pembekuan paket.

**Aturan pita (mekanis, satu kali):** saring seluruh kolam pada
[45, 75]. Bila anggota < 8, atau fraksi in-band > 70% dari yang
tersaring (pita tidak membedakan), pita diturunkan ulang SATU KALI
sebagai [median − 15, median + 15] dari mean kandidat tersaring,
dicatat, lalu kolam disaring ulang satu kali. Tidak ada penurunan
kedua.

**Komposisi:** set probe wajib ≥4 episode bahasa (aturan fondasi);
cadangan bahasa disaring lebih dulu. Bila sesudah seluruh kolam
bahasa < 4 tetapi total ≥ 8, paket menyatakan cakupannya kode-saja
secara eksplisit di berkas vonis.

**Variansi:** sebaran A/B per kandidat tercatat; kandidat
bersebaran > 50 ditandai. Keanggotaan menurut mean (utama);
penandaan ini mengalir ke laporan sensitivitas §6.

**Anggaran penyaringan & pintu keluar:** kolam beku (60 kandidat)
+ maksimal 2 gelombang pabrik korpus × 12 kandidat lebih berat
bila kolam jenuh (risiko langit-langit: organ API menjenuhkan
kandidat yang ada, seperti judge lokal menjenuhkan bahasa di
0005/0006 — dinyatakan di sini sebagai risiko bernama). Sesudah
itu anggota tetap < 8 → vonis **INSTRUMEN_TIDAK_CUKUP**, klaim
tidak diuji, paket tutup.

## 4. Material pola (dibekukan sebelum lengan pertama)

- **Sumber:** episode ratified dari gelombang kalibrasi penerus
  0006 (berkas wave1/wave2, sandbox) + episode ratified gelombang
  kalibrasi paket ini + korpus beku rumah. Pemilihan final tercatat
  di berkas pembekuan.
- **Pendistilasi** (organ bernama di §2) menulis per episode
  ratified satu record `pattern_distilled` berskema #254:
  task_shape (kosakata tugas sendiri), approach, pitfalls (dari
  reasons judge), source_episode. Disimpan lewat
  record_verified_event, kelas event `pattern_distilled` (kind
  semantic).
- **Cap panjang:** persentil-95 panjang record terdistilasi nyata
  (aturan fondasi), tercatat bersama sha snapshot.
- Store pola dibekukan sebagai snapshot + sha256 pin sebelum
  lengan pertama; store live tidak disentuh; tidak ada write-back
  selama probing.

## 5. Lengan (empat kondisi, set probe yang sama)

(a) **POLA** — konteks pattern_distilled ter-recall (approach +
pitfalls disisipkan ke proposer). (b) **RECEIPT** — konteks
receipt ratifikasi bentuk 0005 (pembanding isi-vs-kehadiran).
(c) **SHAM** — konteks sepadan bentuk dari episode tak-ratified
(kontrol kehadiran tanpa isi lolos). (d) **KOSONG** — tanpa
konteks. Urutan episode diacak per lengan dengan seed tercatat.

## 6. Aturan vonis

- **Gerbang antar per lengan ≥ 75%** dari episode probe; di
  bawahnya vonis **TIDAK_TERANTAR**, klaim tidak diuji.
- **TERDUKUNG** iff accept-rate POLA > RECEIPT dan POLA > KOSONG
  pada set terantar. SHAM dilaporkan penuh sebagai kontrol.
- **Laporan ganda variansi:** vonis utama pada set penuh; bacaan
  sensitivitas tanpa episode bersebaran kalibrasi > 50 dilaporkan
  di sebelahnya (tidak mengubah vonis utama).
- Mean skor judge per lengan = bacaan sekunder, dilaporkan, tidak
  mengubah aturan vonis.

## 7. Disiplin paket

Stop-on-first-error di setiap fase; baris error dikarantina ke
berkas `<fase>_invalid.jsonl` dengan invalid_reason dan diukur
ulang hanya bila fase dilanjutkan lewat keputusan tercatat.
Amandemen hanya lewat PR teratifikasi hub. Brain-of-origin setiap
produk dan baris tercatat; tidak ada keluaran organ API yang
disajikan sebagai keluaran lokal.

## 8. Anggaran terukur (basis: smoke Stage 1 + Gonka, 18 Nov)

- Kalibrasi: ≤ 84 kandidat × 2 lari judge ≈ 168 panggilan judge.
  Di ~226 token/panggilan (smoke Gonka) ≈ 38 rb token dari saldo
  Gonka 100 rb/bulan. Lengan: 4 × ±13 episode × 1 judge ≈ 52
  panggilan ≈ 12 rb token. Total judge ≈ 50 rb — muat, tetapi
  saldo Gonka adalah kendala pengikat paket; kemajuannya
  dilaporkan per fase, dan jeda §2 berlaku bila habis.
- Proposer/validator/pendistilasi: ±300 panggilan Groq/Gemini —
  jauh di dalam jatah gratis harian keduanya; wall per panggilan
  terukur 1–7 detik, jadi seluruh paket berorde jam, bukan hari.

## 9. Prasyarat bangun sebelum pembekuan

1. Kelas event `pattern_distilled` terwire di EVENT_CLASSES +
   tesnya (pola PR #244) — pekerjaan Ian.
2. Runner paket `evo0007_run.py` (fase calib/arms) dengan disiplin
   §7, di atas jalur recall + ratification_loop yang ada; mesin
   mandiri WS-4 Codex hanya dipakai sesudah review Ian dan
   penyambungannya oleh Ian, sesuai kontrak jalur Codex.
3. Pabrik korpus: 24 kandidat lebih berat siap panggil (2 × 12)
   sebagai cadangan §3 — tidak disaring sebelum dibutuhkan.

## 10. Risiko bernama

Langit-langit judge pada kandidat mudah (§3, dimitigasi aturan
pita satu kali + pabrik korpus); saldo Gonka (§8); batas laju
jatah gratis Groq/Gemini (paket berorde jam memberi ruang napas);
perputaran katalog provider (organ paket ini teregistrasi dan
bernama model — pergantian model = amandemen, bukan penyesuaian
diam-diam). LLMTR dengan sengaja BUKAN organ paket ini: jalurnya
tergerbang verifikasi $5 dan registrasinya tertangguh, jadi ia
tidak memenuhi syarat instrumen terukur.
