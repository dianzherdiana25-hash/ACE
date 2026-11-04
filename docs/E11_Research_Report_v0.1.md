# ACE E1.1 — Independent Method Discovery Challenge

**Laporan penelitian v0.1 | 4 November 2026**  
**Keputusan:** `ENGINEERING_PASS / RESTRICTED_PROGRAM_SYNTHESIS_SUPPORTED / OUTPERFORMS_STRONG_BEAM_NOT_CONFIRMED / OPEN_ENDED_INVENTION_NOT_DEMONSTRATED`

## 1. Ringkasan

Penelitian E1.1 menindaklanjuti hasil E1, khususnya kebutuhan mempelajari **motif prosedur baru dari contoh tugas target**, bukan hanya mentransfer macro sumber yang telah disintesis sebelumnya. Empat pencari program memiliki akses ke 12 operasi dasar yang sama, empat contoh input–output per tugas, anggaran 256 kandidat per tugas, dan panjang program tetap empat operasi. Tidak ada API model berbayar, pelatihan neural, ataupun eksekusi kode Python buatan agen.

Pada 24 seed konfirmatori baru, masing-masing berisi dua tugas, pencarian evolusioner berbasis umpan balik (**EVOLVE**) menghasilkan **111/480 (23,13%)** prediksi benar pada input tersembunyi panjang sembilan. Kontrol RANDOM menghasilkan **21/480 (4,38%)**, mutasi dengan umpan balik semu namun tetap memilih terbaik di akhir (**SHAM_EVOLVE**) **30/480 (6,25%)**, dan pencarian beam berbasis skor (**BEAM**) **60/480 (12,50%)**.

Perbandingan berpasangan berbasis 24 cluster seed mendukung perbedaan EVOLVE atas RANDOM dan SHAM_EVOLVE pada benchmark internal ini. Perbedaan EVOLVE atas BEAM **belum konklusif**. Tidak ada bukti ditemukannya primitive baru atau peningkatan kecerdasan umum.

## 2. Pertanyaan dan rancangan

**Pertanyaan utama:** Dapatkah pencarian yang dipandu skor contoh menghasilkan program komposit yang menyelesaikan motif transformasi yang tidak diberikan sebagai metode siap pakai, lebih baik daripada pencarian acak dan kontrol pencarian kuat dengan anggaran sama?

- Domain: vektor bilangan bulat modulo 11, 12 operasi dasar dari bahasa DSL E1. Target: **program empat operasi**; program target memuat paling sedikit satu operasi yang bergantung pada struktur/posisi (`neighbor`, `spread`, atau `alt`).
- Batas kebaruan yang digunakan dalam generator: tanda tangan target berbeda dari semua program satu atau dua operasi pada delapan input referensi, dan tidak memuat tiga operasi sumber sebagai subsekuens berurutan. **Ini uji kebaruan terbatas, bukan bukti ekuivalensi formal global.**
- Contoh yang terlihat pencari: empat pasangan vektor panjang enam; tidak ada jawaban evaluasi akhir pada antarmuka pencari.
- Evaluasi tersembunyi: sepuluh input panjang sembilan dan sepuluh input panjang tiga belas per tugas.
- Dataset pengembangan: delapan seed 1201–1208, 16 tugas. Dataset konfirmatori: 24 seed 9301–9324, 48 tugas. Kedua kelompok terpisah.
- Keempat metode memulai setiap tugas dari 24 proposal yang sama, diikuti eksplorasi berbeda sesuai kebijakan. Semua memakai **256 evaluasi kandidat × empat contoh × empat operasi = 4.096 eksekusi primitive** per tugas per kebijakan, tidak termasuk overhead pencarian dan audit.
- Kebijakan: RANDOM (acak, skor hanya untuk seleksi akhir), SHAM_EVOLVE (mutasi dari populasi yang dipilih menggunakan skor acak, skor tugas hanya untuk seleksi akhir), EVOLVE (mutasi dari populasi unggul berdasarkan skor contoh tugas), dan BEAM (mutasi terjadwal dari arsip kandidat unggul). Semua memilih kandidat akhir menggunakan skor contoh tugas.
- Interpreter dipercaya dan membatasi program ke DSL empat operasi; tidak ada `eval`/`exec` pada kode kandidat.

## 3. Pra-penguncian kode

Berkas `preconfirm_lock.json` disimpan sebelum seed 9301–9324 dijalankan dan berisi SHA-256 seluruh kode inti, unit test, auditor, dan protokol. Pengujian konfirmatori dijalankan **sekali** tanpa penyetelan kode setelah melihat hasil. Timestamp pada berkas merupakan catatan lokal, bukan penguncian terpublikasi, dan tidak membuktikan independensi penilai eksternal. Berkas `posthoc_analysis.py` dibuat **setelah** pengujian untuk menghitung ketidakpastian; tidak ikut menentukan kandidat atau protokol.

## 4. Hasil konfirmatori

| Kebijakan | Prediksi benar len9 | Akurasi | Prediksi benar len13 | Tugas dengan seluruh 10 len9 benar |
|---|---:|---:|---:|---:|
| RANDOM | 21/480 | 4,38% | 23/480 | 2/48 |
| SHAM_EVOLVE | 30/480 | 6,25% | 30/480 | 3/48 |
| **EVOLVE** | **111/480** | **23,13%** | **110/480** | **11/48** |
| BEAM | 60/480 | 12,50% | 61/480 | 6/48 |

Tidak semua skor cocok-demo menjadi keberhasilan tersembunyi: misalnya, EVOLVE cocok sempurna pada empat contoh untuk 14 dari 48 tugas tetapi hanya mencapai seluruh 10 jawaban tersembunyi pada 11 tugas.

### Ketidakpastian perbandingan EVOLVE

Bootstrap 12.000 replikasi dengan **seed sebagai unit sampling berkelompok** (dua tugas per seed); angka dalam *poin persentase*, bersifat interval eksploratori untuk distribusi generator saat ini:

| Pembanding | Selisih | Interval 95% bootstrap | Seed EVOLVE unggul / seri / tertinggal |
|---|---:|---:|---|
| RANDOM | +18,75 | [+8,54; +29,17] | 9 / 14 / 1 |
| SHAM_EVOLVE | +16,88 | [+4,17; +29,38] | 10 / 12 / 2 |
| BEAM | +10,63 | [−4,17; +23,33] | 8 / 14 / 2 |

**Keputusan inferensi:** EVOLVE menunjukkan manfaat dibanding kontrol acak dan skor semu. EVOLVE belum terbukti lebih kuat daripada BEAM, karena interval utama meliputi nol. Observasi positif harus dibaca bersama tingginya jumlah seed yang seri pada nol serta domain eksperimen yang sangat sempit.

## 5. Audit dan reproduksibilitas

- **12/12** tes rekayasa lulus, termasuk determinisme, pengaruh umpan balik pada lintasan proposal, dan kesamaan 24 kandidat awal.
- **192/192** rekaman run dan rantai SHA-256 lulus audit.
- **3.840/3.840** prediksi tersembunyi dihitung ulang dengan interpreter kedua yang ditulis terpisah dari interpreter penelitian utama.
- **48/48** tugas memiliki inisialisasi yang sama pada empat pembanding.
- Pengujian ulang dari kode paket dapat dijalankan tanpa sambungan internet, akun, atau biaya API; notebook Colab disediakan. Eksekusi notebook pada **akun Colab pengguna** belum diuji pada saat laporan ini dibuat.
- Rantai hash dan manifest melindungi deteksi perubahan data, **bukan** bukti pihak ketiga tentang keberadaan atau waktu eksperimen.

## 6. Ancaman validitas

1. **Kebaruan terbatas.** Seluruh solusi terdiri dari empat operasi yang telah didefinisikan manusia. Sistem tidak dapat menemukan primitive di luar kosakata itu; istilah “penemuan metode” di sini berarti sintesis urutan program baru yang dipilih dari contoh.
2. **Benchmark internal.** Generator dan evaluator ditulis dalam penelitian yang sama. Interpreter audit terpisah menyediakan pemeriksaan teknis, bukan evaluasi eksternal oleh peneliti yang independen.
3. **Biaya operasional tidak sepenuhnya identik.** Jumlah kandidat dan eksekusi primitive untuk penilaian adalah sama, tetapi biaya pengelolaan arsip, mutasi, dan pembangkitan soal berbeda.
4. **Distribusi target direkayasa.** Guru target memakai tepat empat operasi dan sejumlah operasi kompleks; metode pencarian disetel pada keluarga tugas itu. Transfer ke domain lain belum teruji.
5. **Kecocokan contoh tidak menjamin generalisasi.** Empat contoh mungkin mengandung ambiguitas; hidden length9/13 lebih menantang, tetapi tetap diciptakan dari generator sama.
6. **Ketidakpastian luas.** Efek terhadap BEAM belum konklusif. Sampel 24 cluster dan banyaknya hasil nol membatasi kesimpulan.
7. **Tidak ada model AI otonom.** Agen E1.1 adalah mesin sintesis klasik berbasis heuristik buatan peneliti; eksperimen ini belum mendemonstrasikan penemuan tujuan riset baru atau modifikasi mandiri mekanisme belajarnya.

## 7. Keputusan dan langkah berikutnya

| Gerbang | Status |
|---|---|
| Mekanisme sintesis program dari contoh | PASS dalam DSL terbatas |
| Fairness anggaran kandidat dan primitive penilaian | PASS; bukan CPU yang benar-benar identik |
| Reproduksibilitas dan audit kedua | PASS secara lokal |
| Unggul atas RANDOM dan SHAM_EVOLVE | DIDUKUNG untuk benchmark internal |
| Unggul atas BEAM | **BELUM KONKLUSIF** |
| Menemukan primitive fundamental baru / AGI | **TIDAK DIBUKTIKAN** |

**Keputusan:** `CONTINUE_RESEARCH_WITH_FROZEN_E11_RESULTS`. Jangan menyesuaikan metode dari pengujian konfirmatori yang telah dibuka lalu mengklaim konfirmasi lagi pada seed yang sama. Studi berikutnya harus menggunakan generator dan evaluator yang benar-benar dirancang terpisah, benchmark dengan grammar tidak diketahui sebelumnya, kontrol sintesis yang lebih kuat, pengukuran CPU, serta tugas yang tidak dipilih untuk menguntungkan program empat langkah.

Dokumen ini tidak mengubah repositori Tod atau akun pengguna, tidak memakai layanan berbayar, dan tidak menjalankan eksperimen dunia fisik.
