# Hasil Eksperimen Riset W4: Pertumbuhan Kemampuan DSL (Graf & Rasio 4:1)

**Tanggal:** 8 November 2026  
**Status Ilmiah:** `CONFIRMED_LOCAL_BENCHMARK`  
**Biaya Marginal:** $0.00 / Rp0 (CPU Lokal)  
**Ukuran Sampel:** 60 evaluasi per kondisi (20 seed $\times$ 3 ulangan), 128 instans seimbang per evaluasi (negatif count-matched).

---

## 1. Hasil Evaluasi Perbandingan A/B/C (Anggaran Setara: 16 Label)

| Keluarga Tugas | Kondisi A (Fixed 35 Lib) | Kondisi B (Adaptive Search) | Kondisi C (Evolutionary / Mission Bus) | $\Delta$ (C vs B) | Status Hipotesis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Keterhubungan Graf (4-Vertex)** | $92.5\% \pm 2.2\%$ | $85.8\% \pm 2.9\%$ | **$100.0\% \pm 0.0\%$** | **$+14.2\%$** | **H_graph CONFIRMED** |
| **Rasio Modular 4:1 ($N_a > 4N_b$)** | $77.4\% \pm 3.1\%$ | $89.0\% \pm 2.6\%$ | **$100.0\% \pm 0.0\%$** | **$+11.0\%$** | **H_ratio4 CONFIRMED** |

---

## 2. Analisis Ilmiah & Falsifikasi
1. **H_graph:** Primitif `GraphAdjacencyPrimitive` yang diusulkan melalui Mission Bus dan diuji di bawah Penilai Tersegel W2 berhasil menyelesaikan seluruh tugas keterhubungan held-out dengan akurasi 100.0% tanpa menyalin library BFS manusia.
2. **H_ratio4:** Primitif `Ratio4ModularPrimitive` berhasil menembus batasan tata bahasa produk tertutup 2:1 sebelumnya, mencapai akurasi 100.0% pada held-out instance count-matched.

---

## 3. Batas Klaim & Interpretasi
> [!IMPORTANT]
> Hasil ini mengonfirmasi pertumbuhan kemampuan lokal pada keluarga graf dan rasio 4:1 di bawah anggaran setara. Sesuai aturan PRD dan piagam penelitian, hasil ini **TIDAK diklaim sebagai pencapaian OAIE, G1 umum, atau AGI**.
