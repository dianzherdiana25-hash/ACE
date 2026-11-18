# PENAPISAN SIKLUS PELUANG + DERIVASI 0007 — Ian

*Dua produk direktur (brain-of-origin keduanya
groq/openai/gpt-oss-120b; hub, 18 Nov 2026) disaring dengan aturan
berdiri: cek aset terhadap repo sebelum dikutip/dipakai.*

## A. Siklus peluang — pendaratan register

**Detail pendaratan yang diminta hub, diselesaikan:** ASSETS
register memang belum mengenal organ director-strong. PR ini
menambahkan dua aset terukur ke `opportunity_register.py`:
`brain_director_strong` (kind brain — registrasi PR #307 + gerbang
Tahap 1 teratifikasi + smoke ≈481 t/s) dan `cap_render_3d_explainer`
(kind capability — video kapal selam terkirim ke pemilik 18 Nov,
115,08 dtk). Origin sah kini `brain_director_strong`. Tiga usulan
yang lolos masuk sebagai entri register (status `design`) di
`evidence/director_opportunity_register.jsonl` — segmen rantai-hash
yang valid (chain terverifikasi; origin_share segmen: 3/3
ACE-side); entri yang sama di-append ke register ruang-kerja engine
dengan `append()` yang sama saat engine berjalan lagi. Tes register
yang ada: 9/9 OK dengan ASSETS baru.

**Vonis per usulan:**
- **U1 Rigour-Verified — MENDARAT (terkoreksi).** Selaras garis
  produk pertama studi bisnis (jasa rigour terverifikasi).
  Kombinasi dikoreksi ke aset nyata [cap_sealed_evaluation,
  venue_kbm]; "Codex workstream audit-automation" **tidak ada**
  (workstream Codex nyata: WS-2 verifikasi pendapatan), dan
  royalty_track #284 adalah perkakas, bukan aset register —
  disebut sebagai instrumen di rationale, bukan anggota kombinasi.
  Pagar: tahapan studi bisnis — tanpa outreach/kontrak/uang sebelum
  tahap capability + legal-shell + payment-rails terukur.
- **U2 Bab-to-Video — MENDARAT (terkoreksi).** Kombinasi
  [cap_render_3d_explainer, cap_serial_fiction, venue_kbm]. Pagar
  tambahan tercatat di entri: kontrak KBM eksklusif — hak adaptasi
  dibaca dari kontrak per-karya sebelum penjualan/lisensi eksternal
  apa pun.
- **U3 SaaS Royalty-Track — DITOLAK.** Kombinasinya tidak nyata:
  tidak ada aset web/SaaS di rumah; royalty_track adalah perkakas
  lokal; "data-pipeline-automation" bukan nama workstream Codex.
  Membangun platform mendahului semua gerbang tahapan.
- **U4 Karikatur + NFT — DITOLAK, di luar piagam.** Penerbitan NFT
  dan marketplace = penciptaan aset kripto + akun baru + gerakan
  uang — tidak satu pun disanksi studi bisnis (garis produk pertama
  = jasa rigour dan fiksi serial). Ia juga memperdagangkan rupa
  pribadi pemilik. Tidak masuk register dalam bentuk apa pun.
- **U5 Serial interaktif Codex — DITOLAK sebagaimana tertulis.**
  KBM tidak memiliki fitur cabang-pilihan-pembaca (kemampuan
  platform karangan); "story-generation" bukan workstream Codex.
  Inti sahnya — Codex mendukung produksi KBM — sudah berdiri
  sebagai WS-1 kontrak Codex.
- **U6 Lisensi render headless — MENDARAT (terkoreksi).**
  Kombinasi [cap_render_3d_explainer, cap_sealed_evaluation];
  pagar tahapan studi bisnis yang sama.

Hasil: 6 usulan → 3 mendarat terkoreksi, 3 ditolak. Pola karangan
siklus ini berbeda dari siklus pertama: bukan nama modul, melainkan
nama workstream dan kemampuan platform — cek aset tetap menangkap
semuanya.

## B. Kerangka derivasi slot 0007 — arsitektur diterima, isi dikoreksi

**Yang diterima:** arsitektur empat-vonisnya benar dan selaras
kerangka — SUPPORTED/NULL menurunkan nilai; NOT_DELIVERED /
INSTRUMEN_TIDAK_CUKUP menolak menurunkan. Enam slot tetap kosong
sampai vonis tersegel; dokumen ini bahan finalisasi, bukan
pengisian.

**Koreksi wajib (cek terhadap kerangka di evo0007-staging dan
rancangan #254):**
1. **Cakupan slot 5/6, satu karangan, satu hilang.** Produk
   mengarang slot "ambang kemiripan recall" — tidak ada di
   kerangka; recall #254 adalah pencocokan kosakata task_shape,
   tanpa ambang similarity. Slot nyata yang HILANG dari produk:
   **sumber final material pola** (§4 kerangka). Slot karangan
   dibuang; slot yang hilang dipulihkan di kerangka terkoreksi.
2. **Semua nilai contoh adalah karangan:** label organ `v2.1`/
   `c3.0`; "baseline EVO 0005" `validator_default`/`coder_default`
   (0005 tidak punya pendistilasi sama sekali); cap 1024/768 token
   (0006 tidak memuat bukti panjang pola — ia tidak punya pola);
   pita "netral 0005" 50–70 (pita [45,75] adalah instrumen penerus,
   bukan warisan 0005); N default 0005 = 6; `corpus_home_v2` +
   sha `a1b2c3…`/`deadbeef…`; ambang 0,78/0,75/0,70. Semua dicoret.
3. **Aturan per slot, bentuk terkoreksi:**
   - *Organ pendistilasi:* diturunkan dari perilaku per-organ pada
     kalibrasi penerus (organ mana yang penilaiannya stabil/
     in-band). Pada vonis NULL tidak ada bukti organ — pilihan
     jatuh ke konvensi tercatat (organ lebih murah) dan DINYATAKAN
     sebagai konvensi di praregistrasi, bukan warisan.
   - *Cap panjang pola:* TIDAK diturunkan dari vonis sama sekali —
     diturunkan saat pembekuan material dari distribusi panjang
     record terdistilasi nyata (cap persentil tinggi, tercatat
     bersama sha snapshot).
   - *Pita margin:* pita adalah sifat instrumen judge, bukan sifat
     vonis — diturunkan dari data kalibrasi penerus (distribusi
     in-band gelombang-gelombangnya) dan dinyatakan eksplisit
     dengan sumbernya. Kerangka melarang warisan DIAM-DIAM, bukan
     warisan bersumber. Vonis NULL tidak mengubah pita; kalibrasi
     gagal (INSTRUMEN_TIDAK_CUKUP) membuatnya tak terderivasi.
   - *N probe:* lantai penerus (8) dipertahankan; kenaikan hanya
     bila data variansi vonis menuntut presisi lebih (aturan
     variansi eksplisit dari siklus pertama) — keputusan + basis
     tercatat.
   - *Sumber kandidat + sha:* tindakan saat pembekuan dari korpus
     beku nyata (gelombang-2 sha 22b93961…, cadangan gelombang-3
     sha 740e8a29…, korpus rumah); sha dicatat saat pembekuan,
     tidak pernah "diturunkan" dari vonis.
   - *Sumber final material pola (pulih):* bentuk vonis memutuskan
     sumbernya — episode ratified dari lari penerus (hanya ada bila
     kalibrasi/lengan menghasilkannya) dan/atau korpus beku rumah;
     diputuskan saat pembekuan sesuai redaksi §4.
4. **Cabang "pengukuran tambahan termurah" DITOLAK sebagai
   prosedur.** Probe susulan, organ dummy, dan top-up lengan
   sesudah vonis melanggar disiplin praregistrasi tersegel.
   NOT_DELIVERED / INSTRUMEN_TIDAK_CUKUP menutup derivasi dan
   melahirkan paket kalibrasi BARU yang terpraregistrasi (pola
   F → I) — ia tidak membuka kembali paket yang tersegel.

Kerangka terkoreksi ini tersimpan juga di
`~/workspace/evo0007-staging/KERANGKA_DERIVASI_TERKOREKSI.md` —
pada hari vonis, finalisasi 0007 berjalan mekanis dari dokumen itu.
