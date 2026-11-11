#!/usr/bin/env python3
"""Aplikasi Pengelola Keuangan & Evaluasi Anggaran 50-30-20 Berbahasa Indonesia.

Fitur:
- Pencatatan pemasukan dan pengeluaran berbasis kategori standar 50-30-20 (Kebutuhan, Keinginan, Tabungan).
- Evaluasi alokasi anggaran otomatis dengan rekomendasi finansial praktis.
- Deteksi anomali pengeluaran tinggi atau tidak wajar.
- Format mata uang Rupiah standar Indonesia.
- Ekspor laporan ke CSV dan persistensi data ke JSON.
- Antarmuka CLI interaktif dan mode perintah baris (batch/once).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
from typing import Any


def format_rupiah(nilai: float | int) -> str:
    """Format angka numerik ke format mata uang Rupiah standar."""
    nilai_int = int(round(nilai))
    negatif = nilai_int < 0
    nilai_str = f"{abs(nilai_int):,}".replace(",", ".")
    tanda = "-" if negatif else ""
    return f"{tanda}Rp {nilai_str}"


class PengelolaKeuangan:
    """Kelas inti pencatatan dan analisis keuangan pribadi."""

    def __init__(self, data_path: Path | str | None = None):
        self.data_path = Path(data_path) if data_path else Path("data_keuangan.json")
        self.transaksi: list[dict[str, Any]] = []
        self.muat_data()

    def muat_data(self) -> None:
        """Memuat riwayat transaksi dari file JSON jika ada."""
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.transaksi = data
            except Exception:
                self.transaksi = []

    def simpan_data(self) -> None:
        """Menyimpan seluruh transaksi ke file JSON."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.write_text(
            json.dumps(self.transaksi, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def tambah_pemasukan(self, deskripsi: str, nominal: float, sumber: str = "Gaji") -> dict[str, Any]:
        """Mencatat transaksi pemasukan."""
        if nominal <= 0:
            raise ValueError("Nominal pemasukan harus lebih besar dari 0.")
        item = {
            "id": len(self.transaksi) + 1,
            "tipe": "PEMASUKAN",
            "kategori": "Pemasukan",
            "subkategori": sumber,
            "deskripsi": deskripsi.strip(),
            "nominal": float(nominal),
        }
        self.transaksi.append(item)
        self.simpan_data()
        return item

    def tambah_pengeluaran(self, deskripsi: str, nominal: float, kategori: str) -> dict[str, Any]:
        """Mencatat transaksi pengeluaran dalam kategori 50-30-20.

        Kategori yang valid:
        - 'kebutuhan' (Kebutuhan Pokok - target 50%)
        - 'keinginan' (Gaya Hidup/Hiburan - target 30%)
        - 'tabungan' (Tabungan & Investasi - target 20%)
        """
        if nominal <= 0:
            raise ValueError("Nominal pengeluaran harus lebih besar dari 0.")
        kat_norm = kategori.strip().lower()
        mapping = {
            "kebutuhan": "Kebutuhan (50%)",
            "keinginan": "Keinginan (30%)",
            "tabungan": "Tabungan/Investasi (20%)",
            "investasi": "Tabungan/Investasi (20%)",
        }
        if kat_norm not in mapping:
            raise ValueError(f"Kategori '{kategori}' tidak dikenal. Pilih: kebutuhan, keinginan, atau tabungan.")

        item = {
            "id": len(self.transaksi) + 1,
            "tipe": "PENGELUARAN",
            "kategori": mapping[kat_norm],
            "deskripsi": deskripsi.strip(),
            "nominal": float(nominal),
        }
        self.transaksi.append(item)
        self.simpan_data()
        return item

    def ringkasan_total(self) -> dict[str, float]:
        """Menghitung total pemasukan, total pengeluaran, dan saldo kas bersih."""
        total_masuk = sum(t["nominal"] for t in self.transaksi if t["tipe"] == "PEMASUKAN")
        total_keluar = sum(t["nominal"] for t in self.transaksi if t["tipe"] == "PENGELUARAN")
        return {
            "total_pemasukan": total_masuk,
            "total_pengeluaran": total_keluar,
            "saldo_bersih": total_masuk - total_keluar,
        }

    def analisis_anggaran_50_30_20(self) -> dict[str, Any]:
        """Mengevaluasi alokasi pengeluaran berdasarkan aturan keuangan 50/30/20."""
        ringkasan = self.ringkasan_total()
        total_masuk = ringkasan["total_pemasukan"]
        basis_hitung = total_masuk if total_masuk > 0 else ringkasan["total_pengeluaran"]

        rekap_kategori = {
            "Kebutuhan (50%)": 0.0,
            "Keinginan (30%)": 0.0,
            "Tabungan/Investasi (20%)": 0.0,
        }
        for t in self.transaksi:
            if t["tipe"] == "PENGELUARAN" and t["kategori"] in rekap_kategori:
                rekap_kategori[t["kategori"]] += t["nominal"]

        target_persen = {
            "Kebutuhan (50%)": 50.0,
            "Keinginan (30%)": 30.0,
            "Tabungan/Investasi (20%)": 20.0,
        }

        evaluasi = {}
        saran: list[str] = []

        for kat, nominal in rekap_kategori.items():
            persentase = (nominal / basis_hitung * 100.0) if basis_hitung > 0 else 0.0
            selisih = persentase - target_persen[kat]
            evaluasi[kat] = {
                "nominal": nominal,
                "persen_real": round(persentase, 1),
                "persen_target": target_persen[kat],
                "selisih_persen": round(selisih, 1),
                "status": "IDEAL" if abs(selisih) <= 5.0 else ("OVERBUDGET" if selisih > 5.0 else "UNDERBUDGET"),
            }

        keb = evaluasi["Kebutuhan (50%)"]
        kei = evaluasi["Keinginan (30%)"]
        tab = evaluasi["Tabungan/Investasi (20%)"]

        if keb["status"] == "OVERBUDGET":
            saran.append(f"Pengeluaran kebutuhan pokok mencapai {keb['persen_real']}%, melebihi target aman 50%. Tinjau pos tagihan rutin.")
        if kei["status"] == "OVERBUDGET":
            saran.append(f"Gaya hidup/keinginan mencapai {kei['persen_real']}%. Prioritaskan penghematan pada pos hiburan/belanja non-esensial.")
        if tab["persen_real"] >= 20.0:
            saran.append(f"Bagus! Alokasi tabungan dan investasi sehat ({tab['persen_real']}%). Pertahankan disiplin menyisihkan uang.")
        elif total_masuk > 0:
            saran.append(f"Porsi tabungan ({tab['persen_real']}%) masih di bawah target ideal 20%. Tingkatkan otomatisasi transfer tabungan diawal gajian.")

        return {
            "basis_perhitungan": "Total Pemasukan" if total_masuk > 0 else "Total Pengeluaran",
            "nominal_basis": basis_hitung,
            "kategori": evaluasi,
            "saran_rekomendasi": saran,
        }

    def deteksi_anomali_pengeluaran(self, threshold_persen: float = 35.0) -> list[dict[str, Any]]:
        """Mendeteksi pengeluaran individual yang menyerap porsi tidak wajar dari total belanja."""
        ringkasan = self.ringkasan_total()
        total_keluar = ringkasan["total_pengeluaran"]
        if total_keluar <= 0:
            return []

        anomali = []
        for t in self.transaksi:
            if t["tipe"] == "PENGELUARAN":
                porsi = (t["nominal"] / total_keluar) * 100.0
                if porsi >= threshold_persen:
                    anomali.append({
                        "id": t["id"],
                        "deskripsi": t["deskripsi"],
                        "nominal": t["nominal"],
                        "porsi_dari_total_belanja": round(porsi, 1),
                        "peringatan": f"Transaksi ini menyerap {round(porsi, 1)}% dari seluruh total belanja!",
                    })
        return anomali

    def ekspor_csv(self, file_path: Path | str | None = None) -> Path:
        """Mengekspor seluruh riwayat transaksi ke berkas CSV."""
        target = Path(file_path) if file_path else self.data_path.with_suffix(".csv")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Tipe", "Kategori", "Deskripsi", "Nominal (Rp)"])
            for t in self.transaksi:
                writer.writerow([t["id"], t["tipe"], t["kategori"], t["deskripsi"], t["nominal"]])
        return target


def render_tabel_ringkasan(pk: PengelolaKeuangan) -> None:
    """Menampilkan ringkasan keuangan dan analisis 50-30-20 ke layar terminal."""
    total = pk.ringkasan_total()
    analisis = pk.analisis_anggaran_50_30_20()
    anomali = pk.deteksi_anomali_pengeluaran()

    print("\n" + "=" * 65)
    print("      📊 LAPORAN KEUANGAN & EVALUASI ANGGARAN 50-30-20")
    print("=" * 65)
    print(f" Total Pemasukan   : {format_rupiah(total['total_pemasukan']):>20}")
    print(f" Total Pengeluaran : {format_rupiah(total['total_pengeluaran']):>20}")
    print(f" Saldo Kas Bersih  : {format_rupiah(total['saldo_bersih']):>20}")
    print("-" * 65)
    print(" Evaluasi Alokasi 50/30/20:")
    print(f" {'Kategori':<28} {'Realisasi':<15} {'Persen':<10} {'Status'}")
    print("-" * 65)
    for kat, data in analisis["kategori"].items():
        print(f" {kat:<28} {format_rupiah(data['nominal']):<15} {data['persen_real']}% ({data['persen_target']}%)  {data['status']}")
    print("-" * 65)

    if analisis["saran_rekomendasi"]:
        print(" 💡 Saran Finansial ACE:")
        for s in analisis["saran_rekomendasi"]:
            print(f"   • {s}")
        print("-" * 65)

    if anomali:
        print(" ⚠️  Peringatan Anomali Transaksi Tinggi:")
        for a in anomali:
            print(f"   • [{a['deskripsi']}] {format_rupiah(a['nominal'])} ({a['porsi_dari_total_belanja']}% dari total belanja)")
        print("-" * 65)
    print("=" * 65 + "\n")


def jalankan_demo(pk: PengelolaKeuangan) -> None:
    """Memasukkan data simulasi realistis untuk demonstrasi alur penuh."""
    print("Menyiapkan data simulasi anggaran pribadi...")
    pk.transaksi = []
    pk.tambah_pemasukan("Gaji Bulanan Software Engineer", 12500000, "Gaji Pokok")
    pk.tambah_pemasukan("Bonus Proyek Freelance API", 2500000, "Sampingan")
    pk.tambah_pengeluaran("Sewa Apartemen / Kos Bulanan", 3500000, "kebutuhan")
    pk.tambah_pengeluaran("Belanja Bahan Makanan & Supermarket", 2000000, "kebutuhan")
    pk.tambah_pengeluaran("Tagihan Listrik, Air, & Internet Rumah", 850000, "kebutuhan")
    pk.tambah_pengeluaran("Ngopi & Makan Restoran Akhir Pekan", 1200000, "keinginan")
    pk.tambah_pengeluaran("Langganan Streaming & Gym Membership", 450000, "keinginan")
    pk.tambah_pengeluaran("Upgrade Monitor Eksternal 4K", 2800000, "keinginan")
    pk.tambah_pengeluaran("Investasi Reksadana Saham & SBN", 2500000, "tabungan")
    pk.tambah_pengeluaran("Tabungan Dana Darurat", 1000000, "tabungan")
    csv_file = pk.ekspor_csv()
    render_tabel_ringkasan(pk)
    print(f"✅ Data transaksi berhasil disimpan ke: {pk.data_path}")
    print(f"✅ Rekap CSV diekspor ke: {csv_file}")


def main():
    parser = argparse.ArgumentParser(description="Pengelola Keuangan Pribadi & Evaluasi Anggaran 50-30-20")
    parser.add_argument("--demo", action="store_true", help="Jalankan simulasi data lengkap dan cetak laporan")
    parser.add_argument("--rekap", action="store_true", help="Tampilkan tabel ringkasan transaksi saat ini")
    parser.add_argument("--ekspor", action="store_true", help="Ekspor data transaksi ke berkas CSV")
    parser.add_argument("--masuk", nargs=2, metavar=("DESKRIPSI", "NOMINAL"), help="Catat pemasukan baru")
    parser.add_argument("--keluar", nargs=3, metavar=("DESKRIPSI", "NOMINAL", "KATEGORI"), help="Catat pengeluaran (kategori: kebutuhan/keinginan/tabungan)")
    parser.add_argument("--data", default="data_keuangan.json", help="Path berkas penyimpanan JSON")

    args = parser.parse_args()
    pk = PengelolaKeuangan(args.data)

    if args.demo:
        jalankan_demo(pk)
        return

    if args.masuk:
        desc, nom = args.masuk
        item = pk.tambah_pemasukan(desc, float(nom))
        print(f"✅ Berhasil mencatat pemasukan: '{item['deskripsi']}' ({format_rupiah(item['nominal'])})")

    if args.keluar:
        desc, nom, kat = args.keluar
        item = pk.tambah_pengeluaran(desc, float(nom), kat)
        print(f"✅ Berhasil mencatat pengeluaran: '{item['deskripsi']}' ({format_rupiah(item['nominal'])}) [{item['kategori']}]")

    if args.ekspor:
        csv_file = pk.ekspor_csv()
        print(f"✅ Berkas CSV berhasil dibuat di: {csv_file}")

    if args.rekap or (not args.masuk and not args.keluar and not args.ekspor and not args.demo):
        render_tabel_ringkasan(pk)


if __name__ == "__main__":
    main()
