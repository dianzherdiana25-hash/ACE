# 💰 Pengelola Keuangan Pribadi & Evaluasi Anggaran 50-30-20

Aplikasi CLI Python mandiri berbahasa Indonesia untuk mengelola arus kas harian, mengevaluasi alokasi anggaran berdasarkan prinsip finansial **50-30-20** (Kebutuhan, Keinginan, Tabungan/Investasi), mendeteksi pengeluaran anomali, serta mengekspor data ke JSON dan CSV.

Dibuat dan diverifikasi otomatis oleh **ACE (Agentic Coding Engine)**.

---

## 🚀 Cara Menjalankan

Masuk ke direktori aplikasi:
```bash
cd projects/pengelola_keuangan
```

### 1. Menjalankan Mode Demo (Simulasi Cepat)
Untuk melihat contoh laporan lengkap dengan data simulasi:
```bash
python3 app.py --demo
```

### 2. Mencatat Pemasukan Baru
Format: `python3 app.py --masuk "<Deskripsi>" <Nominal>`
```bash
python3 app.py --masuk "Gaji Bulanan" 12000000
python3 app.py --masuk "Freelance Desain" 1500000
```

### 3. Mencatat Pengeluaran
Format: `python3 app.py --keluar "<Deskripsi>" <Nominal> <Kategori>`  
*Kategori yang valid: `kebutuhan`, `keinginan`, atau `tabungan`*
```bash
python3 app.py --keluar "Sewa Kos" 2500000 kebutuhan
python3 app.py --keluar "Nonton Bioskop & Makan" 350000 keinginan
python3 app.py --keluar "Beli Reksadana Pasar Uang" 1000000 tabungan
```

### 4. Melihat Laporan & Rekap 50-30-20
```bash
python3 app.py --rekap
```

### 5. Mengekspor ke File CSV
```bash
python3 app.py --ekspor
```
File akan otomatis tersimpan di `data_keuangan.csv`.

---

## 🧪 Menjalankan Pengujian Mandiri (Unit Tests)

Aplikasi dilengkapi unit tests komprehensif yang memvalidasi format rupiah, logika alokasi 50/30/20, deteksi anomali, serta integritas data JSON dan CSV:
```bash
python3 -m unittest test_app.py
```
Hasil: `Ran 6 tests in 0.014s OK` (100% lulus).
