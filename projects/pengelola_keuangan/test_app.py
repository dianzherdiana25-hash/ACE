#!/usr/bin/env python3
"""Unit tests komprehensif untuk Aplikasi Pengelola Keuangan & Anggaran 50-30-20."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from app import PengelolaKeuangan, format_rupiah


class TestPengelolaKeuangan(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "test_keuangan.json"
        self.pk = PengelolaKeuangan(self.data_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_format_rupiah(self):
        self.assertEqual(format_rupiah(1500000), "Rp 1.500.000")
        self.assertEqual(format_rupiah(0), "Rp 0")
        self.assertEqual(format_rupiah(-50000), "-Rp 50.000")
        self.assertEqual(format_rupiah(1234567.89), "Rp 1.234.568")

    def test_tambah_pemasukan_dan_pengeluaran(self):
        m = self.pk.tambah_pemasukan("Gaji Pokok", 10000000, "Kantor")
        self.assertEqual(m["nominal"], 10000000)
        self.assertEqual(m["tipe"], "PEMASUKAN")

        k = self.pk.tambah_pengeluaran("Beli Beras & Lauk", 1500000, "kebutuhan")
        self.assertEqual(k["nominal"], 1500000)
        self.assertEqual(k["kategori"], "Kebutuhan (50%)")

        self.assertEqual(len(self.pk.transaksi), 2)
        total = self.pk.ringkasan_total()
        self.assertEqual(total["total_pemasukan"], 10000000)
        self.assertEqual(total["total_pengeluaran"], 1500000)
        self.assertEqual(total["saldo_bersih"], 8500000)

    def test_validasi_input_negatif_dan_kategori_salah(self):
        with self.assertRaises(ValueError):
            self.pk.tambah_pemasukan("Uang Gaib", -100)
        with self.assertRaises(ValueError):
            self.pk.tambah_pengeluaran("Belanja Minus", 0, "kebutuhan")
        with self.assertRaises(ValueError):
            self.pk.tambah_pengeluaran("Salah Kategori", 100000, "foya-foya")

    def test_analisis_anggaran_50_30_20(self):
        self.pk.tambah_pemasukan("Gaji Bulanan", 10000000)
        self.pk.tambah_pengeluaran("Sewa Rumah", 4500000, "kebutuhan")
        self.pk.tambah_pengeluaran("Hiburan Kafe", 3200000, "keinginan")
        self.pk.tambah_pengeluaran("Reksadana", 2000000, "tabungan")

        analisis = self.pk.analisis_anggaran_50_30_20()
        kat = analisis["kategori"]
        self.assertEqual(kat["Kebutuhan (50%)"]["persen_real"], 45.0)
        self.assertEqual(kat["Keinginan (30%)"]["persen_real"], 32.0)
        self.assertEqual(kat["Tabungan/Investasi (20%)"]["persen_real"], 20.0)
        self.assertTrue(len(analisis["saran_rekomendasi"]) >= 1)

    def test_deteksi_anomali_pengeluaran(self):
        self.pk.tambah_pemasukan("Bonus", 10000000)
        self.pk.tambah_pengeluaran("Belanja Makan Harian", 1000000, "kebutuhan")
        self.pk.tambah_pengeluaran("Beli Laptop Flagship Mewah", 6000000, "keinginan")

        anomali = self.pk.deteksi_anomali_pengeluaran(threshold_persen=35.0)
        self.assertEqual(len(anomali), 1)
        self.assertEqual(anomali[0]["deskripsi"], "Beli Laptop Flagship Mewah")
        self.assertGreaterEqual(anomali[0]["porsi_dari_total_belanja"], 80.0)

    def test_persistensi_json_dan_ekspor_csv(self):
        self.pk.tambah_pemasukan("Proyek Freelance", 5000000)
        self.pk.tambah_pengeluaran("Tagihan Listrik", 500000, "kebutuhan")

        # Reload dari file JSON
        pk_baru = PengelolaKeuangan(self.data_file)
        self.assertEqual(len(pk_baru.transaksi), 2)
        self.assertEqual(pk_baru.ringkasan_total()["saldo_bersih"], 4500000)

        # Ekspor CSV
        csv_file = self.data_file.with_suffix(".csv")
        pk_baru.ekspor_csv(csv_file)
        self.assertTrue(csv_file.exists())
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            self.assertEqual(len(reader), 3)  # header + 2 transaksi
            self.assertEqual(reader[0], ["ID", "Tipe", "Kategori", "Deskripsi", "Nominal (Rp)"])


if __name__ == "__main__":
    unittest.main()
