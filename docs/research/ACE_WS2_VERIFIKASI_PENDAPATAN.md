# Verifikasi pendapatan WS-2

Verifikator membandingkan tiga kaki bukti per peristiwa pencairan. Laporan Markdown
menampilkan status, temuan per kaki, dan total rupiah yang masuk pada peristiwa
`COCOK PENUH`. Aturan penerimaan mengikuti revisi spesifikasi
[`db319672` di #332](https://github.com/dianzherdiana25-hash/ACE/blob/db319672/handover/SPESIFIKASI_WS2_REL_DAN_BUKTI.md).

## Siapkan bukti lokal

Kelompokkan bukti berdasarkan ID pencairan yang sama. Isi `ref` dengan
ID bukti lokal yang unik per jenis kaki. Simpan pemetaan ID ke dokumen privat
untuk pemeriksaan ulang. ID dan ref dimulai dengan huruf ASCII dan bisa diikuti
huruf, angka, tanda hubung, garis bawah atau titik, sampai 64 karakter.
Gunakan ID samaran dan hilangkan nomor rekening sebelum menyalin bukti.

Contoh sintetis untuk satu pencairan Fastwork.

```json
{
  "schema": "ace.revenue-evidence.v1",
  "events": [
    {
      "id": "contoh-pencairan",
      "rail": "fastwork_bank",
      "platform": {
        "ref": "contoh-platform", "provider": "fastwork", "date": "2026-01-10",
        "amount_rupiah": 20000
      },
      "withdrawal": {
        "ref": "contoh-tarik", "provider": "fastwork", "date": "2026-01-11",
        "amount_rupiah": 20000, "fee_rupiah": 1250
      },
      "statement": {
        "ref": "contoh-mutasi", "provider": "bank", "date": "2026-01-12",
        "amount_rupiah": 18750, "recipient": "Penerima Contoh"
      }
    }
  ]
}
```

- `kbm_seabank` memakai `kbm` untuk platform dan penarikan serta `seabank` untuk mutasi.
- `fastwork_bank` memakai `fastwork` untuk platform dan penarikan serta `bank` atau `seabank` untuk mutasi. Isi bruto di dua kaki awal dan neto di mutasi. Penarikan harus menyatakan biaya secara eksplisit, termasuk saat biayanya nol.
- `gopay_qris` memakai `gopay` atau `qris` pada penyelesaian dan transfer, serta `gopay` atau `seabank` pada mutasi.
- Nilai rel seperti `facebook` menghasilkan `REL TAK TERDAFTAR`.

Tanggal platform untuk laporan periode adalah tanggal akhir periode. Untuk KBM,
gunakan jumlah laporan royalti yang ditautkan ke satu peristiwa pencairan.
Jika memakai ringkasan dari `royalty_track.py`, petakan agregat IDR yang terkait
ke `amount_rupiah` hanya setelah pengaitan itu terbukti. Tool memeriksa nominal
dan urutan tanggal dari ekstrak yang diberikan. Penetapan bahwa ekstrak benar-benar
berasal dari dokumen asli tetap dilakukan oleh pemeriksa sumber.

Kaki absen boleh dihilangkan atau diisi `null`. Nama `recipient` disertakan
bila tersedia di bukti. Verifikator membandingkannya dengan acuan privat setelah
merapikan spasi dan kapitalisasi. Hasil hanya memuat ID peristiwa, rel, status,
kode temuan, dan nominal yang terverifikasi. Bukti dan acuan dibaca lokal.

## Jalankan

```sh
python3 tools/revenue_verify.py /path/privat/bukti.json \
  --recipient-file /path/privat/nama.txt --max-lag-days 14 > /tmp/verifikasi.json
python3 tools/revenue_report.py /tmp/verifikasi.json
```

`HILANG` menandai kaki atau biaya Fastwork absen. `SEBAGIAN` menandai
setidaknya satu pasangan yang memenuhi pemeriksaan pasangan saat pemeriksaan
tiga kaki menemukan konflik. Kode temuan menunjuk kaki atau hubungan yang
meleset. `TIDAK COCOK` dipakai ketika ketiga kaki tersedia tetapi tak ada
pasangan yang memenuhi syarat. Ketiganya tidak menambah total terverifikasi.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q \
  tools.test_revenue_verify tools.test_revenue_report tools.test_royalty_track
```
