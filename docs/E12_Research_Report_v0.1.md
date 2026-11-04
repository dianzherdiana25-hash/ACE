# ACE E1.2 — Primitive Discovery: laporan konfirmatori v0.1

**Tanggal:** 4 November 2026  
**Keputusan:** `ENGINEERING_PASS / BOUNDED_OPERATOR_INDUCTION_AND_REUSE_SUPPORTED / OPEN_ENDED_PRIMITIVE_DISCOVERY_NOT_DEMONSTRATED`

## 1. Ringkasan eksekutif

Penelitian E1.2 membangun induksi operator baru dalam bahasa ekspresi numerik terbatas. Sistem menerima contoh input–output, menyintesis satu fungsi berbentuk ekspresi aritmetika dan tetangga, lalu menyimpannya sebagai primitive yang dapat dipakai untuk menyelesaikan tugas berikutnya. Primitive merupakan *kombinasi parameter dan struktur yang tersedia dalam grammar*, **bukan** operasi fundamental baru di luar grammar.

Pada 40 episode konfirmatori baru (masing-masing dua tugas terkait dan dua tugas tak terkait), metode yang menggunakan kembali primitive hasil induksi (**REUSE**) menyelesaikan 640/640 input tersembunyi pada tugas dengan operator sumber yang sama. Kontrol **TARGET_ONLY** memperoleh 48/640, **SHAM** 56/640, **WRONG** 40/640. Namun, kontrol kuat **STRUCTURED**, yang mengetahui grammar dan menyelesaikan koefisien menggunakan eliminasi modular, juga mencapai **640/640**. Dengan demikian, eksperimen membuktikan mekanisme komposisi/penyimpanan/transfer operator **pada keluarga masalah yang sengaja berbagi operator**, bukan nilai tambah penemuan dibanding solver analitis yang mengetahui grammar.

Pada tugas yang menggunakan operator lain, REUSE hanya mencapai 48/640, sedangkan TARGET_ONLY mencapai 88/640 dan STRUCTURED 640/640. **Tidak ada bukti transfer bebas ke operator yang benar-benar berbeda.**

## 2. Pertanyaan dan prapenguncian

**Hipotesis utama yang dikunci:** pada tugas terkait, primitive yang diinduksi dari contoh sumber akan meningkatkan keberhasilan tersembunyi dibanding pencarian target saja, dengan jumlah evaluasi kandidat yang sama.

Rancangan dikunci sebelum seed konfirmatori `12501–12540` dijalankan. Prapenguncian disimpan pada `preconfirm_lock.json` yang merekam hash SHA-256 tujuh berkas inti dan protokol, serta ringkasan pengembangan. Ini adalah penguncian **lokal**, bukan pendaftaran resmi pihak ketiga. Setelah penguncian, berkas tersebut diverifikasi belum berubah. Analisis statistik pascauji tidak digunakan untuk mengubah kode/hipotesis.

Pada fase pengembangan, kontrol label-acak sempat memungkinkan keluaran tetap di posisi semula. Masalah ini **dikoreksi sebelum penguncian**, menggunakan permutasi siklik tanpa titik tetap; hasil konfirmatori menggunakan desain yang telah diperbaiki.

## 3. Lingkungan dan primitive yang diinduksi

Domain: vektor bilangan bulat modulo 17, panjang bervariasi. Bahasa representasi berisi `x[i]`, tetangga kiri/kanan, paritas posisi, perkalian konstanta kecil, penjumlahan, dan offset. Bentuk operator:

`P(x)[i] = (a*x[i] + b*x[(i+side) mod n] + c*(i mod 2) + d) mod 17`

Dengan `a,b,c∈{1,2,3}`, `d∈{0,1,2,3}`, `side∈{-1,+1}`: **216 kandidat operator**. Tidak ada operator penuh ini yang diberikan sebagai primitive siap pakai dalam antarmuka pencarian; inducer menilai semua 216 kandidat pada lima contoh sumber. Tugas target adalah komposisi operator tersebut dengan satu dari enam wrapper: identity, increment, decrement, rotasi kiri, rotasi kanan, atau balik. Ada 4 contoh target, 8 input *hidden* panjang 9, dan 8 input *hidden* panjang 13.

**Catatan batas:** peneliti menentukan struktur ekspresi dan ruang parameternya di muka. Proses ini lebih tepat disebut *induksi operator terparametrisasi* daripada penemuan primitive terbuka.

## 4. Metode pembanding dan anggaran

Lima kebijakan dijalankan untuk **160 tugas per kebijakan** (80 terkait, 80 tak terkait):

| Kebijakan | Fungsi |
|---|---|
| REUSE | Menyintesis operator sumber dan menggunakannya sebagai titik awal pencarian target |
| TARGET_ONLY | Menjalankan biaya induksi sumber yang sama tetapi membuang hasilnya; mencari solusi dari contoh target |
| SHAM | Mempelajari dari label sumber yang dipermutasi tanpa pasangan tepat, lalu mentransfer kandidat tersebut |
| WRONG | Mempelajari operator dari tugas sumber lain yang berbeda |
| STRUCTURED | Solver matematis eksplisit yang mengetahui persamaan dalam grammar, tanpa perlu transfer; kontrol kuat |

Untuk setiap episode dan kebijakan: 216 evaluasi kandidat sumber + 4×64 evaluasi kandidat target = **472 evaluasi kandidat**. Semua kebijakan memulai 12 proposal target awal yang sama. Namun, waktu CPU dan overhead khusus solver struktural tidak disetarakan. Kontrol STRUCTURED memakai inferensi aljabar eksplisit di luar evaluasi kandidat; ini **bukan** kompetisi waktu komputasi yang setara.

Tugas RELATED memakai operator sumber sama dengan wrapper yang bervariasi; UNRELATED memakai operator berbeda. Ini ditentukan generator dan sengaja menguji *positive transfer* versus *negative transfer*.

## 5. Hasil konfirmatori

Hasil *exact-vector accuracy* pada masing-masing 640 prediksi tersembunyi panjang 9:

| Kebijakan | RELATED | UNRELATED |
|---|---:|---:|
| **REUSE** | **640/640 (100%)** | 48/640 (7,50%) |
| TARGET_ONLY | 48/640 (7,50%) | 88/640 (13,75%) |
| SHAM | 56/640 (8,75%) | 32/640 (5,00%) |
| WRONG | 40/640 (6,25%) | 48/640 (7,50%) |
| **STRUCTURED** | **640/640 (100%)** | **640/640 (100%)** |

Untuk input tersembunyi panjang 13, skor sama pada seluruh kebijakan dalam eksperimen ini. Pola ini memperkuat ketepatan solusi pada panjang yang berbeda **dalam grammar sama**, tetapi bukan transfer lintas domain.

### Ketidakpastian statistik

Bootstrap berpasangan dengan **40 episode sebagai unit cluster**, 10.000 pengambilan ulang; interval persentil 95%, satuan poin persentase:

| Kontras | Selisih akurasi | Interval 95% |
|---|---:|---:|
| REUSE − TARGET_ONLY, RELATED | +92,50 | [+86,25; +97,50] |
| REUSE − SHAM, RELATED | +91,25 | [+83,75; +97,50] |
| REUSE − WRONG, RELATED | +93,75 | [+88,75; +98,75] |
| REUSE − STRUCTURED, RELATED | 0,00 | [0,00; 0,00] |
| REUSE − TARGET_ONLY, UNRELATED | −6,25 | [−15,00; +2,50] |

Interval merupakan ringkasan ketidakpastian pada distribusi generator internal, bukan generalisasi ke semua persoalan dunia nyata. Selisih UNRELATED tidak konklusif pada ukuran sampel ini.

## 6. Audit dan reproduksibilitas

- **14/14** pengujian rekayasa lulus.
- **800/800** run konfirmatori dan rantai SHA-256 diperiksa.
- **12.800/12.800** prediksi tersembunyi dihitung ulang dengan implementasi evaluator kedua.
- **160/160** kelompok tugas memiliki 12 proposal awal yang identik pada seluruh kebijakan.
- **7/7** berkas inti + protokol cocok dengan hash lokal pra-konfirmasi.
- Pengujian berjalan pada CPU lingkungan sesi tanpa API berbayar. Artefak menyimpan kode, protokol, log, hasil, statistik, dan notebook untuk reproduksi di Google Colab; **belum ada bukti reproduksi Colab pengguna untuk E1.2**.

## 7. Ancaman terhadap validitas

1. **Generator dibuat sesuai grammar yang diketahui.** Transfer terkait hampir terjamin ketika operator sumber dapat ditemukan dari lima contoh dan langsung dipakai ulang.
2. **Kontrol struktural sempurna.** Ini membantah klaim bahwa pendekatan pembelajaran primitive unggul atas penalaran analitis dengan pengetahuan struktur.
3. **Bukan penemuan terbuka.** Sistem mencari 216 kombinasi parameter dalam template aritmetika yang sudah didefinisikan peneliti, bukan menambah operator matematika fundamental baru.
4. **Benchmark internal dan deterministik.** Evaluator kedua memeriksa semantik, tetapi tidak ada penilai eksternal atau grammar yang disembunyikan dari peneliti.
5. **Anggaran evaluasi kandidat, bukan CPU, disetarakan.** Biaya penyelesaian struktural tidak dibandingkan pada satu metrik compute yang adil.
6. **Tidak ada eksplorasi tujuan ilmiah mandiri.** Mesin riset belum memilih topik, merumuskan tujuan, atau mengubah algoritma belajarnya sendiri tanpa rancangan manusia.
7. **Keuntungan turun pada tugas tidak terkait.** Mengulang primitive yang salah dapat mengalihkan pencarian dari solusi target.

## 8. Keputusan dan arah E1.3

**Keputusan:** `CONTINUE_RESEARCH / LIMITED_OPERATOR_REUSE_PASS / OPEN_ENDED_INVENTION_NO_GO`.

Persyaratan eksperimen berikutnya:

- Gunakan **keluarga grammar yang disembunyikan dari agen dan berbeda secara struktural** dari grammar konstruksi E1.2, dengan oracle/evaluator terpisah.
- Bandingkan dengan solver struktural, enumerasi program, dan *inductive program synthesis* yang kuat dengan metrik biaya total (CPU, pemanggilan, evaluasi, memori), bukan hanya jumlah kandidat.
- Nilai **kebaruan semantik** metode, transfer ke motif yang tidak ada pada contoh sumber, dan kemunduran akibat transfer yang salah.
- Pertahankan pemisahan development/confirmation, versi beku, serta bukti keluaran tersimpan. Jangan menyimpulkan kecerdasan umum dari komposisi yang berhasil pada DSL sempit.

Tidak ada perubahan repositori pengguna, layanan berbayar, atau eksperimen fisik selama E1.2.
