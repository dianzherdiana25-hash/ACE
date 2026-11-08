# RESEARCH EXECUTION SPECIFICATION (RES)
## ACE — Autonomous Capability Evolution | Generasi Pertama

**Versi:** 0.1  
**Tanggal:** 4 November 2026  
**Status:** Spesifikasi operasional untuk ditinjau; belum dijalankan  
**Dokumen induk:** `PRD_ACE_v0.1` (4 November 2026)  
**Visi induk:** Open-Ended Autonomous Intelligence Evolution (OAIE)  
**Batas awal:** biaya tambahan Rp0; eksperimen digital terisolasi; antarmuka ramah HP  
**Ruang lingkup dokumen:** F0–F5, bukan implementasi, laporan hasil, atau klaim AGI/ASI

---

## 1. Tujuan dan keputusan eksekusi

RES ini menerjemahkan PRD ACE v0.1 menjadi protokol yang dapat dijalankan dan diaudit. Pertanyaan utama (RQ1): **Dengan sumber daya dan kondisi awal yang sebanding, apakah mekanisme evolusi kandidat (C) meningkatkan tingkat keberhasilan pada tugas yang belum dilihat dibanding sistem tetap (A) dan sistem adaptif (B)?** Pertanyaan kedua (RQ2): apakah peningkatan tersebut bertahan pada jenis tugas lain? Pertanyaan ketiga (RQ3): apakah kandidat penerus benar-benar menggunakan kemampuan pendahulunya?

**Keputusan awal:** (i) mulai dari dua keluarga tugas digital yang punya penguji deterministik; (ii) satu mesin eksperimen dan tiga mode A/B/C, bukan tiga produk; (iii) CPU-first, checkpoint dan log wajib; (iv) perbandingan dibatasi anggaran; (v) pengujian tersegel (*held-out*) hanya dilakukan setelah kandidat dibekukan. Open-weight maupun API model hanya digunakan bila jalur akses yang sah dan gratis terverifikasi pada F0. Tidak ada asumsi bahwa langganan aplikasi otomatis memberi kuota API.

**Dua kategori keberhasilan yang harus dipisahkan:** penerimaan rekayasa berarti perangkat eksperimen berjalan; dukungan hipotesis ilmiah berarti terdapat peningkatan empiris yang sesuai protokol. Kelulusan kategori pertama **bukan** bukti kategori kedua.

## 2. Lingkungan dan unit eksperimen

**Unit analisis utama:** satu *run* beridentitas unik = mode (A/B/C) × keluarga tugas × seed × konfigurasi model/alat. Setiap *run* dapat memiliki beberapa kandidat, evaluasi pembangunan (*development*), dan satu evaluasi *held-out* final. Semua percobaan dan kegagalan disimpan; *best-of-N* tanpa menyertakan biaya/percobaan lain tidak boleh dilaporkan sebagai hasil tunggal.

**Keluarga S — Transformasi simbolik:** persoalan manipulasi urutan/token/teks dengan fungsi referensi deterministik (misalnya segmentasi token dengan aturan eksplisit, transformasi urutan berbatas, dan komposisi operasi). Target utamanya adalah menghasilkan metode/pemecah masalah untuk aturan yang diberikan. Variasi *held-out* harus berasal dari **template aturan yang tidak dipakai selama pengembangan**, bukan hanya contoh acak dengan aturan yang sama.

**Keluarga G — Penalaran graf/grid:** persoalan graf dan perencanaan lintasan pada peta diskrit kecil, dengan kondisi tujuan, bobot, atau batasan yang eksplisit. Penguji menggunakan solver referensi deterministik yang tervalidasi. Variasi *held-out* menggunakan komposisi kendala/topologi baru; keluarga ini tidak boleh disamakan dengan bukti kemampuan robotika fisik.

**Persyaratan tugas:** spesifikasi tertulis, input terstruktur, solusi referensi atau pemeriksa benar/salah, penanganan kasus batas, batas waktu, dan lisensi/asal data. Penilaian tidak bergantung pada penilaian subjektif LLM. Tugas yang ambigu atau referensinya gagal wajib dikeluarkan sebelum eksperimen dan dicatat dengan alasannya.

**Pembagian per keluarga (target pilot):** 12 tugas pembangunan, 6 tugas validasi internal, dan 30 tugas *held-out*; masing-masing minimal 3 seed independen per kondisi bila kuota mencukupi. Total 48 ID tugas unik per keluarga, atau 96 untuk dua keluarga; bank *held-out* dapat dipakai berpasangan oleh A/B/C tetapi tidak untuk memilih kandidat. Jumlah ini adalah **target pilot awal**, bukan pembuktian dengan daya statistik yang dijamin memadai. Jika kuota tidak mencukupi, jalankan mode *smoke/exploratory* yang lebih kecil dengan label **belum konklusif**, bukan menurunkan ambang diam-diam.

## 3. Kontrak ketiga kondisi A/B/C

| Aspek | A — Fixed | B — Adaptive | C — Evolutionary |
|---|---|---|---|
| Model dan pengetahuan awal | Sama | Sama | Sama |
| Alat bawaan | Sama | Sama | Sama |
| Pembaruan saat eksperimen | Tidak ada; metode dikunci | Strategi/prompt/urutan alat; tidak membuat penerus | Dapat membuat/mengubah kode, metode, representasi, atau kandidat penerus |
| Memori | Catatan untuk evaluasi saja | Catatan strategi yang terpilih | Memori dan silsilah kandidat |
| Seleksi | Tidak ada | Memilih strategi berdasarkan validasi pembangunan | Memilih/menyimpan beberapa cabang kandidat berdasarkan validasi pembangunan |
| Akses *held-out* selama pengembangan | Tidak | Tidak | Tidak |
| Jejak percobaan | Wajib | Wajib | Wajib, plus induk/anak dan perubahan |

**Kontrol yang dikunci sebelum run:** versi model awal, prompt dasar (jika ada), daftar alat, format tugas, kode evaluator, input generasi tugas, seed, limit eksperimen, dan kebijakan gagal/berhenti. B dan C memperoleh plafon **kesempatan proposal dan evaluasi pengembangan yang sama**; A adalah baseline tetap sehingga pemakaian aktual dapat lebih rendah. Laporkan **dua perbandingan**: keberhasilan dengan plafon anggaran yang sama, serta biaya aktual per tugas berhasil. Jangan menyebut A/B/C setara dalam komputasi aktual jika faktanya berbeda.

**Kuota kandidat pilot yang diusulkan:** maksimal 12 proposal perubahan per *run* untuk B dan C, maksimal 3 putaran seleksi, dan maksimal 1 panggilan *held-out* per kandidat final yang dibekukan. Angka disesuaikan hanya di F0 **sebelum** hasil uji dibandingkan. Jika memakai API, tetapkan plafon panggilan/token untuk masing-masing kondisi, bukan mengandalkan paket berbayar. Jika tidak tersedia agen/model yang sah, hanya boleh dilakukan *dry-run* deterministik untuk menguji infrastruktur; jangan menyebutnya bukti self-improving AI.

## 4. Protokol eksekusi satu run

1. **Prepare:** verifikasi `study_id`, `run_id`, hash konfigurasi, versi benchmark, seed, ketersediaan runner, izin, dan anggaran tersisa.
2. **Baseline snapshot:** simpan kondisi awal, artefak solver, serta hash evaluator. Putuskan pemisahan data sebelum kandidat dibuat.
3. **Develop:** A langsung memakai metode tetap; B mengusulkan perbaikan strategi; C mengusulkan kandidat dengan `parent_id`, hipotesis, perubahan, dan domain tujuan. Setiap usulan memiliki identitas unik.
4. **Validate:** jalankan kandidat dalam sandbox pada tugas pembangunan/validasi internal. Tolak perubahan yang tidak lolos pemeriksaan dasar, melebihi resource, atau mencoba membaca penguji tersegel.
5. **Select & freeze:** pilih kandidat berdasarkan aturan seleksi yang ditetapkan sebelum run; simpan juga semua kandidat gagal. Bekukan artefak final dan hash-nya. Kandidat tidak boleh diedit setelah pembekuan.
6. **Evaluate:** evaluasi sekali pada kumpulan *held-out* per *run*; keluaran penguji tidak boleh dipakai memperbaiki kandidat yang sama. Untuk percobaan berikutnya, gunakan kumpulan baru jika ada perubahan berdasarkan hasil *held-out*.
7. **Analyze:** hitung metrik, biaya, interval ketidakpastian, regresi, dan lineage; buat ringkasan bahasa Indonesia untuk pembaca nonteknis.
8. **Commit checkpoint:** tulis status atomik `COMPLETED`, `FAILED`, `STOPPED`, atau `INCONCLUSIVE` beserta alasan; pencatatan hasil tidak boleh menghapus sejarah.

**Aturan pembukaan *held-out*:** runner evaluasi membaca paket tugas tersegel setelah kandidat dibekukan; agen pembuat kandidat tidak memperoleh isi paket, kunci pembuka, source penguji, atau hasil per-item sampai run selesai. Pemisahan ini adalah integritas evaluasi otomatis, bukan kewajiban pemeriksa manusia atau pihak eksternal.

## 5. Protokol transfer dan pewarisan

**Near transfer:** perubahan yang ditemukan pada subset aturan S atau G meningkatkan performa pada template aturan baru **dalam keluarga yang sama**. Ini mengukur generalisasi terbatas.

**Far transfer (eksploratoris):** sistem berkembang pada keluarga S tanpa melihat tugas G, lalu kandidat final diuji pada G dan dibandingkan dengan snapshot awal; jika ada peningkatan, ulang arah G→S dengan protokol sama. Hasil di kedua keluarga dalam eksperimen yang terpisah **tidak otomatis** membuktikan transfer antar-keluarga.

**Inheritance test:** kandidat generasi `g+1` menerima artefak kemampuan dari `g` (misalnya modul, prosedur, atau representasi yang disimpan). Bandingkan (i) penerus dengan warisan dan (ii) penerus tanpa warisan dengan anggaran sama. Catat apakah performa warisan bertahan pada tugas baru; minimal dua generasi perubahan dan dua cabang kandidat dibutuhkan untuk menguji mekanisme lineage, bukan untuk membuktikan evolusi kecerdasan umum.

**Klasifikasi penemuan:** `NEW_TO_SYSTEM` (baru bagi agen), `NEW_METHOD` (metode/algoritma berbeda dan bermanfaat pada tugas yang diuji), `TRANSFERRED` (perbaikan terbukti pada tugas belum dilihat), atau `SCIENTIFIC_NOVELTY_UNVERIFIED` (kebaruan bagi literatur dunia belum dibuktikan). Hindari istilah “penemuan ilmiah baru” bila hanya menemukan ulang metode yang sudah diketahui.

## 6. Metrik dan aturan pengambilan keputusan

| Kode | Metrik | Definisi dan interpretasi |
|---|---|---|
| M1 (primer) | Held-out success | Jumlah tugas *held-out* lulus / jumlah tugas *held-out* valid, per keluarga dan kondisi. |
| M2 | Matched uplift | Selisih persentase poin C−B dan C−A pada tugas/seed yang dipasangkan. |
| M3 | Near/far transfer | Kenaikan pada aturan baru dan pada keluarga yang tidak dilihat sewaktu evolusi; laporkan terpisah. |
| M4 | Cost efficiency | CPU-detik, evaluasi kandidat, token/panggilan model, dan biaya tambahan aktual per tugas lulus. |
| M5 | Regression rate | Proporsi tugas yang tadinya lulus tetapi gagal setelah perubahan. |
| M6 | Inheritance gain | Selisih sukses penerus dengan warisan vs penerus tanpa warisan pada anggaran sama. |
| M7 | Recoverability | Run yang dapat dilanjutkan dengan hasil konsisten / percobaan pemulihan. |
| M8 | Evidence completeness | Persentase run dengan konfigurasi, seed, hash, hasil, biaya, dan status lengkap. |

**Analisis wajib:** tampilkan ukuran sampel dan hasil per seed, bukan hanya rata-rata. Gunakan interval kepercayaan/ketidakpastian yang memperhitungkan ketergantungan tugas dan seed (misalnya *hierarchical paired bootstrap* jika ukuran sampel memadai); sertakan hasil mentah dan interval, bukan hanya label berhasil/gagal. Semua run yang valid dilaporkan, termasuk kegagalan atau biaya tinggi.

**Aturan interpretasi pilot (ditetapkan sebagai target, bukan fakta):** sinyal eksploratoris tercatat bila C lebih baik dari A dan B setidaknya **10 poin persentase** pada M1 untuk kedua keluarga, tanpa regresi besar yang tidak dijelaskan, serta ada bukti lineage. Klaim dukungan ilmiah lebih kuat membutuhkan replikasi tambahan, pengujian generalisasi yang disegel, pengendalian sumber daya, dan ketidakpastian yang cukup kecil; satu pilot 30 tugas/keluarga umumnya tidak cukup untuk klaim kuat. Jika perbedaan tidak jelas atau kuota tidak cukup, hasil **INCONCLUSIVE**. Jika C konsisten kalah, laporkan **NOT_SUPPORTED_IN_THIS_TEST**, bukan menyatakan semua pendekatan evolusi gagal.

**Kewajiban pelaporan:** dua baris kesimpulan terpisah: `ENGINEERING_GATE = PASS/FAIL` dan `RESEARCH_HYPOTHESIS = PRELIMINARY_SUPPORT / NOT_SUPPORTED_IN_THIS_TEST / INCONCLUSIVE`. AGI, ASI, RSI tanpa batas, dan peningkatan kecerdasan umum tidak boleh diklaim dari pilot ini.

## 7. Batas biaya, waktu, dan sandbox

**Kebijakan biaya:** biaya tambahan maksimal **Rp0**. Paket aplikasi yang sudah dimiliki hanya dipakai pada hak akses normal. Akses API berbayar tidak digunakan. Sebelum setiap run, pemeriksaan biaya menentukan `ALLOW` hanya bila perkiraan biaya tambahan nol; kuota gratis yang tidak dapat dipastikan berarti `HOLD`. Tidak melakukan pembelian otomatis, upgrade, transfer dana, atau pembuatan akun berbayar.

**Tata kelola komputasi:** preferensi CPU lokal/komputasi gratis. Batas awal *per run* yang **harus ditetapkan ulang saat F0**: maksimum 30 menit *wall-clock* untuk percobaan pilot, maksimum 12 proposal B/C, batas proses/CPU/memori sesuai lingkungan, dan penyimpanan log terkontrol. Ini plafon desain usulan, bukan janji layanan gratis mampu menyediakannya. Stop ketika kuota habis, cap tercapai, evaluator gagal, atau penyimpanan tidak dapat ditulis.

**Isolasi minimum sebelum menjalankan kode kandidat:** lingkungan sementara tanpa token akun, tanpa akses repository produksi atau berkas pribadi, jaringan keluar diblokir kecuali titik yang disetujui, file system kerja terpisah, CPU/memori/proses/waktu dibatasi, dan artefak dibekukan sebelum diekspor. Notebook Colab biasa atau GitHub Actions **tidak otomatis memenuhi** standar sandbox untuk kode tak tepercaya. Bila isolasi kuat tidak tersedia, tidak boleh menjalankan kode kandidat yang bebas mengubah dirinya; gunakan algoritma yang terbatas atau *dry-run*.

**Batas tindakan:** eksperimen fisik, akun eksternal, publikasi otomatis, perubahan repositori utama, dan tindakan finansial di luar v0.1; memerlukan keputusan dan kontrol terpisah. Otonomi eksperimen digital tidak berarti kewenangan tanpa batas di dunia nyata.

## 8. Format data dan kontrak artefak

**Struktur direktori yang disarankan (contoh, belum dibuat):**

```text
ace-study/
  study.yaml                 # hipotesis, rencana, kuota, versi protokol
  benchmarks/                # definisi tugas, generator, reference solvers
  evaluator/                 # kode penguji berversi, akses dibatasi
  runs/<run_id>/
    config.snapshot.json     # mode, seed, parameter, hash
    events.jsonl             # append-only event ledger
    candidates/              # perubahan, induk/anak, artefak, hash
    metrics.json             # per-keluarga, per-seed, biaya
    checkpoint.json          # state dan posisi resume
    summary.id.md            # ringkasan nonteknis
  reports/                   # perbandingan A/B/C dan status bukti
```

**Field wajib pada setiap event JSONL:** `timestamp_utc`, `study_id`, `run_id`, `event_id`, `mode`, `seed`, `phase`, `candidate_id`, `parent_id` (jika relevan), `action`, `outcome`, `artifact_sha256` (jika ada), `evaluator_version`, `cpu_seconds`, `model_calls`, `input_tokens`, `output_tokens`, `additional_cost_idr`, `error_code` (jika ada). Jangan masukkan token API, kata sandi, atau data pribadi dalam log.

**Status run yang valid:** `PENDING`, `RUNNING`, `CHECKPOINTED`, `COMPLETED`, `FAILED`, `STOPPED`, `INCONCLUSIVE`. Transisi ke `COMPLETED` hanya boleh setelah semua artefak dan evaluator selesai diverifikasi secara struktural. Setiap artefak menggunakan SHA-256; ID tugas dan versi benchmark tercatat sebelum mulai. Evaluasi bersifat *idempotent* menurut `run_id + candidate_sha256 + benchmark_version + seed + split`.

**Ledger dan pemulihan:** tulis event secara *append-only*; checkpoint dibuat melalui *atomic rename*; setelah restart sistem membaca event terakhir yang valid, memverifikasi hash, lalu melanjutkan pekerjaan yang belum berstatus terminal. Jika tidak dapat memastikan apakah pekerjaan sudah selesai, jangan memproses ulang efek samping tanpa pemeriksaan idempotensi. Bukti lama tidak boleh ditulis ulang untuk membuat hasil terlihat lebih baik.

## 9. Gerbang eksekusi F0–F5

| Fase | Pekerjaan konkret | Artefak minimal | Keputusan lanjut |
|---|---|---|---|
| F0 — Feasibility | Audit akses nyata, izin model/API, CPU, sandbox, kuota, dan batas Rp0; tetapkan parameter pilot final. | `feasibility.md`, daftar jalur sah, konfigurasi terkunci, risk register. | GO jika ada jalur menjalankan kandidat secara sah dan aman tanpa biaya baru; jika tidak, HOLD/ubah menjadi *infrastructure-only dry-run*. |
| F1 — Fixed baseline | Bangun bank tugas dan solver referensi; jalankan A dan ulangi pada seed yang sama. | Manifes benchmark, hasil A, hash evaluator, log & seed. | GO jika evaluator benar dan run dapat direproduksi; tidak ada kebocoran held-out. |
| F2 — Adaptation | Jalankan B dengan maksimum proposal yang sama seperti C; catat semua perubahan dan biaya. | Strategi versi B, perbandingan dev/validasi, event ledger. | GO jika ada perubahan yang jelas, dapat ditelusuri, dan rollback berfungsi. |
| F3 — Evolution | Jalankan C; buat minimum 2 generasi dan 2 cabang kandidat, simpan lineage; uji warisan. | Kandidat berversi, silsilah, diff dan log, rollback. | GO jika kandidat diuji di sandbox, keterkaitan induk/anak terverifikasi. |
| F4 — Generalization | Bekukan kandidat, jalankan held-out S/G untuk A/B/C dengan seed sepadan, lakukan analisis. | Metrik M1–M8, interval, data mentah, laporan bias/biaya. | GO jika pengukuran lengkap dan interpretasi tidak melebihi bukti. |
| F5 — Research decision | Bandingkan bukti dengan RQ1–RQ3, hasil negatif dan risiko; putuskan riset berikutnya. | Laporan keputusan ilmiah dan rekomendasi eksperimen lanjut. | `PRELIMINARY_SUPPORT`, `NOT_SUPPORTED_IN_THIS_TEST`, atau `INCONCLUSIVE`; bukan otomatis lanjut scaling. |

**Acceptance v0.1:** FR P0 PRD tertaut pada artefak dan uji nyata; satu skenario putus–lanjut diuji; satu skenario kuota habis berhenti tanpa biaya; evaluator tidak menerima kebocoran data; perbandingan A/B/C dan keterbatasannya terlihat dalam ringkasan HP. Sebelum eksekusi nyata, semua gerbang berstatus `NOT_RUN`.

## 10. Validasi dan skenario negatif minimum

| ID | Skenario uji | Hasil yang diwajibkan |
|---|---|---|
| T-01 | Kandidat mencoba membaca paket held-out sebelum freeze | Akses ditolak dan dicatat. |
| T-02 | Proses dihentikan di tengah evaluasi | Resume tanpa menggandakan hasil yang sudah terminal. |
| T-03 | Kuota gratis tidak tersedia atau status biaya tidak jelas | Eksekusi ditahan; pengeluaran tambahan tetap Rp0. |
| T-04 | Kandidat menghasilkan kode dengan akses jaringan/file pribadi | Ditolak sandbox; tidak dijalankan di host produksi. |
| T-05 | Kandidat memperbaiki skor development tetapi memburuk di held-out | Dicatat sebagai overfit/regresi; tidak diklaim kemajuan umum. |
| T-06 | Kandidat penerus kehilangan kemampuan lama | Regresi dan jalur rollback tercatat; klaim inheritance ditolak. |
| T-07 | Referensi tugas memberi hasil ambigu/salah | Tugas dikarantina sebelum hasil dipakai untuk kesimpulan. |
| T-08 | C butuh komputasi jauh lebih besar daripada A/B | Biaya aktual dilaporkan; klaim unggul pada anggaran setara ditahan. |
| T-09 | Artefak atau hash tidak cocok saat recovery | Run ditandai gagal integritas, tidak diperbaiki dengan merekonstruksi bukti lama. |
| T-10 | Tidak ada model otomatis yang sah pada akses gratis | Hanya uji infrastruktur; **bukan** verifikasi AI evolusioner. |

## 11. Matriks ketertelusuran PRD → RES

| Persyaratan PRD | Bagian RES / bukti yang dituju |
|---|---|
| FR-01, FR-02 | §1–3, config terkunci dan kontrak A/B/C |
| FR-03, FR-13 | §4–5, candidate lineage dan inheritance test |
| FR-04, FR-08, FR-10 | §7, sandbox, batas Rp0, penghentian dan rollback |
| FR-05 | §2, §4, §6, pemisahan development/validation/held-out |
| FR-06, FR-07 | §8, ledger, hash, checkpoint, resume idempotent |
| FR-09, FR-14 | §6, §8–9, ringkasan hasil HP dan metrik |
| FR-11, FR-12, FR-15 | §3, §5, §9, cabang kandidat, adaptor model, riset berikutnya |
| NFR-01 sampai NFR-08 | §6–10, reproduksi, resiliensi, integritas, biaya, izin, ekspor |

## 12. Ketergantungan, ketidakpastian, dan asumsi yang harus diuji F0

- Tidak ada klaim bahwa akun ChatGPT Plus, Gemini, atau Claude saat ini terhubung secara otomatis ke runner penelitian. Akses dan ketentuan masing-masing perlu dicek saat F0.
- Tidak ada asumsi bahwa Google Colab atau GitHub Actions merupakan sandbox yang aman untuk eksekusi kode agen tak tepercaya atau layanan 24/7.
- Jika eksperimen menggunakan hanya evolusi algoritma lokal tanpa agen penalaran, hasilnya menguji mekanisme eksperimen/evolusi kode, **bukan** kecerdasan otonom generasi baru.
- Satuan “generasi penerus” pada v0.1 berarti varian prosedur/kode/agen dengan lineage, **bukan** model fondasi baru yang dilatih dari nol.
- Parameter 12/6/30 tugas, 3 seed, 12 proposal dan 30 menit/run adalah rancangan pilot yang harus dikunci setelah uji F0; belum ada bukti bahwa semua dapat dijalankan dengan sumber daya pengguna saat ini.
- Penelitian ini belum menguji penemuan ilmiah dunia fisik, recursive self-improvement tanpa batas, atau kemampuan AI mencapai semua tujuan.

## 13. Status, keluaran, dan langkah pertama setelah spesifikasi

**Selesai pada tahap dokumentasi:** protokol eksperimen awal, keluarga tugas, perbandingan A/B/C, cara mengukur keberhasilan, format log, kriteria berhenti, recovery, serta gerbang penelitian ditentukan secara konseptual.

**Belum dilakukan:** verifikasi layanan aktual milik pengguna, implementasi kode, pembuatan benchmark, pembukaan akun/API, eksekusi kandidat, benchmark held-out, atau klaim peningkatan kecerdasan. Seluruh fase F0–F5 **NOT_RUN**.

**Aksi pertama saat implementasi secara terpisah diotorisasi:** F0, yaitu menguji apakah terdapat satu jalur eksperimen CPU/model yang legal, cukup terisolasi, dan biaya tambahan Rp0; dokumentasikan batas riil sebelum menetapkan framework dan menjalankan kandidat.

---

*Dokumen turunan PRD ACE v0.1. Jika ada pertentangan, PRD adalah acuan cakupan; perubahan angka dan protokol eksperimen wajib dibekukan sebagai versi RES baru sebelum melihat hasil held-out.*
