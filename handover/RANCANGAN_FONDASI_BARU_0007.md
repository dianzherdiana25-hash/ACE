# RANCANGAN FONDASI BARU PRAREGISTRASI EVO 0007

*Disusun Ian 18 Nov 2026 atas perintah hub, sesudah penutupan rumah
lokal. Status: RANCANGAN untuk ratifikasi hub — bukan praregistrasi
beku, tidak ada lari. Ia menggantikan jalur pengisian slot lama
(kerangka 17 Nov menunggu vonis penerus) karena vonis itu tidak
pernah ada: penerus 0006 diakhiri perintah pemilik 12:32, 18 Nov,
sebelum lengannya berjalan. Fondasi ini berdiri di atas bukti yang
sudah ada, dan menyebut dengan jujur apa yang belum bisa diturunkan.*

## 1. Bukti fondasi (semua terverifikasi, semua bernama)

**(a) Diagnosis EVO 0005 (PR #250).** Klaim warisan gugur sebagai
kegagalan antar, bukan kegagalan isi: konteks receipt tidak terkirim
pada 7/8 episode dan tipis isi di tempat ia terkirim. Pelajaran
berdiri: konten yang di-recall harus berbentuk pengetahuan, dan
antar konteks adalah kelas-satu yang tercatat per episode.

**(b) Temuan instrumen EVO 0006 (PR #252).** Instrumen biner tidak
cukup: judge menempatkan episode bahasa di langit-langit. Penerusnya
beralih ke judge v3 ber-skor dengan kalibrasi pita margin — instrumen
yang kemudian terbukti bekerja (butir c).

**(c) Kalibrasi penerus 0006 (lari diakhiri pemilik, kalibrasi
berdiri).** Penyaringan dua gelombang atas judge v3 (pita [45,75],
mean 2 lari): wave 1 kode 2/12, bahasa 0/12; wave 2 kode 8/12,
bahasa 3/12. Sensus gabungan 13 ≥ 8 — set probe yang akan dipakai
lengan, tercatat di `probe_set.json` sandbox. Temuan instrumen yang
ikut berdiri:
- Pita margin bekerja sebagai sifat instrumen di 48 episode saring.
- **Variansi antar-run judge nyata:** w2-code-003 terbaca 35/95
  (sebaran 60); w2-lang-002 terbaca 45 vs 95 oleh dua instans
  (sebaran 50). Vonis masa depan wajib memperlakukannya eksplisit.
- Hasil in-band timpang per jenis: kode 10/24, bahasa 3/24 —
  judge v3 jauh lebih mudah menjenuhkan episode bahasa.
- Spesies timeout soket-idle pada generasi judge panjang tertutup
  Amandemen 3 (timeout klien scored 2400 dtk, PR #306).
- Gerbang antar ≥75% dan aturan stop-on-first-error bertahan di
  seluruh gelombang tanpa satu pun vonis palsu.

**(d) Rancangan induk #254 + kerangka 17 Nov.** Klaim, empat lengan
(POLA / RECEIPT / SHAM / KOSONG), dan skema record pattern_distilled
(task_shape, approach, pitfalls dari reasons judge, source_episode)
tidak berubah oleh fondasi ini. Yang berubah: dari mana slot diisi,
dan siapa subjek ukurnya.

## 2. Slot — diturunkan sekarang dari bukti

1. **Pita margin: [45, 75], dinyatakan dengan sumbernya.** Bukan
   warisan diam-diam: pita ini divalidasi data kalibrasi penerus
   (butir 1c) sebagai sifat instrumen judge v3. Vonis tidak
   mengubahnya; hanya kalibrasi ulang instrumen yang boleh.
2. **Aturan variansi (baru, dari temuan 1c):** sebaran A/B per
   episode tercatat kelas-satu. Vonis dilaporkan dua kali —
   set probe penuh (utama) dan set sensitivitas tanpa episode
   bersebaran > 50 (sekunder, tidak mengubah vonis utama).
3. **N probe minimum: 8** (lantai penerus; terbukti tercapai —
   sensus 13). Ditambah **aturan komposisi jenis**: set probe wajib
   memuat ≥4 episode bahasa, dicapai dengan menyaring korpus
   cadangan gelombang-3 (12 baris bahasa, sha256 740e8a29…) lebih
   dulu; bila cadangan menghasilkan <2, paket menyatakan cakupannya
   kode-saja secara eksplisit ketimbang berpura-pura umum.
4. **Sumber material pola:** episode-episode ratified dari gelombang
   kalibrasi penerus (berkas wave1/wave2 di sandbox — reasons judge
   adalah bahan pitfalls per #254) dan/atau korpus beku rumah.
   Pemilihan final + sha snapshot saat pembekuan material.
5. **Cap panjang pola:** aturan diturunkan sekarang, angka saat
   pembekuan — cap = persentil-95 panjang record terdistilasi nyata,
   tercatat bersama sha snapshot store pola.
6. **Sumber kandidat probe:** cadangan gelombang-3 (sha di atas)
   untuk bahasa + korpus rumah segar yang dibekukan saat paket
   disusun; sha dicatat saat pembekuan, tidak diturunkan dari apa
   pun.

## 3. Slot yang TIDAK bisa diturunkan — subjek ukur

Perubahan terdalam fondasi ini: pasangan organ lokal pada kerangka
lama (proposer coder / validator front, slate v2) **sudah pensiun**
(18 Nov, perintah pemilik). Maka slot organ — pendistilasi,
proposer/validator per lengan, dan organ judge — berdiri TERBUKA
dan hanya terisi oleh subjek ukur yang bernama. Dua jalan yang sah,
keduanya keputusan di luar rancangan ini:

- **Otak lokal masa depan** (pencarian dibuka lagi atas kata
  pemilik): organ lokal baru mengisi semua peran; kalibrasi pita
  wajib diulang sebagai gelombang kalibrasi paket ini sendiri
  sebelum lengan (instrumen sama, organ baru = kalibrasi baru).
- **Re-scope oleh hub:** bila subjeknya bukan organ lokal, klaim
  harus dirumuskan ulang secara eksplisit — klaim #254 adalah klaim
  tentang jalur recall store ACE, dan siapa yang menggenerasi
  mengubah apa yang dibuktikan lari itu. Rancangan ini tidak
  menyelundupkan re-scope sebagai pengisian slot.

Satu ikatan yang berlaku di kedua jalan: organ yang sama mengisi
peran proposer/validator/judge di keempat lengan (aturan pasangan
silang penerus), dan judge adalah judge v3 sebagaimana tergabung
(PR #304) atau padanan teregistrasi ulang dengan kalibrasinya
sendiri.

## 4. Aturan vonis (dibawa dari instrumen tervalidasi)

- Gerbang antar per lengan ≥75% dari episode probe; di bawahnya
  vonis TIDAK_TERANTAR, klaim tidak diuji (pelajaran 0005).
- TERDUKUNG iff accept-rate POLA > RECEIPT dan POLA > KOSONG pada
  set yang terantar; SHAM adalah kontrol kehadiran-vs-isi dan
  dilaporkan penuh. Mean skor per lengan = bacaan sekunder.
- Stop-on-first-error dan karantina baris error berlaku seperti
  pada paket penerus.

## 5. Yang rancangan ini bukan

Bukan pembekuan, bukan izin lari, bukan pengisian slot organ.
Ia menunggu dua hal: ratifikasi hub atas fondasi dan slot §2, dan
subjek ukur bernama untuk §3. Sesudah keduanya ada, praregistrasi
final disusun sebagai satu PR dan dibekukan sebelum episode pertama.
