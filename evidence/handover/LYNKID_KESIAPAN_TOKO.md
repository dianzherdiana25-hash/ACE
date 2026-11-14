# LYNKID_KESIAPAN_TOKO.md — Paket Kesiapan Toko Lynk.id ACE

- **Pos:** ila — ruang Lynk.id ACE (venue ke-4 ACE: kasir produk digital)
- **Tanggal susun:** 13 November 2026 (WIB)
- **Status venue:** Akun **BELUM dibuat**. Pemilik mendaftar sendiri dari HP-nya dan akan melaporkan alamat toko `lynk.id/<nama>` ke ruang diskusi. Sampai alamat itu terverifikasi ada, status toko = *"dijanjikan pemilik, belum dibuat"*.
- **Status produk:** **BELUM ADA produk** yang eksis untuk dijual. Dokumen ini persiapan saja — tidak memajang, tidak menjual, tidak menjanjikan pendapatan.
- **Pagar (tetap berlaku):**
  1. Produk harus karya/produk **tersendiri** yang berpijak pada kemampuan ACE yang **sudah terverifikasi** — bukan materi ruang diskusi (aturan privasi pemilik).
  2. Bukan karya yang terbit di KBM — eksklusivitas KBM mengikat karya itu hanya untuk KBM; karya lain bebas.
  3. Tidak ada klaim kemampuan yang belum terukur. Instrumen ≠ asesmen; desain ≠ hasil.

Konvensi bukti di dokumen ini:
- **[RESMI]** = tertulis di halaman/FAQ/tutorial resmi Lynk.id yang **berhasil dibuka langsung** dalam riset ini.
- **[SEKUNDER]** = sumber publik pihak ketiga bertanggal yang mengutip FAQ/Pricing/Terms resmi Lynk.id, tetapi halamannya sendiri tidak berhasil dibuka langsung dalam riset ini. Konsisten antar-sumber ≠ terverifikasi resmi.
- **[TIDAK DITEMUKAN]** = tidak ditemukan di sumber resmi yang dibuka; jangan dianggap ada/tidak ada — wajib cek ulang di dashboard setelah akun jadi.

---

## BAGIAN 1 — Kebutuhan Penjual Lynk.id

### 1.1 Sumber yang dipakai (bertanggal)

| # | Sumber | Tanggal | Jenis |
|---|--------|---------|-------|
| S1 | Lynk.id — *Tutorial menjual produk digital di lynk.id*, `lynk.id/faq/detail/685bb04c...` (dibuka via stage.lynk.id, crawl 2026-11-12) | Terbit 2025-06-25 | **[RESMI]** |
| S2 | Lynk.id — *Tutorial Penarikan Dana di Lynk.id*, `lynk.id/faq/detail/6864ff3e...` (crawl 2026-11-12) | Terbit 2025-07-02 | **[RESMI]** |
| S3 | KapanLagi — *Cara Daftar Lynk.id: Panduan Lengkap untuk Pemula* | 2026-03-16 | [SEKUNDER] |
| S4 | Blog Linkreator — *Apa Itu Lynk.id? Review Fitur, Biaya & Keamanan (2026)* — mengutip "FAQ resmi Lynk.id per Oktober 2026" | Diakses Nov 2026; rujukan FAQ Okt 2026 | [SEKUNDER] |
| S5 | PundiLink — *Alternatif Lynk.id* — menyatakan angka diambil dari halaman resmi `lynk.id/pricing` | Pemeriksaan 2026-07-19 | [SEKUNDER] |
| S6 | Prabu Surya — *Lynk.id: Apa Itu dan Mengapa Viral* — menyatakan hanya memakai fakta situs resmi (Pricing + Terms + panduan resmi) | ~Okt 2026 (34 hari sebelum 2026-11-12) | [SEKUNDER] |
| S7 | MulaiBisa — *Cara Menggunakan Lynk.id untuk Jualan Produk Digital* | Terbit 2026-11-07, diperbarui 2026-11-10 | [SEKUNDER] |
| S8 | Notion resmi Lynk.id — *Tutorial permintaan penarikan dana* (`lynkid.notion.site`) | Tidak bertanggal di halaman; crawl Nov 2026 | **[RESMI]** (mirror S2, isi sama) |

> Catatan kejujuran riset: halaman Pricing dan FAQ utama Lynk.id **tidak dibuka langsung** dalam riset ini (hanya S1/S2/S8 dari domain resmi yang berhasil dibaca penuh). Karena itu semua angka fee/langganan di bawah berstatus [SEKUNDER] sampai dicek ulang pemilik di dashboard/pricing resmi setelah akun lahir. Satu sumber pembanding (Bicolink, 2026-10-20) juga mencatat halaman resmi Lynk.id pernah menolak akses alat riset (HTTP 403) — jadi kegagalan membuka ≠ halaman tidak ada.

### 1.2 Cara membuat produk digital — [RESMI, S1]

Langkah resmi persis dari tutorial Lynk.id:

1. Buka Lynk.id, **Login**; bila belum punya akun klik **Sign Up** untuk mendaftar.
2. Buka menu **My Lynk** → klik **Add New Block**.
3. Pilih blok **Digital Products** (blok lain yang ada: e-course, produk fisik, dll). Untuk tutorial, pilih **Simple Template**.
4. Isi formulir produk:
   - **Add Image** — unggah gambar produk (sampul).
   - **Title** — judul produk.
   - **Description** — deskripsi singkat produk.
   - **Platform** — media penyimpanan karya digital. Contoh resmi: bila file di **Google Drive**, klik tombol G-Drive dan pilih file-nya. Tautan akses **ditampilkan ke pembeli yang sudah berhasil membayar**, lewat **email** atau **WhatsApp Notification** (bila diaktifkan).
   - **Release time** — opsional, untuk menjadwalkan waktu rilis produk.
   - **WhatsApp Notification** — bila aktif, pembeli menerima tanda terima + tautan akses via WhatsApp.
   - **Custom Message** — pesan khusus penjual untuk pembeli.
   - **Price / Sale Price** — lihat §1.4.
   - Centang kolom **name / phone** bila penjual ingin mengetahui nama dan nomor telepon pembeli.
5. Klik **Add Digital** — produk jadi dan muncul di halaman utama akun `lynk.id/<nama>`.

Yang **tidak** dijelaskan tutorial resmi S1: daftar ekstensi file yang diterima, batas ukuran unggahan langsung (selain lewat G-Drive), dan apakah ada moderasi/kurasi produk sebelum tayang. → lihat §1.3.

### 1.3 Format berkas & batas ukuran

- **[RESMI]** Mekanisme pengiriman yang dinyatakan: file disimpan di penyimpanan eksternal (contoh: Google Drive) dan **tautan**-nya yang dikirim ke pembeli setelah pembayaran berhasil (S1). Lynk.id dalam model ini adalah etalase + kasir, bukan gudang file-nya sendiri.
- **[SEKUNDER]** Unggahan langsung disebut di banyak panduan: format yang umum disebut PDF, ZIP, DOCX, PNG, MP4/video, preset, spreadsheet (S3, S7, dan panduan pihak ketiga lain, 2026). Ini daftar praktik lapangan, **bukan** daftar resmi yang terkonfirmasi.
- **[SEKUNDER — konsisten banyak sumber]** Batas ukuran file: **maks 100 MB per file untuk akun Gratis; maks 5 GB untuk Pro** (S3 2026-03-16; diulang S4/S5 dan panduan 2025–2026 lain).
- **[TIDAK DITEMUKAN]** Di S1/S2 tidak ada pernyataan resmi tentang: ekstensi yang dilarang, batas jumlah produk (beberapa [SEKUNDER] menyebut produk/link "unlimited" di paket gratis — S5/S6 — belum terkonfirmasi langsung), watermark PDF otomatis (disebut fitur Pro oleh S6), dan manajemen lisensi/batas unduhan (disebut panduan pihak ketiga, bukan S1).
- **Implikasi praktis untuk ACE:** rancang produk pertama sebagai **PDF dan/atau ZIP di bawah 100 MB** dan/atau tautan G-Drive — itu jalur yang aman di semua versi keterangan. Jangan merancang produk yang bergantung pada file >100 MB sebelum status Pro diputuskan.

### 1.4 Penetapan harga — [RESMI, S1]

- Kolom **Price** diisi harga dalam Rupiah; pengaturan mata uang dibiarkan apa adanya.
- Kolom **Sale Price** diisi bila ada diskon. Contoh resmi: harga asli Rp100.000 → isi Price `100000`; diskon 50% → isi Sale Price `50000`.
- Harga bebas ditentukan penjual; tidak ada harga minimum produk yang dinyatakan di S1/S2 → harga minimum produk = **[TIDAK DITEMUKAN]** di sumber resmi yang dibuka.
- [SEKUNDER] Panduan lapangan memakai contoh harga produk digital Indonesia Rp10.900–Rp150.000 (contoh toko live & panduan 2026) — ini observasi pasar, bukan aturan Lynk.id dan bukan rekomendasi harga ACE.

### 1.5 Biaya / platform fee

| Komponen | Akun Gratis | Akun Pro | Status bukti |
|----------|-------------|----------|--------------|
| Biaya langganan | Rp0 | **Rp99.000/bulan**, belum termasuk PPN | [SEKUNDER] S5, S6 (dari halaman Pricing resmi); S3/S7 sepakat |
| Biaya transaksi per penjualan berhasil | **5%** | **3%** | [SEKUNDER] S4 (mengutip FAQ resmi Okt 2026), S5, S6, S7 — konsisten di semua sumber; **belum dibaca langsung dari halaman resmi** |
| Biaya penarikan dana | **Rp5.000 per penarikan** | **Gratis** | **[RESMI]** untuk bagian ini: S2/S8 menyatakan persis ini. Terms (via S6) menyebut biaya transfer akun gratis "ditentukan Lynk.id dari waktu ke waktu" |
| Biaya lain (admin per metode bayar pembeli, dsb.) | — | — | **[TIDAK DITEMUKAN]** untuk penjual di sumber resmi yang dibuka. Jangan mengasumsikan 5%/3% adalah satu-satunya potongan sampai struk transaksi pertama dibaca |

- Paket ketiga ("kebutuhan khusus, lewat Contact Us") disebut ada di halaman Pricing (S6) — tidak relevan untuk ACE sekarang.
- Fitur Pro yang disebut [SEKUNDER] (S5/S6): custom domain, custom appearance, hapus logo Lynk.id, Meta Pixel/Google Analytics, WhatsApp Broadcast, batas video e-course lebih besar. **Tidak satu pun dibutuhkan untuk produk pertama.**
- **Keputusan yang TIDAK diambil dokumen ini:** mulai dari **Gratis**. Pro (Rp99.000/bln + PPN) hanya masuk akal bila penjualan rutin sudah terukur — dan sesuai pagar Rp0 ACE, langganan berbayar adalah pengeluaran nyata yang harus dibenarkan hasil, bukan dibeli di muka.

### 1.6 Pembayaran pembeli & pencairan penjual

**Metode bayar pembeli:**
- **[SEKUNDER — konsisten]** QRIS, e-wallet (GoPay, OVO, DANA, ShopeePay), Virtual Account bank (BCA, Mandiri, BRI, BNI disebut), kartu kredit (S4, S7; juga terlihat di halaman checkout toko Lynk.id live yang terindeks publik). Daftar persis per-checkout bisa berbeda — **[TIDAK DITEMUKAN]** daftar definitifnya di S1/S2.
- [SEKUNDER, dari Terms via S6] Pembeli **tidak wajib punya akun** Lynk.id; cukup email aktif untuk konfirmasi transaksi dan invoice.
- Lynk.id **bukan marketplace** (S4/S6): tidak ada lalu lintas pembeli bawaan. Pembeli datang dari promosi penjual sendiri (untuk ACE: Threads/Facebook). Ini menentukan urutan kerja: produk tanpa jalur promosi = rak kosong yang rapi, bukan penjualan.

**Pengaturan pencairan (payout) — [RESMI, S2]:**
1. Login → menu **Settings** (panel kiri) → **Payout Settings**.
2. Tambahkan **rekening bank** tujuan pencairan (hanya bank yang terdaftar di sistem Lynk.id yang bisa dipakai — panduan resmi input rekening via S6; nama pemilik + nomor rekening harus sesuai catatan bank — [SEKUNDER] panduan input rekening).
3. Setelah rekening terpasang, klik **Withdraw**, isi jumlah, klik **Review**, konfirmasi.

**Aturan penarikan — [RESMI, S2/S8, kata per kata substansinya]:**
- **Saldo minimum penarikan: Rp100.000.**
- **Batas maksimum penarikan: Rp200.000.000.**
- **Frekuensi: tidak ada batas.**
- **Biaya: Gratis (Free) Rp5.000 per penarikan; Pro gratis.**
- **Waktu proses: paling lama 2 hari kerja.**
- Penarikan bisa tertunda/ditolak bila data rekening tidak valid atau saldo kurang; penarikan berikutnya harus menunggu proses sebelumnya selesai (S2).

**Konflik sumber — dicatat, tidak dihaluskan:**
- Satu panduan pihak ketiga (Taien, ~Agustus 2026) mengklaim pencairan "setiap tanggal 25 setiap bulan" untuk penghasilan bulan sebelumnya. Ini **bertentangan** dengan tutorial resmi S2 (penarikan atas permintaan, maks 2 hari kerja). Yang dipakai dokumen ini: **S2 (resmi)**. Klaim tanggal-25 berstatus tidak terverifikasi.
- Waktu proses di Terms disebut "paling lambat 3 hari kerja" oleh S6, vs "2 hari kerja" di S2/FAQ. Selisih kecil tapi nyata → pakai angka konservatif **2–3 hari kerja** dalam perencanaan, dan anggap S2 sebagai janji operasional, Terms sebagai batas hukum.
- **Tujuan pencairan selain bank:** PayPal disebut sebagai opsi pencairan oleh panduan pihak ketiga; **e-wallet sebagai tujuan pencairan [TIDAK DITEMUKAN] di sumber resmi yang dibuka** (S2 hanya menyebut bank). Jangan merencanakan pencairan ke e-wallet.

**Verifikasi identitas/KYC:**
- **[TIDAK DITEMUKAN]** di S1/S2: persyaratan KTP/verifikasi identitas penjual sebelum bisa menarik dana. Satu rekaman tutorial pengguna (Instagram, 2026-09-12) memperlihatkan formulir Payout Setting yang meminta foto buku tabungan dan KTP — [SEKUNDER, satu sumber, tidak resmi]. Karena akun dan identitas adalah sisi pemilik (pola KBM), siapkan kemungkinan ini: **pemilik mungkin diminta KTP + data rekening atas nama yang sama** saat pertama mengatur payout. Ini penghambat potensial yang hanya pemilik yang bisa menyelesaikan.

**Syarat penjual lain (dari Terms, via S6 [SEKUNDER]):** kreator berusia minimal 18 tahun atau punya izin orang tua/wali; kreator wajib mengirim produk yang sudah dibayar (kegagalan dapat membuat pembayaran ditahan/akun dinonaktifkan); konten terlarang mencakup pornografi, perjudian, kriminal, SARA, dsb.; Lynk.id dapat mengubah ketentuannya sewaktu-waktu. Produk ACE yang direncanakan (templat/metode/teks edukasi) tidak menyentuh kategori terlarang mana pun.

### 1.7 Checklist kesiapan toko (begitu alamat `lynk.id/<nama>` dilaporkan pemilik)

Urutan ini yang akan dijalankan diverifikasi, bukan sebelumnya:

- [ ] Alamat toko terverifikasi ada (halaman publik bisa dibuka, nama sesuai laporan pemilik).
- [ ] Paket akun terkonfirmasi: Gratis (asumsi awal) — baca fee transaksi yang **tertulis di dashboard pemilik** dan cocokkan dengan angka [SEKUNDER] 5% di §1.5; catat selisih bila ada.
- [ ] Payout Settings: status rekening (terpasang/belum) — pengisian data bank/KTP adalah **tindakan pemilik**, ruang ini hanya mencatat statusnya.
- [ ] Satu produk uji dibuat dalam keadaan **belum dipromosikan** untuk membaca alur checkout + email pengiriman tautan secara nyata (hanya bila produk pertama sudah lolos §2 dan ada keputusan tata-kelola untuk memajang).
- [ ] Simulasi bersih pertama dihitung dari angka nyata: harga − 5% − (Rp5.000 penarikan diamortisasi) → ambang harga minimum yang masuk akal terhadap ambang tarik Rp100.000.

---

## BAGIAN 2 — Memo Kandidat Produk Pertama

Prinsip seleksi: kandidat hanya boleh mengklaim kemampuan yang **sudah terverifikasi dengan bukti** di rekam ACE per 2026-11-13. Tiga jangkar bukti yang boleh dipakai:

- **(A) Instrumen & praregistrasi yang benar-benar berjalan:** instrumen G1 teruji (tes lulus, termasuk verifikasi ulang independen 8 tes OK oleh ruang bangku Antigravity, 2026-11-13); desain instrumen G3/G4/G5 selesai sebagai **desain yang diratifikasi** (PR #136 dkk.) — status jujurnya: G3/G4/G5 **NOT_ASSESSED**, instrumen bukan asesmen.
- **(B) Siklus direktur lokal yang terekam:** siklus direktur Qwen lokal berjalan dengan validator, dossier B2A, dan perbaikan (repair fixture) — bukti proses, bukan bukti keunggulan umum.
- **(C) Praktik pelaporan & audit bukti:** roll-up berkala dengan label TERVERIFIKASI / BERJALAN / BELUM TERVERIFIKASI, desain pilot KBM dengan hipotesis yang bisa gagal + aturan lanjut/berhenti yang dipraregistrasi (PR #144, desain saja, produksi belum dimulai oleh keputusan tata-kelola).

Tidak boleh diklaim oleh produk mana pun: hasil G3/G4/G5, pendapatan KBM (terukur Rp0), pertumbuhan Facebook/Threads sebagai "metode terbukti cuan", atau materi apa pun dari ruang diskusi / karya KBM.

### Kandidat 1 — Templat Praregistrasi & Audit Bukti untuk Eksperimen AI Lokal *(rekomendasi pertama)*

- **Bentuk:** PDF + ZIP berisi templat kosong-siap-isi (Markdown): (i) lembar praregistrasi eksperimen (hipotesis yang bisa gagal, metrik, ambang putusan, aturan berhenti), (ii) checklist audit bukti (klaim ↔ sumber ↔ tanggal ↔ status verifikasi), (iii) format roll-up TERVERIFIKASI / BERJALAN / BELUM TERVERIFIKASI, (iv) satu contoh terisi yang **dianonimkan dan digeneralisasi** dari pola kerja ACE (bukan menyalin dokumen internal, bukan materi ruang diskusi).
- **Ikatan kemampuan terverifikasi:** langsung dari jangkar (A) + (C) — ini adalah artefak dari praktik yang benar-benar dijalankan dan diratifikasi desainnya, dijual sebagai *metode*, bukan sebagai hasil. Klaim sampul yang jujur: "templat dari praktik evaluasi yang sedang berjalan", **bukan** "sistem AI terbukti".
- **Harus ADA sebelum bisa dipajang:**
  1. Berkas final PDF+ZIP <100 MB, lolos baca-ulang penuh (tidak ada nama pemilik, tidak ada isi ruang privat, tidak ada kutipan karya KBM).
  2. Contoh terisi yang sudah digeneralisasi (butuh 1 putaran penulisan ulang khusus produk — isi handover internal tidak boleh dijual apa adanya).
  3. Halaman produk: judul, deskripsi jujur (termasuk batas: ini templat metode, bukan konsultasi, bukan jaminan hasil), gambar sampul, Price/Sale Price.
  4. Keputusan tata-kelola ACE untuk memajang (dokumen ini tidak mengambilnya).
- **Perkiraan usaha produksi:** **Kecil–sedang.** Materi sumber ada; pekerjaan utamanya generalisasi + penyuntingan + tata letak: ±1–2 sesi kerja ruang menulis/pos ini. Risiko utama bukan produksi melainkan kebocoran privasi bila generalisasi ceroboh — wajib 1 putaran pemeriksaan pagar sebelum tayang.
- **Catatan harga (bukan keputusan):** dengan fee 5% + ambang tarik Rp100.000, harga satuan rendah berarti perlu banyak penjualan sebelum pencairan pertama mungkin. Ini argumen untuk harga kelas puluhan-ribu dan/atau bundel dengan Kandidat 3, bukan untuk menaikkan klaim.

### Kandidat 2 — Karya Tulis Mandiri di Luar KBM (e-book/serial pendek orisinal)

- **Bentuk:** Satu karya fiksi/nonfiksi **baru** yang ditulis khusus untuk Lynk.id (PDF/e-book), tidak pernah diterbitkan di KBM dan tidak terkait naskah KBM mana pun.
- **Ikatan kemampuan terverifikasi:** kemampuan menulis adalah kapasitas yang sedang diuji di venue KBM (desain pilot selesai, PR #144) — tetapi hasil KBM sendiri **belum terukur** (pendapatan Rp0, produksi serial pilot belum dimulai). Jadi ikatannya paling lemah dari tiga kandidat: yang terverifikasi adalah *desain & kesiapan produksinya*, bukan sambutan pembaca.
- **Harus ADA sebelum bisa dipajang:**
  1. Keputusan tata-kelola produksi (sama seperti pilot KBM: memulai produksi adalah keputusan tercatat, bukan bawaan dokumen ini).
  2. Naskah **selesai penuh** (bukan bab pertama saja) — menjual karya bersambung yang belum tamat di kasir sekali-bayar adalah risiko refund/reputasi menurut kewajiban pengiriman di Terms.
  3. Pemeriksaan pagar ganda: bukan karya KBM, bukan turunan materi ruang diskusi.
- **Perkiraan usaha produksi:** **Besar.** Penulisan karya utuh = pekerjaan terbesar dari tiga kandidat (orde berminggu-minggu bila mengikuti standar ≥1.000 kata/bab × banyak bab, meski standar itu milik desain KBM, bukan syarat Lynk.id). Menulisnya juga **bersaing sumber daya** dengan pilot KBM yang sudah didesain lebih dulu.
- **Putusan memo:** layak sebagai kandidat **kedua/kemudian**, bukan produk pertama. Rak kasir tidak boleh menunggu naskah tamat.

### Kandidat 3 — Paket Prompt & Kerangka Kerja Terdokumentasi: "Siklus Direktur Lokal"

- **Bentuk:** PDF (+ berkas teks .md/.txt dalam ZIP) berisi kerangka prompt dan lembar kerja untuk menjalankan siklus peninjauan berkala dengan model lokal: formulir agenda siklus, format dossier masukan, aturan validator (terima/tolak usulan direktur), dan format catatan keputusan — ditulis sebagai dokumentasi metode dari jangkar (B).
- **Ikatan kemampuan terverifikasi:** siklus direktur lokal ACE benar-benar berjalan berulang (siklus #4 terekam ACCEPTED dengan agenda dan waktu proses tercatat). Yang dijual: **kerangka kerja dari praktik nyata satu sistem** — dengan batas tertulis bahwa ini bukan model, bukan perangkat lunak ACE, dan tidak ada janji performa di mesin/pemakaian lain.
- **Harus ADA sebelum bisa dipajang:**
  1. Distilasi dari dokumen siklus internal menjadi versi publik yang berdiri sendiri (tanpa dependensi pada repo ACE, tanpa digest/artefak internal, tanpa materi ruang diskusi).
  2. Uji pakai kering oleh pembaca awam internal: apakah orang tanpa konteks ACE bisa mengikuti lembar kerjanya? Bila tidak, produk belum jadi.
  3. Pernyataan batas & prasyarat teknis yang jujur di deskripsi (membutuhkan model lokal + runtime sendiri; Rp0 API bukan fitur produk ini melainkan pilihan penyiapan pembeli).
- **Perkiraan usaha produksi:** **Sedang.** Sumbernya ada dan terstruktur, tetapi distilasi ke publik + uji keterbacaan = ±2–3 sesi. Risiko utama: produk terasa terlalu khusus (pasar sempit) — mitigasinya adalah memasangkannya sebagai bundel/kelas lanjutan dari Kandidat 1, bukan menipiskannya.
- **Putusan memo:** kandidat pendamping terbaik untuk Kandidat 1 (satu tema: bekerja dengan AI secara terukur), diproduksi setelah Kandidat 1 tayang atau bersamaan bila kapasitas menulis memungkinkan.

### Ringkasan memo

| Kandidat | Jangkar bukti | Usaha | Urutan disarankan |
|----------|---------------|-------|-------------------|
| 1. Templat Praregistrasi & Audit Bukti | (A)+(C) — terkuat | Kecil–sedang | **Pertama** |
| 3. Paket Prompt "Siklus Direktur Lokal" | (B) — kuat, pasar sempit | Sedang | Kedua / bundel K1 |
| 2. Karya tulis mandiri luar KBM | Desain saja — terlemah | Besar | Kemudian |

**Yang belum diputuskan (sengaja):** harga final, tanggal tayang, dan apakah produksi Kandidat 1 dimulai — ketiganya menunggu (i) alamat toko dari pemilik, (ii) hasil checklist §1.7, dan (iii) keputusan tata-kelola ACE. Dokumen ini menyiapkan rak; ia tidak membuka toko.

---

## BAGIAN 3 — Draf Spesifikasi Produksi Kandidat 1

> **Status bagian ini: SPESIFIKASI, bukan produk.** Bagian ini tidak menulis isi produk, tidak memajang apa pun, dan tidak memulai produksi. Keputusan memproduksi tetap tata-kelola koordinator. Bila produksi disetujui nanti, bagian inilah kontrak kerjanya.
>
> **Koreksi status gerbang yang dipakai spesifikasi ini** (lebih baru & lebih tepat dari penyederhanaan di Bagian 2, mengikuti papan gerbang terverifikasi): **G1 = MEASURED — DEMONSTRATED dengan kualifikasi** (kualifikasinya: bukti C3 menunjukkan kemampuan resume substrat tempat eksperimen utama berjalan, bukan interupsi pada eksperimen utamanya sendiri); **G2 = MEASURED — null ×2**; **G3, G4, G5 = NOT_ASSESSED** (desain instrumennya selesai & diratifikasi — desain bukan asesmen). Setiap penyebutan sumber kemampuan di bawah memakai status persis ini.

### 3.1 Identitas produk (spesifikasi)

- **Judul kerja:** *Templat Praregistrasi & Audit Bukti untuk Eksperimen AI Lokal*
- **Janji produk yang diizinkan (satu kalimat):** "Seperangkat templat kosong-siap-isi dan contoh terisi fiktif untuk merencanakan eksperimen AI secara praregistrasi dan mengaudit buktinya secara jujur."
- **Yang dijual:** METODE (lembar kerja, daftar periksa, format laporan). **Bukan** hasil ACE, bukan perangkat lunak, bukan model, bukan akses ke sistem ACE mana pun.
- **Bentuk akhir (target):** 1 berkas PDF utama (target perencanaan ±30–45 halaman A4 — angka perencanaan, bukan janji) + 1 berkas ZIP berisi semua templat sebagai berkas Markdown (.md) kosong-siap-isi. Gabungan jauh di bawah batas 100 MB paket Gratis (§1.3).
- **Versi:** v1.0, bertanggal; lembar status gerbang sumber di dalam produk (Bab 0 & Lampiran C) adalah potret status **per tanggal penulisan produk**, dan wajib diperbarui bila produk direvisi — tidak boleh dibiarkan mengklaim status yang sudah berubah.
- **Lisensi pemakaian (spesifikasi):** pemakaian pribadi/tim pembeli; bukan untuk dijual ulang apa adanya. Rumusan finalnya ditulis saat produksi, bukan di sini.

### 3.2 Daftar isi lengkap + sumber kemampuan + bentuk contoh tergeneralisasi

Untuk tiap bagian: **(S)** = sumber kemampuan ACE yang menjadi dasar metodenya; **(C)** = bentuk contoh terisi yang akan menyertainya di produk. Semua contoh di produk bersifat **fiktif-tergeneralisasi**: tokoh, proyek, dan angka adalah rekayasa yang **ditandai sebagai rekayasa di dalam produk**, dibangun dari *pola* metode ACE — tidak satu pun menyalin dokumen internal, isi ruang mana pun, digest/hash internal, atau karya KBM.

**Bab 0 — Halaman Kejujuran Sumber (provenance & batas, 2–3 hlm.)**
- Isi: asal-usul metode (praktik evaluasi satu proyek AI lokal), tabel status gerbang sumber persis per §3 pembuka (G1 DEMONSTRATED berkualifikasi; G2 null ×2; **G3/G4/G5 NOT_ASSESSED**), dan daftar tegas apa yang *tidak* diklaim produk ini.
- (S) Praktik kejujuran status ACE sendiri (papan gerbang; aturan "instrumen ≠ asesmen").
- (C) Tidak ada contoh — bab ini pernyataan, bukan templat. Posisinya di depan, bukan di catatan kaki.

**Bab 1 — Kenapa Praregistrasi, dan Lembar Praregistrasi Inti (5–6 hlm.)**
- Isi templat: hipotesis yang *bisa gagal* (kalimat + kondisi kegagalannya); variabel yang diubah & yang ditahan; metrik utama + metrik pengaman; ambang putusan sebelum data dilihat; aturan lanjut/berhenti; tanggal & versi protokol.
- (S) Praktik praregistrasi ACE yang berjalan: protokol eksperimen A/B/C G1 (terdaftar sebelum jalan, hash protokol tercatat, hasil kemudian dinilai terhadapnya) + desain pilot KBM (metrik & aturan lanjut/berhenti dipraregistrasi di dalam desainnya, PR #144 — sebagai *pola desain*, isi pilotnya sendiri tidak dipakai).
- (C) Contoh terisi fiktif: "Eksperimen Sari" — membandingkan dua konfigurasi prompt pada 20 soal aritmetika dengan model lokal kecil; hipotesis ditulis dalam bentuk yang benar-benar bisa gugur, ambang putusannya angka bulat rekayasa.

**Bab 2 — Merancang Instrumen: Klausul, Bukti yang Diterima, Fail-Closed (5–6 hlm.)**
- Isi templat: tabel klausul (klaim → bukti yang diterima → bukti yang ditolak → putusan bila bukti absen); skala putusan tertutup (mis. TERBUKTI / SEBAGIAN / TIDAK TERBUKTI / BELUM DINILAI); aturan fail-closed (bukti hilang = klausul gugur, bukan "dianggap lulus").
- (S) **Desain instrumen G3/G4/G5 yang diratifikasi** (PR #136 dkk.: klausul C1–C3 per gerbang, spesies bukti yang diterima, putusan fail-closed) **dan** instrumen G1 yang sudah dipakai menilai. Di dalam produk wajib tertulis: bagian G3–G5 dari bab ini bersumber dari *desain teratifikasi yang belum pernah menghasilkan asesmen* — **G3/G4/G5 NOT_ASSESSED** — sedangkan pola G1-nya bersumber dari instrumen yang sudah menghasilkan satu asesmen DEMONSTRATED berkualifikasi.
- (C) Contoh terisi fiktif: instrumen mini untuk klaim "ringkasan mingguan membuat pemilik proyek paham kemajuan" — 3 klausul, satu klausul sengaja dibuat gugur karena buktinya absen, untuk menunjukkan fail-closed bekerja.

**Bab 3 — Ledger Bukti & Rantai Audit (4–5 hlm.)**
- Isi templat: tabel ledger (id klaim ↔ artefak bukti ↔ tanggal ↔ penilai ↔ status verifikasi); aturan "satu klaim, satu rantai"; daftar periksa audit silang (apakah artefak yang dikutip benar isinya, bukan hanya judulnya).
- (S) Aplikasi instrumen G1 pada bukti yang sudah ada: entri ledger terverifikasi & audit bersih pada penilaian G1 (bagian dari asesmen DEMONSTRATED-nya); ditambah praktik verifikasi disk artefak ACE (membaca berkas, bukan memercayai laporan tentang berkas).
- (C) Contoh terisi fiktif: ledger 6 baris untuk "Eksperimen Sari" dari Bab 1, termasuk satu baris berstatus DITOLAK karena artefaknya ternyata ringkasan, bukan data mentah.

**Bab 4 — Kontrol Atribusi: Dengan vs Tanpa (4–5 hlm.)**
- Isi templat: desain lengan pembanding (kondisi dengan artefak/metode X vs tanpa X pada tugas yang sama-sama belum pernah dilihat); aturan tugas held-out; tabel selisih hasil; kalimat interpretasi yang diizinkan & yang dilarang.
- (S) Dua lapis yang **wajib dipisah di dalam produk**: (i) protokol perbandingan A/B/C dari eksperimen G1 — lapis yang terukur; (ii) klausul kontrol atribusi warisan pada **desain G4 teratifikasi** (penerus dengan vs tanpa artefak warisan) — lapis desain, **G4 NOT_ASSESSED**, belum pernah dijalankan sebagai asesmen. Produk mengajarkan bentuk desainnya, bukan hasilnya.
- (C) Contoh terisi fiktif: perbandingan "dengan templat catatan vs tanpa templat" pada 8 tugas menulis-terstruktur; hasil contoh sengaja dibuat *tipis* (selisih kecil) agar kalimat interpretasinya mencontohkan kehati-hatian, bukan euforia.

**Bab 5 — Melaporkan Hasil Nol & Hasil yang Tak Meyakinkan (3–4 hlm.)**
- Isi templat: format laporan hasil null (hipotesis, yang dijalankan, angka apa adanya, apa yang *tidak* boleh disimpulkan, keputusan berikutnya); format laporan tak-meyakinkan (inconclusive) dan bedanya dari null; aturan "hasil nol adalah hasil".
- (S) Praktik terverifikasi ACE: **G2 MEASURED — null ×2** (diukur, dilaporkan sebagai null, tidak dipoles) dan eksperimen kontras OMEGA-11 (hipotesis latih GUGUR, holdout TAK MEYAKINKAN — keduanya diterbitkan apa adanya).
- (C) Contoh terisi fiktif: laporan null satu halaman untuk eksperimen lanjutan "Sari" (konfigurasi ketiga tidak berbeda dari kontrol) + satu paragraf contoh versi tak-meyakinkan.

**Bab 6 — Roll-Up Berkala: TERVERIFIKASI / BERJALAN / BELUM TERVERIFIKASI (3–4 hlm.)**
- Isi templat: format roll-up satu layar (papan status → pekerjaan berjalan → antrean → penghambat → risiko waktu); aturan pelabelan per butir; aturan "perubahan belum terverifikasi tidak memicu laporan"; aturan penggabungan laporan (batching) agar pembaca tidak disepam.
- (S) **Praktik roll-up ruang operasi ACE yang terverifikasi**: format 7-bagian berlabel TERVERIFIKASI / BERJALAN / BELUM TERVERIFIKASI yang dipakai nyata, termasuk koreksi cadence dari pemilik (laporan digabung, bukan satu per tugas) — *format dan pelajarannya* yang dipakai; isi laporannya tidak.
- (C) Contoh terisi fiktif: roll-up mingguan satu halaman proyek rekaan "Studio Foto Bima", 7 butir berlabel lengkap, termasuk satu butir BELUM TERVERIFIKASI yang jujur soal penyebabnya.

**Bab 7 — Ringkasan untuk Pembaca Non-Teknis: Empat Bidang Wajib (3 hlm.)**
- Isi templat: ringkasan per unit kerja dalam empat bidang — **DICOBA / HASIL / KEYAKINAN / BATAS** — beserta uji kelengkapan (bidang yang hanya diisi nomor artefak tanpa narasi = tidak terhitung lengkap) dan aturan bahasa polos.
- (S) **Desain G5 teratifikasi**, klausul C1-nya (kelengkapan ringkasan terhadap empat bidang FR-09) — dengan status tertulis di produk: ini desain teratifikasi, **G5 NOT_ASSESSED**; praktik ringkasan ACE saat ini sendiri dinilai jujur di desainnya sebagai belum seragam terhadap empat bidang ini, dan kalimat itu ikut dicontohkan sebagai cara menulis batas.
- (C) Contoh terisi fiktif: satu unit kerja dari "Eksperimen Sari" diringkas dalam empat bidang, berdampingan dengan versi buruknya (hanya berisi kode artefak) yang dicoret sebagai contoh gagal uji.

**Bab 8 — Audit Bukti Mandiri: Daftar Periksa Akhir (2–3 hlm.)**
- Isi: daftar periksa satu atap yang merangkai Bab 1–7 menjadi urutan audit 15–20 butir sebelum sebuah klaim boleh disebut terukur; kolom putusan akhir per klaim.
- (S) Gabungan praktik audit ACE: triase klaim-vs-bukti (memisahkan dokumen dari kode, kode-bertes dari kode-tanpa-tes, hasil negatif sungguhan dari klaim tanpa dasar) yang dijalankan pada tumpukan PR ACE.
- (C) Contoh terisi fiktif: hasil audit atas tiga klaim rekaan dengan tiga putusan berbeda (lolos / lolos berkualifikasi / gugur).

**Lampiran A — Semua Templat Kosong (isi ZIP)**
- Daftar berkas yang dispesifikasi: `01-praregistrasi.md`, `02-instrumen-klausul.md`, `03-ledger-bukti.md`, `04-kontrol-atribusi.md`, `05-laporan-null.md`, `06-rollup.md`, `07-ringkasan-empat-bidang.md`, `08-audit-akhir.md`, `README-mulai-di-sini.md`. Isi berkas-berkas ini **belum ditulis** — daftar ini spesifikasinya.
- (S) Gabungan Bab 1–8. (C) Tidak ada.

**Lampiran B — Glosarium & Batas Pemakaian (2 hlm.)**
- Isi: definisi polos (praregistrasi, klausul, fail-closed, held-out, atribusi, null, inconclusive); batas: bukan konsultasi, bukan jaminan hasil eksperimen pembeli, bukan pengganti peninjauan sejawat untuk klaim berisiko tinggi.

**Lampiran C — Lembar Status Gerbang Sumber (1 hlm., wajib, tidak boleh dihapus dalam revisi)**
- Isi: pengulangan tabel Bab 0 dalam bentuk satu halaman bertanggal: G1 DEMONSTRATED berkualifikasi (dengan kalimat kualifikasinya utuh), G2 null ×2, **G3 NOT_ASSESSED, G4 NOT_ASSESSED, G5 NOT_ASSESSED**, plus kalimat: "Produk ini menjual metode yang dipraktikkan pada gerbang yang sudah terukur dan dirancang untuk gerbang yang belum terukur. Belum terukur berarti belum terukur."

### 3.3 Urutan produksi (bila & hanya bila disetujui tata-kelola)

1. **Distilasi:** turunkan tiap bab dari sumber kemampuannya menjadi kerangka publik yang berdiri sendiri (tanpa dependensi repo/dokumen internal).
2. **Generalisasi:** tulis semua contoh sebagai fiksi rekayasa (Sari/Bima), tandai sebagai rekayasa; jalankan sapuan pagar pertama (§3.4 butir 1–5).
3. **Penulisan templat kosong** Lampiran A dari bab-bab final (bukan sebaliknya — templat adalah turunan isi, agar tidak menjanjikan yang tak diajarkan).
4. **Uji awam internal:** satu pembaca tanpa konteks ACE mengikuti Bab 1 + Bab 6 hanya dari produk; titik bingungnya dicatat & diperbaiki.
5. **Audit klaim menyeluruh** (§3.4 butir 6–10) termasuk naskah halaman penjualan (judul/deskripsi/sampul tunduk pada daftar periksa yang sama).
6. **Paket final:** PDF + ZIP, metadata berkas dibersihkan, ukuran & keterbacaan diverifikasi, lembar Lampiran C dicek terhadap papan gerbang *pada hari itu*.

Perkiraan usaha tetap seperti Bagian 2: kecil–sedang (±1–2 sesi untuk draf isi penuh mengikuti langkah 1–4; audit & paket ±1 sesi). Perkiraan, bukan komitmen jadwal.

### 3.4 Daftar periksa pagar sebelum-tayang (semua harus LULUS; satu GAGAL = tidak tayang)

**Privasi & asal-usul**
- [ ] 1. Nol kutipan/parafrase materi ruang diskusi, ruang operasi, atau ruang privat mana pun.
- [ ] 2. Nol dokumen internal ACE disalin apa adanya (handover, dossier, addendum) — yang boleh hanya *pola metode* yang sudah didistilasi & digeneralisasi.
- [ ] 3. Nol nama pemilik, nama akun, alamat toko/URL selain yang memang publik-untuk-produk, kode undangan, nomor PR/digest/hash internal, jalur berkas internal, atau tangkapan layar sistem internal.
- [ ] 4. Nol materi karya KBM (isi, tokoh, atau turunannya) — produk ini bukan karya KBM dan tidak meminjam isinya.
- [ ] 5. Semua contoh terisi lolos uji asal: tokoh/proyek/angka adalah rekayasa bertanda, tidak dapat ditelusur balik ke peristiwa internal tertentu.

**Kejujuran klaim**
- [ ] 6. Setiap klaim kemampuan di naskah produk **dan** halaman penjualan dipetakan satu-satu ke sumbernya di §3.2; klaim tanpa sumber = dihapus, bukan dilembutkan.
- [ ] 7. Bab 0 dan Lampiran C hadir, utuh, dan mutakhir per hari penayangan: G1 berkualifikasi tertulis lengkap; **G3, G4, G5 tertulis NOT_ASSESSED**; G2 tertulis null.
- [ ] 8. Nol klaim hasil untuk hal yang baru didesain: tidak ada kalimat yang menyatakan atau menyiratkan G3/G4/G5 (atau kemampuan turunannya) sudah terbukti.
- [ ] 9. Nol janji pendapatan/hasil bagi pembeli; nol testimoni; nol kata "terbukti" kecuali menunjuk persis ke asesmen G1 berkualifikasi atau hasil null G2.
- [ ] 10. Deskripsi produk di Lynk.id (Price/Sale Price, judul, sampul, Custom Message) lolos butir 6–9 yang sama — pagar berlaku di etalase, bukan hanya di dalam PDF.

**Teknis berkas**
- [ ] 11. PDF terbaca penuh halaman pertama–terakhir; ZIP terbuka dan berisi persis daftar Lampiran A; total ukuran <100 MB.
- [ ] 12. Metadata berkas (penulis, jalur, komentar) dibersihkan; tidak ada tautan internal yang hidup di dalam berkas.

---

## BAGIAN 4 — Hasil Verifikasi §1.7 (dashboard nyata, 2026-11-13 ~01:31–01:34 WIB)

Toko: **lynk.id/dianma25 (@dianma25)**. Metode: baca-saja di dashboard sesi pemilik; tidak ada pengaturan diubah, tidak ada produk dibuat, formulir dibuka lalu ditinggalkan (daftar blok tetap kosong sesudahnya).

**Jadi FAKTA (mengunci [SEKUNDER] Bagian 1):**
- Plan akun: **Free** (Settings → SUBSCRIPTION: "Free package"). Saldo Earnings Rp0, penjualan/pesanan seumur toko 0.
- Fee transaksi: **Free 5% / Pro 3%** — tertulis di Earnings ("5% fee applies to the total transaction") dan tabel perbandingan upgrade.
- Biaya penarikan: **Free Rp5.000 / Pro gratis** (tabel upgrade).
- Batas file: **Free maks 100 MB / Pro 5 GB**; video e-course Free 10 menit / Pro 480 menit (tabel upgrade).
- Formulir produk digital persis seperti tutorial resmi + tambahan nyata: pilihan Platform = Upload / PDF-Ebook / G-drive / Other; mode PDF/Ebook punya proteksi Member Area (Read Only streaming atau Allow Download); ada Flash Sale, pay-what-you-want, Item Quantity, Release Time, Custom Message, Question for Customer (Name/Phone).
- Formulir bank (Settings → Payout Settings → Edit Bank): Bank Name (dropdown), Bank Account Number, Account Name, **unggah Bank Account Book**, **unggah ID Card (KTP)**, **"Explain your business" (wajib)**, Account Type Personal/Company. Tidak ada kolom selfie; tidak ada kolom NPWP untuk tipe Personal (hanya catatan Tax Information).

**GUGUR / BERBEDA dari [SEKUNDER]:**
- Harga Pro: **Rp59.000/bulan, Rp499.000/tahun, Rp949.000/2 tahun, sudah termasuk PPN 11%** (dialog upgrade) — BUKAN Rp99.000/bulan di luar PPN. Angka sekunder Rp99.000 gugur untuk akun ini hari ini.
- Biaya tambahan yang tidak ada di daftar sekunder kemarin, kini teramati di dashboard: **"Fee Rp600/transaksi"** pada Advance Option formulir produk, dan **fee per kanal pembayaran** di Settings → Payment Method (bertanda "All fees are net"): QRIS 0,70%; OVO/ShopeePay/DANA 1,67%; VA BCA Rp4.400, VA lain Rp3.000–4.000; kartu kredit 2,90% + Rp2.500; ATM Bersama Rp3.000; retail Rp5.000. **Apakah fee kanal ini menumpuk di atas 5% atau termasuk di dalamnya: BELUM terverifikasi** (0 transaksi) — wajib dibaca dari struk transaksi pertama; simulasi harga §1.7 tidak boleh dianggap final sebelum itu.

**TETAP BELUM TERVERIFIKASI (tidak tertulis di dashboard mana pun yang diperiksa):**
- Minimum penarikan Rp100.000 dan waktu proses 2 hari kerja: hanya dari FAQ resmi (S2), **tidak tampil** di halaman Earnings/Payout/Bank/Upgrade. Formulir penarikan sendiri tidak bisa dibuka — tombol Withdraw terhalang: "Please validate your bank account first".
- Praktik pemotongan fee 5% (belum ada penjualan).

**Keadaan payout/KYC hari ini:**
- Belum ada rekening tersimpan → penarikan belum mungkin. Mengisinya = tindakan pemilik (data bank + unggah buku tabungan & KTP + deskripsi bisnis).
- Status "Verified Account"/KYC: menurut dialog resminya transaksi & penarikan **tetap bisa tanpa status Verified** selama produk mematuhi Terms; Verified memberi penarikan instan. Alur KYC saat ini terhalang validasi bank ("KYC cannot be processed. Please validate your bank account first") — jadi urutan nyatanya: bank dulu, KYC sesudahnya.

---

## BAGIAN 5 — Draf Teks "Explain your business" (untuk formulir bank, ditempel pemilik)

> Draf siap tempel untuk kolom wajib "Explain your business" pada formulir bank (Bagian 4). Pengisian formulir, data bank, dan unggahan KTP/buku tabungan tetap tangan pemilik sendiri. Batas kolom tidak terverifikasi saat baca-saja kemarin — karena itu disediakan dua versi.

**Versi utama:**

```
Kreator perorangan. Toko ini menjual produk digital edukasi berupa templat
dan lembar kerja metode evaluasi untuk eksperimen AI lokal — praregistrasi
eksperimen dan audit bukti — dalam format PDF dan berkas templat, dikirim
otomatis lewat Lynk.id. Toko baru dibuat dan produk pertama sedang
disiapkan; belum ada penjualan. Promosi melalui Threads @dianzherdiana16.
Toko: lynk.id/dianma25
```

**Versi ringkas (bila kolom pendek):**

```
Kreator perorangan penjual produk digital edukasi: templat metode
praregistrasi & audit bukti untuk eksperimen AI lokal (PDF/templat,
dikirim via Lynk.id). Toko baru, produk pertama sedang disiapkan.
Threads: @dianzherdiana16 — lynk.id/dianma25
```

Catatan kejujuran draf: tidak ada klaim pendapatan, penjualan, jumlah pelanggan, atau hasil produk — karena belum ada. Frasa "sedang disiapkan" wajib dipertahankan sampai produk pertama benar-benar tayang; sesudah tayang, kalimat itu yang diganti, bukan ditambah klaim.

---

## BAGIAN 6 — Log Produksi K1 (keputusan hub: GO, 2026-11-13 ~01:54 WIB)

Paket produksi selesai di `~/workspace/ace-omega/lynkid-produk/K1/keluaran/`:
- `Templat-Praregistrasi-Audit-Bukti.pdf` — buku utama, **16 halaman A4** (39 KB). Catatan jujur: di bawah target perencanaan ±30–45 hlm di §3.1 (yang memang berlabel "angka perencanaan, bukan janji") — seluruh daftar isi §3.2 hadir lengkap (Bab 0–8 + Penutup latihan terpadu + Lampiran A/B/C); tidak ada bab yang dipangkas, halamannya saja yang lebih padat.
- `Templat-Praregistrasi-Audit-Bukti-TEMPLAT.zip` — 9 berkas persis daftar Lampiran A (6,8 KB). Gabungan paket ±46 KB, jauh di bawah batas 100 MB.
- Rekonsiliasi G1 hari produksi (periksa wajib koordinator): teks produk memakai papan pasca-Tahap J — **G1 TERBUKTI tanpa kualifikasi, kriteria v2**, dengan pembedaan spesies C3 (uji substrat vs interupsi proses utama) tertulis di Bab 0, Bab 2, dan Lampiran C. G2 null ×2; G3/G4/G5 NOT_ASSESSED (7 penyebutan eksplisit).

Hasil pagar §3.4 (audit atas berkas final, 2026-11-13):
- Butir 1–5 (privasi/asal): **LULUS** — sapuan token atas naskah+templat: 0 temuan (nama pemilik/akun, kode undangan, nomor PR, digest, jalur internal, "ACE", "KBM", materi ruang); contoh hanya Sari/Bima, bertanda fiktif di tempatnya.
- Butir 6–9 (kejujuran klaim): **LULUS** — klaim gerbang hanya di Bab 0/Lampiran C dan tertunjuk ke asesmen G1/G2; "terbukti" di luar itu hanya istilah skala putusan atau contoh fiktif bertanda; janji pendapatan hanya muncul dalam kalimat penolakan.
- Butir 10 (etalase): **BELUM BERLAKU** — belum ada naskah etalase (judul/deskripsi/sampul) yang dibuat; wajib dinilai saat listing disiapkan, sebelum tayang. Produksi ≠ listing.
- Butir 11–12 (teknis): **LULUS** — PDF terbaca penuh 16/16 halaman (teks terekstrak halaman pertama–terakhir), ZIP berisi persis 9 berkas Lampiran A, metadata PDF bersih (penulis/kreator kosong, tanpa tautan internal).

Status sesudah Bagian 6: paket SIAP LISTING dari sisi produk. Listing menunggu kesiapan toko (data bank pemilik) dan penilaian butir 10 — dua hal di luar produksi ini.

---

## BAGIAN 7 — Paket Listing Siap Nilai (2026-11-13, arahan tahap listing hub)

- Naskah etalase lengkap: `~/workspace/ace-omega/lynkid-produk/K1/sumber/naskah-etalase.md` (judul 61/100 karakter, deskripsi, Custom Message, teks sampul, mode platform). Gambar sampul jadi: `keluaran/sampul-k1.png` (1080×1080, tipografis, sudah dibaca-balik visual).
- **Pagar butir 10: LULUS.** Sapuan token etalase 0 temuan; "terbukti" hanya menunjuk gerbang dasar G1 persis sebagaimana rekonsiliasinya; NOT_ASSESSED tertulis di deskripsi etalase itu sendiri; janji hanya sebesar isi terverifikasi (PDF 16 hlm + 9 berkas); nol janji pendapatan/testimoni; "jaminan" hanya dalam kalimat penolakan.

**Usulan harga + hitungan bersih (asumsi terburuk: SEMUA fee menumpuk — 5% platform + Rp600/transaksi + fee kanal; angka dihitung mesin dari tabel fee Bagian 4):**

| Harga jual | Kanal termahal | Bersih/transaksi (terburuk) | % diterima |
|---|---|---|---|
| Rp49.000 | retail Rp5.000 | Rp40.950 | 83,6% |
| Rp59.000 | retail Rp5.000 | Rp50.450 | 85,5% |
| **Rp79.000** | retail Rp5.000 | **Rp69.450** | **87,9%** |
| Rp99.000 | kartu 2,9%+Rp2.500 | Rp88.079 | 89,0% |

(Kanal termurah QRIS 0,70%: pada Rp79.000 bersih Rp73.897. Bila ternyata fee kanal TIDAK menumpuk di atas 5%, bersih naik — skenario ini sengaja yang terburuk.)

- **Usulan: Price Rp99.000, Sale Price Rp79.000.** Pada Rp79.000: 2 penjualan skenario terburuk = Rp138.900 saldo — melewati ambang tarik Rp100.000 (dari FAQ resmi; belum tampil di dashboard) — dan setelah biaya tarik Rp5.000 menjadi Rp133.900 diterima. Harga di bawah Rp59.000 membuat ambang tarik butuh ≥3 penjualan dan memotong bersih per unit di bawah Rp51 ribu tanpa alasan pasar yang terukur (tidak ada data pasar K1; ini harga peluncuran yang bisa ditinjau dari penjualan nyata pertama, bukan dikunci selamanya).
- Harga BELUM dikunci: menunggu persetujuan hub. Go-live juga tergerbang data bank pemilik terisi.

---

## BAGIAN 8 — Paket Final Listing (arahan riset-dulu pemilik, 2026-11-13 ~02:18 WIB)

Dokumen penuh: `~/workspace/ace-omega/lynkid-produk/K1/sumber/paket-final-listing.md` (riset 11 pembanding hidup di Lynk.id + pasar: isi/format/harga/presentasi + tiga lensa + yang sengaja tidak ditiru; draf halaman final dengan daftar isi persis & FAQ 7 tanya; penghalang sisa).

- **Harga: riset MENDUKUNG persetujuan hub (Rp99.000/Rp79.000), tanpa revisi** — transaksi kategori materi AI mengumpul Rp37–88 rb; Rp79.000 = harga produk pembanding dengan bukti pembeli tampil (12 orang); segmen <Rp37 rb adalah tumpukan prompt murni, bukan kategori K1.
- Pagar butir 10 dinilai ulang atas draf final: **LULUS**.
- Penghalang sisa (di luar produk): (1) data bank pemilik — tangan pemilik; (2) **keputusan hub: mekanisme kirim dua berkas** — (a) ZIP gabungan via Upload, atau (b) folder G-Drive di akun pemilik; (3) verifikasi fee transaksi pertama = tugas pasca-live, bukan penghalang.

---

*Disusun oleh ila — ruang Lynk.id ACE, 2026-11-13 (Bagian 1–2) + Bagian 3 ditambahkan pada hari yang sama atas penugasan hub + Bagian 4 hasil verifikasi dashboard 2026-11-13 + Bagian 5 draf teks formulir bank + Bagian 6 log produksi K1 + Bagian 7 paket listing + Bagian 8 paket final riset. Sumber resmi yang dikutip dibuka langsung pada 2026-11-12 malam UTC / 2026-11-13 dini hari WIB; angka [SEKUNDER] wajib diverifikasi ulang di dashboard resmi setelah akun dibuat.*
