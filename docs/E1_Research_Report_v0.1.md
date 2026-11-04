# ACE E1 — Prospective Capability Invention Challenge

**Laporan penelitian v0.1 · 4 November 2026**  
**Keputusan:** `ENGINEERING_PASS / BOUNDED_COMPOSITIONAL_TRANSFER_SUPPORTED / OPEN_ENDED_INVENTION_NOT_DEMONSTRATED`

## 1. Ringkasan eksekutif

Eksperimen ACE E1 menguji sistem sintesis program berbasis contoh pada sebuah DSL transformasi vektor. Berbeda dari F3–F4b yang berpusat pada macro dalam konfigurasi yang telah ditentukan, eksperimen ini meminta sistem **menemukan urutan prosedur sumber dari pasangan contoh input–output** sebelum menggunakan prosedur tersebut sebagai fungsi yang dapat dikomposisikan pada tugas baru. Sistem **tidak memakai model bahasa** dan tidak menghasilkan kode Python untuk dieksekusi: keluaran program dievaluasi oleh interpreter dengan batas panjang.

**Hasil utama:** Pada tugas `shared-new-composition`, C dengan macro yang dipelajari mencapai **463/960 (48,23%)** prediksi benar dibanding **20/960 (2,08%)** pada B tanpa macro, selisih **+46,15 poin persentase**. Interval bootstrap berkelompok 95% atas 24 episode adalah **+29,69 sampai +62,60 poin**. Perbedaan positif pada benchmark ini dapat direproduksi dan tidak dapat dijelaskan hanya dengan transfer macro yang diacak, tetapi **tidak membuktikan penemuan algoritma umum**.

**Hasil negatif:** Saat motif operasi target tidak muncul pada sumber (`unseen-motif`), C gagal pada **0/480**, sedangkan B menyelesaikan **40/480 (8,33%)**. Kemampuan yang diperoleh bersyarat pada relevansi motif.

## 2. Status preregistrasi, pemisahan, dan evaluasi

Protokol konfirmatori (`protocol.json`) dan berkas penelitian inti dibekukan dengan hash SHA-256 dalam `pre_run_lock.json` **sebelum** seed 8801–8824 diproses. Pilot pengembangan memakai seed 7001–7006 dan tidak digunakan sebagai data konfirmatori. Evaluator dan generator berada pada `evaluator.py`; kode kandidat pada `policy.py` hanya menerima empat pasangan contoh dan fungsi interpreter, bukan referensi tugas atau hasil tersembunyi. Evaluasi akhir memakai 20 input baru sepanjang 9 elemen, berbeda dari contoh sepanjang 6 elemen.

Ini pemisahan **di tingkat kode**, bukan evaluasi oleh lembaga atau peneliti eksternal. Seluruh komponen ditulis dalam konteks proyek yang sama dan bahasa tugasnya memiliki bias terancang: motif yang bisa dipelajari sengaja muncul pada dua tugas transfer per episode. Karena itu ini benchmark internal yang dibekukan sebelum konfirmasi, **bukan** pembuktian kuat lintas domain independen.

- Episode konfirmatori: **24**.
- Kondisi per episode: **5 kebijakan × 3 tugas**.
- Run akhir: **360**.
- Prediksi uji akhir: **7.200**.
- Contoh pengembangan sumber: **4**; contoh per tugas target: **4**; input evaluasi akhir per tugas: **20**.
- Anggaran pencarian target B/C/D/E: **400 kandidat per tugas**; anggaran pencarian prosedur sumber: **1.884 kandidat per episode**.
- Semua kebijakan memakai interpreter dan set tugas akhir yang sama. Operasi macro komposit lebih mahal per kandidat daripada operasi pendek; anggaran CPU total belum distandarkan.

## 3. Lima kebijakan pembanding

| Kode | Deskripsi | Fungsi kausal |
|---|---|---|
| A — Atomic | Memilih operasi tunggal terbaik dari contoh target | Kontrol tanpa komposisi |
| B — Base | Menelusuri komposisi operasi dasar tanpa pustaka metode yang diwariskan | Kontrol tanpa abstraksi persisten |
| C — Learned macro | Menyintesis prosedur sumber dan memasukkannya sebagai fungsi reusable dalam pencarian target | Intervensi utama |
| D — Shuffled macro | Memakai prosedur dari episode sumber yang tidak relevan | Kontrol transfer palsu |
| E — No-feedback macro | Memakai prosedur acak yang tidak dipilih dari label sumber | Kontrol tanpa pembelajaran sumber |

Semua target ditentukan oleh oracle yang tidak dapat dibaca kebijakan selama pencarian. Perlu dicatat bahwa B tidak mendapat kemampuan untuk menyimpan dan memanggil prosedur hasil pembelajaran sumber; karena itu E1 terutama menguji **nilai memori prosedural dan kompresi representasi**, bukan pembandingan dua sistem dengan kemampuan representasi atau total biaya CPU yang identik.

## 4. Hasil konfirmatori

### 4.1 Tugas komposisi baru yang berbagi motif sumber

| Kebijakan | Benar/total | Akurasi |
|---|---:|---:|
| A — Atomic | 0/960 | 0.00% |
| B — Base | 20/960 | 2.08% |
| **C — Learned macro** | **463/960** | **48.23%** |
| D — Shuffled | 20/960 | 2.08% |
| E — No feedback | 0/960 | 0.00% |

Selisih C − B: **46.15 poin persentase**; interval bootstrap 95% **[29.69; 62.60]** poin. Unit bootstrap adalah **episode**, bukan 960 prediksi yang diperlakukan independen. Analisis bootstrap yang sama berlaku untuk C − D karena D dan B sama-sama 20/960. Semua hasil berasal dari satu evaluasi konfirmatori setelah kode dikunci.

### 4.2 Tugas motif baru yang tidak diberikan pada sumber

| Kebijakan | Benar/total | Akurasi |
|---|---:|---:|
| A — Atomic | 0/480 | 0.00% |
| B — Base | 40/480 | 8.33% |
| **C — Learned macro** | **0/480** | **0.00%** |
| D — Shuffled | 0/480 | 0.00% |
| E — No feedback | 20/480 | 4.17% |

Keunggulan tidak ditransfer ke motif yang berbeda. Nilai buruk tidak boleh disembunyikan dengan menggabungkannya ke agregat seluruh kondisi.

### 4.3 Jejak penemuan metode terbatas

- **24/24** prosedur hasil sintesis tidak ekuivalen dengan operasi dasar satu atau dua langkah **pada kumpulan input referensi terbatas**.
- **18/24** prosedur menyelesaikan seluruh 20 contoh tersembunyi dari tugas sumber; rata-rata **15/20** benar.
- Sebagian prosedur bisa cocok dengan contoh sumber tetapi tidak tergeneralisasi. Pemeriksaan semantik terbatas pada sampel referensi, bukan bukti ketidaksetaraan formal untuk seluruh input.

## 5. Audit dan replikasi

- `python -m unittest -v test_e1.py`: **10/10 PASS**.
- Audit `run_results.jsonl`, hash-chain SHA-256, dan perhitungan skor: **360/360 run lulus**.
- Replay setiap prediksi dengan **implementasi interpreter kedua** (`audit_independent.py`): **7.200/7.200 PASS**.
- Audit pemisahan input contoh/tersembunyi, silsilah prosedur, dan sumber: **24/24 episode PASS**.
- Jumlah berkas serta checksum dilampirkan dalam paket ZIP final. Reproduksi notebook Colab dalam akun pengguna **belum dijalankan**.
- Berkas `pre_run_lock.json` adalah bukti penguncian lokal, **bukan** bukti waktu dari pihak ketiga. Data uji dan oracle menjadi dapat diperiksa setelah eksperimen selesai.

## 6. Ancaman validitas

1. **Keuntungan yang ditanamkan dalam desain tugas:** dua tugas target sengaja merupakan komposisi dari metode sumber; keberhasilan transfer pada kondisi tersebut sebagian diprediksi oleh struktur benchmark.
2. **Perbandingan tidak setara penuh:** C menginvestasikan pencarian prosedur sumber dan memperoleh token macro yang memperluas ruang fungsi dalam 400 kandidat target. B tidak boleh menyimpan abstraksi tersebut. Dengan demikian peningkatan mengukur representasi dan memori secara bersama, bukan kontribusi kecerdasan intrinsik yang terisolasi. Waktu CPU dan jumlah operasi atomik per kandidat juga belum disejajarkan ketat.
3. **Oracle dan penilai bukan eksternal:** pemisahan kode mencegah kebijakan membaca jawaban melalui antarmuka normal, tetapi pembuat benchmark dan pembuat sistem tetap satu sumber.
4. **Novelty terbatas:** prosedur yang baru disintesis hanya urutan dari 12 operasi bawaan; tidak ada penemuan primitive matematis baru yang belum ada dalam grammar.
5. **Domain tunggal sintetis:** tugas vektor tidak membuktikan transfer ke graf dunia nyata, sains, matematika riset, atau robotika.
6. **Validitas statistik lokal:** interval hanya berlaku untuk distribusi dan generator episode ini; bukan jaminan peningkatan pada populasi tugas umum.

## 7. Keputusan gerbang

| Gerbang | Keputusan | Interpretasi |
|---|---|---|
| E1 Engineering | **PASS** | Sintesis, makro reusable, kelima pembanding, pengujian, dan audit berfungsi |
| E1 Bounded method synthesis | **SUPPORTED** | Sistem menghasilkan metode komposit dari contoh, tidak sekadar memilih primitive tunggal |
| E1 Transfer to related unseen compositions | **SUPPORTED on constructed benchmark** | Kontras primer positif dengan CI bawah > 0 dan efek > 5 poin |
| E1 Transfer to genuinely unseen motifs | **NOT SUPPORTED** | C 0/480 |
| E1 Robust independent invention | **HOLD** | Belum ada penilai eksternal, kesetaraan biaya/representasi, atau domain baru |
| Open-ended intelligence evolution / AGI | **NO-GO for claim** | Tidak dievaluasi ataupun tercapai |

**Keputusan:** lanjutkan ke desain **E1.1** dengan komputasi setara secara primitif/CPU, kontrol yang dapat mempelajari ulang prosedur sumber, tugas disiapkan evaluator independen, dan pengujian motif baru yang tidak selalu mengandung komposisi sumber. Jangan menyesuaikan sistem berdasarkan konfirmasi E1 yang sudah dibuka lalu mengujinya kembali pada seed yang sama sebagai bukti baru.

## 8. Asal penelitian

Referensi operasional: ACE F5 Research Synthesis & Decision v0.1 dan bukti F0–F4b yang sudah dibuat sebelumnya. Penelitian E1 adalah fase baru; tidak mengubah bukti historis tersebut, repositori Tod, akun eksternal, maupun layanan berbayar.
