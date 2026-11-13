# ALUR DP 50% — dari kesepakatan sampai serah terima

Alur baku untuk semua jasa ACE (Paket A, Paket B, dan jasa lain yang memakai `TEMPLATE_PERJANJIAN_JASA.md`). Tujuannya: tidak ada pekerjaan yang dimulai tanpa komitmen bayar yang nyata, dan tidak ada pembayaran tanpa bukti yang bisa dicocokkan.

## Aturan keras (tidak bisa ditawar di tengah jalan)

1. **Pekerjaan TIDAK dimulai sebelum DP 50% diterima DAN buktinya terverifikasi** (notifikasi / tangkapan layar yang cocok dengan rel pembayaran — nama merchant/NMID untuk QRIS, nama penerima untuk transfer).
2. Setiap tahap pembayaran selalu didahului invoice bernomor dan diakhiri kwitansi/bukti catat.
3. Hasil akhir penuh diserahkan setelah pelunasan — sebelum itu yang dibagikan adalah bukti progres (milestone), bukan hasil akhir.

## Langkah-langkah

### 1. Kesepakatan & invoice DP
- Perjanjian jasa ditandatangani (atau disetujui tertulis).
- Terbitkan invoice jenis **DP 50%** (`TEMPLATE_INVOICE.md`).
- Kirim perjanjian + invoice DP ke Klien.

### 2. Gerbang mulai kerja (work-start gate)
- Klien membayar DP dan mengirim bukti bayar.
- Verifikasi bukti: jumlah cocok dengan invoice, rel/nama penerima cocok.
- **Gerbang lolos** → catat penerimaan, terbitkan kwitansi, tetapkan tanggal mulai & target selesai sesuai perjanjian.
- **Gerbang tidak lolos** (belum bayar / bukti tidak cocok) → pekerjaan tidak dimulai; ingatkan Klien dengan sopan, tanpa memulai pekerjaan "sebagai itikad baik".

### 3. Pengerjaan + bukti milestone
- Kerjakan sesuai ruang lingkup perjanjian.
- Pada titik tengah / tonggak yang disepakati, kirim **bukti milestone** ke Klien: ringkasan progres + artefak antara (mis. untuk Paket A: hasil pengukuran "sebelum" yang tersegel; untuk Paket B: draf protokol evaluasi yang terkunci).
- Permintaan di luar ruang lingkup yang muncul di tengah jalan: jangan dikerjakan dulu — tawarkan tambahan tertulis (biaya + waktu) dan tunggu persetujuan.

### 4. Invoice pelunasan
- Saat hasil akhir siap, terbitkan invoice jenis **PELUNASAN** dengan nomor urut berikutnya; rincian wajib mengurangkan DP yang sudah diterima.
- Kirim invoice + pemberitahuan bahwa hasil akhir siap diserahkan begitu pelunasan masuk.

### 5. Serah terima & penutup
- Klien melunasi dan mengirim bukti bayar → verifikasi seperti langkah 2.
- Serahkan hasil akhir penuh.
- Terbitkan kwitansi pelunasan (untuk QRIS/pembayaran langsung pakai `TEMPLATE_KWITANSI_QRIS.md`; pola yang sama untuk rel lain).
- Catat transaksi selesai; masa revisi berjalan sejak tanggal serah terima (sesuai batas di perjanjian).

## Bila dibatalkan di tengah jalan

**Dibatalkan Klien:**
- Sebelum gerbang mulai kerja lolos: DP dikembalikan penuh, perjanjian berakhir.
- Sesudah pekerjaan dimulai: nilai pekerjaan yang sudah benar-benar selesai dihitung; DP menutup nilai itu. Bila nilai selesai < DP → selisihnya dikembalikan. Bila nilai selesai > DP → kelebihannya ditagih dengan invoice terakhir. Hasil kerja parsial diserahkan sebatas yang sudah terbayar.
- Permintaan fitur/ruang lingkup baru tidak pernah menjadi alasan menahan pengembalian yang menjadi hak Klien.

**Dibatalkan Penyedia Jasa:**
- Sebelum mulai: DP kembali penuh.
- Sesudah mulai: bagian DP untuk pekerjaan yang belum dikerjakan dikembalikan penuh; hasil kerja parsial yang sudah jadi diserahkan apa adanya; alasannya disampaikan tertulis.

**Macet tanpa kabar:**
- Klien tidak membayar DP dalam [7] hari sejak invoice diterbitkan → kesepakatan dianggap batal, tidak ada kewajiban apa pun di kedua pihak.
- Klien tidak melunasi dalam [14] hari sejak invoice pelunasan diterbitkan → hasil akhir ditahan, pengingat dikirim; lewat [30] hari perjanjian dapat diakhiri Penyedia Jasa sesuai Pasal 9 perjanjian dan hasil kerja yang belum dibayar tidak diserahkan.

---

*Cara pakai: jalankan langkah 1–5 berurutan untuk setiap order jasa; angka hari dalam [kurung] boleh disesuaikan per kesepakatan asal ditulis di perjanjian sebelum invoice DP diterbitkan.*
