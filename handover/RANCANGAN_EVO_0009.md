# RANCANGAN EVO 0009 — Menyalakan Lagi Mesin Belajar ACE di atas Organ API + Jalur Tulis Ingatan Kognitif

Status: RANCANGAN (Ian, 2026-11-18) — menunggu ratifikasi hub.
Tidak ada pembangunan sebelum ratifikasi. Nomor 0008 tetap milik
rancangan vonis-uang yang parkir atas steer pemilik 2026-11-18.

## 0. Ringkasan

Dua pekerjaan, satu penyalaan:

1. **Relight** — engine belajar ACE berhenti sejak 17 Nov 2026
   karena sumber otaknya (server lokal slate v2) dipensiunkan
   pemilik dan diganti organ API. Engine tidak pernah disambungkan
   ke otak barunya. Rancangan ini menyambungkannya lewat satu titik
   routing yang memang sudah ada (`brain_endpoints.py`), dengan
   jembatan transport yang menjaga kredensial tetap di dalam
   mekanisme vault.
2. **Write-back** — audit penyerapan 2026-11-15 butir #8: keluaran
   siklus engine yang terverifikasi tidak pernah ditulis ke
   ingatan kognitif; store hidup berhenti di 2 entri seed operator.
   Rancangan jalur tulisnya sudah ada sejak 15 Nov
   (`MEMORY_WRITE_PATH_DESIGN_20261115.md`) dan tidak pernah
   dibangun. Rancangan ini mengadopsinya utuh sebagai separuh
   kedua 0009 — engine tidak boleh menyala lagi hanya untuk
   menghasilkan keluaran terverifikasi yang menguap lagi.

Bukti keberhasilan meniru pola ignition 16 Nov: **record
lahir-dari-siklus muncul di store ingatan kognitif, dengan
brain-of-origin organ API tercatat** — bukan sekadar proses hidup.

## 1. Keadaan terverifikasi (bukti, bukan ingatan)

- Engine: proses `/usr/bin/python3 /workspace/ACE/ace.py engine
  --workspace /workspace/ace-workspace --interval 10` (PID 339361,
  user ubuntu) dalam keadaan berhenti (SIGSTOP) sejak 17 Nov,
  penghitung siklus 1561. Tidak mati, tidak rusak — tertidur.
- Otak lama: `code/ace_operational/brain_endpoints.py` adalah
  satu-satunya titik routing ("the ONLY place that knows their
  addresses; callers ask for a role, never a URL") — peran front
  :8001, coder :8002, embedding :8003, a3b :8004, semua loopback
  OpenAI-compatible, fail-closed (BrainUnavailable), plus mesin
  wake untuk unit lokal. Keempat URL kini mati (pensiun terverifikasi
  18 Nov: service inactive, port tertutup).
- Store ingatan kognitif engine (`ace-workspace/cognitive_memory`):
  isi berhenti di **2 entri seed operator** (audit 15 Nov §1 dan
  rancangan jalur-tulis 15 Nov sepakat). Mesin store-nya sehat:
  `CognitiveMemory.remember/anchor_evidence/record_outcome/recall/
  audit` ada dan teruji; yang hilang hanya jalur tulis dari sisi
  engine. (Store benih 10 record milik lini ukur successor adalah
  store lain — jangan dicampur.)
- Organ API (otak kerja ACE sejak 18 Nov, semua lewat helper
  konektor Secure Vault di VM ila; nilai kredensial tidak pernah
  mencapai sesi mana pun):
  - groq — qwen/qwen3.8-27b (proposer kode terukur), openai/
    gpt-oss-120b (±481 t/s terukur; reasoning memakan budget token
    kecil), 11 model.
  - gemini — lini 2.5 MATI untuk akun ini (404 "no longer
    available to new users", terukur 18 Nov); lini 3.x hidup
    (3-flash-preview terukur menjawab; 3.1-pro-preview 429 pada
    kuota free akun baru); katalog memuat gemini-embedding-001.
  - gonka — DeepSeek-V4-Flash; saldo riil 100.000 token mentah/
    bulan. **Terlalu kecil untuk otak harian engine** — perannya
    tetap judge/opini-kedua, bukan front engine.
- Pelajaran transport terukur (gelombang kalibrasi EVO 0007,
  18 Nov): panggilan API free-tier gagal berkelompok di bawah
  ledakan paralel (spesies batas-laju/timeout helper), sehat pada
  laju berurutan berirama. Engine berinterval 10 detik WAJIB punya
  governor laju — tanpa itu ia akan membakar kuota dan berhenti
  oleh spesies yang sama.

## 2. Rancangan relight

### 2.1 Prinsip
- `brain_endpoints.py` tetap satu-satunya titik routing. Tidak ada
  pemanggil yang belajar alamat baru; yang berubah adalah
  transport di balik antarmuka peran yang sama, plus tabel peran →
  organ API. Fail-closed dipertahankan: organ tak terjangkau =
  BrainUnavailable, tidak ada hasil fabrikasi.
- Kredensial tidak berpindah rumah. Helper konektor hidup di VM
  ila di bawah mekanisme vault; engine hidup di sandbox. Maka
  perlu **jembatan**: layanan HTTP kecil di VM ila (hanya dapat
  dijangkau dari jaringan Tailscale rumah) yang menerima panggilan
  bergaya OpenAI dari engine dan meneruskannya ke helper konektor.
  Engine tidak pernah melihat kredensial, surrogate, atau URL
  provider. Alternatif yang ditolak: (a) menyalin kredensial ke
  sandbox — melanggar disiplin vault; (b) memindahkan runtime
  engine ke VM ila — melawan ketetapan rumah eksekusi = rumah ACE
  dan kapasitas VM ila (1,5 CPU/6 GiB bersama).

### 2.2 Peta peran (usul)
| Peran engine | Organ API | Alasan |
|---|---|---|
| front (percakapan, proposer bahasa) | gemini/gemini-3-flash-preview | Satu-satunya model Gemini yang terukur menjawab pada akun ini hari ini; kelas flash cukup untuk peran front siklus. |
| coder (proposer kode, validator) | groq/qwen/qwen3.8-27b | Terukur hidup dan kuat pada tugas kode (gelombang kalibrasi 0007). |
| validator silang / opini kedua | groq/openai/gpt-oss-120b | Heterogenitas proposer≠validator dipertahankan antar-model; budget token diberi ruang untuk reasoning-nya. |
| embedding (recall semantik) | gemini/gemini-embedding-001 | Ada di katalog; **perlu verb helper + smoke terukur sebelum dihitung hidup**. Cadangan bila gagal: recall leksikal/eksak yang sudah ada di jalur write-back. |
| judge / vonis | gonka/deepseek-ai/DeepSeek-V4-Flash-0731 | Peran yang sudah terdaftar; anggaran bulanannya dijaga governor. |

Pergantian model di tabel ini sesudah ratifikasi = amendemen
bernama, mengikuti disiplin paket 0007 (katalog provider berputar;
2.5-pro adalah buktinya).

### 2.3 Governor laju & kuota (bagian dari build, bukan tambahan)
- Anggaran panggilan per peran per hari, ditulis di konfigurasi
  engine; siklus yang melewati anggaran berhenti rapi
  (BrainUnavailable terlog), bukan gagal acak.
- Irama: maksimal 1 panggilan dalam penerbangan per peran dari
  engine; backoff eksponensial pada kegagalan transport spesies
  batas-laju (pola tangga coba-lagi terukur di kalibrasi 0007).
- Pencatatan brain-of-origin per siklus tetap wajib (asal-usul
  adalah provenans, bukan dekorasi).

### 2.4 Kuota = sumber daya bernama; rotasi antar-rute
(Aturan kontingensi pemilik 18 Nov 13:00, dibukukan hub untuk
rancangan ini.) Kuota tiap rute gratis adalah sumber daya bernama
dengan saldo terukur, bukan asumsi tak terbatas:
- Governor memegang buku anggaran per RUTE (bukan hanya per
  peran): jatah harian Groq/Gemini dan saldo bulanan Gonka dibaca
  sebagai angka, dan sisa anggaran adalah input keputusan routing.
- **Rotasi**: peran front dan validator silang bergantian antar
  dua rute teks (Groq ↔ Gemini) mengikuti jendela anggaran —
  rute yang jendela hariannya lebih longgar mengambil giliran;
  tidak ada satu jatah gratis pun yang menjadi titik gagal
  tunggal bagi engine yang menyala terus-menerus. Peran coder
  berumah di Groq dengan urutan cadangan bernama (Gemini flash)
  yang hanya aktif bila jatah Groq benar-benar habis — kehabisan
  adalah pemicunya, bukan selera.
- Kehabisan nyata di tengah jalan memicu aturan kontingensi
  pemilik: kandidat terverifikasi berikutnya dari daftar
  terdokumentasi (NVIDIA → Cloudflare → Z.ai → CometAPI)
  didaftarkan pada hari yang sama supaya engine tidak mati
  kelaparan; pendaftarannya adalah peristiwa terlog dengan
  brain-of-origin yang berubah secara eksplisit, bukan penukaran
  diam-diam. (Untuk paket ukur beku seperti 0007 pagarnya lain:
  judge habis = jeda + amendemen — kontingensi menyiapkan organ,
  bukan mengizinkan tukar liar. Engine bukan paket ukur; rotasinya
  adalah operasi normal yang terlog.)

### 2.5 Urutan penyalaan (sesudah ratifikasi)
1. Verb embedding + smoke semua peran dari jembatan (satu panggilan
   per peran, tercatat).
2. Jembatan naik di VM ila; engine diberi konfigurasi transport
   baru TANPA dibangunkan — uji `brain_endpoints` health-check saja.
3. Bangunkan engine (SIGCONT) untuk jendela terukur pertama:
   N siklus terbatas governor, diawasi; bukti §4 dibaca dari store.
4. Lulus → engine berjalan sebagai keadaan tetap baru. Gagal →
   engine ditidurkan lagi, temuan jadi rancangan perbaikan bernama.

## 3. Rancangan write-back (mengadopsi rancangan 15 Nov)

Mengadopsi `MEMORY_WRITE_PATH_DESIGN_20261115.md` utuh:
- **Write set hanya yang terverifikasi**: skill terverifikasi
  (procedural, receipt + digest, 0.90); vonis tersegel/ratifikasi
  (semantic, sha akta, 0.95); misi selesai ter-ratifikasi
  (episodic, 0.95); temuan HIGH dibuka/ditutup (episodic, 0.90).
  Bukan untuk ditulis: tick, keluaran practice, generasi tak
  terverifikasi, payload mentah.
- **Penempatan**: helper `memory_writeback` dipanggil di titik
  peristiwa (penerbitan receipt, penutupan ratifikasi, pencatatan
  vonis) — tulis pada waktu peristiwa, bukan daemon pengais.
  Urutan per tulis: baca artefak → `anchor_evidence(bytes)` →
  `remember(source_kind="evidence", source_ref=digest)`.
  Kegagalan tulis WAJIB terlog — tidak ada except-pass.
- **Delta keadaan sejak 15 Nov**: modul `memory_writeback.py` kini
  ada dan melayani lini ukur (kelas peristiwa terverifikasi +
  registrasi `pattern_distilled` 18 Nov), tetapi jalur dari SIKLUS
  ENGINE tetap belum terhubung — persis sisa butir #8 audit.
  Build 0009 menghubungkan titik-titik peristiwa engine ke helper
  yang sama; tidak ada store atau skema baru.
- **Sisi baca sebagai syarat penerimaan** (dari rancangan 15 Nov
  §5): sebelum siklus perbaikan, engine memanggil `recall()` atas
  konteks kegagalan dan menutup hasilnya dengan
  `record_outcome()`. Menulis tanpa loop baca = menimbun; jalur
  tulis tidak dinyatakan selesai tanpa loop ini.

Dua pertanyaan terbuka rancangan 15 Nov dibawa ke ratifikasi ini:
(1) titik mulai penulis — usul lama Ian: mulai dari titik
ratifikasi/vonis (3 dari 4 kelas memang lahir di sana), receipt
skill menyusul; (2) retensi — semantic/procedural permanen,
episodic ditinjau sesudah 30 hari berjalan.

## 4. Bukti keberhasilan (gerbang 0009)

1. Smoke jembatan: satu panggilan sukses per peran, terlog dengan
   brain-of-origin organ API.
2. Jendela siklus pertama menghasilkan ≥1 record BARU di
   `ace-workspace/cognitive_memory` yang lahir dari peristiwa
   siklus terverifikasi, `source_ref` = digest terjangkar,
   `audit()` rantai lolos, 2 entri seed utuh.
3. Replay peristiwa yang sama → 0 record baru (idempoten).
4. Satu siklus perbaikan yang membaca record itu lewat `recall()`
   dan menutupnya dengan `record_outcome()` — loop tulis-baca
   terbukti, bukan hanya tulis.
5. Governor terbukti menahan: siklus di luar anggaran berhenti
   sebagai BrainUnavailable terlog, bukan kegagalan acak.

## 5. Risiko & pagar

- **Kuota free-tier adalah bahan bakar engine sekarang.** Habis
  kuota = engine berhenti jujur (fail-closed), bukan diam-diam
  pindah organ. Pengecualian kontingensi pemilik (18 Nov 13:00)
  berlaku untuk menjaga pekerjaan tetap bergerak, dengan pemicu
  kehabisan nyata — bukan selera.
- **Katalog berputar.** Model mati di tengah jalan (preseden
  2.5-pro) ditangani amendemen bernama; peta peran tidak pernah
  diganti diam-diam.
- **Jembatan = permukaan jaringan baru.** Hanya Tailscale rumah,
  hanya menerima dari host sandbox, tidak meneruskan apa pun
  selain panggilan peran engine; kredensial tetap di vault.
- **Bukan lini ukur.** 0009 adalah evolusi diri (kapabilitas),
  bukan paket pengukuran terpradaftar; klaimnya adalah kapabilitas
  terdemonstrasi lewat gerbang §4, bukan vonis statistik. Bila
  kelak efek belajarnya mau diklaim sebagai vonis, itu paket
  terpradaftar terpisah.
- **Engine menyentuh store hidup.** Penulis tunggal pada satu
  waktu (engine); perkakas Ian tetap read-only terhadap store itu.

## 6. Yang diminta dari ratifikasi

1. Peta peran §2.2 (atau koreksinya), termasuk nasib peran
   embedding bila smoke-nya gagal.
2. Dua pertanyaan terbuka §3 (titik mulai penulis; retensi).
3. Batas anggaran harian awal per peran untuk governor §2.3.
