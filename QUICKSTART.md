# ACE 5-Minute Quickstart (Panduan Cepat 5 Menit)

Selamat datang di ACE (Autonomous Capability Evolution). Repositori ini menyediakan platform penelitian mandiri untuk evolusi kemampuan perangkat lunak dan sintesis program bertipe, berjalan 100% lokal dengan biaya Rp0.

---

## 1. Verifikasi Kesehatan Sistem (30 Detik)
Periksa integritas sistem dan status gerbang ilmiah menggunakan:
```bash
python3 ace.py doctor
```
Keluaran harus menunjukkan `"overall_health": "HEALTHY"` dan `"source_integrity_pass": true` (25/25 file identik dengan upstream Git blobs).

---

## 2. Menjalankan Demo Sintesis & Pewarisan (1 Menit)
Jalankan loop lengkap intake, training, validasi, dan pewarisan kemampuan:
```bash
python3 ace.py demo --workspace ./ace-work
```
Perintah ini akan menjalankan 3 tugas publik (`source_equal`, `inherited_equal`, `changed_ends`), memvalidasi pewarisan kemampuan tanpa refitting, dan mencetak laporan evaluasi terminal 128/128.

---

## 3. Menggunakan Mission Bus (1 Menit)
Kanal komunikasi utama antara runtime ACE dan agen peneliti:
```bash
# 1. Hasilkan misi baru dari diagnosis kegagalan
python3 ace.py mission --workspace ./ace-work generate

# 2. Cek status antrean misi dan rantai hash kriptografis
python3 ace.py mission --workspace ./ace-work status

# 3. Ambil misi berikutnya (CLAIMED)
python3 ace.py mission --workspace ./ace-work next --agent "advisor_antigravity"

# 4. Kirim hasil patch artefak
python3 ace.py mission --workspace ./ace-work submit \
  --id "<MISSION_ID>" \
  --artifact "/path/to/solution.py" \
  --agent "advisor_antigravity"
```

---

## 4. Pelatihan dengan Toleransi Kesalahan (Max Errors) (1 Menit)
Gunakan `ace.py train` untuk melatih model dengan seleksi sadar-admission:
```bash
python3 ace.py train \
  --workspace ./ace-work \
  --task examples/equal.json \
  --max-errors 1
```

---

## 5. Menjalankan Seluruh Uji Regresi & Penilai Tersegel (1.5 Menit)
```bash
# Uji Penilai Tersegel W2 (anti-curang & 6 keluarga tugas)
PYTHONPATH=code python3 -m unittest discover -s code/ace_evaluator -p "test_*.py"

# Uji Perbaikan Inti W3 (sadar-admission, anti-drift, decomposed library)
PYTHONPATH=code python3 -m unittest discover -s code/ace_core_repair -p "test_*.py"

# Uji Mission Bus W1
PYTHONPATH=code python3 -m unittest discover -s code/ace_mission -p "test_*.py"
```

---

## Catatan Integritas Ilmiah
- **Rp0:** Tidak ada panggilan API eksternal berbayar.
- **Seeded Seal:** Bila `ACE_SEALED_SEED` tidak disuplai di lingkungan, semua klaim ilmiah secara fail-closed berstatus `NOT_ASSESSED`.
