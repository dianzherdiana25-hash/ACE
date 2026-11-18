# AMANDEMEN EVO 0007 — Judge fase lengan berpindah ke NVIDIA; kalibrasi ditutup pada 54 baris

Status: AMANDEMEN TERATIFIKASI HUB, 2026-11-18. Mengamendemen
PRAREGISTRASI_EVO_0007_FINAL_DRAF.md (PR #311 @ b3868b3f) pada
dua titik: penutupan fase kalibrasi dan identitas judge fase
lengan. Semua ketentuan lain praregistrasi berdiri utuh.

## 1. Fakta yang memaksa amendemen

Judge paket (gonka/deepseek-ai/DeepSeek-V4-Flash-0731) mati di
tengah fase kalibrasi: HTTP 401 "API key is paused or access
disabled" (invalid_api_key), persisten, terverifikasi hub
dengan tangannya sendiri. Bacaan sebab: saldo mentah free tier
100.000 token/bulan habis — panggilan judge kalibrasi nyata
menarik 400–800 token per panggilan (prompt membawa tugas +
jawaban penuh), bukan 226 token estimasi prompt-kecil di
dokumen konektor; ±160 panggilan judge dalam satu hari
menembus saldo itu. Broker mengekspresikan kehabisan saldo
sebagai kunci yang dipause. Saldo pulih 1 Desember 2026.

## 2. Kalibrasi DITUTUP pada 54 baris

Fase kalibrasi ditutup pada 54 baris tersegel di bawah judge
Gonka (24 kode + 30 bahasa; cadangan 12/12, gelombang-2 24/24,
gelombang-1 kode 12/12, gelombang-1 bahasa 6/12). Enam kandidat
bahasa gelombang-1 yang belum tersaring (cd-lang-007 s.d.
cd-lang-012; pass berhenti pada panggilan judge untuk
cd-lang-008) DIKECUALIKAN dari korpus dan tercatat sebagai
tidak-tersaring-akibat-judge-mati — bukan gugur kualitas, bukan
baris invalid. calibrate() beku berjalan atas 54 baris ini;
komposisi bahasa dihitung dari 30 kandidat bahasa tersaring
dan syarat ≥4 bahasa pada set probe terpenuhi dari hitungan
tersegel. Aturan pita §3 berjalan mekanis atas 54 (satu kali
penurunan bila anggota < 8), tanpa penyesuaian kedua.

## 3. Judge fase lengan = NVIDIA (organ kontingensi pertama)

Judge fase lengan adalah organ kontingensi urutan pertama
dari daftar pemilik (NVIDIA), model kelas DeepSeek dari
katalognya — keluarga model yang sama dengan judge Gonka;
keringanan itu kunamai sebagai keringanan, bukan kesetaraan.
Registrasi (akun, kunci via vault, konektor, smoke terukur)
dilakukan hub; judge baru tidak dipakai sebelum smoke-nya
berdiri. Judge NVIDIA berlaku SERAGAM untuk keempat lengan
(POLA / RECEIPT / SHAM / KOSONG): klaim paket membandingkan
lengan di bawah satu judge, jadi validitas internal vonis
utuh.

Konsekuensi yang dinyatakan terang-terangan:
- Pita seleksi diturunkan di bawah judge Gonka; lengan dijudge
  NVIDIA. Dua fase, dua judge — tercatat, tidak disamarkan.
- Bacaan sekunder mean-score TIDAK dibandingkan lintas fase.
  Yang dibandingkan untuk vonis hanyalah accept-rate antar-
  lengan di dalam fase lengan, persis bunyi §6 praregistrasi.
- Heterogenitas proposer≠validator di dalam lengan tidak
  berubah; judge tetap organ ketiga yang berbeda dari
  keduanya.

## 4. Statistik jembatan (tercatat, bukan gerbang)

Sebelum lengan berjalan, judge NVIDIA menilai ulang sampel
jawaban tersegel yang dulu dijudge Gonka (baris saring membawa
jawabannya). Kesepakatan lintas-judge (selisih mean + laju
sepakat accept) masuk konsolidasi sebagai statistik jembatan
yang jujur. Ia tidak menggerbangi lengan dan tidak mengubah
pita.

## 5. Gonka sesudah paket

Gonka kembali sebagai organ opini-kedua saat saldonya pulih
1 Desember — tidak di tengah paket ini. Aritmetika dokumen
konektornya dikoreksi: 400–800 token nyata per panggilan judge
kalibrasi; irama free tier 6 RPM (≥10,5 dtk/panggilan) adalah
basis anggaran paket berikutnya.

## 6. Revisi bernama — NVIDIA → Cloudflare (hub, 2026-11-18)

Jalur NVIDIA mati di tembok kenyataan sebelum satu pun
panggilan lengan: verifikasi OTP telepon tidak pernah tiba ke
nomor Indonesia pemilik, dan pemilik mengarahkan memakai API
tanpa nomor HP. Akun NVIDIA jadi tetapi tidak terverifikasi
dan tanpa kunci; tugasnya diparkir. Tangga kontingensi
bergerak ke #2 dan judge lengan menjadi:

**Cloudflare Workers AI — `@cf/meta/llama-3.3-70b-instruct-fp8-fast`**

Alasan pemilihan dari katalog hidup (299 model), dinamai
supaya tercatat:
- Baris DeepSeek di Cloudflare (v4-flash-0731, v4.1-flash-1017,
  v4-pro-0813) mensyaratkan metode pembayaran berbayar menurut
  halaman harga resmi — kontinuitas kelas DeepSeek tidak bisa
  dibeli dengan Rp0 di rumah ini.
- qwq-32b dan deepseek-r1-distill-qwen-32b terkena
  deprecation 20 Nov 2026 — tidak layak untuk paket berjalan.
- `@cf/qwen/qwen3.8-27b` gugur oleh aturan heterogenitas paket
  sendiri: model itu proposer kode instrumen ini (lewat Groq);
  judge tidak boleh model yang sama dengan proposer di host
  mana pun.
- Llama-3.3-70B lolos tiga saringan sekaligus: plan gratis,
  tidak terdeprecation, independen dari keempat
  proposer/validator.

Smoke terukur (hub, konektor custom.cloudflare): satu
panggilan judge utuh pada butir kalibrasi tersegel w3-lang-003
dalam bentuk judge instrumen — keluaran JSON persis bentuknya,
waktu dinding 5,4 dtk, biaya terukur **14,14 Neurons/panggilan**
dari alokasi gratis terverifikasi 10.000 Neurons/hari; seluruh
fase lengan (±52 panggilan) berada jauh di dalam satu hari
alokasi. Limitasi lintas-judge yang dinyatakan di §3 tetap
berlaku utuh; statistik jembatan §4 kini mengukur kesepakatan
Gonka ↔ Cloudflare. JUDGE_ORGAN di runner berubah lewat
komit amendemen ini — tidak ada suntikan diam-diam.
