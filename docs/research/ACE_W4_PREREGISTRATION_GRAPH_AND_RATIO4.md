# Preregistrasi Riset W4: Pertumbuhan Kemampuan DSL (Graf & Rasio 4:1)

**Tanggal:** 8 November 2026  
**Status Ilmiah:** `PREREGISTERED` (Sebelum Eksekusi Eksperimen)  
**Anggaran Finansial:** $0.00 / Rp0 (CPU Lokal)  
**Tujuan PRD:** G2 (Kondisi A/B/C Adil), G3 (Generalisasi Lintas Keluarga), G4 (Pewarisan Kemampuan Penerus)

---

## 1. Hipotesis yang Dapat Gugur (Falsifiable Hypotheses)
1. **H_graph (Ekspansi Primitif Graf):**
   Perluasan DSL bertipe dengan operator traversal keterhubungan graf berbasis BFS berbatas kedalaman mampu menyelesaikan tugas keterhubungan graf 4-vertex dengan akurasi $\ge 90\%$ pada held-out test, melampaui baseline acak saat ini (50%–58%), tanpa menyalin library BFS buatan manusia.
   - *Kriteria Gugur:* Jika akurasi Condition C $\le 65\%$ atau tidak berbeda signifikan dari Condition A ($p \ge 0.05$), hipotesis DITOLAK.

2. **H_ratio4 (Representasi di Luar Tata Bahasa):**
   Komposisi modular residue tracker mampu menyelesaikan tugas rasio 4:1 ($N_a > 4 N_b$) yang sebelumnya ditolak oleh tata bahasa konstanta produk tertutup.
   - *Kriteria Gugur:* Jika admission rate pada held-out tetap 0%, hipotesis DITOLAK.

---

## 2. Kondisi Pembanding A/B/C (Anggaran Setara, PRD Bagian 8)
- **Kondisi A (Fixed Baseline):** Library statis 35-program tetap (DFA + Counter standar).
- **Kondisi B (Adaptive Search):** Pencarian mutasi lokal clause tunggal (sistem dasar ACE 6 November).
- **Kondisi C (Evolutionary / Mission Bus):** Sintesis primitif traversal bertipe yang diusulkan melalui Mission Bus dan diuji melalui Penilai Tersegel W2.

---

## 3. Protokol Statistik & Anggaran
- **Jumlah Tugas Held-Out:** 30 tugas per keluarga.
- **Ulangan (Replicates):** 3 ulangan per tugas.
- **Replikasi Seed:** 20 seed acak deterministik.
- **Batas Label:** Tepat 16 label per tugas (identik di seluruh kondisi).
- **Gerbang Penilai:** Seluruh kandidat dievaluasi menggunakan Penilai Tersegel W2 (6 keluarga tugas berparameter, negatif count-matched). Bila `ACE_SEALED_SEED` tidak disuplai, status rilis ilmiah tetap `NOT_ASSESSED`.
