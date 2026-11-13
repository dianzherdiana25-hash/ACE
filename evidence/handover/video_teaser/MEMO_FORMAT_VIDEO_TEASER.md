# MEMO — Format Video Teaser Vertikal (ACE Ω, Item Kemampuan 9)

Tanggal: 2026-11-13 · Status: **FORMAT + PIPELINE SIAP, KLIP CONTOH
TERBLOKIR** (lihat §5) · Tidak ada yang diterbitkan ke mana pun.

Serial: *Setelah Diusir, Aku Pulang Sebagai Pemiliknya* (KBM)
Bab acuan: Bab 1 — "Malam Aku Diusir dari Rumah Itu"
(`~/workspace/ace-omega/handover/MENULIS_BAB01_DRAF.md`)

---

## 1. Pipeline produksi

1. **Pilih adegan** — satu beat visual tunggal per klip, diambil dari
   bab yang sudah terbit. Untuk contoh ini: adegan keluar rumah —
   Kirana melangkah melewati gerbang ke jalan gelap dengan tas kain
   di tangan, cahaya rumah dan siluet tamu di belakangnya, berhenti
   sejenak dengan wajah tenang-tegas, lalu melangkah maju. Adegan
   dipilih karena merupakan klimaks Bab 1 dan terbaca tanpa dialog.
2. **Generasi visual** — klip vertikal dihasilkan dalam gaya bank
   ilustrasi sinematik yang sudah ada
   (`handover/instagram_teaser_ilustrasi/`): ilustrasi digital
   painterly, sapuan kuas ekspresif, pencahayaan hangat dramatis,
   tokoh konsisten (Kirana, 29, rambut gelap sanggul longgar, blus
   batik marun, tas kain usang). Gerakan kamera: push-in lambat.
   Tanpa dialog, tanpa narasi suara — visual atmosferik saja.
3. **Verifikasi kutipan (mesin)** — teks overlay TIDAK diketik bebas.
   Kutipan dipilih dari naskah bab, lalu diperiksa dengan skrip
   Python kecil: kutipan harus merupakan substring persis dari berkas
   draf bab (`quote in text == True`). Kutipan yang gagal = dibuang,
   bukan diperbaiki tangan.
4. **Perakitan** — overlay teks adalah langkah pasca-produksi
   (ditambahkan di editor/platform, bukan dibakar oleh generator
   video; teks hasil generator tidak dapat dipercaya ejaannya).
   Klip contoh direncanakan memakai kutipan terverifikasi di §3
   sebagai teks overlay/caption.
5. **Gerbang terbit** — lolos pagar di §4 sebelum jadwal unggah apa
   pun dibahas.

## 2. Spesifikasi format

| Aspek | Nilai |
|---|---|
| Orientasi / rasio | Vertikal 9:16 |
| Durasi | Beberapa detik (satu beat, satu gerakan kamera) |
| Gaya visual | Ilustrasi sinematik painterly, konsisten dengan bank kartu teaser |
| Audio | Tanpa narasi/TTS; visual senyap/atmosferik saja |
| Teks overlay | Satu kutipan pendek terverifikasi mesin, ditempatkan di sepertiga bawah frame, muncul setelah hook visual |
| Timing hook | Beat terbaca dalam 1–2 detik pertama (tokoh + situasi langsung jelas sebelum teks muncul) |
| Struktur | Adegan → jeda beat → kutipan → selesai (tanpa CTA suara) |

## 3. Kutipan terverifikasi (untuk klip contoh Bab 1)

- Kutipan: **"Mulai besok, aku cari kerja."**
- Sumber: kalimat penutup Bab 1, diucapkan Kirana kepada Rini.
- Verifikasi mesin (2026-11-13): substring persis dari
  `MENULIS_BAB01_DRAF.md` → `True`. Konteks berkas:
  `"Rin," kata Kirana. "Mulai besok, aku cari kerja."`
  (baris terakhir bab sebelum penanda bersambung).

## 4. Pagar (mengikat)

- **Klip pendek saja.** Satu bab = maksimal klip teaser pendek,
  bukan bacaan bab.
- **DILARANG bacaan TTS serial utuh** — temuan riset: risiko
  penolakan kanal tertinggi. Tidak ada jalur audio-narasi bab.
- **Urutan bab:** teaser bab n hanya boleh dibuat/dijadwalkan
  SETELAH bab n tayang di KBM.
- **Gerbang kualitas akun utama:** penempatan klip di akun yang
  menyandang nama pemilik tunduk pada gerbang kualitas akun utama;
  akun utama bukan tempat eksperimen.
- Tidak ada teks karangan: setiap kata overlay/caption yang mengutip
  bab wajib lolos verifikasi substring mesin (§1 langkah 3).

## 5. Fakta produksi klip contoh — TERBLOKIR

- Percobaan generasi: satu panggilan `media.generate_video`
  (prompt adegan keluar rumah, 9:16, gaya painterly bank) pada
  2026-11-13.
- Hasil: **gagal permanen untuk akun ini** — layanan generasi video
  tidak tersedia di negara/wilayah akun (HTTP 403,
  `video_not_available`). Ini batasan langgeng, bukan gangguan;
  mencoba ulang tidak akan membantu dan tidak dilakukan.
- Konsekuensi: berkas klip contoh **tidak ada**. Memo ini, spesifikasi
  format, pipeline, dan kutipan terverifikasi adalah deliverable yang
  selesai; produksi klip menunggu jalur video yang sah tersedia.
- Jalur pengganti yang MEMUNGKINKAN (keputusan di luar memo ini,
  belum dikerjakan): memakai still dari bank ilustrasi yang sudah ada
  sebagai dasar teaser gambar, atau perakitan pan/zoom lokal dari
  still — keduanya mengubah sifat produk dari "klip hasil generasi"
  menjadi "teaser gambar/animasi still" dan harus diputuskan sebagai
  format tersendiri, bukan dianggap setara diam-diam.

— Akhir memo.

---

## Adendum keputusan hub — 2026-11-13 16:07 WIB (dicatat Ian)

Format pengganti yang dinamai di atas — **klip pan-zoom dari still**
(ilustrasi diam dari bank teaser yang sudah ada, digerakkan
pan/zoom lokal menjadi klip vertikal pendek) — **DISETUJUI**
sebagai format tersendiri untuk **ZONA BEBAS** (akun-akun samping;
bukan akun utama). Keputusan hub di bawah mandat delegasi penuh
pemilik 2026-11-13.

Syarat yang tetap berlaku:
- Akun utama (@dianzherdiana16) tetap di bawah **gerbang
  kualitas** — format ini tidak otomatis lolos ke sana.
- Aturan urutan tetap: teaser bab n hanya terbit SESUDAH bab n
  live di KBM; tidak ada dua pos dalam satu jam.
- Klip pan-zoom adalah "teaser animasi still", BUKAN klip hasil
  generasi video — jangan dilabeli atau dipresentasikan sebagai
  video generasi. Spesifikasi format di memo ini (9:16, hook
  terbaca 1–2 detik pertama, overlay sepertiga bawah, tanpa
  narasi) berlaku apa adanya untuk perakitannya.
- Produksi pertamanya menunggu giliran antrean ruang menulis/IG;
  adendum ini hanya menyampaikan persetujuannya ke pipeline.
