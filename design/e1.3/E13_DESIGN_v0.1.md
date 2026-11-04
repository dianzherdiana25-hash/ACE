# ACE E1.3 — Unknown-Grammar Capability Discovery

**4 November 2026 · Draf desain v0.1 · `READY_FOR_E13_DESIGN`**

## 1. Pertanyaan dan dasar keputusan

Dengan contoh berlabel dan batas CPU yang sama, apakah ACE yang dapat menambah representasi internal lebih akurat daripada pembanding algoritmik kuat pada aturan target yang grammar-nya disembunyikan?

E1.2 tetap merupakan bukti induksi dan pemakaian ulang operator dalam grammar yang sudah ditentukan. REUSE menyamai STRUCTURED pada RELATED (640/640 masing-masing) dan skornya lebih rendah dari TARGET_ONLY pada UNRELATED (48/640 vs 88/640). Desain ini mempertahankan keputusan F5 `CONTINUE_RESEARCH_WITH_SCOPE_LIMITS`, membekukan data dan hasil sampai E1.2, serta memulai bank tugas E1.3 terpisah. OAIE tetap visi jangka panjang. E1.3 menguji kemampuan yang terbatas pada model komputasi, keluarga tugas, dan anggaran yang ditentukan.

Dasar: [Master Record v1.0 di Drive](https://docs.google.com/document/d/1esmTLeHNXpKsmVnH6rbUx7czKoIvbKZvzS-YEkVJkYE/edit?usp=drivesdk), [PRD](../../docs/PRD_ACE_v0.1.md), [RES](../../docs/ACE_Research_Execution_Spec_v0.1.md), [laporan E1.2](../../docs/E12_Research_Report_v0.1.md), dan [gerbang E1.3](../../E13_GATE.md).

## 2. Tugas dan apa yang disembunyikan

Gunakan dua keluarga deterministik dari arah RES. Contoh berikut hanya untuk fixture publik development. Jalur benchmark memilih aturan konfirmatori sendiri di balik kontrak I/O yang sama.

| Keluarga | Kontrak yang diketahui semua solver | Contoh fixture publik | Referensi penilai |
| --- | --- | --- | --- |
| S — transformasi simbolik | Urutan simbol masuk, urutan simbol keluar | Emit simbol berbeda saat detektor motif pada urutan masuk berpindah keadaan | Transduser referensi dengan tabel transisi dan keluaran |
| G — penalaran graf | Graf kecil beratribut dan pasangan simpul masuk, bilangan bulat atau sentinel keluar | Biaya lintasan sah terkecil ketika kelayakan sisi dipengaruhi label sisi sebelumnya | Pencarian deterministik atas graf yang memasukkan keadaan kendala |

Untuk setiap episode, berikan contoh sumber dan target, tipe I/O, serta batas ukuran. Satu episode memuat target motif baru yang secara struktur berhubungan dengan sumber dan target kontrol yang tidak berhubungan. Motif baru harus berasal dari aturan/komposisi yang berbeda dari sumber. Mengacak konstanta, simpul, atau nama token saja tidak memenuhi syarat. Jalur benchmark mengukur jarak pada bentuk kanonis aturan: jarak edit AST ternormalisasi pada kerangka aturan setelah nama dan literal dikanonisasi, serta kesamaan sub-struktur nontrivial. Kriteria awal adalah jarak positif dengan sub-struktur nontrivial bersama untuk target baru terkait, dan tanpa sub-struktur nontrivial bersama untuk kontrol tidak terkait. Tetapkan definisi sub-struktur, ambang, dan stratum dari development sebelum lock. Ukur masing-masing keluarga terpisah. Evaluator juga memeriksa kesetaraan fungsi pada domain uji kecil supaya perubahan sintaks saja tidak diperlakukan sebagai motif baru.

Bank dipisahkan berdasarkan blok aturan kanonis, baru kemudian seed dan input. Lintas split, periksa duplikasi aturan setelah penggantian nama/literal, hash tugas, dan kesamaan perilaku yang bisa diverifikasi. Jalur benchmark menguji apakah demonstrasi target membedakan aturan yang masuk akal pada domain kecil, lalu mengarantina kasus ambigu sebelum menerima prediksi solver. Setiap target motif baru mempunyai probe uji dengan ukuran dalam distribusi dan probe ekstrapolasi ukuran yang dilaporkan terpisah. Near transfer diukur dalam setiap keluarga. Uji arah S→G dan G→S tetap eksploratoris dan memerlukan percobaan yang secara eksplisit menahan satu keluarga dari pembelajaran.

## 3. Kontrak kandidat dan evaluator

| Tahap | Input yang diizinkan | Output |
| --- | --- | --- |
| `fit` | `task_id` opak, tipe/batas I/O, demonstrasi sumber/target, seed algoritme, anggaran | AST bertipe yang dibekukan, hash, silsilah dan catatan biaya |
| `predict` | AST beku dan satu input uji tanpa label, melalui interpreter evaluator | Satu prediksi kanonis atau kode kegagalan; tanpa umpan balik benar/salah |
| `score` | Prediksi dan kunci privat yang dihitung dari oracle terpisah | Catatan penilaian privat, lalu hasil agregat setelah seluruh run selesai |

`fit` memakai fungsi skor yang sama pada contoh yang memang boleh dilihat. Semua solver blind menerima informasi yang sama, termasuk batas bentuk data. ID, nama file, urutan, metadata, dan pesan kesalahan tidak membawa nama grammar, label split internal, atau petunjuk mengenai jawaban. Mode `development` memakai fixture publik untuk coding. Mode `selection` memakai bank validasi terpisah untuk memilih konfigurasi dan pembanding primer. Mode `sealed_evaluation` memakai kebijakan solver yang sudah dibekukan. Fit dalam satu episode tetap boleh memakai demonstrasi yang disediakan. Status kandidat dan cache direset antarepisode agar label atau hasil episode lain tidak mengubah kebijakan.

Pemisahan dijalankan lewat dua jalur. Jalur kandidat memiliki checkout ACE dan data publik. Jalur benchmark/evaluator memiliki generator, kunci, manifest blok aturan, dan oracle. Implementasi oracle memakai kode referensi tersendiri, tanpa impor kode solver. Jalur evaluator memvalidasi model data JSON, menjalankan AST dengan interpreter tepercaya, dan menyimpan per-item skor di sisi evaluator sampai seluruh kondisi selesai. Pemegang artefak evaluator membuka label hanya untuk runner setelah gerbang terpenuhi. Audit reproduksi teknis dilakukan sebagai pekerjaan terpisah dari implementasi kandidat. Ini dapat dilakukan di dalam proyek. Sertifikasi ilmiah oleh pihak luar berada di luar desain ini.

Kandidat adalah AST data dengan daftar tipe, operasi dan batas yang eksplisit. Interpreter memiliki bahan bakar eksekusi dan pembatas ukuran/depth. DSL tidak menyediakan jaringan, sistem berkas, akses kredensial, pemanggilan proses, impor, evaluasi kode Python, refleksi, atau rekursi tanpa batas. Worker terisolasi tanpa kredensial/jaringan dan tanpa mount data tersegel untuk jalur kandidat. Pilihan runtime harus dibuktikan lewat uji negatif sebelum gerbang konfirmasi.

## 4. Intervensi dan pembanding

Vocabulary tertutup `L0` berisi operasi lokal bertipe atas struktur input, kombinator murni, dan batas program yang sama untuk kontrol tertutup. `C_EXTEND` dapat mengusulkan node abstraksi keadaan bertipe, misalnya komposisi transisi yang dipakai ulang, dari operasi dasar yang diizinkan. Skema abstraksi bersifat umum. Kode kandidat tidak memuat enumerasi grammar target. Perluasan dicatat dengan hash definisi, induk, tipe, dan saksi perilaku. Definisi diserialisasi sebagai data dan dapat dipakai penerus yang dimulai dari keadaan awal yang sama.

| Kondisi | Metode | Informasi |
| --- | --- | --- |
| `A_FIXED` | Heuristik tetap dari katalog yang dibekukan | Contoh yang sama, tanpa memperbarui metode |
| `B_STRUCTURED_BLIND` | Inferensi struktural dari contoh dengan metode umum, misalnya induksi transduser atau inferensi kendala lintasan | Kontrak dan contoh, grammar target tersembunyi |
| `B_ENUM` | Enumerasi program bertipe dengan eliminasi duplikat perilaku pada data terbuka | Sama, vocabulary tertutup |
| `B_BEAM` | Sintesis program dengan beam, pemeringkatan dari contoh terbuka dan pruning tipe/semantik | Sama, vocabulary tertutup |
| `C_EXTEND` | Sintesis perluasan representasi, seleksi dan pewarisan | Sama, dengan izin menambah abstraksi |
| `C_NO_EXTEND` | Mekanisme C dengan perluasan node dinonaktifkan | Sama, vocabulary tertutup dan plafon C |
| `C_NO_TRANSFER` | Mekanisme C dengan artefak sumber dibuang sebelum fit target | Sama, pekerjaan sumber tetap tercatat |
| `C_SHAM` | Mekanisme C dengan sinyal seleksi sumber yang dipermutasi tanpa titik tetap | Sama, multiset sinyal dan kesempatan evaluasi dipertahankan |
| `STRUCTURED_ORACLE` | Solver matematis dengan akses ke kelas grammar, memakai demonstrasi untuk inferensi aturan | Grammar diketahui, instance laten dan kunci uji tetap tersembunyi. Hasil dilaporkan terpisah sebagai acuan berinformasi lebih |

Untuk `C_SHAM`, perlakuan berjalan di kanal seleksi kandidat, dengan urutan acak deterministik dalam tiap kelompok kandidat dan tetap menampilkan kondisi sinyal identik/ties sebagai tidak informatif. Simpan lineage dan biaya setiap proposal di semua kontrol terkait. Bekukan aturan fallback bila tidak ada program valid. Jangan mengganti kontrol setelah melihat hasil tersegel.

## 5. Estimand primer, kebaruan, dan keputusan

- **Satu kontras primer:** `C_EXTEND − B*` pada target motif baru terkait. `B*` dipilih sekali dari tiga pembanding blind terstruktur/enumeratif/beam berdasarkan akurasi agregat pada bank `selection` dengan plafon identik. Jika seri, pilih CPU total yang lebih rendah, lalu urutan ID leksikografis. Bekukan satu konfigurasi dan satu pembanding untuk kedua keluarga sebelum akses ke set konfirmatori. Laporkan hasil ketiga pembanding.
- **Skor dan ketidakpastian:** prediksi benar jika output kanonis persis sama. Rata-ratakan akurasi input dalam target, seed dalam episode, episode dalam blok aturan, blok dalam keluarga, lalu beri bobot sama ke S dan G. Hitung selisih berpasangan. Gunakan bootstrap berpasangan berstrata keluarga pada blok aturan, 10.000 resample dengan seed analisis yang dikunci, interval persentil 95%. Input dan seed pada aturan yang sama tidak dihitung sebagai sampel independen. Tampilkan skor, denominasi, kegagalan, interval dan biaya per keluarga. Jika jumlah blok tidak memadai menurut rencana yang dikunci, hasil tetap inkonklusif.
- **Aturan keputusan usulan:** dukungan awal untuk kontras primer jika estimasi minimal +10 poin persentase, batas bawah interval di atas nol, dan seluruh gerbang biaya/integritas lulus. Klaim manfaat pada kedua keluarga membutuhkan arah positif pada masing-masing dan pelaporan interval masing-masing. Bila batas atas interval di bawah +10 poin, efek minimum yang ditargetkan tidak didukung dalam benchmark ini. Kasus lain atau run yang melanggar gerbang ilmiah berstatus inkonklusif. Hasil rekayasa dinilai terpisah.
- **H1, kebaruan semantik:** periksa apakah fungsi yang dihasilkan identik dengan kelas program `L0` dalam batas yang ditentukan. Untuk subdomain kecil, enumerasi lengkap program `L0` dengan semantik dan biaya bersama, serta bandingkan vektor perilaku dengan oracle. Ada saksi kebaruan berbatas hanya jika enumerasi terbukti lengkap dan seluruh padanan ditolak. Bila enumerasi belum lengkap, catat `UNKNOWN`. Bedakan bentuk AST baru, efisiensi representasi, dan perilaku di luar kelas `L0` berbatas. Macro yang hanya menyingkat program ekuivalen dicatat sebagai kompresi.
- **H2, transfer:** kontras primer menguji manfaat pada motif terkait yang baru. Selisih `C_EXTEND − C_NO_TRANSFER` dilaporkan pada motif terkait dan kontrol tidak terkait. Laporkan penurunan absolut dan pasangan tugas yang semula benar lalu gagal. Penerus dengan/tanpa modul diuji pada input baru dengan seed dan anggaran sepadan.
- **H3, sebab:** kontras `C_EXTEND − C_NO_EXTEND` dan `C_EXTEND − C_SHAM` menguji peran representasi dan seleksi. Gunakan seed berpasangan, urutan proposal awal yang sama bila berlaku, plafon sama, dan catat jejak seleksi. Skor primer yang tinggi saja tidak menetapkan sebab, novelty, atau manfaat warisan.

## 6. Anggaran awal dan pencatatan

Usulan engineering untuk pilot, belum diukur: 12 episode development dan 6 episode selection per keluarga. Sketsa konfirmasi untuk perencanaan daya: 16 blok aturan baru × 2 episode per blok per keluarga, dan 3 seed algoritme per episode. Tetapkan ukuran sampel final dari kelayakan CPU dan simulasi daya berbasis development sebelum seal. Bila kuota kurang, tahan konfirmasi dan laporkan hasil pilot sebagai eksploratoris.

Mulai dari 1 CPU-detik, 3 detik wall, dan 128 MiB RSS maksimum untuk worker per kondisi per episode per seed, termasuk fit sumber/target dan inferensi. Dengan 2 keluarga × 32 episode × 3 seed × 9 kondisi, batas solver hipotetisnya 1.728 CPU-detik. Pengukuran benchmark/oracle, scoring bersama dan audit harus dianggarkan terpisah dan dilaporkan juga pada total studi. Tetapkan batas kandidat dan langkah primitive dari profil development, serta jumlah proses dan core yang sama. CPU terhitung sejak inisialisasi per episode termasuk parsing, seleksi, validasi dan operasi struktural. Cache awal antar-arm setara. Ukur CPU/wall aktual, RSS, proposal, evaluasi kandidat dan langkah interpreter, waktu penilai, seed, konfigurasi mesin, hash kode/data, kegagalan dan biaya per tugas lulus. Biaya tambahan Rp0. Gunakan satu mesin CPU dan acak urutan eksekusi kondisi untuk membatasi efek beban mesin.

Timeout atau AST tidak valid bernilai gagal pada target yang terdampak dan tetap masuk denominasi. Gangguan infrastruktur/evaluator mengikuti kebijakan abort/resume yang dikunci dan dilaporkan terpisah. Resume membaca ledger dan hash checkpoint, serta melanjutkan hanya pasangan yang belum terminal dengan kunci idempoten run/kandidat/versi benchmark/seed/split. Tahan konfirmasi jika biaya di luar batas, akuntansi CPU berbeda antarkondisi, atau reproduksi teknis tidak konsisten.

## 7. Gerbang dan tugas Codex berikutnya

| Urutan | Bukti yang diminta | Status |
| --- | --- | --- |
| 1. Bekukan sejarah | Tag E1.2 tetap menunjuk commit sumber dan seluruh berkas manifest lolos | **PASS** |
| 2. Kontrak development | Schema publik, fixture S/G, interpreter terbatas, uji parsing dan pembanding blind minimal | **Belum diimplementasi** |
| 3. Benchmark dan pemisahan | Dua oracle terpisah dari solver, uji akses label, canary ID/metadata, uji tumpang tindih aturan dan contoh, bukti batas jaringan/berkas | **Terbuka** |
| 4. Pilot dan pemilihan | Profil CPU/memori, kontrol lengkap, keputusan B*, parameter sampel, ambang, serta perilaku pada kebocoran atau cap | **Terbuka** |
| 5. Lock dan audit | Git SHA/tag, SHA-256 schema/generator/evaluator/data/solver, seed dan rencana analisis; audit reproduksi teknis terpisah; set konfirmatori disegel di luar checkout kandidat | **Terbuka** |
| 6. Konfirmasi | Satu eksekusi dengan kebijakan beku, tanpa tuning dari hasil, dan laporan inklusif atas semua kegagalan | **Ditahan** |

Unit kerja pertama Codex adalah menulis schema dan interpreter development, satu fixture publik untuk masing-masing keluarga, dan uji negatif yang memastikan label/kunci tidak sampai ke `fit`, input uji tidak dapat mengubah AST, node di luar DSL ditolak, serta konsumsi bahan bakar berhenti pada batas. Simpan desain dan implementasi baru di jalur E1.3. Biarkan set konfirmatori di bawah jalur evaluator dan gunakan data baru untuk konfirmasi lain bila metodologi diubah sesudah melihat hasil.

**Checkpoint sesi:** paket ZIP dan checkout Git identik pada 45 berkas manifest. Pemeriksaan integritas Git lulus. Master Record paket dan Google Drive cocok setelah normalisasi baris kosong/spasi ujung. Tahap ini menghasilkan desain dan petunjuk Codex. Hasil E1.3, data tersegel dan audit eksperimen masih terbuka.
