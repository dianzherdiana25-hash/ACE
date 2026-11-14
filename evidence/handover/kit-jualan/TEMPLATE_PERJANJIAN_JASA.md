# TEMPLATE PERJANJIAN JASA — ACE

> Salin berkas ini untuk setiap kesepakatan baru, ganti semua isian dalam [KURUNG SIKU], lalu simpan salinannya dengan nama `PERJANJIAN_[NAMA KLIEN]_[TANGGAL].md`. Jangan sunting berkas template ini.

---

## RINGKASAN BAHASA AWAM (baca ini dulu)

> - **Siapa:** Anda (Klien) memesan jasa dari Penyedia Jasa di bawah ini.
> - **Apa yang Anda terima:** hasil kerja yang tertulis di Pasal 2 — tidak lebih, tidak kurang. Pekerjaan di luar itu perlu kesepakatan tertulis baru.
> - **Berapa & bagaimana bayarnya:** total biaya di Pasal 4. Dibayar dua tahap: **DP 50% di muka** (pekerjaan tidak mulai sebelum DP masuk) dan **pelunasan 50%** setelah hasil akhir diserahkan.
> - **Revisi:** termasuk [JUMLAH] kali revisi minor. Perubahan besar / di luar ruang lingkup = biaya tambahan yang disepakati dulu.
> - **Kode & hasil kerja:** kode Anda tetap milik Anda (khusus Paket A, lihat Pasal 8). Hasil akhir yang sudah lunas menjadi milik Anda.
> - **Rahasia:** kedua pihak menjaga kerahasiaan materi masing-masing.
> - **Batal:** bisa dibatalkan sesuai Pasal 9 — uang yang kembali dihitung dari pekerjaan yang sudah benar-benar dikerjakan.

---

# PERJANJIAN JASA

Nomor: [AGR/[YYYYMM]/[NNN]]
Tanggal: [TANGGAL]

## Pasal 1 — Para Pihak

**PENYEDIA JASA**
- Nama: [NAMA PENYEDIA JASA]
- Kontak: [EMAIL / NOMOR WHATSAPP]
- Selanjutnya disebut "Penyedia Jasa".

**KLIEN**
- Nama / nama usaha: [NAMA KLIEN]
- Kontak: [EMAIL / NOMOR WHATSAPP]
- Selanjutnya disebut "Klien".

Kedua pihak sepakat mengikatkan diri pada perjanjian ini dengan syarat dan ketentuan berikut.

## Pasal 2 — Ruang Lingkup & Hasil Kerja (Deliverables)

Paket yang dipesan (centang satu):

- [ ] **Paket A — Perbaikan Keamanan + Bukti Tersegel + Uji Ulang.** Untuk satu kerentanan yang sudah teridentifikasi pada kode milik Klien: perbaikan kerentanan, paket bukti sebelum/sesudah yang tersegel (hasil evaluator sebelum perbaikan vs sesudah perbaikan), dan uji ulang (retest) atas perbaikan tersebut.
- [ ] **Paket B — Desain Evaluasi LLM yang Reprodusibel + Audit Bukti Tersegel.** Perancangan evaluasi LLM yang dapat direproduksi (protokol, kriteria, dan data uji yang terkunci) beserta audit atas bukti hasil evaluasi yang tersegel.
- [ ] **Lainnya:** [URAIAN JASA]

Hasil kerja yang diserahkan kepada Klien:
1. [HASIL KERJA 1 — mis. kode perbaikan yang diterapkan pada repositori Klien]
2. [HASIL KERJA 2 — mis. paket bukti tersegel (laporan sebelum/sesudah + hasil uji ulang)]
3. [HASIL KERJA 3]

Yang **tidak** termasuk: [PEKERJAAN DI LUAR RUANG LINGKUP — mis. pencarian kerentanan baru di luar yang teridentifikasi, pemeliharaan berkelanjutan, perubahan fitur].

## Pasal 3 — Jangka Waktu

- Pekerjaan dimulai setelah DP 50% diterima dan terverifikasi (lihat Pasal 4), paling lambat [JUMLAH] hari kerja setelahnya.
- Target selesai: [TANGGAL / JUMLAH HARI KERJA] sejak pekerjaan dimulai.
- Keterlambatan yang disebabkan Klien (keterlambatan akses, materi, atau persetujuan) menggeser target selesai sejumlah hari keterlambatan tersebut.

## Pasal 4 — Biaya & Jadwal Pembayaran

- Total biaya: **Rp[JUMLAH]** ([TERBILANG]).
- **Tahap 1 — DP 50%:** Rp[JUMLAH], dibayar sebelum pekerjaan dimulai, berdasarkan invoice DP.
- **Tahap 2 — Pelunasan 50%:** Rp[JUMLAH], dibayar paling lambat [JUMLAH] hari setelah hasil akhir diserahkan, berdasarkan invoice pelunasan.
- Cara bayar mengikuti instruksi pada invoice (QRIS / transfer / Lynk.id).
- Pekerjaan **tidak dimulai** sebelum DP diterima dan buktinya terverifikasi. Alur lengkap: lihat `ALUR_DP50.md`.

## Pasal 5 — Batas Revisi

- Termasuk **[JUMLAH, mis. 2] kali revisi minor**: perbaikan atas hasil kerja yang sudah disepakati (kesalahan, ketidaksesuaian dengan Pasal 2).
- Bukan revisi (dikenakan biaya tambahan yang disepakati tertulis lebih dulu): perubahan ruang lingkup, penambahan hasil kerja, atau pengulangan pekerjaan karena perubahan keputusan Klien.
- Permintaan revisi disampaikan tertulis dalam [JUMLAH] hari setelah penyerahan; lewat dari itu hasil kerja dianggap diterima.

## Pasal 6 — Hak Kekayaan Intelektual & Kepemilikan

- Hasil kerja akhir yang dibuat khusus untuk Klien dalam perjanjian ini menjadi milik Klien setelah pelunasan penuh.
- Kode, sistem, dan materi milik Klien yang sudah ada sebelum perjanjian ini tetap sepenuhnya milik Klien (lihat juga Pasal 8).
- Alat, metode, dan kerangka kerja umum milik Penyedia Jasa yang dipakai selama pekerjaan tetap milik Penyedia Jasa; Klien mendapat hak pakai sebatas yang melekat pada hasil kerja yang diserahkan.

## Pasal 7 — Kerahasiaan

- Kedua pihak wajib menjaga kerahasiaan materi non-publik pihak lain yang diterima selama pekerjaan (kode, data, kredensial akses, dokumen internal) dan tidak menggunakannya di luar perjanjian ini.
- Penyedia Jasa tidak mempublikasikan nama Klien, kode Klien, atau temuan atas sistem Klien tanpa izin tertulis Klien.
- Kewajiban ini tetap berlaku [JUMLAH, mis. 12] bulan setelah perjanjian berakhir.

## Pasal 8 — KLAUSUL KHUSUS PAKET A: Izin Tertulis atas Kode Klien (WAJIB untuk Paket A)

Pasal ini berlaku dan wajib ada bila paket yang dipesan adalah **Paket A**.

1. **Izin akses & perubahan.** Klien memberikan izin tertulis kepada Penyedia Jasa untuk mengakses, membaca, dan **mengubah** kode sumber milik Klien sebatas yang diperlukan untuk: (a) memeriksa kerentanan yang teridentifikasi di Pasal 2, (b) menerapkan perbaikannya, dan (c) menjalankan uji sebelum/sesudah serta uji ulang atas perbaikan tersebut.
2. **Kepemilikan tetap.** Kode sumber tersebut, beserta seluruh hak atasnya, **tetap milik Klien sepenuhnya**. Izin dalam pasal ini bukan pengalihan hak dalam bentuk apa pun.
3. **Batas ruang lingkup.** Pekerjaan hanya dilakukan pada bagian kode yang berkaitan dengan kerentanan yang disepakati di Pasal 2. Penyedia Jasa tidak mengubah bagian lain, tidak mengakses sistem/data di luar yang diberikan Klien untuk pekerjaan ini, dan tidak melakukan pengujian penetrasi di luar kerentanan yang disepakati.
4. **Cara akses.** Akses dilakukan melalui [REPOSITORI / SALINAN KODE / LINGKUNGAN UJI — sebutkan persisnya] yang disediakan Klien. Klien dianjurkan memberikan akses terbatas (bukan kredensial utama) dan dapat mencabut akses kapan pun; pencabutan akses menghentikan pekerjaan dan diperlakukan sesuai Pasal 9.
5. **Bukti tersegel.** Hasil pengukuran sebelum dan sesudah perbaikan dicatat dalam paket bukti tersegel yang diserahkan kepada Klien sebagai bagian dari hasil kerja.

## Pasal 9 — Pengakhiran & Pembatalan

- Salah satu pihak dapat mengakhiri perjanjian ini secara tertulis.
- Bila **Klien** membatalkan:
  - Sebelum pekerjaan dimulai: DP dikembalikan penuh.
  - Setelah pekerjaan dimulai: DP tidak kembali sebatas nilai pekerjaan yang sudah dikerjakan; bila pekerjaan yang selesai melebihi nilai DP, kelebihannya ditagih; bila kurang, sisanya dikembalikan.
- Bila **Penyedia Jasa** membatalkan setelah pekerjaan dimulai: bagian DP untuk pekerjaan yang belum dikerjakan dikembalikan, dan hasil kerja parsial yang sudah jadi diserahkan apa adanya.
- Hasil kerja yang sudah diserahkan dan dilunasi sebelum pengakhiran tetap milik Klien sesuai Pasal 6.

## Pasal 10 — Lain-lain

- Perubahan atas perjanjian ini hanya sah bila tertulis dan disetujui kedua pihak (pesan tertulis/email yang dikonfirmasi kedua pihak dianggap tertulis).
- Perjanjian ini tunduk pada hukum Republik Indonesia.
- Perselisihan diselesaikan secara musyawarah terlebih dahulu.

---

Ditandatangani pada [TANGGAL]:

| Penyedia Jasa | Klien |
|---|---|
| [NAMA + TANDA TANGAN] | [NAMA + TANDA TANGAN] |

---

*Cara pakai: salin berkas ini per kesepakatan, isi semua [KURUNG SIKU], pastikan Pasal 8 utuh bila Paket A dipesan, lalu minta Klien menandatangani (tanda tangan basah / digital / persetujuan tertulis via email sama-sama dicatat sebagai bukti persetujuan).*
