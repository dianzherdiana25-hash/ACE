# TEMPLATE INVOICE — ACE

> Salin berkas ini untuk setiap penagihan, ganti semua isian dalam [KURUNG SIKU], simpan salinannya dengan nama sesuai nomor invoice-nya.

## Skema penomoran

Format: **INV/[YYYYMM]/[NNN]**

- `YYYYMM` = tahun + bulan invoice diterbitkan (mis. `202611` untuk November 2026).
- `NNN` = nomor urut 3 digit yang **berjalan terus lintas bulan** (tidak mulai lagi dari 001 tiap bulan), supaya tidak pernah ada dua invoice bernomor sama. Contoh urutan: `INV/202611/001`, `INV/202611/002`, `INV/202612/003`.
- Jenis tagihan (DP / pelunasan) **tidak** mengubah format nomor — dibedakan lewat kolom "Jenis" di badan invoice. Satu perjanjian biasanya memakai dua nomor invoice berurutan: satu untuk DP, satu untuk pelunasan.
- Catat setiap nomor yang diterbitkan (nomor, klien, jumlah, status lunas/belum) agar urutan tidak lompat dan tidak ganda.

---

# INVOICE

**Nomor:** INV/[YYYYMM]/[NNN]
**Tanggal terbit:** [TANGGAL]
**Jatuh tempo:** [TANGGAL]
**Jenis:** [DP 50% / PELUNASAN / PENUH]

**Dari:**
[NAMA PENYEDIA JASA]
[EMAIL / NOMOR WHATSAPP]

**Ditujukan kepada:**
[NAMA KLIEN / NAMA USAHA]
[EMAIL / NOMOR WHATSAPP]

**Rujukan:** Perjanjian Jasa No. [NOMOR PERJANJIAN] tanggal [TANGGAL PERJANJIAN]

## Rincian

| # | Uraian | Jumlah |
|---|---|---|
| 1 | [URAIAN JASA — mis. Paket A: perbaikan kerentanan + bukti tersegel + uji ulang] | Rp[JUMLAH] |
| 2 | [URAIAN TAMBAHAN, bila ada] | Rp[JUMLAH] |
| | **Subtotal** | **Rp[JUMLAH]** |
| | DP yang sudah diterima (khusus invoice pelunasan) | − Rp[JUMLAH] |
| | **Total harus dibayar** | **Rp[JUMLAH]** |

Terbilang: [TERBILANG TOTAL]

## Catatan pajak

Invoice ini adalah tagihan pembayaran jasa, **bukan faktur pajak**. Perlakuan pajak atas pembayaran ini mengikuti status perpajakan penjual yang berlaku pada saat transaksi; tidak ada nomor NPWP atau tarif pajak yang dicantumkan di invoice ini. Bila Klien memerlukan dokumen pajak tertentu, sampaikan sebelum pembayaran agar dapat disiapkan sesuai ketentuan yang sebenarnya berlaku.

## Instruksi pembayaran

Bayar ke salah satu rel berikut, lalu kirim bukti bayarnya (notifikasi / tangkapan layar) agar dapat dicocokkan dan dicatat:

1. **QRIS** — merchant **KINNEH USAHA MANDIRI GROU**, NMID **ID1026571630742** (pindai kode QRIS yang dibagikan Penyedia Jasa).
2. **Transfer bank** — **SeaBank a.n. Dian Herdiana**, nomor rekening: [nomor tertera di ledger — minta ke Penyedia Jasa bila belum punya].
3. **Lynk.id** — https://lynk.id/dianma25 (untuk produk/jasa yang ditayangkan di toko).

Cantumkan nomor invoice ini pada keterangan transfer bila kolom keterangan tersedia.

---

*Cara pakai: terbitkan invoice DP lebih dulu (jenis: DP 50%); setelah hasil akhir diserahkan, terbitkan invoice pelunasan dengan nomor urut berikutnya dan kurangi DP yang sudah diterima di baris rinciannya.*
