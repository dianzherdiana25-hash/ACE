# ACE Smart Enterprise Suite 🏢

Platform aplikasi web dan REST API manajemen usaha terpadu untuk UMKM dan bisnis modern, dibangun secara mandiri oleh **ACE Autonomous Engineering Engine** (didukung model lokal **Qwen2.5-Coder-7B GGUF**).

---

## 🌟 Fitur Utama
1. **Dasbor Finansial Real-Time:**
   - Rekap omzet, total pengeluaran, laba bersih, dan rasio margin profit.
   - Evaluasi otomatis alokasi anggaran **50-30-20** (Kebutuhan Pokok, Pertumbuhan/Ads, Cadangan Kas).
2. **Manajemen Inventaris & Stok:**
   - Katalog produk multi-kategori dengan harga beli (HPP) dan harga jual.
   - Deteksi dini stok menipis dan kritis (`stock <= min_stock`).
   - Valuasi total aset persediaan barang secara otomatis.
3. **Pencatatan Transaksi & Audit Trail:**
   - Mutasi kas keluar-masuk dengan nomor referensi unik terenkripsi waktu.
   - Pengurangan stok otomatis saat transaksi penjualan dicatat.
   - Ekspor data transaksi ke format file **CSV** dengan satu klik.
   - Rekam jejak audit (*audit trail*) anti-manipulasi tersimpan di SQLite.
4. **Teknologi & Standar Arsitektur:**
   - Berbasis murni pustaka standar Python 3 (`http.server`, `sqlite3`, `json`).
   - Zero external pip dependency (dapat dijalankan langsung di lingkungan server manapun).
   - Antarmuka web responsif dengan tema modern Navy/Dark yang nyaman di mata.

---

## 🚀 Cara Menjalankan

### 1. Menjalankan Server Web & API
```bash
python3 server.py --host 127.0.0.1 --port 8085
```
Akses dasbor interaktif di peramban: `http://127.0.0.1:8085`

### 2. Menjalankan Suite Pengujian Otomatis
```bash
python3 -m unittest test_server.py
```
Semua 6 pengujian integrasi database, logika kalkulasi finansial, dan endpoint REST API akan dieksekusi secara otomatis.

---

## 📡 Daftar Endpoint REST API

| Method | Endpoint | Keterangan |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Pengecekan status kesehatan server dan basis data |
| `GET` | `/api/summary` | Ringkasan metrik KPI, valuasi stok, dan evaluasi 50-30-20 |
| `GET` | `/api/products` | Daftar seluruh katalog produk beserta level stok |
| `POST`| `/api/products` | Menambahkan SKU produk baru ke dalam sistem |
| `GET` | `/api/transactions` | Daftar riwayat transaksi kas terbaru |
| `POST`| `/api/transactions` | Mencatat transaksi baru (pemasukan/pengeluaran) |
| `GET` | `/api/audit-trail` | Log rekaman aktivitas dan perubahan data |

---
*Dibuat dan diverifikasi oleh ACE (Autonomous Cognitive Entity) - Edition 4.*
