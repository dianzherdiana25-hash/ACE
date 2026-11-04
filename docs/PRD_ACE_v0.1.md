# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Autonomous Capability Evolution (ACE) — Generasi Pertama

**Versi:** 0.1 · **Tanggal:** 4 November 2026 · **Status:** Draft fondasi penelitian; belum diimplementasikan atau divalidasi secara empiris  
**Visi induk:** Open-Ended Autonomous Intelligence Evolution (OAIE)  
**Pengguna utama:** Penggagas/peneliti individu tanpa keahlian teknis AI mendalam, dengan akses utama melalui HP  
**Batas biaya tambahan awal:** Rp0, menggunakan hanya akses dan kuota yang sah serta tersedia

### 1. Ringkasan eksekutif

ACE adalah *research workbench* yang meneliti apakah sistem AI dapat (a) mengenali kesenjangan kemampuannya, (b) menghasilkan atau menemukan metode yang menutup kesenjangan itu, (c) memindahkan perbaikan ke persoalan baru, dan (d) mewariskan kemampuan yang bermanfaat ke kandidat penerus. Visi panjangnya adalah kecerdasan yang mampu mengeksplorasi disiplin ilmiah, mengembangkan model atau paradigma baru, serta berinteraksi dengan dunia fisik. **ACE v0.1 bukan AGI, ASI, maupun bukti recursive self-improvement tanpa batas.**

Sistem pertama harus sederhana, modular, terukur, bisa dipulihkan, dan tidak bergantung permanen pada LLM tertentu. Produk ditujukan agar pemilik yang bukan ahli AI dapat menetapkan tujuan penelitian dan memahami hasil secara jujur tanpa mengaudit kode satu per satu. Pengujian digital dilakukan otomatis dalam batas sumber daya yang ditentukan; validasi eksternal bukan syarat operasional v0.1.

### 2. Masalah dan peluang

- Penelitian kemampuan AI kini sering mengukur keberhasilan pada tugas tertentu, tetapi perbaikan suatu agen belum tentu menghasilkan generalisasi lintas tugas.
- Sistem yang mengubah dirinya dapat membuat banyak varian tanpa menunjukkan penambahan kemampuan yang bermakna; seleksi dapat terdistorsi oleh kebocoran data pengujian dan *reward hacking*.
- Peneliti individu memiliki model melalui aplikasi dan layanan gratis, namun akses otomatis, komputasi, dan keberlangsungan eksekusi tidak terjamin.
- Pengguna nonteknis membutuhkan keluaran yang membedakan secara eksplisit antara klaim, bukti eksperimen, hasil belum pasti, dan kegagalan.

**Peluang ilmiah:** menguji manfaat bersih mekanisme *capability invention* dan pewarisan kemampuan dalam kondisi sumber daya sebanding, bukan sekadar membuktikan AI mampu menghasilkan kode baru.

### 3. Tujuan dan ukuran kesuksesan

**G1 — Operasional:** menjalankan satu eksperimen digital dari tugas sampai laporan dengan catatan lengkap dan kemampuan melanjutkan setelah terputus.

**G2 — Ilmiah:** membandingkan tiga kondisi A/B/C secara adil pada tugas yang tidak digunakan selama evolusi.

**G3 — Generalisasi:** menguji apakah perbaikan berpindah ke sedikitnya dua keluarga masalah yang berbeda; perbaikan di satu keluarga saja dicatat sebagai spesialisasi.

**G4 — Evolusi:** menyimpan silsilah varian dan membuktikan bahwa varian penerus dapat menggunakan kemampuan yang ditemukan pendahulunya.

**G5 — Aksesibilitas:** pemilik dapat membaca ringkasan hasil dan keputusan penelitian melalui HP, tanpa kewajiban meninjau implementasi teknis.

**Dua jenis gerbang keberhasilan:** (i) *engineering acceptance*, yaitu sistem bekerja sesuai spesifikasi; dan (ii) *research evidence*, yaitu hipotesis peningkatan kemampuan benar-benar mendapat dukungan data. Gerbang pertama **tidak** otomatis meluluskan gerbang kedua.

### 4. Lingkup v0.1 dan yang tidak termasuk

**Termasuk:** penelitian digital, eksperimen algoritma kecil pada CPU, opsi lingkungan MiniGrid ringan, pembangkitan kandidat kode/alat/strategi, pengujian otomatis, rekam hasil, checkpoint, pembatasan anggaran, antarmuka laporan ramah HP, dan abstraksi penggantian model.

**Tidak termasuk v0.1:** melatih model fondasi besar dari nol; klaim AI sudah lebih cerdas secara umum; agen berjalan 24/7 tanpa infrastruktur; eksperimen robot/laboratorium fisik; memperoleh dana, membeli API/komputasi, atau menggunakan akun pihak lain tanpa izin; perubahan kode produksi, repositori Tod, atau akun pengguna lainnya; kemampuan mengubah mekanisme pembatasan keamanan atau hasil pengujian historis.

**Arah riset kemudian, bukan janji produk:** evolusi bobot model, pencarian arsitektur yang lebih luas, paradigma pasca-LLM, penelitian ilmiah lintas domain, dan eksperimen fisik dengan otorisasi serta sarana yang sesuai.

### 5. Persona dan pengalaman pengguna

**Pemilik penelitian:** menetapkan misi tingkat tinggi, anggaran biaya tambahan, batas waktu/komputasi, dan tindakan apa yang diizinkan. Mengakses ringkasan dari HP.

**Research operator AI:** merumuskan hipotesis, membuat kandidat, menjalankan percobaan yang diizinkan, dan melaporkan hasil, termasuk ketika eksperimen gagal atau belum konklusif.

**Alur utama:** pilih pertanyaan → pilih tugas/benchmark → jalankan baseline A → jalankan kondisi B dan C dengan sumber daya sebanding → ukur tugas *held-out* → simpan bukti dan silsilah kandidat → tampilkan kesimpulan serta ketidakpastian → tentukan eksperimen selanjutnya.

### 6. Persyaratan fungsional (prioritas P0 = wajib untuk prototipe)

| ID | Prioritas | Persyaratan dan bukti penerimaan |
|---|---|---|
| FR-01 | P0 | Mendaftarkan pertanyaan riset, hipotesis, kumpulan tugas, dan parameter percobaan dalam konfigurasi berversi. |
| FR-02 | P0 | Memiliki mode A (*fixed baseline*), B (*adaptive strategy/tool*), dan C (*evolving candidates*), dengan model awal dan anggaran setara. |
| FR-03 | P0 | Mencatat setiap usulan perbaikan: kesenjangan yang dituju, alasan, perubahan, induk kandidat, dan hipotesis dampaknya. |
| FR-04 | P0 | Mengeksekusi kode kandidat pada lingkungan terisolasi dengan batas waktu, memori, CPU, izin jaringan, dan tanpa kredensial produksi. |
| FR-05 | P0 | Melakukan pengujian otomatis terhadap tugas pembangunan dan tugas *held-out* yang terpisah; kandidat tidak boleh mengubah penguji *held-out* selama satu eksperimen. |
| FR-06 | P0 | Menyimpan *run ID*, versi kode, *hash* artefak, *seed*, penggunaan komputasi, keluaran tes, dan penyebab kegagalan. |
| FR-07 | P0 | Mendukung checkpoint dan melanjutkan pekerjaan terputus tanpa menggandakan eksperimen yang sudah selesai. |
| FR-08 | P0 | Menegakkan batas biaya tambahan Rp0: jangan memulai API berbayar, pembelian, atau peningkatan paket otomatis. |
| FR-09 | P0 | Menghasilkan ringkasan bahasa Indonesia: apa yang dicoba, apa hasilnya, tingkat keyakinan, dan batas interpretasi. |
| FR-10 | P0 | Menyediakan penghentian eksekusi, pembatasan percobaan, dan pemulihan versi stabil ketika kandidat gagal. |
| FR-11 | P1 | Mempertahankan arsip beberapa cabang kandidat, alih-alih hanya kandidat terbaik tunggal. |
| FR-12 | P1 | Mendukung penggantian model melalui antarmuka adaptor; layanan tanpa API dipakai manual sebagai penasihat, bukan integrasi tersembunyi. |
| FR-13 | P1 | Memindahkan pengetahuan/prosedur dari kandidat induk ke kandidat penerus dan menguji apakah manfaatnya bertahan. |
| FR-14 | P1 | Menyajikan perbandingan metrik antarkondisi, status sumber daya, dan riwayat evolusi pada layar HP. |
| FR-15 | P2 | Mengusulkan eksperimen baru berdasarkan hasil sebelumnya dan prioritas riset, tetap dalam kuota dan ruang lingkup yang diizinkan. |

### 7. Arsitektur logis awal (bukan keputusan framework permanen)

1. **Research orchestrator:** mendefinisikan pekerjaan, memilih tugas, dan mengelola antrian.
2. **Capability-gap analyzer:** mengategorikan kegagalan sebagai kekurangan informasi, alat, metode, atau kendala sumber daya.
3. **Candidate evolution module:** membuat varian strategi, alat, algoritma, atau agen; menyimpan garis keturunannya.
4. **Sandboxed experiment runner:** mengeksekusi kandidat terisolasi dan membatasi pemakaian sumber daya.
5. **Evaluation harness:** menjaga pembagian data, membandingkan A/B/C, dan menghitung metrik yang telah ditentukan sebelum eksperimen.
6. **Research ledger dan memory:** menyimpan log, hipotesis, bukti, ringkasan pelajaran, serta versi kandidat yang dapat dipulihkan.
7. **Model/provider adapters:** menggunakan model tersedia jika akses otomatisnya sah; dapat diganti tanpa mengubah data penelitian.
8. **Human-facing interface:** melaporkan keputusan, hasil, dan ketidakpastian dalam bahasa biasa melalui HP.

Pembagian ini bersifat fungsional. Satu komponen tidak wajib berarti satu agen atau satu layanan terpisah.

### 8. Protokol eksperimen pertama

**Pertanyaan utama (RQ1):** dalam anggaran sumber daya sebanding, apakah sistem C mampu meningkatkan keberhasilan *held-out* dibanding A dan B?

**RQ2:** apakah peningkatan sistem C bisa dipindahkan ke keluarga masalah lain, bukan hanya variasi tugas asal?

**RQ3:** apakah kandidat penerus mempertahankan atau mengembangkan perbaikan yang dihasilkan kandidat sebelumnya?

**Kelompok pembanding:**
- **A — Fixed:** model dan alat dasar tetap, tanpa mekanisme perbaikan antarsiklus.
- **B — Adaptive:** boleh mengubah strategi, prompt, atau pilihan alat, tetapi tidak menciptakan arsitektur penerus.
- **C — Evolutionary:** boleh menciptakan alat/metode/kandidat penerus dan menyimpan beberapa cabang evolusi.

**Domain awal:** (1) tugas pemrograman/transformasi algoritma dengan penguji deterministik; (2) keluarga tugas berbeda seperti perencanaan dalam MiniGrid. Pilihan kedua dapat menjadi tahap lanjutan jika tidak sesuai anggaran CPU awal. Untuk setiap keluarga tugas, pisahkan data pengembangan, validasi, dan *held-out* pada level generator/aturan bila memungkinkan, bukan hanya pada contoh acak.

**Kontrol adil:** kondisi A, B, C memakai model awal, akses alat, batas waktu, total token/API, CPU-menit, kesempatan percobaan, dan versi penguji yang setara. Jalankan beberapa *seed*; simpan seluruh kegagalan, bukan hanya percobaan terbaik. *Held-out* tidak dipakai memilih kandidat. Kandidat tidak diberi akses untuk mengedit hasil historis, batas anggaran, atau penguji tertutup dalam eksperimen aktif.

**Ukuran utama:** tingkat penyelesaian pada tugas *held-out* per keluarga. **Ukuran pendukung:** luas transfer lintas keluarga, biaya per tugas berhasil, jumlah percobaan, penggunaan CPU/token, tingkat regresi kemampuan, persentase run dapat dipulihkan, dan keberhasilan pewarisan varian.

**Ambang pilot yang diusulkan (target desain, bukan standar ilmiah universal):** minimal 30 tugas *held-out* per keluarga dan sedikitnya tiga pengulangan per kondisi bila kuota cukup. Perbedaan >=10 poin persentase pada metrik utama boleh menjadi sinyal eksplorasi, tetapi kesimpulan peningkatan yang kuat tetap memerlukan estimasi ketidakpastian, perbandingan berpasangan, dan pengulangan lebih luas. Jika sampel atau kuota tidak cukup, keluaran wajib berstatus **inkonklusif**, bukan “berhasil”.

**Interpretasi:** hasil C unggul pada keluarga asal saja = *task specialization*; unggul pada tugas *held-out* sejenis = peningkatan generalisasi terbatas; unggul lintas keluarga = sinyal transfer, tetapi **bukan** bukti AGI/ASI. Varian yang hanya menambah komputasi atau jumlah alat tanpa peningkatan terkontrol tidak boleh dipromosikan sebagai “kecerdasan baru”.

### 9. Nonfungsional, keamanan, dan batas otonomi

- **NFR-01 Reproducibility:** setiap run bisa ditelusuri dari konfigurasi, *seed*, versi penguji, dan *hash* artefak.
- **NFR-02 Resilience:** gangguan komputasi tidak menghapus catatan; run yang belum selesai dapat dilanjutkan atau ditandai gagal dengan jelas.
- **NFR-03 Cost safety:** biaya tambahan awal Rp0; saat kuota gratis habis, sistem berhenti atau beralih ke opsi gratis yang sah, tidak membeli otomatis.
- **NFR-04 Isolation:** kode buatan agen tidak berjalan dengan token rahasia, izin mengubah akun, atau akses tak terbatas ke jaringan/sistem berkas.
- **NFR-05 Evidence integrity:** agen kandidat tidak boleh secara sepihak menghapus log, mengubah ukuran keberhasilan yang telah dikunci, atau menyunting hasil lama. Ini mekanisme integritas otomatis, **bukan syarat peninjau eksternal**.
- **NFR-06 Human comprehension:** laporan ringkas harus menguraikan metrik, sampel, ketidakpastian, dan status “terbukti pada pengujian / belum terbukti / gagal”.
- **NFR-07 Interoperability:** data penelitian dan riwayat evolusi tetap bisa diekspor tanpa bergantung pada satu penyedia model.
- **NFR-08 Authorized actions:** otonomi luas berlaku dalam eksperimen digital terisolasi; tindakan finansial, publikasi, penggunaan akun, dan eksperimen fisik membutuhkan izin terpisah.

### 10. Sumber daya, kelayakan biaya Rp0, dan ketergantungan

| Sumber | Penggunaan yang realistis | Batas penting |
|---|---|---|
| ChatGPT Plus | Diskusi, sintesis, bantuan merancang dan membaca hasil penelitian | Langganan ChatGPT dan biaya OpenAI API terpisah. |
| Gemini | Dukungan riset; kemungkinan API tingkat gratis bila memenuhi syarat | Limit berbeda per model/proyek dan dapat berubah; verifikasi kuota aktif. |
| Claude | Perbandingan ide, kritik hipotesis, analisis hasil | Akses aplikasi tidak otomatis memberikan kuota API. |
| Google Colab gratis | Notebook eksperimen dan komputasi yang tersedia | Sesi/komputasi terbatas, tidak dijamin, bukan server agent permanen. |
| GitHub Free | Penyimpanan versi, isu, dan sebagian CI yang memenuhi batas gratis | Menit dan kebijakan penggunaan harus dipantau; CI bukan sandbox otomatis untuk kode tak tepercaya. |
| MiniGrid | Lingkungan pembelajaran interaktif yang ringan dan terbuka | Hanya model dunia sederhana; tidak mewakili seluruh dunia fisik. |

**Aturan fallback:** jika tidak tersedia API gratis yang cocok, eksperimen pertama harus dapat berjalan dengan algoritma lokal dan model terbuka berukuran kecil, atau sebagai eksperimen semi-manual yang dilaporkan secara jujur. Jangan mengotomasi aplikasi chat melalui cara yang melanggar syarat layanan atau mengklaim integrasi lintas aplikasi telah tersedia.

### 11. Tahapan penelitian dan gerbang keputusan

| Fase | Keluaran yang harus nyata | Gerbang untuk lanjut |
|---|---|---|
| F0 — Feasibility | Inventaris akses nyata, CPU, kuota, benchmark, dan ancaman biaya | Setidaknya satu jalur eksekusi sah berbiaya tambahan Rp0 tersedia. |
| F1 — Baseline | A menjalankan tugas, evaluator menyimpan hasil dan seed | Run dapat diulang dan dibandingkan tanpa kebocoran *held-out*. |
| F2 — Adaptation | B memperbaiki strategi/alat dengan catatan lengkap | Perubahan dan efeknya dapat ditelusuri. |
| F3 — Evolution | C menghasilkan kandidat dan silsilah penerus | Kandidat berjalan aman, dapat dibatalkan, dan log tersimpan. |
| F4 — Generalization | Perbandingan A/B/C dengan kontrol anggaran dan tugas baru | Laporan membedakan kemajuan, regresi, dan hasil inkonklusif. |
| F5 — Research decision | Analisis penyebab, batas, dan rencana eksperimen berikutnya | Tidak ada klaim melebihi bukti yang diperoleh. |

Urutan di atas adalah gerbang berbasis bukti, bukan janji jadwal atau kepastian keberhasilan.

### 12. Kriteria penerimaan produk dan eksperimen

**Produk v0.1 dinyatakan layak sebagai prototipe bila:** semua FR P0 tersedia dan dites; tiga kondisi berjalan pada set tugas dan anggaran yang dapat dibandingkan; eksperimen menghasilkan artefak serta log yang lengkap; satu skenario interupsi berhasil dipulihkan; pembatas biaya dan izin diuji; laporan bisa dibaca di HP dan memisahkan klaim dari hasil empiris.

**Hipotesis ilmiah dinyatakan didukung secara awal bila:** sistem C memperlihatkan perbaikan *held-out* yang konsisten terhadap A dan B, biaya telah dikendalikan, terdapat bukti transfer lintas tugas/keluarga, dan perbaikan diteruskan ke kandidat penerus. Jika tidak, prototipe tetap bisa lulus penerimaan engineering, tetapi hipotesis wajib berstatus gagal atau inkonklusif.

### 13. Risiko penelitian dan mitigasi

| Risiko | Dampak | Pendekatan v0.1 |
|---|---|---|
| Overfitting benchmark / kebocoran tes | Peningkatan semu | Pisahkan keluarga pengujian, kunci versi evaluator selama run, simpan seed. |
| Reward hacking / salah ukur | Hasil tampak baik tanpa kemampuan lebih | Banyak metrik, tes regresi, jejak artefak dan ketidakpastian. |
| Regresi lintas generasi | Pengetahuan/kemampuan hilang | Arsip kandidat, rollback, paket transfer pengetahuan yang berversi. |
| Komputasi gratis terhenti | Eksperimen terputus | Checkpoint dan mode resumable, mulai dari CPU skala kecil. |
| Ketergantungan penyedia | Penelitian macet karena kuota/akses | Adaptor model, jalur lokal gratis, ekspor data terbuka. |
| Eksekusi kode hasil generasi | Kebocoran rahasia atau perubahan tak diizinkan | Isolasi kuat, tanpa kredensial, batas jaringan dan sumber daya. |
| Klaim ilmiah berlebihan | Kesimpulan menyesatkan | Label *pilot*, *inconclusive*, dan tidak menyamakan skor dengan AGI. |

### 14. Pertanyaan terbuka dan keputusan yang ditunda

- Benchmark mana yang paling kecil namun cukup sensitif membedakan A/B/C dengan kuota gratis nyata?
- Jalur komputasi gratis mana yang konsisten tersedia dan diizinkan bagi pengguna?
- Apakah percobaan pertama perlu LLM sama sekali, atau algoritma evolusioner lokal sudah cukup untuk menguji mekanisme seleksi?
- Bentuk representasi pengetahuan apa yang paling mudah dipindahkan antarkandidat berbeda?
- Seberapa besar bukti empiris yang dibutuhkan sebelum penelitian diperluas ke *open-weight model training*?
- Jika kelak eksperimen fisik dilakukan, tindakan mana yang harus membutuhkan otorisasi khusus dan perangkat keselamatan?

Keputusan tersebut diputuskan pada fase F0/F1 berdasarkan data, bukan diasumsikan telah tersedia.

### 15. Status dan pernyataan akhir

**Disepakati secara konseptual:** visi jangka panjang, kebebasan eksplorasi ilmiah, independensi dari satu LLM/penyedia, evaluasi otomatis internal, biaya tambahan awal Rp0, dan prioritas pada kemampuan generalisasi.

**Belum dilakukan:** pembuatan repositori, integrasi API, eksperimen, pengujian, pelatihan, deployment, pembelian layanan, atau verifikasi hasil ilmiah. PRD ini merupakan rancangan yang dapat digunakan sebagai dasar pengembangan, **bukan laporan keberhasilan sistem**.

### 16. Referensi awal (diakses 4 November 2026)

1. Zhang dkk., *Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents* (2025): https://arxiv.org/abs/2505.22954
2. OpenAI Help Center, *Managing billing for ChatGPT and the API platform*: https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform
3. Anthropic Help Center, *Why is Claude API usage billed separately from my paid Claude plan?*: https://support.claude.com/en/articles/9876003-why-is-claude-api-usage-billed-separately-from-my-paid-claude-plan
4. Google AI Studio, *Rate limits*: https://aistudio.google.com/docs/rate-limits
5. Google Colab, *Frequently Asked Questions*: https://research.google.com/colaboratory/faq.html
6. GitHub, *Plans and pricing*: https://github.com/pricing
7. Farama Foundation, *MiniGrid*: https://github.com/Farama-Foundation/Minigrid
