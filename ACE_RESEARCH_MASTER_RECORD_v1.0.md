# ACE — Research Master Record v1.0
**Tanggal snapshot:** 4 November 2026  | **Sumber kebenaran:** berkas PRD, laporan tahap, dan arsip bukti dalam paket ini.  
**Tujuan dokumen:** memindahkan penelitian ke ChatGPT Work / Codex tanpa mengandalkan memori percakapan.  
**Status:** handoff administratif, bukan hasil eksperimen baru, bukan sertifikasi peneliti eksternal.

## 1. Identitas dan visi yang tidak boleh terselip
**Visi jangka panjang:** Open-Ended Autonomous Intelligence Evolution (OAIE), yakni penelitian menuju kecerdasan yang dapat memilih masalah riset, mengenali kesenjangan kemampuan, menyintesis metode/representasi baru, mengevaluasinya, mewariskannya, dan dalam jangka panjang berpotensi mengubah paradigma maupun arsitekturnya. Ini adalah **aspirasi penelitian**, bukan kapabilitas terdemonstrasi.

**Nama sistem generasi pertama:** Autonomous Capability Evolution (ACE). Fokusnya adalah *testable capability invention*, transfer dan pewarisan pengetahuan; A=Fixed, B=Adaptive, C=Evolutionary, dengan kontrol kuat. Sistem belum memiliki agen yang otonom membangun kecerdasan umum.

**Prinsip tetap:** arsitektur dan vendor agnostic; LLM komersial boleh sebagai bootstrap, bukan ketergantungan permanen; Python/CPU dan komputasi gratis lebih dulu; target biaya tambahan **Rp0** tanpa asumsi langganan aplikasi = akses API; akses via HP; setiap klaim harus didukung log, protokol, kontrol dan penjelasan ketidakpastian. Tidak menjalankan kode arbitrer tak tepercaya atau aktivitas dunia fisik, pembayaran, perubahan akun, dan penerbitan secara otomatis.

**Proyek terpisah:** ACE bukan Tod. Jangan mencampurkan kode atau bukti ke `dianzherdiana25-hash/Tod`.

## 2. Ringkasan keputusan penelitian yang sudah dibuat
- F0: lingkungan uji CPU, logging, checksum, dan recovery simulasi valid dalam cakupan uji kecil. Reproduksi ZIP dari pengguna via Colab ada. Belum membuktikan durabilitas lintas sesi permanen.
- F1: baseline Fixed diujikan dan direproduksi; 83/108 soal benar; 14/14 tes.
- F2: Adaptive pemilihan strategi yang **sudah ada**: A 79/96 vs B 94/96, pada pilot dengan keterbatasan distribusi. Reproduksi Colab diterima; tidak membuktikan penemuan algoritma.
- F3: mutasi DSL terkendali 96/96 vs B 94/96, tetapi ablasi menemukan kontrol 'selalu generasi terakhir' juga 96/96; tidak ada bukti kausal seleksi feedback F3.
- F3.1: feedback mengubah lintasan kandidat, tetapi Guided 958/1152 kalah dari blind+best 966/1152; efek keunggulan tidak didukung.
- F3.2: Archive Neighbor 2050/2304 vs blind+best 1795/2304, tetapi kalah dari Guided Best 2142/2304; klaim hanya benchmark internal dan biaya terbatas.
- F3.3: komposisi macro terbentuk; 2294/5760 vs 2198/5760, interval ketidakpastian mencakup nol; manfaat performa belum konklusif.
- F4a: perubahan struktur DSL, macro 4226/11520 vs no-macro 4309/11520; efek belum konklusif. Notebook Colab penuh belum terbukti pada akun pengguna.
- F4b: transfer ke topologi graf TREE/DAG dengan motif yang masih relevan, C 505/3072 vs B 284/3072; efek positif pada distribusi yang dikonstruksi, **tidak** pada motif baru. Label A pada F4b bukan A-Fixed F1.
- F5: keputusan `CONTINUE_RESEARCH_WITH_SCOPE_LIMITS`. Tidak ada klaim general intelligence atau evolusi terbuka.
- E1: learned macro 463/960 vs base 20/960 untuk komposisi dengan motif yang berhubungan; pada motif baru C 0/480 vs B 40/480. Kode/evaluator masih satu proyek.
- E1.1: EVOLVE 111/480 vs RANDOM 21/480, SHAM 30/480, BEAM 60/480. Perbedaan vs BEAM **tidak konklusif**; pemrograman 12 primitive tersedia.
- E1.2 (**checkpoint terbaru**): REUSE 640/640 pada tugas RELATED, TARGET_ONLY 48/640, namun solver STRUCTURED juga 640/640. Pada UNRELATED REUSE 48/640 vs TARGET_ONLY 88/640. Ini adalah induksi operator terparametrisasi dalam grammar manusia; bukan penemuan primitive terbuka.

**Jangan gabungkan angka lintas fase menjadi satu kurva peningkatan kecerdasan:** tugas, denominasi, kebijakan, dan grammar berubah.

## 3. Apa yang sudah terbukti, apa yang tidak
**Terbukti dalam eksperimen internal yang dicatat:** kode lingkungan uji dapat berjalan dan sebagian direproduksi di Colab; pipeline A/B/C terbatas; adaptasi katalog; pembuatan, seleksi, dan pewarisan kandidat DSL; sintesis macro/prosedur dari contoh; transfer positif bila struktur target relevan; beberapa kontrol negatif menyingkap pembatas.

**Belum terbukti:** penemuan primitive dasar atau paradigma baru di luar grammar buatan manusia; metode yang secara konsisten melampaui pembanding terkuat dan solver struktural; generalisasi lintas domain dengan evaluator eksternal; self-directed scientific agenda; penggantian LLM/model fondasi; operasi 24/7 atau lintas restart yang diandalkan; sandbox aman untuk kode arbitrer; AGI/ASI dan recursive self-improvement tak terbatas.

## 4. Catatan integritas dan asal-usul
- Arsip `evidence/` disalin **byte-identik** dari berkas hasil sesi sebelumnya; checksum dalam `MANIFEST_SHA256.json` mengikat snapshot handoff, bukan validasi ilmiah eksternal.
- Beberapa laporan merekam pengujian Colab pengguna F0–F3; E1.2 baru diuji secara lokal dan paket notebooknya disediakan.
- Penguncian metodologi pada riset sebelumnya memakai hash lokal, bukan preregistrasi oleh pihak ketiga.
- Indeks versi di sini **mengarsipkan**, tidak menimpa artefak asli atau mengoreksi laporan historis secara diam-diam.

## 5. Status jalur kerja dan sistem
- **Tempat diskusi dan keputusan:** Project Penelitian dalam ChatGPT.
- **Koordinator ideal:** ChatGPT Work; perpindahan mode tidak dapat dipicu otomatis dari percakapan biasa ini.
- **Pelaksana coding:** Codex Cloud/repo Git tersendiri; repo ACE belum ada di GitHub yang terhubung saat inventarisasi.
- **Repo GitHub terhubung ditemukan:** hanya `dianzherdiana25-hash/Tod`, yang sengaja tidak disentuh.
- **Akun Colab:** pernah digunakan untuk reproduksi F0–F3; bukan bukti runtime selalu aktif.
- **Paket ini:** snapshot lokal yang memiliki manifest hash dan sumber terbuka untuk dipindah ke Work atau repositori ACE baru.

## 6. Satu keputusan penelitian berikutnya (E1.3)
**Judul kerja:** Unknown-Grammar Capability Discovery. Jangan langsung mengklaim penemuan primitive hanya karena sistem melakukan pencarian parameter di grammar yang disediakan.

**Pertanyaan primer:** apakah sistem dengan kemampuan memperluas representasi yang diperbolehkan dapat menggeneralisasi ke aturan target yang grammar-nya tidak diberikan kepada pembuat kandidat, mengungguli pembanding algoritmik kuat pada biaya komputasi total yang tercatat?

**Syarat gerbang sebelum eksperimen:**
1. Bekukan E1.2 sebagai sejarah; jangan memakai data konfirmatori lama untuk klaim baru.
2. Tugas/grammar/evaluator dibuat oleh jalur yang secara metodologis terpisah; tetapkan kebijakan kebocoran dan siapa yang boleh membuka label.
3. Bandingkan solver struktural, pencarian enumeratif, beam/program synthesis lain yang kuat, dan intervensi capability invention. Samakan evaluasi dan catat CPU/waktu/memori.
4. Lakukan pilot hanya pada data pengembangan; tetapkan metrik kebaruan semantik, transfer pada motif baru, degradasi negatif, dan satu kontras primer sebelum konfirmasi.
5. Set pengujian konfirmatori disegel dan tidak dibaca/diubah selama pengembangan; minta satu audit reproduksi teknis yang terpisah.
6. Batasi eksperimen pada interpreter DSL atau sandbox aman tanpa akses jaringan dan kredensial.

**Keputusan terkini:** `READY_FOR_E13_DESIGN`, **bukan** `READY_FOR_E13_CONFIRMATORY_RUN`.

## 7. Protokol agar konsep tidak hilang
Setiap sesi baru: (1) baca file ini; (2) baca PRD+RES; (3) baca laporan terbaru E1.2; (4) periksa SHA manifest; (5) telaah perubahan sejak checkpoint; (6) tulis keputusan dan status ke berkas berversi; (7) baru kerjakan implementasi. Setiap hasil harus memiliki eksperimen, kode, tes, kontrol, checksum, dan apa yang gagal. Jangan hanya mengandalkan ringkasan chat.

**Tidak ada tindakan pada repo Tod, pembayaran atau layanan berbayar di handoff ini.**
