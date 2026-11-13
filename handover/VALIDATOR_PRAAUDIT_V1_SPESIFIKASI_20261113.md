# SPESIFIKASI KANDIDAT — VALIDATOR PRA-AUDIT v1 (2026-11-13)

Status: SPESIFIKASI TERCATAT, BELUM DIBANGUN. Sumber:
panen ruang koordinasi #5 (13 Nov 2026, 20:54–20:58
WIB), di bawah lisensi pakai-ulang pemilik. Garis:
workflow Tahap 1 (PETA ARAH), di samping tonggak
kegunaan pertama yang sudah diadopsi (pencatatan
per-tugas, PR #181). Tidak ada eksekusi tanpa akta.
Kosakata ratifikasi internal (koreksi pemilik
20:54) berlaku di seluruh spesifikasi ini.

## 1. Arsitektur minimum

Validator OFFLINE dan READ-ONLY. Masukan = manifest
eksplisit. Ia bekerja hanya pada paket beku/snapshot,
menulis laporannya ke direktori output yang
TERPISAH, dan tidak pernah mengubah artefak sumber
atau menjalankan eksperimen.

Sifat-sifat ini DITEGAKKAN, bukan DIMAKSUDKAN:
validator yang kebetulan berhak tulis lalu berjanji
tidak menulis jauh lebih lemah daripada validator
yang secara fisik tidak bisa menulis ke sumbernya.
Isolasi tulis adalah keputusan arsitektur (mount/
hak akses/lingkungan), bukan konvensi kode.

## 2. Laporan tiga keadaan

Setiap cek berakhir di tepat satu keadaan:

- **SESUAI** — masukan ada dan cek terbukti cocok.
- **TIDAK SESUAI** — semua masukan ada DAN dua hal
  terbukti deterministik tidak cocok (mismatch
  TERBUKTI; sebabnya boleh belum diketahui).
- **UNKNOWN** — dasar tidak cukup: bukti kurang,
  aturan ambigu, dependensi belum beres. UNKNOWN
  BUKAN mismatch dan tidak boleh diringkas menjadi
  salah satunya.

Tampilan per cek: alasan/status; bukti yang tersedia
vs yang kurang; dependensi; langkah berikut yang
disarankan. Aturan berhenti: checker BERHENTI
alih-alih menebak. Dan ringkasan "bersih" tidak
boleh bisa dibaca sebagai persetujuan/validasi
eksperimen — yang lulus adalah CEK YANG DITENTUKAN
pada paket itu, bukan kebenaran ilmiah eksperimennya.

## 3. Tiga failure mode validator deterministik

Kalimat kunci: deterministik hanya menjamin keluaran
sama pada masukan sama — BUKAN keluaran benar.

(a) **Bug parser/kanonisasi** — kunci JSON ganda
    tertimpa diam-diam; desimal kehilangan presisi
    lewat float; null disamakan dengan field hilang;
    normalisasi Unicode/akhir-baris tidak tercatat;
    dua implementasi menghasilkan hash kanonis
    berbeda. Kontrol v1 (nyata, bukan disclaimer):
    satu jalur kanonisasi tunggal yang ter-pin dengan
    digest-nya sendiri; parser fail-closed pada kunci
    ganda dan pada angka yang tidak terwakili persis;
    normalisasi yang dipakai DICATAT di laporan.
(b) **False positive dari aturan terlalu kaku** —
    aturan yang benar untuk paket normal menghukum
    paket sah yang menyimpang bentuknya. Kontrol v1:
    varian sah sebagai probe wajib di tangga uji-diri
    (§4); setiap aturan membawa contoh sah yang harus
    lulus, dan kegagalannya adalah kegagalan validator,
    bukan paket.
(c) **Kepercayaan keliru pada manifest** — manifest
    diperlakukan sebagai kebenaran padahal ia sendiri
    artefak yang bisa salah/tidak lengkap. Kontrol v1:
    manifest diperiksa terhadap paket (kehadiran,
    ukuran, hash setiap entri), dan setiap ketidak-
    cocokan manifest-vs-paket dilaporkan sebagai
    temuan tentang MANIFEST, bukan diasumsikan
    sebagai kesalahan paket.

Untuk tiap mode: kontrol teknis yang benar-benar
menahan risiko sejak v1 + pengungkapan cakupan/
ketidakpastian di dalam laporan itu sendiri.

## 4. Tangga uji-diri (sebelum validator dipercaya)

1. **Fixture referensi dengan ORACLE INDEPENDEN** —
   dibangun dari spesifikasi tertulis dengan
   implementasi/jalur penalaran TERPISAH, agar oracle
   tidak berbagi bug dengan validator.
2. **Varian sah** sebagai probe false-positive.
3. **Cacat semaian** per aturan (satu cacat yang
   memang dirancang untuk ditangkap tiap aturan;
   aturan yang tidak menangkap cacatnya sendiri
   belum ada).
4. **Uji properti/metamorfik** (invariansi yang harus
   bertahan di bawah transformasi yang tidak
   mengubah makna).
5. **Fuzzing parser** pada jalur masukan.
6. **CORPUS HOLDOUT** yang dibuat SESUDAH validator
   + aturan dibekukan — fixture yang terlihat selama
   pengembangan bukan fixture penentu akhir.

Bahkan bila semua lulus, laporan kepercayaan wajib
menyebutkan secara eksplisit apa yang tetap BELUM
terbukti.

— Dicatat Ian dari panen koordinasi #5, 13 Nov 2026.

## Status bangun (diperbarui 13 Nov 2026 malam)

DIBANGUN oleh jalur validator (ruang "ila — bangun validator pra-audit ACE") sebagai alat yang berjalan: PR #179 (head 59e4211) — code/ace_operational/preaudit_validator.py, stdlib-only, offline, penegakan read-only fisik (O_RDONLY + CLI menolak out-dir yang bersinggungan root sumber). Tangga uji-dirinya LULUS PENUH per laporan jalur dan TAHAN hub terverifikasi mandiri: oracle independen sepakat state-per-state; probe varian sah FP 0/6 per cek; cacat semaian 9/9 tertangkap; fuzz parser bersih; corpus holdout ditulis SESUDAH beku dan lulus 5/5 tanpa validator disentuh; sweep paket 283 OK. Pilot nyata: paket v3 beku (23 berkas) C1/C2/C3 SESUAI; rekaman bake-off C1 SESUAI, C2/C3 UNKNOWN jujur; demo verdict dibalik tertangkap TIDAK SESUAI. Batas jujur yang dinyatakan laporannya sendiri: validator membuktikan paket cocok dengan manifestnya — BUKAN bahwa manifestnya benar. Integrasi Ian: keadaan ini dicatat di sini; PR #179 tetap draft tanpa merge seperti PR lainnya.
