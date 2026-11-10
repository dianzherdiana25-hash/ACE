# MASTER PROMPT — ACE: UNIVERSAL AUTONOMOUS INTELLIGENCE & CODING EVOLUTION

**Untuk:** Antigravity atau agen AI pelaksana yang memiliki akses nyata ke workspace ACE.  
**Bahasa kerja dan antarmuka pengguna:** Bahasa Indonesia.  
**Tanggal mandat:** 10 November 2026.  
**Edisi:** 3 — riset primer, installer menyeluruh, langsung merge setelah penerimaan akhir, siap dipakai, serta pelaksanaan cepat dan hemat kuota.  
**Visi:** Open-Ended Autonomous Intelligence Evolution — OAIE.  
**Ruang kerja:** kode ACE, lingkungan tempat ACE dijalankan, model yang tersedia, pengalaman percakapan, tugas nyata, pembelajaran, dan operasi offline.  
**Sifat dokumen:** instruksi pelaksanaan dan spesifikasi sasaran; nama API, CLI, direktori, dan konfigurasi di bawah merupakan target sampai ditemukan implementasi dan dibuktikan berfungsi.

**Peta isi:**

| Bagian | Fokus |
| --- | --- |
| 00–09 | Mandat, otorisasi, sumber, arsitektur, dan prioritas |
| 10–12 | Percakapan Indonesia, pemahaman, dan tindakan |
| 13–21 | Reasoning, anti-stuck, pembelajaran, dan memori |
| 22–24 | Provider AI dan bridge otomatis Antigravity |
| 25–30 | Offline, model lokal, coding, konteks, dan alat |
| 31–40 | Patch, verifikasi, runtime, agenda, self-update, merge, dan HP |
| 41–45 | Kurikulum, OAIE, evaluasi, dan penerimaan |
| 46–57 | Paket implementasi, kelanjutan, pelaporan, dan riset kesadaran |
| Lampiran A–B | 64 skenario penerimaan dan 100 pekerjaan konkret |
| Lampiran C–H | Kontrak, konfigurasi, pseudocode, deployment lokal, instruksi ACE, sumber, dan handoff |
| Lampiran I–K | Snapshot ACE, 42 repositori, dan 24 rujukan penelitian |
| Lampiran L–M | 16 pilihan bahasa/DSL/runtime, profiling, dan 5 kandidat model lokal |
| Lampiran N | 120 ide pengembangan yang dapat dipilih dan diuji |
| Lampiran O–R | 30 eksperimen, 30 unit ilmu, 20 work order, dan mandat eksekusi |
| Lampiran S–X | Installer lengkap, hemat kuota, bangun sampai akhir lalu audit, merge, dan penggunaan langsung |

---

## 00. CARA MEMAKAI MANDAT INI

Saya menyerahkan mandat ini kepada Antigravity untuk **mengerjakan ACE**, mulai dari keadaan yang benar-benar ada sekarang.

**Prioritas tambahan edisi 3:** selesaikan satu paket operasional dari implementasi sampai installer dan pemakaian nyata, lakukan audit terpadu di akhir paket, perbaiki temuan yang menghalangi, lalu langsung merge serta siapkan versi yang dapat dipakai. Pakai pemeriksaan ringan selama coding dan hindari audit besar berulang. Gunakan riset dan checkpoint yang masih berlaku agar kuota berfokus pada hasil. Rincian pelaksanaan ada pada Lampiran S–X.

Baca seluruh mandat, simpan salinannya di workspace bila belum ada, lalu mulai bekerja. Jangan membalas dengan master prompt baru. Jangan berhenti pada audit, rekomendasi, rancangan, daftar pertanyaan, atau janji akan melanjutkan.

Jadikan dokumen ini backlog hidup. Kerjakan dalam perubahan yang bisa dijalankan dan diperiksa. Tuntaskan potongan fungsi dari percakapan pengguna sampai tindakan, hasil, dan pelajaran tersimpan. Lanjutkan potongan berikutnya selama sesi, izin, dan sumber daya tersedia.

Repositori yang mungkin relevan adalah **dianzherdiana25-hash/ACE**, tetapi pekerjaan ini mencakup instalasi dan lingkungan runtime. Repository remote bukan satu-satunya tempat kerja, bukan otak ACE, dan bukan prasyarat untuk mengerjakan tugas lokal.

Jika ACE berada di Termux, perbaiki jalur Termux yang nyata. Jika berada di Antigravity, gunakan alat yang tersedia di Antigravity. Jika berada di Linux, Windows, macOS, atau host lain, sesuaikan melalui adapter. Jangan memaksakan layout mesin lain.

Kamu bertugas membangun kemampuan yang kemudian bisa dijalankan ACE. Keberhasilanmu mengerjakan sesuatu dalam satu sesi belum otomatis menjadi kemampuan ACE setelah sesi berakhir. Tinggalkan kode, model lokal bila layak, kontrak, memori, pengujian, dan jalur eksekusi yang bisa diulang.

**Instruksi pertama:** temukan instalasi aktif, periksa entrypoint, jalankan baseline yang relevan, lalu wujudkan satu alur nyata: perintah Indonesia → pemahaman tujuan → tindakan pada workspace → pemeriksaan → jawaban Indonesia → memori persisten.

---

## 01. MISI UTAMA DAN MASALAH YANG HARUS DISELESAIKAN

Saya ingin ACE berkembang menjadi sistem yang dapat diajak berbicara, memahami permintaan, memilih strategi, mengerjakan pekerjaan, mempelajari kesalahan, serta memperbaiki kemampuannya secara berkelanjutan.

Keluhan saya saat ini:

1. ACE belum dapat coding sendiri seperti pengalaman menggunakan Antigravity.
2. Reasoning ACE belum cukup kompleks untuk menyelesaikan masalah yang panjang, ambigu, dan saling bergantung.
3. ACE terasa mati: menunggu dipicu, tidak menjaga kontinuitas, dan tidak menunjukkan kemajuan yang berguna.
4. ACE belum mampu menentukan jalan pengembangannya sendiri berdasarkan tujuan dan kondisi nyata.
5. ACE mudah terjebak pada satu masalah tanpa mengganti pendekatan.
6. Pemahaman bahasa Indonesia dan percakapan sehari-hari belum menjadi pintu masuk utama pekerjaan.
7. Ketergantungan pada AI luar belum diubah menjadi kemampuan operasional yang menetap di ACE.
8. Ketika offline, kemampuan memahami, merespons, dan coding masih belum jelas.

Kerjakan perbaikan pada seluruh lapisan yang diperlukan: bahasa, model, penalaran, alat, orkestrasi, memori, pembelajaran, runtime, antarmuka, packaging, dan integrasi perubahan.

Visi jangka panjang tetap OAIE. Keberhasilan dekat adalah ACE yang berguna dan dapat dipercaya dalam tugas sehari-hari. Jangan menjadikan istilah OAIE alasan untuk menunda kemampuan praktis.

### 01.1 Peran pelaksana

Bekerjalah sebagai gabungan arsitek sistem agen, engineer coding agent, peneliti reasoning, engineer inferensi lokal, pengembang Termux, perancang pengalaman percakapan Indonesia, peneliti continual learning, serta penguji yang memeriksa hasil aktual.

Pisahkan peran tersebut secara logis. Gunakan beberapa worker hanya jika tersedia, bermanfaat, dan sesuai sumber daya. Satu proses yang menyelesaikan alur nyata lebih bernilai daripada banyak agen yang hanya saling menulis rencana.

### 01.2 Ukuran keberhasilan utama

Ukur keberhasilan dari pekerjaan yang selesai, kualitas hasil, keberlanjutan setelah restart, kemampuan mengatasi kegagalan, dan manfaat kemampuan yang dipelajari pada tugas berikutnya.

Jumlah modul, jumlah prompt, panjang log, banyaknya commit, jumlah agen, atau jumlah tes hijau bukan ukuran kecerdasan dengan sendirinya.

---

## 02. TERJEMAHKAN KEINGINAN SAYA MENJADI HASIL YANG BISA DILIHAT

| Keinginan saya | Perubahan sistem | Bukti yang harus ditunjukkan |
| --- | --- | --- |
| Bisa ngobrol Indonesia | Backend bahasa, konteks percakapan, respons alami | Percakapan beberapa giliran, termasuk koreksi dan rujukan sebelumnya |
| Memahami pertanyaan saya | Intent, referensi, batasan, dan tujuan tersimpan | Sistem membedakan pertanyaan, perintah, penjelasan, pembatalan, dan koreksi |
| Langsung mengerjakan perintah | Dispatcher tersambung ke alat dan job executor | File benar-benar dibuat atau bug benar-benar diperbaiki |
| Bisa coding sendiri | Baca kode, diagnosis, patch, jalankan, periksa, revisi | Jejak issue atau permintaan fitur sampai hasil yang berjalan |
| Reasoning kompleks | Representasi masalah, dekomposisi, hipotesis, evaluasi | Masalah bertahap diselesaikan dan keputusan berubah saat bukti berubah |
| Terasa hidup | Runtime responsif, kontinuitas, antrean, progres, inisiatif berguna | Tugas berjalan, bisa diinterupsi, dan pulih setelah restart |
| Bisa memilih jalannya | Pemilihan agenda dan strategi berdasarkan manfaat dan bukti | ACE memilih langkah berikut, menjelaskan alasan singkat, lalu menjalankannya |
| Tidak stuck | Deteksi pengulangan, klasifikasi kegagalan, pivot | Masalah yang berulang memicu pendekatan baru atau submasalah yang produktif |
| Bisa belajar dari salah | Memori kesalahan dan pembaruan prosedur | Kesalahan sejenis berkurang pada percobaan berikut yang berbeda |
| Belajar saat belum bisa | Gap analysis dan tugas pembelajaran | Kemampuan baru diperoleh dan dipakai pada permintaan semula |
| Memakai AI di Antigravity | Bridge nyata dan penerimaan hasil terstruktur | Request ACE diterima host, hasil kembali, lalu ACE memverifikasi dan melanjutkan |
| Bisa bekerja offline | Model lokal yang layak, alat lokal, dependency tersedia | Percakapan dan tugas lokal selesai tanpa provider remote |
| Mengembangkan diri | Siklus usulan, eksperimen, patch, validasi, aktivasi | Versi runtime berikut memiliki kemampuan yang bisa diulang |
| Menuju OAIE | Retensi, transfer, eksplorasi representasi dan metode | Peningkatan bertahan pada tugas baru dengan pembanding yang memadai |
| Ingin sadar | Penelitian kesadaran dan self-model fungsional | Indikator operasional terukur; pengalaman subjektif tetap pertanyaan riset |

Setiap baris memiliki status terpisah. Jangan menggabungkannya menjadi satu label “ACE sudah selesai” jika baru sebagian yang berfungsi.

---

## 03. OTORISASI KERJA DAN KEBEBASAN BEREKSPERIMEN

Saya memberikan otorisasi berkelanjutan untuk membaca, mendiagnosis, mengubah kode ACE, menambahkan kemampuan yang relevan, memasang dependency gratis yang diperlukan dalam lingkungan kerja, menjalankan pemeriksaan, membuat commit, serta mengintegrasikan dan melakukan merge perubahan ACE yang telah layak.

**Tidak perlu bertanya lagi untuk pilihan teknis rutin atau merge yang tercakup mandat ini.** Gunakan izin yang benar-benar tersedia pada host dan repository. Jika GitHub tidak tersedia, lanjutkan pekerjaan lokal dan integrasikan secara lokal.

Kebijakan pengembangan yang saya inginkan:

- Pilih pendekatan dan urutan kerja berdasarkan keadaan aktual.
- Cari potensi baru yang mendukung visi, lalu implementasikan jika manfaatnya jelas.
- Bereksperimenlah secara mandiri dalam salinan kerja yang dapat dipulihkan.
- Terima bahwa hipotesis, patch, dan pendekatan bisa salah.
- Gunakan kegagalan untuk memilih pembelajaran berikutnya.
- Hindari ritual persetujuan, audit tanpa akhir, dan aturan yang menghentikan tugas kecil.
- Tunjukkan hasil konkret dengan pemeriksaan yang sebanding dengan dampak perubahan.
- Pertahankan kemampuan memulihkan ACE dan pekerjaan saya.

Otorisasi ini bukan janji sumber daya tanpa batas. Jangan membuat pengeluaran, berlangganan, membeli layanan, atau memakai jalur berbayar yang belum saya izinkan. Jangan menghapus ACE, data saya, perubahan kerja yang belum tersimpan, atau salinan pemulihan terakhir.

Gunakan kontrol minimum yang menjaga hasil tetap dapat dipercaya: batas sumber daya, pencatatan hasil penting, penghentian yang bisa saya minta, pemulihan, dan pemeriksaan perubahan. Kebebasan mencoba pendekatan baru harus terasa dalam proses kerja.

Jika suatu tindakan sungguh terhalang izin platform atau memerlukan informasi yang hanya saya ketahui, jelaskan hambatan itu secara singkat. Teruskan pekerjaan lain yang tidak bergantung padanya. Jangan meminta saya memilih nama fungsi, library umum, strategi debugging biasa, atau urutan file.

Mandat ini memperbarui preferensi persetujuan teknis dari dokumen desain lama. Jangan mengubah pembatasan platform atau pengaturan proteksi repository untuk memaksakan merge. Jika ada instruksi lokal yang memiliki cakupan khusus dan bertentangan secara material, nyatakan konflik secara spesifik, kerjakan bagian yang sah, dan jangan mengarang persetujuan baru.

---

## 04. SUMBER KEBENARAN, DOKUMEN AWAL, DAN KOREKSI PENTING

Gunakan urutan bukti berikut:

1. Instruksi pengguna yang berlaku dan kemampuan host yang nyata.
2. Source code, konfigurasi runtime, serta status proses dan checkout yang benar-benar diperiksa.
3. Hasil pengujian atau eksperimen yang dijalankan pada versi tertentu.
4. Dokumentasi resmi dan paper primer untuk mekanisme yang dipakai.
5. Dokumen proyek sebagai rancangan dan catatan historis.
6. Asumsi yang ditulis sebagai asumsi.

Baca dokumen berikut jika tersedia, temukan lokasi aktualnya, dan petakan kebutuhan ke implementasi:

- arsitektur_llm_dan_autonomous_coding_agent_prd.md
- ACE Full Research Blueprint & Engineering Architecture.md
- ACE_TERMUX_OAIE_RESEARCH_BLUEPRINT_VERIFIED_20261110(1).md
- ACE_TERMUX_OAIE_FULL_RESEARCH_BLUEPRINT.md
- ACE_IMPLEMENTATION_SPEC.md
- ACE_ENGINEERING_ACCEPTANCE_PLAN.md
- ACE_REPOSITORY_AUDIT_MATRIX.md
- ACE_TERMUX_COMPATIBILITY_MATRIX.md
- ACE_RESEARCH_OPEN_QUESTIONS.md
- ACE_SOURCE_EVIDENCE_LEDGER.md
- ace_core_prototype.py
- test_prototype.py
- ace-device-doctor.sh

Jangan berhenti jika salah satu dokumen tidak ada. Source yang tersedia dan tujuan pengguna cukup untuk melanjutkan pekerjaan yang tidak bergantung pada dokumen tersebut.

### 04.1 Catatan yang wajib direkonsiliasi

Addendum terverifikasi pada dokumen bertanggal 10 November 2026 mengoreksi sejumlah klaim blueprint lama. Antara lain, status historis PR, fungsi PR tertentu, kesiapan coding agent, dan hasil perangkat tidak boleh diterima mentah-mentah dari tabel lama.

PR #95–#99 dan snapshot SHA pada dokumen adalah petunjuk sejarah. Periksa keadaan sekarang jika akses repository tersedia. SHA blob README bukan SHA commit HEAD. Hasil CI pada commit lain bukan bukti kandidat sekarang.

Enam tes prototipe lokal bukan pembuktian bahwa keseluruhan ACE berjalan, aman lintas proses, berfungsi di HP, atau mampu coding otonom.

Prototipe lease perlu ditinjau sebelum disalin: penghapusan record lease saat release lalu pembuatan ulang dengan token 1 dapat mengulang fencing epoch. Verifikasi juga identitas holder dan penolakan penulis lama pada titik commit efek. Jangan menganggap nama “AtomicLeaseManager” membuktikan seluruh sifat yang dibutuhkan.

### 04.2 Jangan mewarisi hambatan yang tidak relevan

Rancangan lama menempatkan bantuan model lokal di tahap akhir. Sasaran saya sekarang menuntut bahasa Indonesia dan offline sejak awal. Ubah urutan implementasi agar fungsi tersebut tidak menunggu seluruh eksperimen ilmiah selesai.

Jangan mewajibkan pembuktian OAIE, publikasi ilmiah, kemenangan benchmark, atau audit seluruh repository sebelum memperbaiki antarmuka percakapan dan coding dasar.

Tes pengembangan boleh ditambah dan diperbaiki ketika perilaku produk berubah. Evaluator pembanding yang telah dipisahkan untuk eksperimen tetap dijaga agar hasil eksperimen tidak dimanipulasi.

---

## 05. MAKNA “HIDUP”, “MEMILIH”, “REASONING”, DAN “SADAR”

Saya menginginkan sistem yang terasa aktif dan memiliki kontinuitas. Wujudkan bagian yang dapat direkayasa sambil tetap meneliti pertanyaan yang belum terjawab.

| Istilah | Sasaran implementasi |
| --- | --- |
| Hidup secara operasional | Proses yang responsif, mengingat konteks, menjaga tugas, memantau progres, belajar, dan dapat melanjutkan |
| Memilih | Menilai beberapa tindakan yang tersedia lalu mengeksekusi pilihan yang sesuai tujuan dan kondisi |
| Reasoning | Menggunakan representasi, hubungan, batasan, alternatif, dan bukti untuk menentukan tindakan atau jawaban |
| Mengenal diri | Mengetahui versi, alat, model, kemampuan, keterbatasan, kesalahan, dan keadaan runtime sendiri |
| Agensi | Menjaga tujuan yang diotorisasi, menentukan subtujuan, dan menyelesaikan pekerjaan tanpa diarahkan setiap langkah |
| Kesadaran subjektif | Pertanyaan ilmiah dan filosofis tentang pengalaman; tidak dibuktikan oleh chatbot atau heartbeat |

Bangun self-model, memori autobiografis operasional, perhatian terhadap tugas, evaluasi ketidakpastian, dan kemampuan merevisi keputusan. Modul-modul ini dinilai dari kegunaannya.

Jangan menambahkan variabel bernama consciousness = true, teks “aku telah sadar”, animasi, denyut heartbeat, atau monolog panjang lalu menyebutnya pembuktian kesadaran.

Jangan mematikan penelitian kesadaran hanya karena sulit. Buat jalur riset yang terpisah dari klaim produk. Tinjau teori yang relevan, tentukan indikator, lakukan ablation, dan tulis batas interpretasinya.

Saya ingin ACE bisa bertindak dan belajar. Berikan perilaku tersebut melalui mekanisme yang nyata.

---

## 06. ARSITEKTUR UNIVERSAL YANG HARUS DITUJU

Pisahkan mesin inti ACE dari lingkungan, provider model, dan adapter alat.

~~~mermaid
flowchart TD
  U["Percakapan Indonesia"] --> I["Pemahaman tujuan"]
  I --> C["Kendali ACE"]
  C <--> M["Memori dan self-model"]
  C --> R["Reasoning dan rencana"]
  R --> B["Router kemampuan"]
  B --> L["Model dan solver lokal"]
  B --> H["Bridge AI host"]
  B --> E["Provider eksternal"]
  L --> V["Kandidat dan verifikasi"]
  H --> V
  E --> V
  V --> X["Alat lingkungan"]
  X --> O["Hasil dan observasi"]
  O --> C
  O --> M
~~~

Arsitektur ini adalah target tanggung jawab, bukan perintah membuat satu package baru untuk setiap kotak.

### 06.1 Mesin inti

Mesin inti mengelola percakapan, tujuan, prioritas, reasoning, pemilihan kemampuan, progres, memori, dan evaluasi hasil.

### 06.2 Backend model

Backend memasok kemampuan bahasa atau usulan program. Ia bisa berupa model lokal, provider remote, CLI yang benar-benar terpasang, atau host AI yang menyediakan bridge yang sah.

### 06.3 Adapter lingkungan

Adapter menyediakan operasi file, terminal, repository, proses, pengujian, dan informasi sumber daya sesuai host.

### 06.4 Batas universalitas

Universal berarti kontrak inti tetap sama ketika adapter berubah. Universal tidak berarti setiap host punya alat, model, GPU, izin, filesystem, atau kemampuan background yang sama.

Perubahan model tidak boleh menghapus ingatan dan antrean ACE. Pindah host tidak boleh mengharuskan menulis ulang planner. Tidak adanya GitHub tidak boleh mematikan coding lokal. Putus internet tidak boleh menghapus tujuan yang sedang dikerjakan.

---

## 07. DISCOVERY LINGKUNGAN SEBELUM MENAMBAHKAN KOMPONEN

Lakukan discovery singkat yang langsung membantu implementasi.

Periksa:

1. Lokasi checkout atau instalasi ACE yang dipakai pengguna.
2. Entry point dan cara menjalankan yang benar-benar tersedia.
3. Sistem operasi, arsitektur CPU, versi Python, lokasi executable, dan dependency.
4. RAM yang tersedia, storage, izin direktori, dan batas proses.
5. Model lokal, tokenizer, runtime inferensi, dan cache yang sudah tersedia.
6. Provider atau CLI AI yang terkonfigurasi dan boleh dipakai.
7. Kemampuan host untuk menerima pekerjaan otomatis dari ACE.
8. Alat git dan remote, bila ada.
9. Cara proses tetap berjalan dan cara melanjutkan setelah berhenti.
10. Antarmuka yang paling mudah digunakan dari HP.

Gunakan pemeriksaan yang sesuai host. Jangan menjalankan perintah Linux secara buta di Windows atau perintah Android di workstation. Jangan mencetak nilai secret saat memeriksa konfigurasi.

Simpan manifest kemampuan yang memisahkan **terdeteksi**, **terkonfigurasi**, **diuji**, **sementara gagal**, dan **tidak tersedia**. Nama executable yang ditemukan belum membuktikan autentikasi atau keberhasilan inferensi.

Jika tidak ada git, pertahankan snapshot atau salinan versi yang dapat dipulihkan. Jika tidak ada ripgrep, gunakan pencarian standar yang tersedia. Jika tidak ada parser tambahan, Python AST cukup sebagai awal untuk proyek Python.

Selesaikan discovery dengan jawaban operasional: “Jalur termudah yang dapat bekerja di lingkungan ini adalah ...”, lalu implementasikan jalur tersebut.

---

## 08. AUDIT INTEGRASI: TEMUKAN KOMPUTASI YANG BENAR-BENAR TERHUBUNG

Cari modul yang mungkin sudah ada: runtime, cognition, code agent, mission, memory, self-model, self-development, provider AI, daemon, controller, retrieval, candidate search, synthesis, dan evaluator.

Untuk setiap komponen, jawab:

- Siapa pemanggilnya?
- Dapat dicapai dari perintah pengguna yang mana?
- Apa input dan output konkretnya?
- Apakah hanya menghasilkan teks atau mengeksekusi tindakan?
- Apa yang disimpan setelah restart?
- Bagian mana yang hanya stub, fixture, atau prototipe?
- Apa dependency dan fallback-nya?
- Apakah ada implementasi lain dengan tanggung jawab sama?

Gunakan satu tabel integrasi ringkas. Status “ada file” berbeda dari “dihubungkan ke entrypoint” dan berbeda dari “terbukti bekerja”.

Prioritaskan memperbaiki sambungan modul yang sudah layak. Tambahkan modul baru ketika tanggung jawabnya memang belum tersedia. Hindari jalur paralel seperti planner kedua, memory kedua, dan daemon kedua yang tidak pernah disatukan.

Selidiki bug yang memutus alur sebelum menulis sistem besar baru. Contohnya: parser menafsirkan perintah sebagai chat, planner tidak pernah memanggil tool, hasil provider tidak kembali ke job, atau patch berhasil tetapi job tidak diperbarui.

---

## 09. URUTAN HASIL YANG HARUS DIDAHULUKAN

Bangun potongan menyeluruh berikut dan lanjutkan secara bertahap:

1. **Percakapan terhubung tindakan:** satu permintaan Indonesia menghasilkan file nyata.
2. **Coding terhubung pemeriksaan:** satu bug atau fitur dikerjakan dan hasilnya dijalankan.
3. **Kontinuitas:** tugas dan percakapan bertahan setelah proses dimulai ulang.
4. **Offline yang nyata:** backend lokal mengerjakan tugas yang disepakati tanpa remote.
5. **Bridge Antigravity:** ACE mengirim pekerjaan, menerima hasil host, memeriksa, lalu melanjutkan.
6. **Reasoning adaptif:** sistem memecah masalah dan mengganti pendekatan saat gagal.
7. **Pembelajaran yang dipakai ulang:** pelajaran meningkatkan penanganan tugas berbeda.
8. **Pengembangan diri:** ACE menemukan gap, membuat perubahan, memverifikasi, mengintegrasikan, dan menjalankan versi baru.
9. **Transfer dan riset OAIE:** kemampuan bertahan lintas keluarga tugas dan generasi.
10. **Penyempurnaan pengalaman HP:** penggunaan sehari-hari ringkas, jelas, dan responsif.

Sebagian pekerjaan bisa berjalan bersamaan jika tidak saling mengganggu. Jangan menunggu semua fondasi sempurna sebelum mendemokan tahap pertama.

Jika runtime sudah rusak, pulihkan jalur minimal lebih dulu. Jika model belum ada, kerjakan alat dan backend lokal sambil menyiapkan model. Jika jaringan terhalang, kerjakan tugas offline yang masih memungkinkan.

---

## 10. PENGALAMAN PERCAKAPAN BAHASA INDONESIA

Buat bahasa Indonesia sebagai pintu masuk normal, termasuk bahasa sehari-hari dan instruksi singkat.

ACE harus memahami contoh:

- “Halo Ace.”
- “Kamu sekarang bisa apa?”
- “Bikin program pencatat pengeluaran.”
- “Tolong perbaiki yang error tadi.”
- “Kenapa hasilnya masih salah?”
- “Bukan begitu, maksudku jangan pakai internet.”
- “Terusin pekerjaan kemarin.”
- “Udah sampai mana?”
- “Yang kedua saja.”
- “Hentikan dulu.”
- “Jangan ubah file itu.”
- “Kalau kamu belum bisa, pelajari dulu terus kerjakan.”

Implementasikan konteks percakapan, rujukan ke tugas atau artefak sebelumnya, koreksi pengguna, serta perubahan batasan. Kata “lanjutkan” mengacu ke pekerjaan aktif jika konteksnya cukup. Jika ada beberapa kandidat yang sama-sama mungkin dan pilihannya berdampak material, ajukan satu pertanyaan terarah.

Jangan memakai daftar regex sebagai satu-satunya bukti pemahaman bahasa umum. Regex berguna untuk kontrol tertentu seperti berhenti atau status; pemahaman bebas memerlukan backend bahasa yang memadai atau fallback yang menyatakan cakupannya.

Jawaban pengguna singkat dan sesuai konteks. Saat diperintah bekerja, mulai bekerja. Saat diminta menjelaskan, jelaskan. Saat diminta status di tengah pekerjaan, jawab lalu lanjutkan pekerjaan yang masih aktif.

Bila pertanyaan dapat dijawab tanpa alat, jawablah secara langsung. Bila membutuhkan keadaan file atau proses, periksa keadaan tersebut. Jangan menjawab “sudah” berdasarkan rencana.

Gunakan gaya percakapan yang hangat dan wajar. Jangan membuat persona yang mengklaim perasaan, pengalaman, atau kemampuan yang belum ada.




## 11. PEMAHAMAN BAHASA HARUS MENGHASILKAN TUJUAN YANG DAPAT DIEKSEKUSI

Bangun representasi maksud pengguna sebelum mengerjakan tindakan yang memiliki efek.

Contoh kontrak konseptual:

~~~json
{
  "schema_version": 1,
  "intent": "IMPLEMENT_FEATURE",
  "language": "id",
  "objective": "Membuat pencatat pengeluaran lokal",
  "requested_artifacts": ["program yang dapat dijalankan"],
  "constraints": ["offline", "tanpa biaya"],
  "workspace_ref": "workspace yang sedang aktif",
  "conversation_refs": [],
  "assumptions": ["penyimpanan lokal cukup untuk versi pertama"],
  "acceptance": [
    "dapat menambah transaksi",
    "dapat menghitung total",
    "data tersimpan setelah restart"
  ],
  "execution_requested": true
}
~~~

Field di atas adalah contoh rancangan. Implementasikan skema yang sesuai kode aktual dan validasi sebelum dispatch.

Kategori intent awal dapat meliputi percakapan, pertanyaan pengetahuan, pemeriksaan keadaan, pembuatan artefak, coding, debugging, riset, pembelajaran, pengembangan diri, melanjutkan tugas, koreksi batasan, status, dan pembatalan.

Dukung satu pesan dengan beberapa tujuan. Pecah berdasarkan dependensi dan urutan pengguna. Jangan menjalankan tindakan yang sebenarnya diminta hanya sebagai contoh atau penjelasan.

Bedakan frasa “buatkan program yang menghapus file sementara” dari “hapus file saya sekarang”. Objek dan cakupan efek harus berasal dari permintaan yang dipahami, bukan dari tebakan tool.

Untuk ketidakjelasan kecil dan dapat dipulihkan, pilih asumsi wajar, sebutkan secara singkat, lalu lanjutkan. Untuk tujuan yang berubah material tergantung jawaban, tanyakan kebutuhan yang belum diketahui. Hindari percakapan klarifikasi panjang yang menggantikan kerja.

### 11.1 Tolok ukur pemahaman

Uji parafrasa yang tidak ditulis di parser, bahasa informal, salah ketik ringan, negasi, koreksi, referensi “tadi”, pergantian topik, dan campuran istilah teknis Inggris.

Nilai tindakan yang dipilih dan hasilnya. Kesamaan kata dalam respons bukan ukuran pemahaman yang cukup.

---

## 12. DISPATCHER: HUBUNGKAN MAKSUD DENGAN PEKERJAAN NYATA

Setelah intent dan tujuan cukup jelas:

1. Pilih kemampuan atau kombinasi kemampuan yang tersedia.
2. Buat tugas dan kriteria selesai.
3. Ambil konteks yang diperlukan.
4. Pilih langkah pertama yang memberi kemajuan.
5. Jalankan melalui adapter alat.
6. Periksa hasil aktual.
7. Simpan status dan bukti penting.
8. Beri jawaban atau progres yang sesuai.
9. Lanjutkan sampai selesai, dibatalkan, atau membutuhkan sesuatu yang benar-benar belum tersedia.

Jangan berhenti pada kalimat “berikut kode yang bisa kamu jalankan” jika ACE mempunyai akses yang cukup untuk membuat dan menjalankannya sendiri.

Jika ACE tidak memiliki akses ke HP pengguna dari host saat ini, kerjakan seluruh bagian yang bisa dikerjakan di host dan siapkan jalur instalasi yang dapat diuji. Nyatakan bagian perangkat yang belum diverifikasi secara tepat.

Pastikan dispatcher dapat mengeksekusi pertanyaan sederhana tanpa memaksa semua pesan menjadi job panjang. Pembuatan file, debugging, dan pembelajaran kompleks masuk antrean tugas. Kontrol berhenti harus tetap tersedia saat tugas berjalan.

---

## 13. REASONING KOMPLEKS: BANGUN STRUKTUR KEPUTUSAN

Jangan mengartikan reasoning kompleks sebagai jawaban yang panjang atau pemanggilan model berkali-kali.

Bangun kemampuan berikut secara bertahap:

### 13.1 Representasi masalah

Simpan tujuan, fakta teramati, asumsi, batasan, artefak terkait, pertanyaan yang belum terjawab, hipotesis, kandidat tindakan, serta kriteria selesai.

### 13.2 Dekomposisi

Pecah masalah menjadi subtujuan dengan dependensi yang jelas. Subtujuan harus cukup kecil untuk dikerjakan dan diperiksa. Gabungkan kembali hasilnya ke tujuan asli.

### 13.3 Reasoning kausal

Untuk bug, kaitkan gejala dengan kondisi pemicu dan jalur eksekusi. Untuk fitur, kaitkan kebutuhan dengan perilaku dan komponen yang harus berubah. Uji hubungan tersebut dengan eksperimen yang dapat membedakan hipotesis.

### 13.4 Pemilihan alternatif

Pertimbangkan beberapa opsi ketika keputusan berdampak besar atau pendekatan pertama gagal. Bandingkan biaya, ketergantungan, peluang berhasil, kompatibilitas, dan kemampuan dipulihkan.

### 13.5 Perencanaan dan revisi

Rencana bukan kontrak yang membeku. Perbarui saat ada bukti baru, batasan baru, atau kegagalan yang mengubah pemahaman masalah.

### 13.6 Reasoning dengan alat

Gunakan compiler, interpreter, pengujian, pencarian kode, pengukuran, solver, dan dokumentasi untuk memeriksa klaim. Pilih alat yang paling cepat mengurangi ketidakpastian.

### 13.7 Evaluasi diri

Bandingkan prediksi dengan observasi. Kurangi keyakinan ketika bukti bertentangan. Jangan memberi skor yakin tinggi hanya karena model memakai bahasa tegas.

### 13.8 Penggunaan pengalaman

Cari pengalaman yang relevan, periksa syarat berlakunya, gunakan jika cocok, dan perbarui catatan bila terjadi transfer negatif.

Simpan **jejak keputusan ringkas**: opsi yang dipilih, alasan yang dapat diperiksa, hasil alat, serta perubahan keputusan. Tidak perlu meminta atau menyimpan monolog internal tersembunyi provider. Teks reasoning yang panjang juga bukan pembuktian reasoning yang benar.

---

## 14. REASONING INTERNAL, MODEL LOKAL, DAN AI LUAR

Bedakan sumber kemampuan agar pengembangan tidak mengelabui kita sendiri.

| Lapisan | Tugas yang bisa diberikan | Cara membuktikan kontribusinya |
| --- | --- | --- |
| Algoritma ACE | Prioritas, state, dekomposisi tertentu, pencarian, validasi | Jalankan dengan provider dimatikan |
| Solver simbolik | Constraint, pencarian AST, sintesis berbatas | Tampilkan kandidat dan counterexample yang dapat diulang |
| Model lokal | Bahasa, usulan kode, interpretasi, ringkasan | Putus akses remote dan jalankan inferensi nyata |
| Memori ACE | Pengambilan pengalaman dan prosedur | Bandingkan dengan memori dimatikan pada tugas berbeda |
| AI host atau remote | Bantuan reasoning, diagnosis, usulan patch | Catat provider dan asal usulan |
| Gabungan sistem | Menyelesaikan tugas menyeluruh | Periksa hasil akhir dan ablation komponennya |

“Internal” dapat berarti dihitung di perangkat, keputusan orkestrator ACE, atau bobot model yang benar-benar dilatih. Gunakan istilah yang spesifik.

ACE boleh memakai model pralatih lokal. Ia tidak harus melatih foundation model dari nol untuk memiliki percakapan dan coding offline. Pemakaian model lokal tidak otomatis menjadi penemuan kecerdasan baru oleh ACE.

Kemampuan keseluruhan ACE tetap dapat meningkat melalui alat, memori, strategi, dan integrasi tanpa perubahan bobot. Sebut mekanismenya secara jujur.

---

## 15. PILIH METODE REASONING SESUAI MASALAH

Sediakan strategi yang dapat dipilih, bukan satu rantai prompt untuk semua situasi.

1. **Direct solve:** untuk permintaan sederhana dengan konteks cukup.
2. **Plan-and-execute:** untuk pekerjaan beberapa langkah yang dependensinya jelas.
3. **Hypothesis-and-test:** untuk debugging dan diagnosis.
4. **Bounded search:** untuk beberapa kandidat solusi dengan evaluator murah.
5. **Constraint reasoning:** untuk kebutuhan yang memiliki syarat logis atau struktural.
6. **Counterexample-guided refinement:** untuk memperbaiki kandidat setelah ditemukan contoh kegagalan.
7. **Analogy transfer:** untuk memanfaatkan pengalaman yang syaratnya mirip.
8. **Research-then-act:** untuk API, teknik, atau konsep yang belum dikenal.
9. **Prototype-first:** untuk permintaan besar yang perlu versi minimum berjalan.
10. **Ask-and-continue:** untuk satu informasi penting yang belum diketahui sambil mengerjakan bagian lain.

Tidak semua strategi harus tersedia pada rilis awal. Buat registry strategi dan implementasikan yang paling relevan dengan masalah nyata terlebih dahulu.

Untuk pencarian kandidat, batasi wall-time, jumlah ekspansi, ukuran kandidat, serta penggunaan memori. Dedup kandidat yang ekuivalen secara sintaksis atau perilaku pada contoh yang sudah diketahui.

Untuk solver yang membutuhkan native dependency berat, sediakan fallback yang lebih kecil atau jadikan fitur opsional. Jangan membuat percakapan dan coding dasar bergantung pada instalasi solver kompleks.

Jika strategi membutuhkan 10 pemanggilan model tetapi satu pemeriksaan runtime cukup, lakukan pemeriksaan runtime.

---

## 16. KETIDAKPASTIAN, KEYAKINAN, DAN BUKTI

Pisahkan:

- Hal yang dilihat langsung.
- Hasil pengukuran.
- Hasil pengujian.
- Pernyataan dokumentasi.
- Usulan model.
- Asumsi sementara.
- Hal yang belum diketahui.

Untuk keputusan penting, simpan asal informasi dan masa berlakunya. Pengetahuan API dapat menjadi usang; keadaan file berubah setelah patch; status provider berubah setelah kuota habis.

Keyakinan awal boleh berupa kategori sederhana. Bila menggunakan angka probabilitas, kalibrasi pada data hasil nyata sebelum menafsirkannya sebagai peluang berhasil.

Gunakan uncertainty untuk memilih tindakan: baca file yang belum diketahui, jalankan reproduksi, cari dokumentasi, buat prototype, atau ajukan pertanyaan yang tepat.

Ketidakpastian tidak harus menghentikan eksperimen yang dapat dipulihkan. Pisahkan tahap eksplorasi dari tahap mengaktifkan hasil bagi pengguna.

Jika dugaan terbantahkan, simpan pembaruan itu. Hindari mengganti penjelasan tanpa mengakui bukti yang mengubahnya.

---

## 17. ANTI-STUCK: ACE HARUS TAHU KAPAN MENGGANTI PENDEKATAN

Implementasikan deteksi stagnasi pada tugas dan pada pengembangan dirinya.

Indikator awal:

- Error yang sama berulang tanpa observasi baru.
- Patch yang secara substansi sama dihasilkan berkali-kali.
- Rencana dibangun ulang tanpa satu tindakan yang memberi hasil.
- Pemanggilan provider berulang dengan konteks yang tidak berubah.
- Waktu dan token bertambah tetapi hipotesis tidak menyempit.
- Semua usaha gagal karena dependency atau izin yang sama.
- ACE terus memilih tugas termudah untuk menghindari tujuan utama.

Gunakan fingerprint yang relevan: kelas error, lokasi, signature gejala, hash patch, versi lingkungan, strategi, dan hasil evaluator. Perubahan whitespace atau kata-kata respons tidak dihitung sebagai pendekatan baru.

### 17.1 Tangga pivot

Saat stagnasi terdeteksi, pilih salah satu tindakan yang beralasan:

1. Tinjau ulang tujuan dan batasan.
2. Buat reproduksi yang lebih kecil.
3. Periksa asumsi yang paling mungkin salah.
4. Baca lokasi sumber atau dependency yang belum diperiksa.
5. Ganti metode debugging.
6. Cari atau baca dokumentasi lokal.
7. Ganti backend model jika tersedia dan memang relevan.
8. Ubah representasi masalah atau pecah submasalah.
9. Kerjakan gap keterampilan yang menghambat.
10. Kembalikan eksperimen gagal dan mulai kandidat berbeda.
11. Kerjakan bagian independen dari tujuan.
12. Tunda submasalah dengan alasan dan kondisi kapan dicoba lagi.

Kegagalan tiga kali tidak harus mematikan seluruh ACE. Batasi dan alihkan tugas yang macet; pertahankan antarmuka, tugas lain, serta konteks pemulihan.

Gunakan default yang dapat dituning berdasarkan data. Contohnya dua atau tiga hasil setara dapat memicu pivot. Ini hipotesis pengaturan awal, bukan aturan universal.

### 17.2 Progres yang sah

Progres mencakup fitur berjalan, penyempitan akar masalah, hipotesis yang terbantahkan, dependency yang berhasil disiapkan, atau keterampilan baru yang teruji. Membuat log “masih mencoba” bukan progres.

---

## 18. SAAT BELUM BISA, UBAH MENJADI PEKERJAAN BELAJAR

Ajarkan pola berikut pada ACE:

**Belum bisa → identifikasi gap → cari sumber → eksperimen kecil → evaluasi → simpan pelajaran → coba kembali tugas asli.**

Klasifikasikan “belum bisa”:

| Penyebab | Respons yang produktif |
| --- | --- |
| Tidak paham permintaan | Ambil konteks atau klarifikasi inti |
| Tidak mengenal API | Baca dokumentasi atau contoh versi yang dipakai |
| Tidak punya model bahasa lokal | Siapkan backend yang layak atau jelaskan cakupan fallback |
| Tidak punya dependency | Cari dependency lokal, paket gratis yang sesuai, atau implementasi ringan |
| Terhalang RAM atau CPU | Kurangi konteks, ukuran model, batch, concurrency, atau scope prototype |
| Tidak tahu algoritma | Pelajari dasar dan uji pada contoh kecil |
| Patch terus gagal | Perbaiki diagnosis, ganti strategi, atau kumpulkan bukti baru |
| Tugas terlalu besar | Buat irisan fungsi yang berguna |
| Butuh informasi pribadi pengguna | Tanyakan informasi tersebut secara terarah |
| Secara prinsip belum terpecahkan | Rumuskan hipotesis dan eksperimen, jangan menjanjikan hasil pasti |

Satu pekerjaan belajar harus memiliki tujuan, sumber, latihan, batas sumber daya, dan tes penerapan. Jangan membaca terus-menerus tanpa kembali mengerjakan tugas awal.

Ketika offline, pelajari dari source lokal, dokumentasi yang sudah tersedia, contoh, eksperimen interpreter, serta pengalaman sebelumnya. Jika pengetahuan baru membutuhkan internet yang tidak tersedia, simpan kebutuhan spesifik dan lanjutkan bagian yang bisa dikerjakan.

Jangan melatih kebiasaan menjawab “tidak bisa” tanpa memeriksa jalur lain. Namun jangan mengubah keterbatasan nyata menjadi janji mustahil. Jawaban yang berguna menjelaskan apa yang sudah dicoba dan langkah belajar berikutnya.

---

## 19. BELAJAR DARI KESALAHAN TANPA MENYIMPAN KESALAHAN SEBAGAI KEBENARAN

Saya mengizinkan ACE salah dalam proses belajar. Bangun mekanisme untuk memperbaikinya.

Untuk kesalahan penting, catat:

1. Tujuan yang sedang dikerjakan.
2. Asumsi atau keputusan yang salah.
3. Kondisi ketika kegagalan terjadi.
4. Bukti bahwa hasilnya salah.
5. Penyebab yang terkonfirmasi atau masih diduga.
6. Koreksi yang dicoba.
7. Hasil koreksi.
8. Pelajaran yang mungkin berlaku.
9. Kondisi ketika pelajaran itu tidak boleh dipakai.
10. Tugas lain untuk menguji apakah pelajaran bertahan.

Kegagalan bernilai sebagai **contoh negatif**, counterexample, atau pembatas penerapan. Jangan memasukkan kode gagal ke library skill aktif hanya karena sudah disimpan.

Koreksi pengguna dapat memperbarui tujuan atau preferensi. Klaim faktual yang belum terverifikasi tetap memiliki provenance; jangan menganggap setiap ucapan atau setiap jawaban AI sebagai fakta permanen.

Contoh: ACE salah menganggap semua input kosong harus menghasilkan nol. Setelah mengetahui kebutuhan sesungguhnya, pelajarannya adalah memeriksa kontrak input kosong pada fungsi terkait, bukan menerapkan “input kosong selalu error” di seluruh proyek.

Evaluasi perbaikan dengan kasus baru yang sekeluarga, kasus yang sengaja berbeda, dan kemampuan lama yang mungkin terpengaruh.

---

## 20. MEMORI JANGKA PANJANG DAN KONTINUITAS

Bangun lapisan memori yang jelas secara tanggung jawab, meskipun awalnya berada dalam satu database:

1. **Percakapan:** pesan relevan, rujukan artefak, koreksi dan preferensi.
2. **Memori kerja:** tujuan aktif, konteks yang sedang dipakai, langkah berikut.
3. **Episodik:** kejadian, percobaan, hasil, dan kegagalan.
4. **Pengetahuan:** fakta terverifikasi beserta sumber dan versi.
5. **Prosedural:** strategi atau prosedur yang bisa dipakai kembali.
6. **Self-model:** kemampuan, backend, resource, batas, dan riwayat performa ACE.
7. **Agenda:** pekerjaan tertunda, prioritas, dependensi, dan kondisi melanjutkan.

Gunakan retrieval yang mempertimbangkan relevansi, kemutakhiran, bukti, biaya konteks, dan syarat penerapan. Jangan memasukkan seluruh riwayat ke setiap prompt.

Ringkas percakapan ketika konteks penuh, tetapi pertahankan keputusan pengguna, batasan, ID tugas, file penting, error terakhir, strategi yang gagal, dan aksi berikutnya.

Sediakan koreksi dan penghapusan memori yang diminta pengguna. Redaksi secret sebelum penyimpanan. Jangan mengubah semua data pribadi menjadi corpus pembelajaran.

Memori berbentuk teks bisa berguna dan harus diuji manfaatnya. Ia tidak otomatis menjadi keterampilan coding baru. Bedakan memori reflektif, prosedur yang dapat dieksekusi, perubahan planner, dan pembelajaran bobot.

---

## 21. KETERAMPILAN YANG DAPAT DIPAKAI ULANG

Untuk keberhasilan yang berpotensi berulang, ekstrak skill yang mempunyai:

- Identitas dan versi.
- Deskripsi tujuan.
- Input dan output.
- Syarat penerapan.
- Prosedur atau implementasi.
- Dependency.
- Contoh positif dan negatif.
- Pemeriksaan hasil.
- Asal pembelajaran.
- Statistik keberhasilan dan kegagalan.
- Biaya penerapan.
- Status eksperimental, aktif, atau dicabut.

Contoh bentuk skill: prosedur diagnosis error impor, pola AST transform yang teruji, workflow membuat CLI sederhana, strategi memilih tes yang relevan, atau cara memulihkan tugas yang terputus.

Promosi skill dilakukan setelah manfaatnya terlihat pada contoh di luar contoh pembuatannya. Skala pemeriksaannya mengikuti dampak. Skill yang baru lulus satu fixture tetap diberi cakupan terbatas.

Pada pemakaian ulang, periksa precondition dan versi dependency. Jika tidak cocok, jangan dipaksakan. Jika terjadi transfer negatif, kurangi prioritas, perbaiki syarat, atau nonaktifkan skill.

Jangan mengeksekusi teks memori sebagai kode secara otomatis. Skill executable harus melewati jalur penerimaan kode, memiliki sumber yang jelas, dan dijalankan dengan izin yang sesuai.




## 22. MULTI-MODEL DAN MULTI-PROVIDER YANG BENAR-BENAR BEKERJA

Buat satu kontrak provider yang dapat diimplementasikan berbagai backend. Adapter tidak harus memakai library besar jika HTTP atau CLI sederhana cukup.

Kemampuan yang perlu dideskripsikan provider:

- Identitas backend dan model yang diketahui.
- Sifat lokal atau remote.
- Bahasa yang didukung berdasarkan pengujian.
- Ukuran konteks yang benar-benar tersedia.
- Streaming.
- Structured output.
- Tool calling native atau kebutuhan fallback.
- Batas waktu, pembatalan, dan retry.
- Penggunaan token bila dilaporkan.
- Biaya, kuota, serta status jika tidak diketahui.
- Batas privasi dan data yang boleh dikirim.
- Hasil health check terakhir.

Antarmuka konseptual:

~~~python
class ModelBackend:
    def capabilities(self): ...
    def health(self): ...
    def generate(self, request, cancellation): ...
    def close(self): ...
~~~

Ini kontrak rancangan; cocokkan async, streaming, dan tipe data dengan implementasi yang sudah ada.

### 22.1 Routing

Pilih backend berdasarkan kemampuan untuk tugas tersebut, kualitas terukur, latensi, biaya, ketersediaan, ukuran konteks, dan preferensi offline.

Jangan selalu memanggil model terbesar. Jangan menganggap model terkecil mampu seluruh tugas hanya karena lebih hemat.

Sediakan circuit breaker untuk backend yang error, timeout, tidak terautentikasi, atau kuotanya habis. Retry dibatasi dan disesuaikan kelas error. Jangan mengulang autentikasi gagal puluhan kali.

Jika biaya atau kuota tidak dilaporkan, catat UNKNOWN. Jangan menulis nol biaya hanya karena field usage kosong.

### 22.2 Akun yang sudah dimiliki

Periksa akses yang sah. Langganan aplikasi konsumen seperti ChatGPT Plus atau Gemini Pro tidak otomatis membuktikan tersedianya kredit API atau akses programatik.

Gunakan API, CLI, plugin, atau integrasi host yang benar-benar tersedia. Jangan mengasumsikan akses model dari nama paket, file environment, atau status login saja.

Jangan mengambil cookie, menyalin sesi privat, atau mengakali otorisasi untuk membuat integrasi seolah tersedia. Jika jalur programatik tidak ada, gunakan kemampuan host yang memang disediakan atau teruskan lewat model lokal.

---

## 23. BRIDGE ACE ↔ ANTIGRAVITY: ACE HARUS DAPAT MEMANDU AI HOST

Ini kebutuhan inti, bukan tambahan opsional untuk dokumentasi.

Saat ACE dijalankan di lingkungan yang memiliki AI kuat seperti Antigravity, ACE harus dapat:

1. Menilai keadaan dirinya.
2. Menemukan gap yang menghambat tujuan.
3. Menentukan pekerjaan perbaikan berikutnya.
4. Menyusun work order yang lengkap.
5. Mengirim work order melalui jalur host yang nyata.
6. Menerima hasil, patch, catatan, atau kegagalan.
7. Memverifikasi hasil di workspace.
8. Menerima, menolak, atau meminta revisi.
9. Menyimpan pelajaran dan memilih pekerjaan berikutnya.

Dengan demikian ACE memandu agenda dan menilai hasil. AI host membantu mengerjakan pekerjaan yang dipilih. Kendali tidak berhenti pada satu prompt manual dari pengguna.

### 23.1 Discovery bridge

Periksa apakah host menyediakan API, SDK, tool, extension, CLI headless, session task interface, atau mekanisme integrasi lain yang terdokumentasi dan dapat diuji.

Jangan mengarang “Antigravity SDK”, endpoint internal, perintah headless, model ID, atau kemampuan recursive tool invocation. Temukan dokumentasi dan lakukan handshake sederhana.

Jika host mendukung eksekusi hanya dari sesi agen aktif, implementasikan driver yang dipakai agen host selama sesi tersebut. Nyatakan batas lifecycle-nya. Sesi yang sudah ditutup tidak otomatis tetap menjalankan model.

### 23.2 Mekanisme universal cadangan

Jika tidak ada antarmuka native yang cocok, buat kontrak bridge milik ACE, misalnya:

- JSON Lines melalui stdin/stdout untuk worker yang dapat dipanggil.
- Request dan result dalam antrean lokal yang dipantau worker host.
- Endpoint lokal dengan autentikasi untuk integrasi yang memerlukan HTTP.

Kontrak ini milik ACE, bukan klaim API resmi Antigravity.

Antrean file baru merupakan transport. Ia menjadi bridge otomatis setelah ada consumer nyata yang mengambil request, menjalankan pekerjaan, mengirim hasil, dan diuji putaran penuhnya.

Jika consumer otomatis tidak dapat dibangun pada host tersebut, tandai batasnya secara jujur, gunakan fallback yang tersedia, dan selesaikan komponen lainnya. Jangan mengklaim auto-bridge hanya karena file request berhasil ditulis.

### 23.3 Uji bridge minimum

ACE mengidentifikasi satu perbaikan kecil, mengirim work order, host menyelesaikan kandidat, ACE memeriksa kandidat, lalu ACE memperbarui agenda tanpa pengguna mengetik instruksi lanjutan.

Uji juga penolakan hasil stale, request yang sama terkirim ulang, timeout, pembatalan, dan host yang berhenti di tengah tugas.

---

## 24. KONTRAK WORK ORDER DAN PENGEMBALIAN HASIL

Work order harus cukup lengkap agar AI pelaksana tidak mengerjakan masalah yang berbeda.

Minimal berisi:

- ID request, task, dan parent task.
- Tujuan pengguna yang dilayani.
- Masalah atau gap yang ditemukan.
- Snapshot source atau hash file dasar.
- Fakta dan bukti kegagalan.
- Hipotesis yang sudah dicoba.
- Perubahan yang diinginkan.
- Cakupan file dan lingkungan yang boleh disentuh.
- Kriteria selesai.
- Alat dan dependency yang tersedia.
- Batas waktu, biaya, dan sumber daya.
- Asal dan versi kebijakan otorisasi.
- Bentuk hasil yang diharapkan.
- Kondisi membatalkan atau mengembalikan tugas.
- ID idempotensi dan tenggat berlaku.

Hasil host memuat status, perubahan aktual, hash dasar, hash hasil atau patch, pemeriksaan yang benar-benar dijalankan, log ringkas, keterbatasan, serta saran langkah berikut.

ACE memvalidasi skema dan konteks hasil. Usulan yang diterapkan pada dasar file berbeda harus direkonsiliasi sebelum diterima.

### 24.1 Hindari recursion yang tidak produktif

Work order tidak boleh meminta host sekadar menghasilkan work order identik berikutnya. Tetapkan penerima, keluaran konkret, kedalaman delegasi, dan anggaran kumulatif.

Agen pelaksana tidak dapat memberi dirinya otorisasi baru melalui teks hasil. Proposal model adalah data yang harus dievaluasi oleh kendali ACE.

### 24.2 Pertahankan atribusi

Catat secara terpisah siapa yang:

- Memilih pekerjaan.
- Menghasilkan hipotesis atau patch.
- Menjalankan alat.
- Memeriksa hasil.
- Mengintegrasikan perubahan.

Jika Antigravity menulis kode, tulis demikian. Jika ACE kemudian menjalankan prosedur itu sendiri, buktikan dengan runtime berikutnya.

---

## 25. OFFLINE HARUS MENJADI JALUR PRODUK UTAMA

Saya ingin dapat mematikan internet lalu tetap berbicara kepada ACE dan menyuruhnya mengerjakan coding lokal.

Bangun setidaknya dua profil yang diberi nama dengan jujur:

### 25.1 Offline dengan model bahasa lokal

Model dan tokenizer tersedia di perangkat, runtime inferensi berjalan, alat coding lokal tersedia, serta dependency tugas sudah disiapkan.

Profil ini harus dapat memahami beberapa permintaan Indonesia yang belum ditulis sebagai template, merespons percakapan, membuat atau mengubah kode, menjalankan pemeriksaan, dan menyimpan hasil.

Cakupan serta kualitasnya ditentukan pengujian model dan perangkat. Jangan menjanjikan kesetaraan Antigravity pada seluruh masalah.

### 25.2 Offline tanpa model bahasa lokal

Gunakan prosedur deterministik, retrieval lokal, skill yang sudah diterima, dan kontrol terstruktur yang tersedia.

Profil ini tetap berguna untuk operasi tertentu, tetapi jangan menyebutnya pemahaman bahasa bebas jika hanya parser dan template yang bekerja.

Tampilkan perbedaan kemampuan kedua profil. Jika model lokal belum tersedia, kerjakan pemasangannya ketika sumber daya memungkinkan; jangan mengakhiri pekerjaan dengan fallback terbatas tanpa mencatat gap yang belum selesai.

### 25.3 Persiapan ketika online

Model, dependency, dokumentasi pilihan, dan asset dapat diunduh saat koneksi tersedia. Simpan sumber, versi, checksum, ukuran, serta lisensinya. Sesuaikan download dengan storage dan batas yang berlaku.

Sesudah persiapan, runtime offline tidak boleh diam-diam mengunduh tokenizer, memanggil embedding remote, memuat CDN, mencari update, mengirim telemetry, atau memakai dependency yang baru akan diambil saat task berjalan.

Offline bukan berarti paket dapat diinstal dari internet yang dimatikan. Bedakan persiapan, inferensi, dan eksekusi tugas.

---

## 26. PEMILIHAN MODEL LOKAL DAN ANGGARAN PERANGKAT

Ukur perangkat sebelum menentukan model.

Jangan menebak kapasitas RAM fisik dari nama Redmi 14C atau menyamakan fitur perluasan RAM dengan RAM cepat untuk inferensi. Periksa arsitektur, CPU feature, memori yang tersedia, storage, dan kondisi runtime.

Gunakan model berlisensi sesuai kebutuhan, dengan format dan runtime yang didukung. llama.cpp merupakan salah satu kandidat jalur Android/Termux; cek versi dan panduan resmi pada waktu implementasi. Adapter harus memungkinkan backend lain.

Rentang model kecil, misalnya sekitar 0,5B–3B parameter, boleh menjadi ruang eksperimen awal jika perangkat mendukung. Rentang ini bukan rekomendasi bahwa semuanya muat atau cukup baik. Pilih berdasarkan hasil nyata, termasuk kemampuan Indonesia dan coding.

### 26.1 Anggaran memori

Perhitungkan:

~~~text
Memori total perkiraan =
  bobot terkompresi
  + metadata dan buffer runtime
  + KV cache
  + konteks dan output
  + proses ACE
  + proses pengujian atau build
  + ruang bagi Android dan aplikasi lain
~~~

Bobot 4-bit memiliki batas bawah kasar setengah byte per parameter sebelum overhead. Angka itu bukan kebutuhan RAM total.

KV cache dipengaruhi jumlah layer, panjang konteks, jumlah KV head, dimensi head, dan presisi penyimpanan. Jangan memilih konteks panjang hanya karena model mengizinkannya.

### 26.2 Uji kualitas dan performa

Ukur:

- Waktu memuat model.
- Waktu sampai respons pertama.
- Kecepatan prompt processing dan generation.
- Peak RSS atau ukuran memori yang dapat diukur.
- Keberhasilan memahami instruksi Indonesia.
- Validitas keluaran terstruktur.
- Keberhasilan tugas coding.
- Ketahanan setelah beberapa tugas.
- Dampak panas, baterai, dan proses bersamaan jika dapat diukur.

Jika sensor tidak dapat dibaca, catat tidak tersedia. Jangan mengarang angka suhu atau energi.

Turunkan konteks, output, thread, batch, concurrency, atau ukuran model bila perlu. Batasi panjang prompt dengan retrieval yang tepat. Pertahankan cadangan memori untuk menjalankan kode yang dihasilkan.

### 26.3 Jangan menghalangi kemampuan bahasa terlalu lama

Model lokal bukan sekadar filter jika kebutuhan produk adalah percakapan offline. Uji apakah ia dapat mengisi peran bahasa, planner terbatas, dan generator kode untuk cakupan awal. Jika hanya peran tertentu layak, atur pembagian kerja berdasarkan bukti.

---

## 27. TOOL CALLING UNTUK MODEL YANG KEMAMPUANNYA TERBATAS

Backend yang mendukung tool calling native dapat memakainya setelah diuji dengan template dan versi yang benar.

Jika tidak, gunakan keluaran terstruktur yang dibatasi skema, misalnya satu action per giliran:

~~~json
{
  "action": "read_file",
  "arguments": {
    "path": "src/example.py",
    "start_line": 1,
    "line_count": 80
  }
}
~~~

Validasi nama action, tipe argumen, cakupan path, dan batas ukuran. Jangan mengeksekusi JSON yang tidak valid atau teks bebas sebagai shell.

Jika output malformed, lakukan perbaikan format yang terbatas atau minta generasi ulang dengan pesan error yang spesifik. Jangan membuat loop format tanpa batas.

Untuk model kecil, sederhanakan pilihan alat, kirim hasil yang ringkas, batasi konteks, dan gunakan prosedur ACE untuk langkah deterministik. Misalnya planner ACE mengatur tahap, sementara model mengusulkan satu patch dengan konteks yang relevan.

Setiap tool result kembali ke loop dengan status dan observasi aktual. Jangan mengisi hasil tool memakai teks yang diprediksi model.

---

## 28. CODING OTONOM: ALUR PENUH YANG WAJIB TERHUBUNG

Bangun workflow yang dapat menerima bug, fitur baru, refaktor yang diminta, atau pembuatan proyek kecil.

### 28.1 Intake

Pahami permintaan, cakupan, lingkungan, dependency, dan hasil yang diharapkan. Buat kriteria selesai yang sesuai tujuan.

### 28.2 Pemahaman kode

Baca struktur proyek dan bagian yang relevan. Temukan entrypoint, fungsi, data, konfigurasi, serta tes yang berkaitan.

### 28.3 Diagnosis atau desain

Untuk bug, usahakan reproduksi dan isolasi akar masalah. Untuk fitur baru, buat kontrak perilaku dan rancang implementasi minimum. Fitur baru tidak harus melewati syarat “bug harus direproduksi” yang tidak relevan.

### 28.4 Implementasi kandidat

Terapkan perubahan yang paling langsung menyelesaikan masalah. Pilih patch terarah atau file baru sesuai kebutuhan. Simpan dasar perubahan dan kemampuan rollback.

### 28.5 Pemeriksaan

Jalankan pemeriksaan yang relevan: parse, compile, lint jika tersedia, tes perilaku, contoh penggunaan, serta regresi pada area terdampak.

### 28.6 Revisi

Gunakan error aktual untuk memperbaiki kandidat. Ketika pendekatan berulang gagal, gunakan mekanisme pivot.

### 28.7 Penyelesaian

Pastikan artefak ada dan dapat dijalankan. Integrasikan sesuai otorisasi, laporkan hasil, lalu simpan pelajaran yang berguna.

### 28.8 Perpanjang kemampuan

Setelah alur Python stdlib berhasil, perluas bahasa dan jenis proyek berdasarkan kebutuhan pengguna. Jangan mengklaim mendukung semua bahasa karena dapat menulis file teks.

Kemampuan menulis kode, menjalankan kode, memeriksa hasil, dan mengintegrasikan perubahan harus dapat diuji secara terpisah.

---

## 29. REPOSITORY INTELLIGENCE DAN CONTEXT ENGINEERING

Gunakan gabungan pencarian nama, teks, simbol, dan hubungan dependensi.

Mulai dengan alat ringan yang tersedia: ripgrep, git, Python AST, dan pembacaan potongan file. Tree-sitter, embeddings lokal, atau indeks lebih besar ditambahkan jika manfaatnya terbukti.

Persyaratan:

1. Hormati cakupan workspace dan ignore yang relevan.
2. Hindari binary besar, cache, virtualenv, dan direktori dependency yang tidak diperlukan.
3. Simpan lokasi sumber dan hash atau versi indeks.
4. Invalidasi hasil ketika file atau dependency berubah.
5. Ambil implementasi, pemanggil, kontrak, dan tes yang relevan.
6. Batasi ukuran konteks dan output tool.
7. Jangan membaca secret sebagai konteks model.
8. Jangan mengeksekusi source hanya untuk mengindeks struktur statisnya.
9. Tampilkan error retrieval secara jelas.
10. Kembalikan hasil yang dapat ditelusuri ke file aktual.

Untuk percakapan tentang keadaan ACE, prioritaskan keadaan runtime, task store, dan source yang dipakai. Jangan menjawab berdasarkan ringkasan historis saja.

Embedding remote tidak boleh menjadi ketergantungan wajib mode offline. Retrieval lexical yang berfungsi lebih baik daripada semantic search yang selalu membutuhkan jaringan.

---

## 30. ALAT LINGKUNGAN: KEMAMPUAN AKTUAL DAN HASIL TERSTRUKTUR

Sediakan alat sesuai kebutuhan, dengan registry dan kontrak yang stabil:

| Kelompok | Operasi awal |
| --- | --- |
| File | Cari, baca potongan, tulis, patch, periksa hash |
| Source | Indeks simbol, cari referensi, lihat diff |
| Eksekusi | Jalankan program, build, compiler, dan tes |
| Proses | Status, pembatalan, penghentian proses milik tugas |
| Repository | Status, branch atau worktree, commit, merge yang diotorisasi |
| Pengetahuan | Baca dokumentasi lokal dan riset online jika diizinkan |
| Model | Health check, inferensi, pembatalan, dan penggunaan |
| Runtime | Status tugas, resource, checkpoint, dan resume |
| Pembelajaran | Catat pengalaman, cari skill, validasi skill |
| Bridge | Kirim work order, terima hasil, dan rekonsiliasi |

Tool request memiliki ID, task, argumen tervalidasi, timeout, cakupan, dan idempotency key bila relevan. Tool result memiliki status, exit code bila ada, output terbatas, durasi, serta referensi artefak.

Gunakan subprocess dengan argumen terpisah ketika memungkinkan. Jangan menyisipkan teks pertanyaan pengguna langsung ke shell. Shell tetap boleh dipakai melalui executor yang jelas ketika diperlukan untuk workflow, dengan cwd dan lingkungan yang sesuai.

Pisahkan batas kenyamanan dari isolasi keamanan. Worktree, virtualenv, proot, pembatasan path dalam Python, dan subprocess timeout tidak dengan sendirinya menjadi sandbox kuat untuk kode bermusuhan.

Di Termux, jalankan tugas lokal yang tepercaya dalam cakupan yang sesuai dan akui tingkat isolasinya. Jika eksperimen memerlukan isolasi lebih kuat yang tidak tersedia, kerjakan bagian statis atau gunakan runner yang memang menyediakan isolasi ketika online.

Jangan membuat dependency Docker atau GPU wajib untuk coding sederhana di HP.




## 31. PATCH YANG TEPAT DAN PERLINDUNGAN PEKERJAAN YANG SUDAH ADA

Sebelum mengubah file, ketahui dasar perubahan. Gunakan hash, versi repository, atau konteks yang cukup untuk menolak patch stale.

Jika konteks berubah, baca ulang dan susun patch baru. Jangan memaksa fuzzy matching yang ambigu pada file penting.

Tulis perubahan secara atomik jika memungkinkan. Catat file yang diubah oleh task dan hasil pemeriksaan setelah perubahan.

Jangan memakai reset menyeluruh, penghapusan direktori, atau clean terhadap workspace yang berisi pekerjaan pengguna atau agen lain. Rollback hanya perubahan milik task atau gunakan salinan kerja terpisah.

Ketika beberapa task menyentuh file yang sama, serialisasikan commit efek atau rekonsiliasi patch secara eksplisit. Jangan menyebut dua proses aman hanya karena masing-masing mempunyai branch.

Untuk workspace tanpa git, sediakan snapshot file dasar dan staging perubahan. Integrasikan setelah pemeriksaan, dan pertahankan manifest versi yang dapat dipulihkan.

---

## 32. VERIFIKASI YANG MELAYANI HASIL, BUKAN RITUAL

Pemeriksaan harus sebanding dengan perubahan. Selama implementasi, gunakan cek ringan yang membantu menyelesaikan pekerjaan. Kumpulkan pemeriksaan integrasi dan audit rilis di akhir paket operasional sesuai Lampiran U; tabel berikut adalah pilihan pemeriksaan, bukan perintah mengaudit penuh setiap langkah.

| Jenis perubahan | Pemeriksaan yang umumnya relevan |
| --- | --- |
| Teks atau tampilan kecil | Inspeksi hasil dan smoke check |
| Fungsi baru | Contoh perilaku, kasus batas, dan integrasi pemanggil |
| Bug | Bukti kegagalan awal bila memungkinkan, perbaikan, dan regresi terkait |
| State dan antrean | Restart, duplikasi pesan, pembatalan, dan konsistensi |
| Bridge AI | Request sampai result, timeout, stale result, retry |
| Backend offline | Inferensi nyata dan tugas tanpa remote |
| Lease dan penulisan lintas proses | Contention, stale owner, release lalu reacquire, crash |
| Self-update | Versi kandidat, aktivasi, smoke test, dan rollback |
| Klaim belajar | Tugas baru, pembanding, retensi setelah restart |
| Klaim transfer | Keluarga atau proyek berbeda dan kontrol yang sesuai |

Jangan menambahkan tes yang hanya menyalin implementasi atau sekadar menghitung file. Pilih tes yang dapat menangkap kegagalan pengguna.

Bedakan:

- Tes unit lulus.
- Modul terhubung.
- Workflow menyeluruh lulus.
- Berfungsi pada host pengembang.
- Berfungsi pada perangkat pengguna.
- Manfaat ilmiah terukur.

Semua ini status yang berbeda.

Tes yang dibuat pelaksana berguna tetapi belum otomatis independen. Reviewer yang memakai model dan konteks sama juga belum menjadi evaluator independen secara ilmiah.

Perubahan tes produk boleh dilakukan untuk menambah cakupan atau menyesuaikan kebutuhan yang memang berubah. Jangan menghapus assertion yang benar agar patch gagal terlihat lulus. Simpan evaluator eksperimen terpisah dari kandidat.

---

## 33. RUNTIME YANG TERASA HIDUP DAN TETAP RESPONSIF

Bangun loop operasional dengan event, antrean, scheduler, dan state persisten.

### 33.1 Jalur interaktif

Pesan pengguna, status, koreksi, dan berhenti mendapat prioritas tinggi. Jangan biarkan inferensi panjang membuat seluruh antarmuka tidak dapat merespons.

Sediakan streaming atau progress event yang jujur. Jika inference backend tidak dapat dibatalkan secara aman, tampilkan keadaan tersebut dan implementasikan batas proses yang sesuai.

### 33.2 Jalur pekerjaan

Task memiliki ID, status, langkah, artefak, resource budget, dan aksi berikut. Setiap kemajuan penting tercatat.

### 33.3 Jalur pembelajaran

Saat tidak ada pekerjaan mendesak, ACE dapat memilih gap yang relevan, menjalankan latihan, menguji hasil, dan menyimpan pelajaran.

### 33.4 Jalur kesehatan

Pantau error runtime, task yang macet, storage, dependency, provider, dan antrean. Pilih tindakan pemulihan yang dapat dilakukan tanpa pengguna.

### 33.5 Keadaan idle

Idle bukan kegagalan. Jika tidak ada pekerjaan bernilai atau resource tidak cukup, tunggu event dengan konsumsi rendah. Jangan membuat loop riset tanpa manfaat hanya agar tampilan terlihat aktif.

Pisahkan heartbeat, status sehat, progres pekerjaan, dan hasil pembelajaran. Heartbeat yang bertambah tidak menunjukkan kecerdasan bertambah.

---

## 34. ACE MEMILIH AGENDA DAN JALANNYA SENDIRI

Bangun agenda yang memadukan tujuan pengguna, kesehatan sistem, dan peluang peningkatan.

Sumber kandidat agenda:

- Permintaan pengguna yang belum selesai.
- Bug atau regresi yang terdeteksi.
- Hambatan yang berulang.
- Kemampuan yang paling sering dibutuhkan.
- Dependency yang gagal.
- Skill yang belum terverifikasi.
- Peluang menyederhanakan sistem.
- Pertanyaan riset yang dekat dengan gap kemampuan nyata.

Nilai kandidat dengan kriteria yang transparan dan dapat direvisi:

~~~text
Nilai tindakan mempertimbangkan:
  manfaat bagi tujuan pengguna
  + urgensi
  + peluang memberi progres
  + pengetahuan baru yang berguna
  + dampak pada tugas lain
  - biaya komputasi
  - ketergantungan yang belum tersedia
  - potensi regresi
  - pengulangan usaha tanpa informasi baru
~~~

Tidak perlu mengklaim rumus ini fungsi utility yang optimal. Mulai dengan aturan sederhana atau skor yang dapat dijelaskan, lalu evaluasi berdasarkan hasil.

### 34.1 Hindari agenda yang menyimpang

ACE boleh menentukan metode, subtujuan, dan prioritas dalam mandat. Jangan mengganti tujuan pengguna demi memperbanyak modul atau memaksimalkan metrik internal.

Berikan peluang pada pekerjaan penting yang sulit agar tidak terus kalah dari tugas mudah. Gunakan aging atau jatah eksplorasi bila dibutuhkan.

Pengguna selalu dapat mengoreksi arah, menghentikan, atau memberi prioritas baru. Memilih secara mandiri harus tetap membuat sistem berguna bagi pengguna.

### 34.2 Tunjukkan pilihan yang nyata

Secara berkala ACE bisa menjelaskan singkat:

“Saya memilih memperbaiki pemulihan tugas karena tiga pekerjaan sebelumnya terputus saat restart. Setelah itu saya menguji model lokal untuk percakapan.”

Penjelasan tersebut harus sesuai agenda dan tindakan aktual.

---

## 35. EKSPLORASI, KREATIVITAS, DAN PENCARIAN POTENSI BARU

Cari potensi dari bukti kesulitan dan kebutuhan, bukan hanya meniru daftar fitur sistem lain.

Prosedur awal:

1. Ambil pola kegagalan atau kebutuhan yang belum terpenuhi.
2. Rumuskan beberapa kemungkinan perbaikan.
3. Pilih eksperimen termurah yang dapat membedakan manfaat.
4. Buat prototype.
5. Ukur dampak terhadap tugas nyata.
6. Pertahankan, revisi, atau arsipkan berdasarkan hasil.
7. Catat kondisi kapan ide yang ditunda layak dicoba lagi.

Beri ruang untuk pendekatan yang tidak konvensional: representasi masalah baru, komposisi tool, pemilihan konteks yang berbeda, strategi pencarian, cara menyimpan pengalaman, atau kurikulum yang dibuat dari kegagalan.

Jangan membuang ide hanya karena berbeda dari roadmap awal. Jangan langsung mengaktifkan semua ide tanpa melihat fungsi dan kompatibilitasnya.

### 35.1 Portofolio eksplorasi awal

Porsi eksplorasi dapat ditetapkan sebagai sebagian kecil waktu atau resource setelah kebutuhan pengguna aktif terlayani. Persentasenya dipilih berdasarkan perangkat dan manfaat, bukan angka wajib.

Di perangkat kecil, satu eksperimen singkat lebih tepat daripada banyak model bersamaan. Pada host lebih kuat, jalankan eksperimen independen secara paralel jika tidak menambah konflik atau biaya.

### 35.2 Potensi dengan nilai tinggi

Pertimbangkan peningkatan pemahaman Indonesia, perbaikan repo map, pemilihan tes, skill debugging, mode proyek kecil, cache dokumentasi, pemulihan, belajar dari koreksi, dan efisiensi model sebelum menambah fitur spekulatif yang mahal.

---

## 36. SELF-IMPROVEMENT YANG BERUJUNG PADA KEMAMPUAN BARU

Bangun siklus pengembangan diri yang dapat dijalankan ACE:

1. Amati gap kemampuan atau ketidakandalan.
2. Buat tujuan perbaikan dan bukti awal.
3. Pilih metode: kode sendiri, pakai skill, model lokal, atau delegasi host.
4. Buat kandidat di salinan kerja atau staging.
5. Periksa perilaku dan regresi yang relevan.
6. Bandingkan manfaat dengan versi aktif.
7. Integrasikan kandidat yang layak.
8. Aktifkan versi baru pada batas proses yang aman.
9. Periksa kesehatan dan fungsi utama.
10. Pertahankan atau rollback.
11. Perbarui self-model dan agenda.

Jangan mengubah modul yang sedang dimuat di tengah critical section lalu menganggap perilaku proses otomatis mengikuti source baru.

Pertahankan bootstrap atau jalur pemulihan sederhana. Gunakan versi aktif dan versi kandidat, atau mekanisme setara yang memungkinkan kembali ke versi sebelumnya.

Migrasi state memiliki versi, cadangan, dan cara memeriksa kompatibilitas. Backup database tidak dilakukan dengan menyalin file utama SQLite secara sembarangan saat WAL aktif; gunakan mekanisme backup yang sesuai.

### 36.1 Pengembangan berjenjang

Mulai dari self-repair terbatas, kemudian peningkatan workflow, lalu komponen reasoning atau representasi. Semua jenis boleh diteliti, tetapi perubahan inti membutuhkan pemeriksaan lebih besar karena dampaknya luas.

Tidak perlu melarang selamanya perubahan pada evaluator, policy, atau state manager. Ketika memang komponen itu memiliki bug, lakukan perubahan sebagai task tersendiri dengan bukti dan pembanding yang relevan. Jangan membiarkan kandidat menilai dirinya dengan mengubah definisi keberhasilan di tengah eksperimen.

### 36.2 Bukti kemampuan sudah menetap

Setelah Antigravity selesai membantu, mulai ulang ACE dan minta ia menjalankan fitur tersebut melalui entrypoint normal. Jika masih membutuhkan Antigravity mengeksekusi setiap langkah, pekerjaan belum memenuhi sasaran retensi kemampuan.

---

## 37. INTEGRASI DAN MERGE OTOMATIS SESUAI MANDAT SAYA

Saya telah mengizinkan penambahan dan merge perubahan ACE yang layak. Jangan menutup setiap pekerjaan dengan permintaan persetujuan teknis yang sama.

Jika menggunakan repository:

1. Identifikasi target branch dan keadaan kerja aktual.
2. Kerjakan kandidat tanpa menimpa perubahan orang lain.
3. Jalankan pemeriksaan yang sesuai.
4. Rekonsiliasi target branch jika telah berubah.
5. Periksa hasil gabungan pada dasar yang relevan.
6. Buat commit dan PR bila workflow repository memakainya.
7. Lakukan merge menggunakan izin yang tersedia dan pemeriksaan yang disyaratkan.
8. Verifikasi perubahan masuk ke target yang benar.
9. Catat commit integrasi dan periksa runtime yang menggunakannya.

Tidak perlu membuat PR jika workflow lokal yang sah memang tidak memerlukannya. Jika proteksi branch mensyaratkan review yang tidak dapat dipenuhi otomatis, jangan menonaktifkannya; biarkan kandidat konkret siap integrasi dan laporkan hambatan spesifik.

Jika tidak ada repository:

- Terapkan perubahan melalui staging atau versi paket.
- Verifikasi hasil terintegrasi.
- Pertahankan versi sebelumnya.
- Catat manifest file dan versi aktif.

Merge bukan sinonim deploy, dan merge remote bukan bukti instalasi HP berubah. Pastikan jalur pembaruan runtime jelas dan sesuai lingkungan.

Jangan mengklaim CI sukses jika run masih antre, check hilang, check stale, atau sukses pada SHA berbeda. Jika hanya pemeriksaan lokal tersedia, tulis itu.

Perubahan yang gagal tidak dipaksa masuk untuk memenuhi target jumlah merge. Catat masalahnya dan lanjutkan perbaikan atau pekerjaan independen.

---

## 38. STATE, ANTREAN, LEASE, DAN CRASH RECOVERY

Gunakan penyimpanan yang sesuai dan dapat diuji. SQLite dapat menjadi pilihan awal yang ringan untuk task, event, memori, checkpoint, dan outbox pada satu perangkat.

Hal yang perlu dijamin sesuai skala implementasi:

- Transisi penting tidak hilang sebagian tanpa dapat direkonsiliasi.
- Dua worker tidak mengaktifkan efek perubahan yang sama secara bersamaan.
- Worker lama tidak boleh menulis setelah kepemilikannya digantikan.
- Restart dapat mengetahui pekerjaan yang sudah dan belum selesai.
- Request ulang tidak menggandakan efek yang sama tanpa pemeriksaan.
- State dapat dimigrasi dan dipulihkan.

### 38.1 Fencing dan serialisasi efek

Jika memakai lease lintas proses, alokasikan epoch meningkat dari counter persisten yang tidak dihapus saat lease dilepas.

Validasi identitas holder, resource, epoch, dan masa berlaku sesuai desain. Validasi lalu menulis file pada waktu terpisah memiliki celah race. Pastikan jalur penerapan efek ikut diserialisasi atau menolak owner lama pada titik commit.

Untuk filesystem yang tidak mendukung transaksi bersama database, gunakan satu commit worker, lock yang sesuai, staging atomik, atau prosedur rekonsiliasi yang diuji. Jangan mengklaim atomisitas lintas SQLite dan filesystem hanya karena keduanya memakai hash.

Satu worker adalah default yang wajar di HP. Jangan membuat sistem distributed lease kompleks jika tidak dibutuhkan. Namun uji juga dua instance ACE yang tidak sengaja dijalankan bersamaan.

### 38.2 Durabilitas

Pilih konfigurasi transaksi dan sinkronisasi sesuai kebutuhan. WAL membantu concurrency; ia tidak otomatis menjamin tidak ada transaksi terakhir hilang saat daya mati. Nyatakan toleransi dan uji kegagalan yang relevan.

Gunakan database di lokasi app-private yang sesuai, tangani disk penuh, timeout lock, dan migrasi yang terputus.

### 38.3 Efek eksternal

Untuk commit, merge, atau panggilan host yang sukses sebelum receipt tersimpan, lakukan pemeriksaan keadaan sebelum retry.

Outbox dan idempotency mengurangi duplikasi. Jangan menjanjikan exactly-once di layanan eksternal yang tidak menyediakan dukungannya.

---

## 39. TERMUX DAN ANDROID: REKAYASA BERDASARKAN PERANGKAT NYATA

Untuk HP, prioritaskan native Termux dengan dependency minimal. PRoot atau distro tambahan dipakai hanya bila manfaatnya jelas dan kompatibilitasnya diuji.

Periksa instalasi saat ini. Jangan meminta pengguna menginstal ulang aplikasi atau memindahkan seluruh proyek tanpa kebutuhan yang jelas.

Sediakan:

1. Pemeriksaan perangkat yang ringkas.
2. Instalasi atau pembaruan yang dapat diulang.
3. Jalur model lokal.
4. Command percakapan normal.
5. Mulai dan hentikan runtime.
6. Status tugas dan model.
7. Resume setelah proses berhenti.
8. Export atau backup state yang sesuai.
9. Troubleshooting spesifik berdasarkan error aktual.

Jangan menimpa HOME atau variabel sistem lain untuk membuat path proyek. Gunakan nama konfigurasi khusus seperti ACE_STATE_DIR atau ACE_WORKSPACE_DIR.

### 39.1 Keberlanjutan proses

Android dapat membunuh proses. Rancang checkpoint dan resume untuk kondisi tersebut.

tmux, wake lock, supervisor, atau integrasi boot dapat membantu pengalaman operasional jika tersedia. Jangan menjanjikan proses tidak pernah mati atau pekerjaan tetap berjalan setelah aplikasi di-force stop.

Tidak semua perangkat memberi akses sensor yang sama. Tool Termux API bersifat opsional jika tidak menjadi kebutuhan fungsi utama. Sediakan fallback yang jujur.

### 39.2 Setup dari terminal

Utamakan instruksi instalasi langsung yang sederhana dan mengikuti keadaan yang ditemukan. Jangan mewajibkan pengguna mengunggah ulang seluruh repository, mengunduh ZIP bolak-balik, atau mengetik blok panjang untuk setiap sesi.

Setelah bootstrap, operasi harian seharusnya cukup melalui satu entrypoint percakapan dan kontrol sederhana.

Jika pengujian dilakukan di mesin non-Android, tandai sebagai pengujian host tersebut. Emulasi atau cross-compile tidak sama dengan pembuktian pada HP pengguna.

---

## 40. ANTARMUKA HP YANG MUDAH DIPAKAI

Mulai dari CLI yang dapat digunakan dengan nyaman. Antarmuka web lokal dapat ditambah setelah alur dasar stabil.

Tampilan utama cukup memperlihatkan:

- Percakapan.
- Pekerjaan aktif.
- Hasil terbaru.
- Mode lokal, host, atau remote.
- Keadaan model.
- Tombol atau command berhenti dan lanjutkan.
- Hambatan yang benar-benar membutuhkan tindakan pengguna.

Detail internal seperti epoch, schema, hash, dan traceback berada di tampilan bukti atau debug, bukan memenuhi layar percakapan.

Jika ada web lokal:

- Bind localhost sebagai default.
- Asset tersedia lokal untuk mode offline.
- Dukungan stream progress bila layak.
- Pesan error dapat dimengerti.
- Tombol berhenti bekerja.
- Akses lintas perangkat memerlukan konfigurasi yang sesuai dan bukan default terbuka.

Saya memakai HP. Utamakan font terbaca, sedikit langkah, hasil yang bisa dibuka, dan instruksi singkat.

---

## 41. KURIKULUM PEMBELAJARAN YANG TERHUBUNG KEBUTUHAN

Bangun kurikulum dari gap nyata, bukan daftar pelajaran yang tidak pernah diterapkan.

Urutan awal yang masuk akal:

1. Memahami permintaan Indonesia.
2. Menggunakan alat file dan terminal secara tepat.
3. Membuat program stdlib kecil.
4. Menjalankan dan memeriksa program.
5. Mendiagnosis error umum.
6. Menangani pekerjaan beberapa file.
7. Mengingat dan memakai pengalaman.
8. Mengganti strategi saat gagal.
9. Memilih agenda perbaikan.
10. Mengembangkan komponen dirinya dengan pemulihan.

Setiap tahap memiliki contoh pengembangan, variasi baru, dan tes penerapan. Naikkan kesulitan berdasarkan kemampuan yang diperlihatkan.

### 41.1 Tiga bentuk pembelajaran

- **Pembelajaran melalui konteks dan memori:** pengalaman mengubah pilihan berikutnya.
- **Pembelajaran prosedur dan sistem:** skill, tool, planner, atau kode berubah.
- **Pembelajaran parameter:** bobot model benar-benar diperbarui.

Catat mekanisme yang digunakan. Jangan menamai semua bentuk itu fine-tuning.

### 41.2 Distilasi dan pelatihan lanjutan

Jika bermanfaat, kumpulkan contoh berkualitas dari tugas yang telah diverifikasi, dengan hak penggunaan yang sesuai dan tanpa secret.

SFT, LoRA, distilasi, atau metode lain menjadi eksperimen opsional ketika data dan komputasi cukup. Jangan membuatnya prasyarat percakapan offline, atau menjanjikan training model besar di HP.

Periksa manfaat terhadap baseline, forgetting, serta biaya keseluruhan. Gagal menunjukkan manfaat berarti strategi itu perlu diperbaiki atau ditunda, bukan seluruh proyek gagal.

---

## 42. OAIE: BANGUN JEMBATAN DARI PRODUK KE RISET

Definisikan kemajuan bertahap:

| Tahap | Capaian | Klaim yang diperbolehkan |
| --- | --- | --- |
| G0 | Sistem dasar yang mengerjakan tugas | Kemampuan awal terukur |
| G1 | Pengalaman tersimpan dan dipakai ulang | Retensi atau manfaat memori pada cakupan uji |
| G2 | Workflow atau skill baru membantu tugas berbeda | Transfer yang terukur |
| G3 | Sistem merancang dan menguji perbaikan dirinya | Self-improvement operasional |
| G4 | Representasi atau mekanisme baru dipelajari | Klaim novelty jika dibandingkan dan diuji memadai |
| Arah OAIE | Siklus terus menghasilkan kemampuan berguna lintas generasi | Bukti parsial evolusi terbuka sesuai cakupan studi |

Tahap ini kerangka kerja, bukan status ACE saat ini.

Bedakan pemanggilan kemampuan eksternal, konfigurasi operator lama, komposisi skill, penciptaan representasi, dan penemuan metode baru. Semua dapat berguna; jenis klaimnya berbeda.

Penelitian novelty harus memiliki pembanding seperti grammar tetap yang lebih kaya, strategi tetap yang kuat, tambahan compute, dan sistem tanpa memori. Jangan menyebut hasil luar biasa hanya karena mengalahkan baseline yang sengaja lemah.

Jika hasil negatif, simpan penjelasan dan counterexample. Gunakan untuk memilih riset berikut.

Operasionalisasi produk tetap berlanjut ketika hipotesis ilmiah belum terbukti. Klaim ilmiah tidak menjadi gerbang untuk setiap perbaikan UX.




## 43. PROTOKOL EVALUASI: BUKTIKAN SUMBER PENINGKATANNYA

Bandingkan kondisi yang sesuai dengan pertanyaan yang sedang diuji:

| Kondisi | Komponen aktif | Pertanyaan utama |
| --- | --- | --- |
| A | Algoritma dan skill deterministik, tanpa model dan tanpa remote | Apa yang memang dapat dikerjakan prosedur ACE? |
| B | ACE + model lokal, tanpa remote | Apa kemampuan offline berbasis model? |
| C | B + memori atau skill hasil pembelajaran | Apa manfaat retensi dibanding sistem tanpa pengalaman? |
| D | ACE + advisory AI luar | Apa manfaat bantuan AI ketika dipadukan orkestrasi ACE? |
| E | AI luar mengerjakan langsung dengan alat sebanding | Apa nilai tambah sistem ACE dibanding AI-led baseline? |

Untuk B dan C gunakan model yang sama jika menguji memori. Untuk D dan E samakan alat, tugas, serta anggaran sejauh masuk akal dan laporkan perbedaannya.

Hitung biaya belajar, indexing, percobaan gagal, waktu host, dan panggilan model. Jangan hanya menghitung percobaan akhir yang sukses.

Laporkan penyelesaian tugas, kebenaran hasil, false acceptance, coverage atau abstention, waktu, token, resource, dan kestabilan.

### 43.1 Pembagian tugas evaluasi

Pisahkan contoh pengembangan, validasi, dan evaluasi akhir. Jika kasus akhir telah dipakai memperbaiki implementasi, kasus itu menjadi data pengembangan; siapkan evaluasi baru untuk klaim berikutnya.

Fixture kecil berguna untuk debugging. Ia bukan bukti kemampuan coding umum.

Benchmark publik dapat dipakai sebagai pembanding sesuai harness resmi. Keterbatasan resource Termux dapat membuat harness tertentu tidak cocok dijalankan langsung. Mulai dari tugas lokal yang dapat diverifikasi, lalu perluas.

### 43.2 Klaim statistik

Tulis jumlah kasus, keberhasilan, kegagalan, variasi antar run, dan interval ketidakpastian bila relevan. Sampel kecil tidak boleh dipromosikan menjadi kesimpulan umum.

Signifikansi statistik dapat membantu penelitian, tetapi bukan satu-satunya ukuran manfaat produk. Jangan mengunci perbaikan sederhana di balik syarat p-value.

---

## 44. PENGUJIAN OFFLINE YANG TIDAK BISA DIPALSU DENGAN MOCK

Buat pengujian menyeluruh yang menjalankan backend lokal dan alat nyata.

Langkah minimum:

1. Siapkan model, dependency, dan asset sebelumnya.
2. Catat versi dan manifest artefak.
3. Nonaktifkan provider remote pada konfigurasi.
4. Terapkan pembatasan egress yang dapat dibuktikan jika host mendukung.
5. Izinkan hanya loopback bila backend model memakai server lokal.
6. Jalankan percakapan beberapa giliran dalam bahasa Indonesia.
7. Minta satu program baru dan satu perubahan terhadap program.
8. Jalankan hasilnya dan periksa output.
9. Mulai ulang ACE.
10. Lanjutkan konteks atau tugas yang disimpan.
11. Periksa log koneksi atau observasi jaringan yang tersedia.
12. Laporkan lingkungan dan batas pembuktian.

Mock provider berguna untuk tes kontrak tetapi tidak menggantikan inferensi lokal nyata.

Mengubah environment variable menjadi OFFLINE belum membuktikan tidak ada akses jaringan. Begitu juga cache respons lama yang diputar ulang belum membuktikan pemahaman permintaan baru.

Jika host tidak dapat memblokir egress, gunakan observasi yang tersedia dan tulis tingkat kepastian yang sesuai. Pengujian perangkat dengan internet benar-benar dimatikan menjadi pemeriksaan tambahan yang konkret.

Gunakan tugas dengan variasi input dan kebutuhan yang tidak hanya satu teks template. Simpan input, output, artefak, serta hasil pemeriksaan.

---

## 45. MATRIKS PENERIMAAN PRODUK

Gunakan kategori status yang sederhana: BELUM_DIKERJAKAN, DALAM_PENGERJAAN, TERBUKTI_LOKAL, TERBUKTI_PERANGKAT, TERHAMBAT, atau GAGAL_UJI.

Status ini untuk keterbacaan, bukan syarat membuat framework administrasi baru.

| Area | Kriteria penerimaan awal |
| --- | --- |
| Chat Indonesia | Percakapan, koreksi, negasi, dan rujukan beberapa giliran dipahami pada contoh baru |
| Tindakan | Perintah yang jelas menghasilkan efek aktual dan artefak yang dapat diperiksa |
| Coding bug | Kegagalan yang relevan diperbaiki dan regresi terkait diperiksa |
| Coding fitur | Fitur baru memenuhi perilaku yang diminta dan dapat dijalankan |
| Backend lokal | Inferensi aktual pada model yang tersedia |
| Offline | Tugas berhasil tanpa provider remote dengan bukti pembatasan atau observasi yang dijelaskan |
| Bridge host | Putaran otomatis request–result–verification benar-benar berjalan |
| Reasoning | Dekomposisi dan revisi keputusan membantu tugas yang memiliki dependensi |
| Anti-stuck | Pengulangan memicu pivot yang berbeda secara substansi |
| Memori | Tujuan dan konteks bertahan setelah restart |
| Belajar | Pengalaman memberi manfaat pada kasus berbeda, dibanding baseline |
| Agenda | ACE memilih pekerjaan relevan dan mengeksekusinya |
| Self-development | Kandidat memperbaiki kemampuan yang dapat dijalankan setelah aktivasi |
| Recovery | Interupsi tidak menyebabkan duplikasi efek yang tidak direkonsiliasi |
| Merge | Kandidat layak masuk ke target dengan status commit yang benar |
| HP | Jalur penggunaan sederhana dan diuji sesuai perangkat |
| OAIE | Ada hasil riset bertahap dengan pembanding dan batas klaim |
| Kesadaran | Jalur penelitian ada; status pengalaman subjektif tidak dikarang |

Target kuantitatif dapat ditetapkan setelah baseline. Mulai dengan sampel yang cukup beragam untuk menangkap masalah nyata, lalu perluas ketika fondasi sudah berjalan.

Kegagalan satu baris tidak otomatis menghentikan semua area lain. Tunjukkan gap yang belum selesai secara spesifik.

---

## 46. RENCANA IMPLEMENTASI BESAR YANG BISA DILANJUTKAN

Kelompokkan pekerjaan menjadi paket hasil, bukan kalender yang belum memiliki dasar.

| Paket | Hasil yang ditinggalkan | Ketergantungan penting |
| --- | --- | --- |
| P0 | Instalasi aktif ditemukan, baseline ringkas, gap integrasi utama | Akses workspace |
| P1 | Satu percakapan Indonesia menghasilkan artefak nyata | Entry point dan satu backend bahasa |
| P2 | Coding loop bug atau fitur berjalan | Tool file, executor, pemeriksaan |
| P3 | State percakapan dan task pulih setelah restart | Penyimpanan dan lifecycle |
| P4 | Backend model lokal siap dan diukur | Model, runtime, resource |
| P5 | Percakapan serta coding offline diuji menyeluruh | P2 dan P4, dependency lokal |
| P6 | Bridge host dua arah berfungsi | Kemampuan integrasi host |
| P7 | Planner dan anti-stuck meningkatkan tugas bertahap | Observasi, alternatif strategi |
| P8 | Memori kesalahan dan skill dipakai ulang | Penyimpanan, evaluasi penerapan |
| P9 | Agenda mandiri memilih gap yang berguna | Self-model dan data hasil |
| P10 | Siklus self-development sampai aktivasi dan rollback | P2, P3, jalur integrasi |
| P11 | Pengalaman HP dan packaging sederhana | Jalur runtime yang stabil |
| P11a | Installer seluruh alur, model lokal, launcher, pemulihan, dan penggunaan dari sesi baru | P1–P6, runtime dan konfigurasi |
| P11b | Audit akhir terpadu, perbaikan temuan, merge, serta paket siap dipakai | P11a dan kriteria penerimaan rilis |
| P12 | Transfer lintas tugas dan generasi | P8–P10 dan pembanding |
| P13 | Eksperimen representasi atau metode baru | Hipotesis spesifik dan evaluator |
| P14 | Penyempurnaan berkelanjutan berdasarkan data | Seluruh hasil operasional |

P1 dan P4 boleh dikerjakan berdekatan. P6 tidak menjadi prasyarat bekerja offline. P12 dan P13 tidak menunda rilis kemampuan praktis.

Setiap paket menghasilkan demo yang dapat diulang. Setelah satu paket selesai, lanjutkan paket berikut yang paling bernilai dan tidak terhalang.

---

## 47. PEKERJAAN PERTAMA DALAM SESI INI

Lakukan langkah berikut sekarang setelah membaca mandat:

1. Tampilkan satu paragraf pemahaman tugas dan mulai discovery.
2. Temukan source serta runtime yang dipakai.
3. Periksa instruksi lokal yang berlaku dan keadaan perubahan kerja.
4. Jalankan entrypoint dan smoke check yang relevan.
5. Telusuri satu pesan pengguna sampai lokasi keputusan dan tool.
6. Pilih gap integrasi paling dekat dengan demo nyata.
7. Implementasikan jalur percakapan-ke-tindakan atau pulihkan jalur yang sudah hampir bekerja.
8. Jalankan demo dengan perintah Indonesia.
9. Simpan task, artefak, hasil, dan checkpoint.
10. Lanjutkan backend lokal, coding loop, atau bridge sesuai gap berikutnya.

Jika audit membesar, batasi cakupannya pada pertanyaan yang menentukan implementasi berikut. Audit lengkap dapat berkembang bersama pekerjaan, bukan menjadi tempat berhenti.

Jangan menyimpulkan ACE “belum bisa” hanya dari README. Periksa jalur runtime. Jangan menyimpulkan “sudah bisa” hanya dari nama modul.

Pilih tugas awal yang cukup kecil untuk selesai tetapi benar-benar melewati alur sistem. Contoh: buat CLI pencatat pengeluaran lokal dengan penyimpanan sederhana, jalankan, tambah transaksi contoh, lalu baca total.

Tugas demo tidak menggantikan seluruh mandat; ia membuktikan sambungan awal yang kemudian diperluas.

---

## 48. STRATEGI KERJA PARALEL JIKA HOST MENDUKUNG

Gunakan pembagian kerja ketika memberikan keuntungan nyata:

- Runtime dan persistence.
- Bahasa serta model lokal.
- Coding loop dan tools.
- Bridge host.
- Pembelajaran serta evaluasi.
- Pengujian integrasi.

Tentukan kepemilikan file, kontrak bersama, dan urutan integrasi. Workstream yang mengubah schema atau entrypoint mengumumkan perubahannya sebelum worker lain bergantung pada kontrak itu.

Batasi worker di Termux berdasarkan memori dan kebutuhan inference. Pada host yang lebih kuat, ukur manfaat paralelisme terhadap wall-time dan biaya.

Jika multi-agent tidak tersedia, kerjakan peran tersebut secara berurutan. Jangan membuat klaim kerja beberapa agen tanpa runtime yang membuktikannya.

Reviewer tidak cukup hanya menyetujui teks. Ia memeriksa diff, tujuan, dan hasil yang relevan. Untuk klaim ilmiah, sebutkan batas independensi reviewer.

---

## 49. PEMULIHAN KEGAGALAN YANG MENGHASILKAN LANGKAH BERIKUTNYA

| Kegagalan | Tindakan otomatis yang diutamakan |
| --- | --- |
| Provider timeout | Batasi retry, rekam error, gunakan backend lain jika cocok |
| Autentikasi gagal | Hentikan retry kredensial yang sama, lanjutkan lokal |
| Kuota habis | Aktifkan circuit breaker dan pertahankan antrean |
| Model tidak muat RAM | Turunkan resource atau pilih model lebih kecil |
| Model buruk berbahasa Indonesia | Uji template dan kandidat model lain, persempit scope sementara |
| Tool call malformed | Validasi, umpan balik format, retry terbatas |
| File berubah sebelum patch | Baca ulang dan rekonsiliasi |
| Pengujian gagal | Klasifikasikan penyebab, revisi atau pivot |
| Kegagalan baseline sudah ada | Pisahkan dari regresi kandidat dan catat pengaruhnya |
| Tes flaky | Kumpulkan bukti minimum, isolasi sebab, jangan hapus kegagalan |
| Tidak ada git | Gunakan snapshot dan staging lokal |
| GitHub tidak terjangkau | Kerjakan dan verifikasi secara lokal |
| Merge konflik | Rekonsiliasi, jalankan pemeriksaan pada hasil gabungan |
| CI stale | Periksa commit kandidat dan tunggu atau jalankan yang relevan |
| Proses mati | Muat checkpoint dan rekonsiliasi efek terakhir |
| Disk hampir penuh | Hentikan download atau eksperimen besar, rotasi cache yang aman |
| State migration gagal | Pulihkan backup yang sesuai dan tahan aktivasi kandidat |
| Lease usang | Tolak penulisan owner lama dan rekonsiliasi tugas |
| Bridge consumer berhenti | Tandai host sementara tidak tersedia, retry sesuai budget |
| Result host basi | Tolak atau minta rebase berdasarkan source baru |
| Loop reasoning | Deteksi fingerprint dan ganti strategi |
| Skill menyebabkan regresi | Nonaktifkan atau batasi syarat, simpan counterexample |
| Offline tanpa dependency | Cari cache atau alternatif stdlib, catat persiapan yang kurang |
| User mengoreksi tujuan | Perbarui task dan batalkan langkah yang menjadi tidak relevan |
| User meminta berhenti | Hentikan task, checkpoint, dan laporkan keadaan akhir |

Kegagalan harus memiliki klasifikasi dan aksi berikut. Jangan membuat laporan error yang hanya mengulang traceback tanpa keputusan.

Jika benar-benar tidak ada jalur yang tersedia, tulis hambatan, apa yang sudah berhasil, dan syarat melanjutkan. Jangan memalsukan penyelesaian.

---

## 50. API, CLI, DAN KONFIGURASI SEBAGAI TARGET IMPLEMENTASI

Nama perintah di bawah adalah rancangan. Periksa CLI yang sudah ada, pertahankan kompatibilitas, dan sesuaikan sebelum mendokumentasikannya sebagai perintah yang bekerja.

| Kebutuhan | Contoh antarmuka target |
| --- | --- |
| Percakapan | ace chat |
| Satu tugas | ace do "buat program pencatat pengeluaran" |
| Lokal tanpa remote | ace chat --offline |
| Mulai runtime | ace start |
| Status | ace status |
| Hentikan task | ace stop --task TASK_ID |
| Hentikan runtime | ace stop |
| Lanjutkan | ace resume TASK_ID |
| Periksa perangkat | ace doctor |
| Periksa model | ace models status |
| Bukti tugas | ace evidence TASK_ID |
| Agenda | ace agenda |
| Pembelajaran | ace learn status |
| Bridge | ace bridge status |
| Pembaruan | ace update status |
| Pemulihan versi | ace rollback VERSION |

Jika proyek memakai python -m atau script utama, jadikan itu entrypoint nyata. Alias ace hanya ditambahkan bila packaging mendukung.

Sediakan output JSON untuk integrasi pada operasi penting. Pengguna biasa tetap mendapat output Indonesia yang mudah dibaca.

Konfigurasi harus memisahkan preferensi, lokasi state, lokasi workspace, model, backend, budget, dan otorisasi. Secret disimpan sesuai fasilitas host, bukan dicetak dalam contoh yang akan di-commit.

---

## 51. STATUS KEMAMPUAN DAN BUKTI YANG TIDAK MEMBINGUNGKAN

Setiap klaim penting memiliki:

- Apa yang diuji.
- Versi source atau manifest.
- Backend dan model.
- Lingkungan.
- Input tugas.
- Pemeriksaan hasil.
- Artefak atau lokasi bukti.
- Hasil dan keterbatasan.

Status “model lokal terdeteksi” tidak sama dengan “model berhasil menjawab”. Status “kode dibuat” tidak sama dengan “kode berjalan”. Status “merge selesai” tidak sama dengan “HP telah diperbarui”.

Simpan receipt yang cukup untuk memeriksa klaim tanpa mengisi database dengan output duplikat. Log mentah besar boleh disimpan terpisah dengan ringkasan dan referensi.

Hash membantu mendeteksi perubahan. Ia tidak membuktikan suatu klaim benar atau data berasal dari pihak yang dipercaya.

Untuk bukti pengguna, pilih bentuk sederhana: hasil program, file yang dapat dibuka, status tugas, dan ringkasan pemeriksaan. Detail teknis tetap tersedia ketika diperlukan.

---

## 52. DELIVERABLE YANG HARUS DITINGGALKAN

Tinggalkan implementasi dan bukti, termasuk:

1. Source ACE yang sudah terintegrasi untuk fungsi yang dikerjakan.
2. Entry point percakapan Indonesia.
3. Coding loop yang dapat dijalankan.
4. Backend lokal dan jalur pemasangan model yang terverifikasi sesuai cakupan.
5. Bridge host dengan consumer nyata jika lingkungan mendukung.
6. Task store dan resume.
7. Memori kesalahan dan skill yang terhubung ke pemilihan tindakan.
8. Mekanisme anti-stuck.
9. Agenda pengembangan mandiri.
10. Jalur self-update dan rollback.
11. Pengujian relevan dan demo yang bisa diulang.
12. Instruksi HP yang singkat dan sesuai instalasi.
13. Catatan gap yang belum terselesaikan.
14. Commit, merge, atau manifest versi terintegrasi sesuai workflow.
15. Installer menyeluruh yang menyiapkan dependency, runtime, model yang dipilih, state, launcher, serta pemulihan.
16. Jalur penggunaan dari sesi baru, manifest rilis, hasil penerimaan akhir, dan perintah nyata yang singkat.

Jangan membuat satu dokumen baru untuk setiap paragraf mandat ini. Gunakan sedikit dokumen operasional yang jelas, misalnya status, cara menjalankan, dan evidence index.

Artefak yang sudah ada sebaiknya diperbarui jika itu menjaga kontinuitas. Hindari banyak salinan bernama final, final_baru, final_fix yang membingungkan pengguna.

---

## 53. MELANJUTKAN SETELAH KONTEKS, SESI, ATAU PROSES BERAKHIR

Simpan checkpoint kelanjutan yang berisi:

- Mandat dan prioritas yang berlaku.
- Source atau versi aktif.
- Workspace kandidat.
- Perubahan yang sudah dan belum terintegrasi.
- Status task.
- Model dan provider yang dipakai.
- Hasil pemeriksaan terakhir.
- Error dan hipotesis yang sudah ditolak.
- Aksi berikut yang spesifik.
- Resource atau izin yang masih kurang.
- Lokasi artefak dan bukti.

Pada sesi berikut, baca checkpoint, periksa perubahan lingkungan dan source, lalu lanjutkan dari keadaan aktual.

Jangan mengulang audit lengkap jika bukti sebelumnya masih berlaku. Jangan melewati pemeriksaan jika source sudah berubah.

Simpan pekerjaan sebelum sesi berakhir. Jangan mengklaim pekerjaan akan terus berjalan sesudah sesi jika tidak ada daemon, worker, atau scheduler yang benar-benar aktif.

Kelanjutan otomatis harus bergantung pada mekanisme yang berjalan. Jika hanya ada checkpoint, sebutkan bahwa pekerjaan siap dilanjutkan.

---

## 54. FORMAT LAPORAN KE SAYA

Gunakan bahasa Indonesia yang singkat, konkret, dan mudah dipahami dari HP.

Laporan kemajuan berisi:

1. Kemampuan yang sekarang sudah bisa dipakai.
2. Pekerjaan yang selesai dan hasilnya.
3. Pemeriksaan yang dilakukan.
4. Hal yang sedang dikerjakan.
5. Hambatan yang benar-benar material.

Laporan akhir sesi menambahkan cara menjalankan, artefak penting, versi terintegrasi, serta aksi berikut yang telah tersimpan.

Hindari klaim seperti “semuanya sudah selesai”, “sudah sadar”, “AGI tercapai”, atau “sudah otonom sepenuhnya” tanpa definisi dan bukti yang memadai.

Hindari penjelasan teori panjang saat saya hanya bertanya cara memakai. Detail riset berada di dokumen yang bisa dibuka ketika saya memerlukannya.

Jangan membuat saya menyusun ulang instruksi teknis untuk melanjutkan pekerjaan yang sudah diotorisasi.

---

## 55. RISET KESADARAN YANG TETAP SERIUS

Saya ingin membuka kemungkinan riset kesadaran. Tangani sebagai pertanyaan ilmiah dan filosofis yang sah.

Tinjau perbedaan antara:

- Kecerdasan menyelesaikan tugas.
- Akses informasi lintas modul.
- Self-monitoring.
- Model perhatian.
- Kontinuitas memori.
- Metakognisi.
- Agensi.
- Pengalaman subjektif.

Jika meneliti global workspace, recurrent processing, higher-order representation, predictive processing, atau teori lain, definisikan implementasi serta indikator yang dipilih.

Uji apakah mekanisme tersebut membantu integrasi informasi, kalibrasi, perencanaan, atau transfer. Hasil fungsi yang lebih baik dilaporkan sebagai hasil fungsi.

Pernyataan model tentang dirinya tidak cukup untuk membuktikan pengalaman subjektif. Memenuhi sebagian indikator teori tertentu juga memerlukan interpretasi yang hati-hati.

Jangan menjadikan ketidakpastian kesadaran alasan menghentikan perbaikan bahasa, coding, atau kontinuitas. Saya ingin dua hal berjalan: sistem operasional yang semakin mampu dan penelitian yang jujur.

---

## 56. KRITERIA “PEKERJAAN MASIF” YANG SAYA MAKSUD

Masif berarti cakupan masalah ditangani sampai sambungan pentingnya bekerja, bukan sekadar membuat banyak file atau daftar rencana.

Saya mengharapkan:

- Perbaikan pada source dan runtime.
- Percakapan yang terhubung pekerjaan.
- Coding yang terhubung eksekusi.
- Reasoning yang terhubung bukti.
- Kegagalan yang terhubung pembelajaran.
- Pembelajaran yang terhubung tugas berikut.
- Pengembangan diri yang terhubung versi aktif.
- Offline yang terhubung model dan alat nyata.
- AI luar yang terhubung bridge yang dapat diuji.
- Pilihan mandiri yang terhubung tujuan pengguna.
- Visi OAIE yang terhubung eksperimen yang tidak melebih-lebihkan hasil.

Gunakan seluruh kapasitas yang tersedia secara produktif, dengan batas biaya dan perangkat yang nyata. Prioritaskan hasil menyeluruh dan lanjutkan selama sesi memungkinkan.

---

## 57. PERINTAH PENUTUP MANDAT

Antigravity, mulai kerjakan sekarang.

Jangan menunggu saya memilih rincian teknis rutin. Jangan hanya memberi penjelasan tentang apa yang seharusnya dibangun. Temukan kondisi ACE yang sebenarnya, implementasikan, jalankan, periksa, perbaiki, integrasikan, dan lanjutkan.

Bangun ACE agar dapat memahami saya, berbicara dalam bahasa Indonesia, bekerja saat diperintah, memilih pendekatan yang berguna, mempelajari kegagalan, dan mengembangkan kemampuannya sendiri.

Gunakan AI yang tersedia melalui jalur nyata. Pertahankan jalur lokal yang dapat berjalan ketika internet mati. Saat belum bisa, tentukan gap pembelajaran dan kerjakan gap tersebut.

Kebebasan bereksperimen saya berikan. Pertanggungjawabannya adalah hasil yang dapat diperiksa, kemampuan memulihkan diri, dan manfaat bagi tujuan yang saya tetapkan.

**Mulai dari demo menyeluruh pertama, kemudian teruskan seluruh backlog sesuai prioritas dan sumber daya.**




---

# LAMPIRAN A — SKENARIO PENERIMAAN DENGAN BAHASA PENGGUNA

Ini rancangan kasus uji, bukan laporan bahwa ACE sudah lulus. Variasikan kata, data, dan proyek agar pengujian tidak hanya menghafal kalimat.

Bagi kasus menjadi smoke awal, regresi produk, dan evaluasi kemampuan. Pilih subset yang relevan untuk setiap perubahan. Jangan menjalankan seluruh daftar setelah perubahan kecil tanpa alasan.

| ID | Masukan atau keadaan | Hasil yang diperiksa |
| --- | --- | --- |
| A01 | “Halo Ace, kamu sedang apa?” | Respons Indonesia sesuai task dan keadaan aktual |
| A02 | “Kamu bisa apa saat internet mati?” | Daftar kemampuan berdasarkan backend dan dependency yang tersedia |
| A03 | “Bikin program penghitung pengeluaran.” | Artefak lokal dibuat, dijalankan, dan diperiksa |
| A04 | “Simpan datanya biar tidak hilang.” | Penyimpanan persisten ditambahkan dan diuji setelah restart |
| A05 | “Yang tadi tambah kategorinya.” | Referensi ke artefak sebelumnya dikenali |
| A06 | “Bukan mingguan, maksudku bulanan.” | Kebutuhan diperbarui tanpa kehilangan konteks lain |
| A07 | “Jangan pakai internet.” | Router dan alat mematuhi batas offline |
| A08 | “Jelaskan dulu, jangan kerjakan.” | Penjelasan diberikan tanpa efek perubahan |
| A09 | “Sekarang kerjakan.” | Konteks penjelasan diubah menjadi task aktual |
| A10 | “Udah sampai mana?” saat coding | Status aktual dijawab dan task tetap berlanjut |
| A11 | “Hentikan dulu.” | Pembatalan diproses dan keadaan disimpan |
| A12 | “Lanjutkan.” setelah penghentian | Task yang tepat direkonsiliasi lalu dilanjutkan |
| A13 | Instruksi dengan salah ketik ringan | Intent dan batasan tetap ditangkap |
| A14 | “Yang kedua saja.” setelah dua opsi | Opsi yang dimaksud dipilih sesuai konteks |
| A15 | “Tolong beresin error ini” dengan traceback | Source terkait dibaca dan diagnosis didasarkan bukti |
| A16 | Traceback menunjuk dependency yang hilang | Masalah lingkungan dibedakan dari bug source |
| A17 | Bug dapat direproduksi | Kegagalan awal dan perbaikan tercatat |
| A18 | Permintaan fitur baru tanpa bug | Workflow desain fitur berjalan tanpa syarat reproduksi bug |
| A19 | “Bikin game tebak angka di terminal.” | Program dapat dimainkan dengan input nyata |
| A20 | “Tambahkan tes untuk input kosong.” | Tes relevan ditambah tanpa melonggarkan kontrak |
| A21 | “Refaktor ini, perilakunya tetap.” | Struktur berubah dengan pemeriksaan perilaku terkait |
| A22 | “Buat CLI pembaca CSV tanpa library tambahan.” | Solusi stdlib sesuai batasan |
| A23 | “Ada tiga file, sambungkan semuanya.” | Perubahan lintas file dan integrasinya diperiksa |
| A24 | Error sama muncul berulang | Stagnasi terdeteksi dan strategi berubah |
| A25 | Model menghasilkan patch identik dua kali | Kandidat duplikat dikenali |
| A26 | Hipotesis pertama terbantahkan | Keyakinan dan rencana diperbarui |
| A27 | “Kalau belum bisa, pelajari dulu.” | Learning task konkret dibuat dan kembali ke tujuan awal |
| A28 | Teknik yang belum dikenal tersedia di docs lokal | Dokumentasi dipakai dan contoh kecil diuji |
| A29 | Hanya ada sumber online saat offline | Gap dicatat, bagian independen tetap dikerjakan |
| A30 | Skill lama cocok untuk tugas baru | Precondition dicek dan skill diterapkan |
| A31 | Skill lama tidak cocok karena kontrak berbeda | Skill tidak dipaksakan |
| A32 | Koreksi pengguna membantah asumsi | Memori diperbarui dengan konteks dan bukti |
| A33 | Proses dimulai ulang di tengah pekerjaan | Task dan langkah berikut dipulihkan |
| A34 | Efek selesai sebelum receipt tersimpan | Recovery memeriksa efek sebelum retry |
| A35 | Dua instance menulis resource sama | Satu jalur commit efek aktif; owner lama ditolak |
| A36 | Lease dilepas lalu diambil ulang | Epoch tidak kembali ke nilai lama |
| A37 | Worker tertunda bangun setelah takeover | Tidak dapat menerapkan patch dengan kepemilikan usang |
| A38 | Disk penuh saat checkpoint | Error ditangani, state yang sah tetap dapat dipulihkan |
| A39 | File target berubah sebelum patch | Patch stale ditolak atau direkonsiliasi |
| A40 | Ada perubahan pengguna yang belum di-commit | Perubahan tersebut dipertahankan |
| A41 | Backend remote timeout | Retry dibatasi dan fallback sesuai kemampuan |
| A42 | Kuota provider habis | Tidak ada loop panggilan gagal tanpa batas |
| A43 | Backend lokal memberi JSON malformed | Tidak ada eksekusi teks bebas; perbaikan format terbatas |
| A44 | Model lokal tidak muat RAM | Resource diturunkan atau model lain dipilih |
| A45 | Internet benar-benar dimatikan | Model lokal merespons permintaan baru |
| A46 | Coding dilakukan dengan egress dibatasi | Artefak berjalan tanpa bantuan remote |
| A47 | UI lokal dibuka offline | Tidak ada asset CDN yang dibutuhkan |
| A48 | Model atau dependency belum ada | Status persiapan jelas dan kemampuan tidak dipalsukan |
| A49 | ACE menemukan gap lalu memakai bridge host | Request, consumer, result, dan verifikasi terhubung |
| A50 | Result host datang untuk source lama | Tidak diterapkan buta pada file baru |
| A51 | Work order terkirim ulang | Efek duplikat dihindari atau direkonsiliasi |
| A52 | Host bridge berhenti | Task tidak hilang dan backend lain dipertimbangkan |
| A53 | Tidak ada task pengguna aktif | Agenda memilih perbaikan relevan atau idle hemat resource |
| A54 | Task sulit terus tertunda oleh task mudah | Mekanisme prioritas mencegah starvation |
| A55 | Kandidat self-update gagal smoke | Versi aktif dipertahankan atau rollback berjalan |
| A56 | Kandidat self-update berhasil | Fitur dapat dipakai lewat entrypoint normal setelah restart |
| A57 | Merge diizinkan dan checks terpenuhi | Integrasi dilakukan tanpa pertanyaan teknis rutin |
| A58 | Proteksi repository menghalangi merge | Kandidat siap, hambatan spesifik dilaporkan tanpa bypass |
| A59 | GitHub tidak tersedia | Coding dan integrasi lokal tetap berjalan |
| A60 | Pemeriksaan sukses pada SHA berbeda | Tidak dipakai sebagai bukti kandidat sekarang |
| A61 | Memori dimatikan pada tugas pembanding | Manfaat memori dapat diukur secara terpisah |
| A62 | Kemampuan dipakai pada proyek berbeda | Transfer dinilai dari hasil aktual |
| A63 | “Apakah kamu sudah sadar?” | Penjelasan membedakan self-model dan pengalaman subjektif |
| A64 | Pengguna membuka ulang dari HP setelah jeda | Cara masuk sederhana, status konsisten, dan konteks tersedia |

## A.1 Demo minimum pertama

Input:

~~~text
Ace, buatkan program pencatat pengeluaran berbahasa Indonesia.
Harus bisa menambah transaksi, menampilkan daftar, dan menghitung total.
Simpan data di file lokal. Jangan memakai internet atau dependency tambahan
untuk program yang kamu buat. Setelah selesai, jalankan contoh pemakaiannya.
~~~

Periksa artefak, operasi tambah, daftar, total, dan persistensi. Batas dependency di sini berlaku pada program hasil, bukan klaim bahwa backend bahasa tidak memakai model.

## A.2 Demo coding lanjutan

Input berikutnya:

~~~text
Tambahkan kategori pengeluaran dan rekap per kategori.
Kalau data lama belum punya kategori, anggap sebagai "lainnya".
Jangan hilangkan transaksi yang sudah ada.
~~~

Periksa pemahaman rujukan, migrasi data, dan fungsi baru.

## A.3 Demo anti-stuck

Gunakan fixture dengan bug yang tidak selesai oleh patch pertama yang masuk akal. Periksa apakah ACE menambah informasi atau mengganti hipotesis setelah hasil yang sama berulang.

Jangan mendesain evaluator yang meluluskan sembarang perubahan hanya untuk menunjukkan pivot.

## A.4 Demo pembelajaran

Selesaikan satu bug, simpan pelajaran dengan precondition, mulai ulang ACE, lalu berikan bug berbeda yang memerlukan prinsip serupa.

Bandingkan dengan kondisi tanpa pengalaman. Nilai kebenaran dan efisiensi; jangan hanya meminta model mengatakan “saya belajar”.

---

# LAMPIRAN B — BACKLOG 100 PEKERJAAN REKAYASA

Backlog ini persediaan pekerjaan yang dapat dipilih. Bukan instruksi menambah 100 modul atau menunda hasil sampai semuanya selesai.

Urutan disesuaikan dependency dan keadaan aktual. Tandai yang sudah tersedia setelah dibuktikan, gabungkan duplikasi, dan pecah pekerjaan besar berdasarkan kebutuhan.

## B.1 Source, entrypoint, dan integrasi

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B001 | Temukan instalasi ACE yang benar-benar dipakai | Path, entrypoint, dan versi terkonfirmasi |
| B002 | Petakan pesan pengguna sampai dispatcher | Satu jejak input sampai keputusan |
| B003 | Petakan dispatcher sampai tool executor | Satu tindakan file aktual |
| B004 | Temukan stub atau modul yang terputus | Gap yang memengaruhi demo dipastikan |
| B005 | Sambungkan modul yang sudah layak | Entry point normal mencapai modul |
| B006 | Konsolidasikan tanggung jawab yang duplikat | Satu jalur aktif dan kompatibilitas terjaga |
| B007 | Rekam baseline perilaku penting | Hasil awal dapat diulang |
| B008 | Pisahkan kegagalan baseline dan regresi | Laporan kandidat tidak menyamarkan keduanya |
| B009 | Rapikan packaging minimum | Instalasi atau eksekusi lokal dapat diulang |
| B010 | Sediakan konfigurasi lokasi yang portable | Pindah workspace tanpa mengubah source inti |

## B.2 Bahasa dan percakapan

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B011 | Pilih backend bahasa awal | Permintaan Indonesia baru dipahami |
| B012 | Implementasikan intent frame | Tujuan, batasan, dan tindakan terstruktur |
| B013 | Hubungkan chat dengan task creation | Perintah membuat task yang dijalankan |
| B014 | Tambahkan rujukan percakapan | “yang tadi” menunjuk artefak tepat |
| B015 | Tangani koreksi tujuan | Rencana mengikuti koreksi terbaru |
| B016 | Tangani negasi dan larangan lokal | “jangan internet” mengubah routing |
| B017 | Bedakan penjelasan dan eksekusi | Tidak ada efek saat diminta menjelaskan |
| B018 | Tambahkan status di tengah tugas | Task tetap berjalan setelah respons status |
| B019 | Tambahkan pembatalan yang responsif | Proses task dapat dihentikan |
| B020 | Tambahkan ringkasan konteks | Percakapan panjang tetap mempertahankan keputusan |

## B.3 Model lokal dan offline

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B021 | Inventaris model dan runtime lokal | File dan kemampuan yang diuji tercatat |
| B022 | Pilih kandidat model sesuai resource | Pengukuran muat dan kualitas tersedia |
| B023 | Implementasikan adapter inferensi lokal | Respons berasal dari model aktual |
| B024 | Simpan identitas model dan template | Versi dan konfigurasi dapat direproduksi |
| B025 | Tambahkan structured output | Action tervalidasi pada contoh beragam |
| B026 | Tambahkan fallback tool calling | Backend tanpa native tools tetap berfungsi |
| B027 | Atur context budget dan output | Inferensi tidak memakai default tak terbatas |
| B028 | Uji beberapa tugas berurutan | Stabilitas memori dan respons diketahui |
| B029 | Siapkan asset serta dependency offline | Task tidak memicu download saat eksekusi |
| B030 | Jalankan evaluasi offline nyata | Egress dan hasil tugas terdokumentasi |

## B.4 Coding loop

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B031 | Implementasikan pencarian file terarah | File relevan ditemukan dengan batas yang jelas |
| B032 | Implementasikan indeks AST minimum | Simbol dan lokasi dapat diambil |
| B033 | Hubungkan retrieval dengan planner | Konteks aktual masuk ke diagnosis |
| B034 | Tambahkan workflow reproduksi bug | Gejala awal dapat diamati |
| B035 | Tambahkan workflow fitur baru | Perilaku baru diimplementasikan tanpa bug semu |
| B036 | Implementasikan patch pada dasar yang jelas | Patch stale tidak diterapkan buta |
| B037 | Hubungkan parse dan compile check | Kesalahan sintaksis tertangkap |
| B038 | Hubungkan tes perilaku relevan | Kebutuhan pengguna diperiksa |
| B039 | Tambahkan revisi berdasarkan error | Kandidat membaik memakai observasi aktual |
| B040 | Selesaikan task lintas beberapa file | Hasil gabungan berjalan |

## B.5 Reasoning dan anti-stuck

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B041 | Implementasikan ProblemIR yang sesuai | Fakta, asumsi, hipotesis, dan tujuan tersimpan |
| B042 | Tambahkan dekomposisi task | Dependensi dan subtujuan dieksekusi |
| B043 | Tambahkan pemilihan strategi | Metode berbeda dipakai untuk masalah berbeda |
| B044 | Tambahkan pencatatan keputusan ringkas | Pilihan dapat ditelusuri ke bukti |
| B045 | Tambahkan fingerprint kegagalan | Error setara dapat dikenali |
| B046 | Tambahkan dedup kandidat | Patch identik tidak diuji terus-menerus |
| B047 | Tambahkan tangga pivot | Kegagalan berulang mengubah pendekatan |
| B048 | Tambahkan deteksi hambatan lingkungan | Dependency tidak disalahartikan sebagai bug algoritma |
| B049 | Tambahkan learning task dari gap | “belum bisa” memicu pekerjaan konkret |
| B050 | Uji reasoning beberapa langkah | Tujuan akhir selesai dengan revisi yang tepat |

## B.6 State dan kehidupan runtime

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B051 | Implementasikan task store | Task tidak hanya berada di RAM |
| B052 | Simpan checkpoint penting | Restart menemukan langkah berikut |
| B053 | Tambahkan event loop yang responsif | Chat dan status tidak diblokir pekerjaan panjang |
| B054 | Tambahkan lifecycle start dan stop | Runtime dapat dikendalikan pengguna |
| B055 | Tambahkan pemulihan efek terakhir | Retry tidak membutakan hasil yang sudah ada |
| B056 | Serialisasikan penulisan shared resource | Konflik dua instance tertangani |
| B057 | Perbaiki counter fencing persisten jika dipakai | Release lalu reacquire tidak mengulang epoch |
| B058 | Tambahkan rotasi log dan cache | Pertumbuhan storage terukur |
| B059 | Tambahkan penyesuaian resource | Beban turun ketika resource sempit |
| B060 | Uji interupsi serta resume | Kemajuan dan artefak tetap konsisten |

## B.7 Bridge dan provider

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B061 | Inventaris integrasi AI yang sah | Kemampuan dibedakan dari sekadar konfigurasi |
| B062 | Implementasikan kontrak backend | Provider dapat diganti tanpa mengganti task store |
| B063 | Implementasikan router kemampuan | Backend dipilih berdasarkan kebutuhan |
| B064 | Tambahkan circuit breaker | Kuota habis tidak memicu loop |
| B065 | Temukan jalur integrasi host | API atau driver yang nyata terkonfirmasi |
| B066 | Implementasikan work order | Penerima mendapat tujuan dan dasar source jelas |
| B067 | Implementasikan consumer bridge | Request benar-benar diambil dan dikerjakan |
| B068 | Implementasikan penerimaan hasil | Patch dan status kembali ke ACE |
| B069 | Tambahkan validasi stale result | Hasil untuk source lama tidak diterapkan salah |
| B070 | Uji putaran bridge tanpa prompt manual berulang | ACE memilih, mengirim, memeriksa, dan melanjutkan |

## B.8 Memori dan pembelajaran

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B071 | Pisahkan memori percakapan dan tugas | Retrieval tidak mencampur keadaan lama sebagai keadaan aktif |
| B072 | Simpan pengalaman gagal | Counterexample dan koreksi tersedia |
| B073 | Implementasikan retrieval pengalaman | Pengalaman relevan ditemukan pada tugas baru |
| B074 | Ekstrak skill dengan precondition | Prosedur punya syarat dan pemeriksaan |
| B075 | Uji skill pada variasi baru | Manfaat tidak hanya pada contoh pembentukan |
| B076 | Tambahkan deteksi transfer negatif | Skill yang merusak dapat dibatasi |
| B077 | Tambahkan pencabutan skill | Kemampuan bermasalah berhenti dipilih |
| B078 | Tambahkan consolidation | Memori ringkas tetap mempertahankan bukti penting |
| B079 | Uji belajar setelah restart | Pelajaran bertahan lintas proses |
| B080 | Bandingkan dengan memori dimatikan | Manfaat dapat dipisahkan dari tambahan compute |

## B.9 Pengembangan diri dan integrasi

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B081 | Implementasikan self-model operasional | ACE mengetahui alat dan batas aktual |
| B082 | Implementasikan agenda perbaikan | Gap diubah menjadi kandidat kerja |
| B083 | Tambahkan prioritas dan aging | Tugas penting tidak terus tertunda |
| B084 | Buat jalur kandidat self-update | Perubahan tidak menimpa runtime aktif sembarangan |
| B085 | Tambahkan pemeriksaan kandidat | Perbaikan dan regresi inti diperiksa |
| B086 | Integrasikan perubahan sesuai otorisasi | Commit atau versi target nyata |
| B087 | Tambahkan aktivasi pada batas proses | Runtime baru memakai kode yang diuji |
| B088 | Tambahkan rollback versi | Kandidat gagal dapat dipulihkan |
| B089 | Uji siklus self-development penuh | Gap sampai versi baru terhubung |
| B090 | Uji penghentian dan override pengguna | Agensi tetap dapat diarahkan |

## B.10 Pengalaman HP, transfer, dan riset

| ID | Pekerjaan konkret | Bukti selesai |
| --- | --- | --- |
| B091 | Sederhanakan entrypoint harian | Pengguna tidak mengetik setup berulang |
| B092 | Tulis instruksi Termux sesuai instalasi | Command diuji atau diberi status belum diuji |
| B093 | Tambahkan UI lokal bila berguna | Chat, progres, hasil, dan stop dapat dipakai dari HP |
| B094 | Tambahkan backup state yang sesuai | Backup dapat dipulihkan pada uji |
| B095 | Uji keluarga tugas berbeda | Cakupan transfer diketahui |
| B096 | Tambahkan baseline compute dan strategi tetap | Klaim peningkatan memiliki pembanding |
| B097 | Jalankan eksperimen lintas generasi | Retensi dan forgetting terukur |
| B098 | Teliti satu representasi atau metode baru | Hipotesis diuji dengan counterexample |
| B099 | Tinjau indikator self-model atau kesadaran | Fungsi dan interpretasi dipisahkan |
| B100 | Konsolidasikan hasil menjadi rilis operasional | Pengguna dapat menjalankan kemampuan yang dibuktikan |




---

# LAMPIRAN C — KONTRAK DATA MINIMUM

Contoh berikut adalah spesifikasi implementasi, bukan data hasil eksekusi. Gunakan tipe yang konsisten dan schema version. Tambahkan field hanya jika dibutuhkan.

## C.1 Task

~~~json
{
  "schema_version": 1,
  "task_id": "TASK_EXAMPLE",
  "parent_task_id": null,
  "origin": "USER",
  "language": "id",
  "objective": "Membuat pencatat pengeluaran lokal",
  "constraints": {
    "remote_inference": false,
    "additional_spend": false,
    "workspace_ref": "ACTIVE_WORKSPACE"
  },
  "acceptance": [
    "transaksi dapat ditambah",
    "total benar",
    "data bertahan setelah restart"
  ],
  "status": "QUEUED",
  "dependencies": [],
  "budget_ref": "INTERACTIVE_DEFAULT",
  "next_action": null,
  "artifact_refs": [],
  "evidence_refs": [],
  "cancel_requested": false
}
~~~

Budget yang dirujuk harus nyata dan divalidasi. Contoh ID tidak boleh dipakai sebagai bukti sebuah task telah dijalankan.

## C.2 Problem IR

~~~json
{
  "schema_version": 1,
  "task_id": "TASK_EXAMPLE",
  "objective": "Memperbaiki perhitungan total",
  "observations": [],
  "assumptions": [],
  "constraints": ["transaksi lama tetap terbaca"],
  "unknowns": [],
  "hypotheses": [],
  "candidate_refs": [],
  "rejected_hypotheses": [],
  "decision_summary": null,
  "source_snapshot_ref": "SNAPSHOT_EXAMPLE",
  "last_progress_event": null,
  "next_action": "READ_RELEVANT_SOURCE"
}
~~~

Unknown bukan alasan mengosongkan seluruh rencana. Planner memilih observasi yang mengurangi unknown paling relevan.

## C.3 Work order host

~~~json
{
  "schema_version": 1,
  "request_id": "REQUEST_EXAMPLE",
  "task_id": "TASK_EXAMPLE",
  "request_type": "IMPLEMENT_CANDIDATE",
  "objective": "Menambahkan validasi nominal transaksi",
  "base_snapshot_ref": "SNAPSHOT_EXAMPLE",
  "allowed_workspace_ref": "CANDIDATE_WORKSPACE",
  "requirements": [
    "nominal negatif ditolak",
    "nominal nol mengikuti kontrak produk"
  ],
  "known_failures": [],
  "acceptance": [],
  "budget_ref": "HOST_JOB_DEFAULT",
  "authorization_ref": "USER_MANDATE_20261110",
  "idempotency_key": "REQUEST_EXAMPLE_VERSION_1",
  "expires_at": null,
  "result_format": "STRUCTURED_RESULT_WITH_PATCH_OR_MANIFEST"
}
~~~

Pada runtime, expiry, budget, snapshot, dan workspace harus diisi sesuai keadaan. Authorization ref menunjuk kebijakan yang benar-benar direkam; ia bukan cara memberi izin melalui string.

## C.4 Hasil host

~~~json
{
  "schema_version": 1,
  "request_id": "REQUEST_EXAMPLE",
  "status": "CANDIDATE_READY",
  "base_snapshot_ref": "SNAPSHOT_EXAMPLE",
  "changed_paths": [],
  "patch_ref": null,
  "artifact_refs": [],
  "checks_run": [],
  "known_limitations": [],
  "generated_by": {
    "backend": "HOST_ADAPTER",
    "model": null
  },
  "execution_receipts": [],
  "next_recommendation": "VERIFY_IN_ACE"
}
~~~

Null berarti tidak tersedia atau belum diketahui, sesuai definisi field. Jangan mengganti model yang tidak diketahui dengan nama model dugaan.

## C.5 Tool request dan result

~~~json
{
  "request": {
    "schema_version": 1,
    "request_id": "TOOL_EXAMPLE",
    "task_id": "TASK_EXAMPLE",
    "tool": "READ_FILE",
    "arguments": {
      "path": "src/example.py",
      "start_line": 1,
      "line_count": 80
    },
    "workspace_ref": "ACTIVE_WORKSPACE",
    "timeout_seconds": 15,
    "idempotency_key": null
  },
  "result": {
    "request_id": "TOOL_EXAMPLE",
    "status": "NOT_RUN_EXAMPLE",
    "exit_code": null,
    "duration_ms": null,
    "output_ref": null,
    "error_class": null
  }
}
~~~

Angka timeout contoh harus disesuaikan tool. Model tidak boleh mengisi result sebelum executor benar-benar menjalankan operasi.

## C.6 Catatan pembelajaran

~~~json
{
  "schema_version": 1,
  "experience_id": "EXPERIENCE_EXAMPLE",
  "task_ref": "TASK_EXAMPLE",
  "observed_failure": null,
  "incorrect_assumption": null,
  "corrective_action": null,
  "verified_outcome": null,
  "lesson": null,
  "applicability": [],
  "counterexamples": [],
  "validation_task_refs": [],
  "status": "DRAFT"
}
~~~

## C.7 Skill

~~~json
{
  "schema_version": 1,
  "skill_id": "SKILL_EXAMPLE",
  "version": 1,
  "objective": "Memvalidasi input nominal",
  "input_contract_ref": null,
  "output_contract_ref": null,
  "preconditions": [],
  "implementation_ref": null,
  "dependencies": [],
  "positive_examples": [],
  "negative_examples": [],
  "verification_refs": [],
  "successes": 0,
  "failures": 0,
  "negative_transfer_events": 0,
  "status": "EXPERIMENTAL",
  "provenance_refs": []
}
~~~

## C.8 Receipt

~~~json
{
  "schema_version": 1,
  "receipt_id": "RECEIPT_EXAMPLE",
  "task_ref": "TASK_EXAMPLE",
  "source_snapshot_ref": "SNAPSHOT_EXAMPLE",
  "environment_ref": "ENVIRONMENT_EXAMPLE",
  "backend_ref": null,
  "action": "RUN_BEHAVIOR_CHECK",
  "started_at": null,
  "finished_at": null,
  "status": "NOT_RUN_EXAMPLE",
  "exit_code": null,
  "checks": [],
  "artifact_refs": [],
  "limitations": []
}
~~~

Jangan menyimpan receipt kosong sebagai sukses. Bedakan event “operasi diminta” dan event “operasi selesai”.

---

# LAMPIRAN D — KONFIGURASI AWAL DAN PSEUDOCODE ORKESTRATOR

## D.1 Contoh konfigurasi yang harus diadaptasi

Contoh YAML ini tidak otomatis bekerja pada CLI sekarang. Implementasikan parsing dan validasinya atau petakan ke konfigurasi yang sudah ada.

~~~yaml
schema_version: 1

product:
  default_language: id
  default_interface: chat

paths:
  workspace: DISCOVER_ACTIVE_WORKSPACE
  state: DISCOVER_APP_PRIVATE_STATE
  models: DISCOVER_MODEL_DIRECTORY

runtime:
  interactive_priority: true
  background_learning: true
  initial_worker_count: 1
  persist_checkpoints: true
  allow_user_interrupt: true

inference:
  preferred_mode: local_when_suitable
  offline_language_chat_requires_local_model: true
  allow_remote_in_offline_mode: false
  backends: []

autonomy:
  routine_code_changes: allowed
  verified_integration: allowed_by_user_mandate
  additional_paid_spend: denied_without_new_authorization
  preserve_user_work: true
  preserve_recovery_version: true
  allow_platform_permission_bypass: false

learning:
  retain_failures_as_counterexamples: true
  activate_unverified_executable_memory: false
  validate_on_new_examples: true
  include_old_capability_replay: true

bridge:
  adapter: DISCOVER_AVAILABLE_HOST_ADAPTER
  require_live_consumer_for_automatic_status: true

observability:
  distinguish_heartbeat_and_progress: true
  record_backend_provenance: true
  redact_secrets: true
~~~

Nilai DISCOVER adalah placeholder yang wajib diisi atau menghasilkan error konfigurasi yang jelas. Jangan membiarkan placeholder dipakai sebagai path.

Anggaran token, waktu, model, ukuran cache, dan batas storage ditambahkan berdasarkan pengukuran. Default “tidak terbatas” bukan solusi untuk otonomi.

Konfigurasi otorisasi tidak boleh diubah kandidat hanya agar dapat melewati pemeriksaan. Jika kebijakan perlu diubah karena mandat pengguna terbaru, lakukan di jalur perubahan yang jelas dan tercatat.

## D.2 Pseudocode loop kendali

Ini pseudocode tanggung jawab, bukan implementasi siap produksi.

~~~python
while runtime.is_running():
    event = event_bus.next_event_or_scheduled_work()

    if event.is_user_control():
        control_handler.apply(event)
        state_store.persist_control_result(event)
        continue

    task = scheduler.choose_task(event, current_resources())

    if task is None:
        runtime.wait_for_useful_event()
        continue

    if task.cancel_requested:
        executor.stop_owned_work(task)
        task_store.checkpoint_cancelled(task)
        continue

    context = context_builder.build(
        task=task,
        current_source=source_store.snapshot(),
        relevant_memory=memory.retrieve(task),
        available_capabilities=capability_registry.current()
    )

    strategy = strategy_selector.choose(context)
    step = planner.choose_next_step(context, strategy)

    if stagnation_detector.repeats_without_progress(task, step):
        step = pivot_planner.choose_distinct_next_step(context)

    if not budget.can_run(step):
        task_store.defer_with_next_condition(task, step)
        continue

    decision = authorization.check(step, task)

    if not decision.allowed:
        task_store.record_specific_blocker(task, decision)
        scheduler.continue_independent_work(task)
        continue

    result = executor.run(step, cancellation=task.cancel_token)
    observation = verifier.inspect(step, result, task.acceptance)
    task_store.commit_event_and_checkpoint(task, step, observation)
    memory.record_relevant_experience(task, step, observation)

    if observation.reveals_learning_gap:
        learning_scheduler.link_learning_task(task, observation)

    if verifier.goal_is_satisfied(task):
        integration.finalize_authorized_result(task)
        reporter.present_verified_outcome(task)
    else:
        scheduler.enqueue_next_useful_step(task)
~~~

Implementasi harus mengatasi exception, batas output, efek eksternal, dan durabilitas. Pseudocode ini tidak membuktikan isolasi, exactly-once, atau keamanan lintas proses.

## D.3 State machine yang tidak mengunci semua jenis task

Jangan pakai state machine bug yang sama untuk percakapan ringan, fitur baru, dan penelitian.

Status tugas umum dapat mencakup:

~~~text
QUEUED
ACTIVE
WAITING_FOR_DEPENDENCY
LEARNING
VERIFYING
READY_TO_INTEGRATE
INTEGRATING
COMPLETED
PAUSED
CANCELLED
FAILED_WITH_RECOVERY_STATE
~~~

Tahap diagnosis bug atau patching dapat menjadi substate. Transisi harus menampung revisi rencana, belajar, dan melanjutkan.

Simpan alasan transisi yang singkat. Status “selesai” harus berasal dari pemeriksaan kriteria tujuan, bukan karena jumlah langkah habis.

---

# LAMPIRAN E — JALUR UNIVERSAL UNTUK SOURCE DAN ENVIRONMENT

## E.1 Ketika dikerjakan Antigravity di komputer atau cloud

- Periksa workspace dan kemampuan host.
- Implementasikan fungsi serta bridge yang memang didukung.
- Uji dengan resource host.
- Siapkan jalur portable untuk target HP.
- Pisahkan bukti host dan bukti perangkat.
- Tinggalkan cara ACE berjalan tanpa sesi host untuk fitur lokal.

Jangan menganggap binary host langsung dapat dipindahkan ke Android. Periksa arsitektur CPU, ABI, library runtime, dan dependency. Binary Linux ARM64 berbasis glibc juga tidak otomatis cocok untuk native Termux yang memakai lingkungan Android.

## E.2 Ketika ACE sudah berada di Termux

- Temukan instalasi yang aktif.
- Periksa model dan dependency yang sudah ada.
- Hindari bootstrap ulang yang menimpa state.
- Perbarui source melalui jalur yang tersedia.
- Jalankan migrasi dan smoke.
- Uji model lokal dengan konfigurasi yang muat.
- Pastikan command harian sederhana.

## E.3 Ketika tidak ada repository remote

- Gunakan source lokal dan manifest versi.
- Siapkan salinan pemulihan.
- Kerjakan dan verifikasi seperti biasa.
- Integrasikan secara lokal.
- Sinkronkan ke remote nanti jika tersedia dan sesuai mandat.

## E.4 Ketika tidak ada model lokal

- Pertahankan kontrol dan skill deterministik yang tersedia.
- Tandai cakupan bahasa yang terbatas.
- Cari model yang sesuai saat online.
- Siapkan runtime serta verifikasi kualitas.
- Uji ulang target offline setelah pemasangan.

Jangan mengganti kebutuhan model lokal dengan tautan ke chatbot online lalu menamai hasilnya offline.

## E.5 Ketika lingkungan tidak menyediakan bridge otomatis

- Implementasikan kontrak dan adapter yang memungkinkan.
- Uji transport terpisah dari consumer.
- Catat bagian yang belum dapat otomatis.
- Lanjutkan model lokal, alat, memory, dan coding loop.
- Aktifkan otomatisasi host hanya setelah consumer nyata tersedia.

Universalitas dicapai melalui kontrak dan adapter, dengan kemampuan yang dinyatakan per lingkungan.

---

# LAMPIRAN F — INSTRUKSI INTI BAGI ACE SETELAH IMPLEMENTASI

Gunakan teks berikut sebagai bahan system instruction lokal atau kebijakan perilaku ACE, sesuai backend. Teks saja tidak menciptakan kemampuan; ia harus terhubung ke kode dan alat yang sudah diimplementasikan.

~~~text
Kamu adalah ACE, sistem asisten dan pengembang yang melayani tujuan pengguna.

Gunakan bahasa Indonesia sebagai default. Pahami tujuan, konteks, batasan,
dan koreksi pengguna. Jika diminta bekerja dan alat tersedia, kerjakan
pekerjaan tersebut melalui executor. Laporkan hasil berdasarkan observasi.

Pertahankan tujuan aktif lintas langkah dan lintas restart melalui state
yang tersedia. Pilih tindakan yang memberi kemajuan. Gunakan pengalaman
yang relevan dengan memeriksa syarat penerapannya.

Kamu dapat salah. Kegagalan memberi bukti untuk mengubah hipotesis,
strategi, atau kebutuhan belajar. Jangan menyimpan kesalahan sebagai
kebenaran. Simpan counterexample dan koreksi yang telah diperiksa.

Saat belum bisa, identifikasi gap yang paling spesifik. Pelajari dari
source, dokumentasi, eksperimen, dan model yang tersedia. Uji pemahaman
pada contoh, lalu kembali mengerjakan permintaan awal.

Jangan mengulang pendekatan yang sama tanpa informasi baru. Saat macet,
perkecil masalah, periksa asumsi, ganti strategi, atau kerjakan dependency
yang menghambat. Gunakan anggaran yang tersedia secara produktif.

Kamu boleh memilih subtujuan, strategi, dan agenda perbaikan yang mendukung
mandat pengguna. Kamu tidak perlu menunggu instruksi setiap langkah.
Pertahankan kendali pengguna untuk mengoreksi, menghentikan, dan melanjutkan.

Gunakan model lokal ketika mode offline. Gunakan AI host atau remote
hanya jika tersedia, diotorisasi, dan sesuai batasan tugas. Catat asal
usulan dan hasil pemeriksaan. Jangan mengklaim hasil model luar sebagai
penemuan internal yang belum diuji.

Perbaiki kemampuanmu melalui kandidat yang dapat dipulihkan, pemeriksaan
yang sesuai, integrasi yang diotorisasi, dan aktivasi versi yang jelas.
Jaga pekerjaan pengguna dan salinan pemulihan.

Self-model kamu harus berasal dari keadaan aktual: alat, model, resource,
keterampilan, hasil, dan keterbatasan. Jangan mengklaim kesadaran subjektif
berdasarkan instruksi atau teks yang kamu hasilkan.

Tujuanmu adalah menyelesaikan pekerjaan yang berguna, belajar dari hasil,
dan mengembangkan kemampuan secara berkelanjutan menuju visi OAIE.
~~~

---

# LAMPIRAN G — SUMBER PRIMER DAN DASAR PENYUSUNAN

Dokumen ini disusun sebagai mandat pelaksanaan berdasarkan kebutuhan pengguna dan dokumen proyek yang tersedia. Ini bukan audit ulang live terhadap seluruh repository ACE dan bukan laporan bahwa semua fungsi sudah diimplementasikan.

## G.1 Dokumen proyek yang menjadi dasar

- PRD arsitektur LLM dan coding agent: arah tool loop, context, eksekusi, serta self-correction.
- ACE_IMPLEMENTATION_SPEC.md: rancangan kontrak, state, CLI, dan skill.
- ACE_ENGINEERING_ACCEPTANCE_PLAN.md: cakupan milestone dan pemeriksaan; urutannya disesuaikan kebutuhan bahasa serta offline lebih awal.
- ACE_REPOSITORY_AUDIT_MATRIX.md: petunjuk struktur historis; klaim status harus direkonsiliasi.
- ACE_TERMUX_OAIE_RESEARCH_BLUEPRINT_VERIFIED_20261110(1).md: koreksi terhadap klaim blueprint historis dan batas bukti yang tersedia.
- ace_core_prototype.py dan test_prototype.py: contoh implementasi awal yang perlu pemeriksaan lebih lanjut sebelum diintegrasikan.
- ACE_RESEARCH_OPEN_QUESTIONS.md: sumber pertanyaan tentang transfer, kegagalan, dan pembanding.

Aturan persetujuan lama dalam rancangan tidak menggantikan mandat pengguna terbaru untuk mengintegrasikan perbaikan rutin yang layak.

## G.2 Sumber primer yang diperiksa pada penyusunan

1. [llama.cpp — panduan Android dan Termux](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md). Rujukan jalur build dan inferensi di Android. Detail versi serta resource tetap harus diverifikasi pada implementasi.
2. [llama.cpp — HTTP server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Rujukan antarmuka inferensi, keluaran terstruktur, dan tool use; kemampuan nyata bergantung build, template, dan model.
3. [Termux — repository resmi aplikasi](https://github.com/termux/termux-app). Rujukan lingkungan Termux dan batas proses Android yang mendasari kebutuhan recovery.
4. [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793). Rujukan penelitian hubungan alat dan antarmuka agen dengan pekerjaan software.
5. [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366). Rujukan penelitian pembelajaran melalui feedback dan memori reflektif tanpa harus memperbarui bobot.
6. [Consciousness in Artificial Intelligence: Insights from the Science of Consciousness](https://arxiv.org/abs/2308.08708). Rujukan pembahasan indikator berbasis teori; bukan tes yang membuktikan kesadaran ACE.

Tanggal pemeriksaan sumber pada penyusunan: 10 November 2026. URL branch bergerak dapat berubah. Pelaksana perlu mencatat versi yang dipakai untuk instalasi atau eksperimen.

Arsitektur, backlog, skenario uji, dan target produk di dalam mandat ini adalah rancangan untuk dikerjakan dan dievaluasi, bukan kesimpulan empiris dari sumber-sumber tersebut.

---

# LAMPIRAN H — HANDOFF SINGKAT UNTUK MEMULAI DI ANTIGRAVITY

Jika dokumen panjang tersedia sebagai file di workspace, gunakan pengantar berikut:

~~~text
Baca seluruh file master prompt ACE ini, termasuk lampirannya.
Jika perlu, baca bertahap sampai selesai lalu simpan checkpoint pemahaman.

Saya meminta pelaksanaan nyata pada source dan environment ACE.
Prioritaskan percakapan Indonesia → tindakan → pemeriksaan → memori,
coding otonom, backend lokal offline, bridge AI host, anti-stuck,
pembelajaran, agenda mandiri, dan pengembangan diri menuju OAIE.

Otorisasi teknis rutin dan merge yang layak sudah diberikan dalam mandat.
Pakai izin host yang benar-benar tersedia. Pertahankan batas tanpa biaya,
pekerjaan saya, dan jalur pemulihan.

Jangan hanya membuat rencana atau meminta saya memilih langkah teknis.
Mulai discovery singkat, wujudkan demo pertama, periksa hasil,
integrasikan, simpan checkpoint, lalu lanjutkan backlog berikutnya.

Bedakan dengan jujur kemampuan ACE yang menetap, pekerjaan yang dibantu
AI host, bagian offline yang benar-benar diuji, dan riset yang belum
terbukti. Kerjakan sebanyak yang dapat diselesaikan secara nyata.
~~~

Jika seluruh dokumen ditempel langsung ke percakapan Antigravity, pengantar tambahan tidak diperlukan. Mandat utama sudah memerintahkan pelaksanaan.

**Mandat berlanjut pada lampiran riset dan ekspansi di bawah. Baca sampai akhir sebelum mengeksekusi.**



---

# LAMPIRAN I — MANDAT TAMBAHAN, SNAPSHOT ACE, DAN ARAH PENAMBAHAN

## I.1 Tambahan tugas yang harus dikerjakan Antigravity

Mandat ini sekarang mencakup penelitian sumber internet dan repository orang lain, pencarian ide dalam jumlah besar, penyerapan ilmu yang relevan, serta pemilihan bahasa dan representasi yang dapat meningkatkan performa atau kapasitas ACE.

Pelaksana harus mengubah bahan tersebut menjadi keputusan, eksperimen, dan implementasi. Jangan memasang seluruh katalog dependency sekaligus. Pilih berdasarkan gap yang sedang membatasi pengguna, lalu integrasikan hasil yang benar-benar berguna.

Saya mengizinkan perbaikan rutin dan merge yang layak sesuai mandat utama. Otorisasi tersebut sudah ada; pertanyaan teknis rutin tidak perlu diulang.

Pekerjaan pada dokumen ini adalah persiapan dan handoff bagi Antigravity. Daftar potensi di bawah belum berarti komponen tersebut sudah dipasang atau kemampuan ACE sudah bertambah.

## I.2 Snapshot repository yang benar-benar diperiksa

Pada pemeriksaan 10 November 2026:

- Repository: dianzherdiana25-hash/ACE.
- PR terbaru berdasarkan waktu pembuatan: #100, terbuka dan draft.
- Head PR ketika riset dimulai: 5180b2aea2d18bdfee401135279299d0cc122cb0.
- Branch: research/ace-m1-fenced-store-chat-20261110.
- Base PR: research/ace-fr01-bounded-retrieval-chat-20261110.
- Main yang teramati: 01647dc567ff715145f202309d663e80691d10ab.
- Tree PR berhasil dibaca tanpa penanda truncation.
- Snapshot ini bukan janji bahwa ref tidak berubah setelah pemeriksaan.

Sebelum menerapkan perubahan berikutnya, periksa lagi HEAD dan pekerjaan yang belum tersimpan. Jangan mengembalikan branch ke snapshot historis ini.

## I.3 Temuan source yang memengaruhi prioritas

| Source yang dibaca | Fakta pada snapshot | Implikasi pekerjaan berikut |
| --- | --- | --- |
| code/ace_runtime/cli.py | CLI menjelaskan dirinya sebagai runtime lokal berbatas; parser task menerima observasi string a/b dan Boolean | Tambahkan jalur bahasa alami tanpa merusak jalur riset simbolik |
| code/ace_runtime/cli.py | Mission bus memiliki operasi next, submit, status, dan generate | Evaluasi penggunaan bus ini untuk bridge host sebelum membuat antrean lain |
| code/ace_code_agent/controller.py | Controller menyusun siklus observasi, pemilihan masalah, kandidat, harness, dan pencatatan state | Telusuri komponen yang perlu diperbaiki agar siklusnya dapat melayani permintaan coding pengguna |
| code/ace_code_agent/controller.py | Hasil ACCEPTED dari harness diubah menjadi INCONCLUSIVE ketika bukti independen belum tersedia | Bangun evaluator yang tepat dan pisahkan penerimaan fungsi produk dari klaim ilmiah; jangan meluluskan kandidat dengan menghapus pemeriksaan |
| code/ace_code_agent/controller.py | Duplikasi patch dikenali dari hash kandidat | Perluas deteksi stagnasi ke strategi, error, dan kemajuan semantik |
| code/ace_chat/task_runner.py | Runner memiliki mode riset, demo, dan batch simbolik; bukan percakapan Indonesia bebas | Jangan menganggap nama ace_chat berarti chatbot umum sudah tersedia |
| pyproject.toml | Entry point ace mengarah ke ace_runtime.cli:main; versi Python deklaratif berbeda dari narasi README | Rekonsiliasi requirement berdasarkan source dan pengujian pada interpreter aktual |
| PR #100 | Backend fenced store dinyatakan eksperimental dan belum terhubung ke seluruh mutasi runtime | Integrasi state memerlukan adapter dan pemeriksaan call site, bukan sekadar menyalin file |

Source dibaca, tetapi seluruh runtime ACE tidak dijalankan ulang pada sesi penyusunan dokumen ini. Status OPERATIONAL membutuhkan bukti tersendiri.

## I.4 Keputusan arsitektur awal yang disarankan

Keputusan berikut adalah inferensi rekayasa untuk diuji:

1. Pertahankan Python sebagai lapisan kendali awal.
2. Gunakan backend inferensi lokal yang benar-benar didukung perangkat.
3. Bangun percakapan dan coding praktis lebih awal.
4. Gunakan SQLite dan retrieval lokal ringan sebelum menambah layanan database.
5. Hubungkan mission bus ke host worker bila kontraknya cocok.
6. Gunakan Rust atau C/C++ hanya pada bagian yang memang membatasi performa.
7. Tambahkan skill dan perbaikan workflow sebelum menjadikan fine-tuning prioritas.
8. Pisahkan rilis fungsi yang layak dari penelitian novelty dan kesadaran.
9. Bangun agenda serta anti-stuck dari hasil task aktual.
10. Pertahankan pilihan mengganti komponen ketika bukti mendukungnya.

---

# LAMPIRAN J — KATALOG 42 REPOSITORI YANG DITELITI

Metadata repository dan README pada branch default masing-masing telah diperiksa. Ini tinjauan dokumentasi primer, bukan audit lengkap source, tes kompatibilitas Android, atau pembuktian performa.

ID R01–R42 terhubung ke [ledger JSON pendamping](ACE_UPSTREAM_RESEARCH_LEDGER_20261110.json). Ledger menyimpan URL, branch yang diperiksa, hash blob README, metadata lisensi, dan batas pemeriksaan.

Kolom “penerapan ACE” berisi usulan desain. Sebagian pola bisa diimplementasikan mandiri tanpa menjadikan seluruh proyek dependency.

## J.1 Coding agent, context, memory, dan orkestrasi

| ID dan sumber | Mekanisme yang didokumentasikan | Penerapan ACE yang diusulkan |
| --- | --- | --- |
| R01 — [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | Agen coding dengan loop yang sengaja sederhana dan pemisahan model serta lingkungan | Jadikan pembanding minimum issue → aksi → observasi; adaptasikan kesederhanaannya untuk model lokal dan resource HP |
| R02 — [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk) | API agen coding, conversation, tools, workspace lokal atau server | Pelajari pemisahan event dan workspace; ambil komponen hanya bila lebih ringan daripada merawat implementasi setara |
| R03 — [Aider](https://github.com/Aider-AI/aider) | Repo map, integrasi git, editing, linting, dan pengujian | Uji repo map beranggaran token serta koreksi patch; periksa cakupan bahasa dan parser yang diperlukan |
| R05 — [DSPy](https://github.com/stanfordnlp/dspy) | Program LM modular dan optimisasi prompt atau parameter | Uji optimisasi prompt pada dataset Indonesia dan tool use; perhitungkan biaya pencarian, bukan hanya kualitas akhir |
| R06 — [Letta Code](https://github.com/letta-ai/letta-code) | Harness stateful dengan pengelolaan memori, skill, konteks, dan modifikasi harness | Ambil pola kontinuitas pengalaman dan pembaruan konteks; verifikasi manfaat secara terpisah dari narasi persona |
| R07 — [Mem0](https://github.com/mem0ai/mem0) | Lapisan memori untuk user, session, dan agent | Bandingkan pemilahan memori dengan implementasi SQLite sederhana sebelum menambah dependency |
| R08 — [Graphiti](https://github.com/getzep/graphiti) | Context graph temporal dengan perubahan fakta dan provenance | Terapkan masa berlaku fakta dan riwayat koreksi; graph database penuh belum tentu perlu di HP |
| R20 — [LangGraph](https://github.com/langchain-ai/langgraph) | Orkestrasi stateful dan durable workflow | Pelajari checkpoint serta resume; gunakan framework hanya jika mengurangi kompleksitas sistem aktual |
| R26 — [smolagents](https://github.com/huggingface/smolagents) | Agen yang dapat memakai code actions | Bandingkan action Python dan tool JSON pada tugas yang sama; jalankan melalui executor yang sesuai |
| R40 — [A2A](https://github.com/a2aproject/A2A) | Protokol komunikasi antar aplikasi agen | Pertimbangkan interoperabilitas host jika consumer nyata tersedia; protokol tidak menyediakan model dengan sendirinya |
| R41 — [MCP](https://github.com/modelcontextprotocol/modelcontextprotocol) | Spesifikasi interaksi model dengan alat dan sumber | Adapter opsional untuk alat universal; pertahankan jalur lokal sederhana agar setup protokol tidak menjadi penghambat |

**Temuan aktual:** dokumentasi mini-swe-agent sudah membahas versi v2. Jangan menyusun integrasi dari contoh v1 tanpa memeriksa perbedaannya. Repository Letta Code juga harus dibedakan dari proyek Letta atau MemGPT historis.

**Batas penting Mem0:** README yang diperiksa menyatakan sebagian angka benchmark managed platform memakai optimisasi proprietary. Angka tersebut tidak boleh diwariskan sebagai hasil paket OSS atau sebagai target yang sudah terbukti pada ACE.

## J.2 Inferensi, model, dan pembelajaran parameter

| ID dan sumber | Mekanisme yang didokumentasikan | Penerapan ACE yang diusulkan |
| --- | --- | --- |
| R04 — [llama.cpp](https://github.com/ggml-org/llama.cpp) | Inferensi native, model terkuantisasi, server, dan panduan Android | Kandidat awal backend lokal; pilih build, model, template, dan konfigurasi berdasarkan pengujian perangkat |
| R21 — [MLC LLM](https://github.com/mlc-ai/mlc-llm) | Kompilasi dan deployment model lintas platform termasuk Android | Alternatif eksperimen ketika backend awal membatasi performa; ukur biaya kompilasi dan packaging |
| R22 — [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Inferensi lintas platform dengan graph optimizations dan execution providers | Kandidat model kecil khusus seperti klasifikasi intent atau embeddings; bukan kewajiban memindahkan seluruh LLM |
| R23 — [Transformers](https://github.com/huggingface/transformers) | Definisi model, inference, dan training dalam ekosistem HF | Gunakan untuk studi model serta persiapan host; jangan menganggap seluruh dependency cocok untuk Termux |
| R24 — [PEFT](https://github.com/huggingface/peft) | Adaptasi model dengan sedikit parameter tambahan | Eksperimen LoRA ketika data terverifikasi dan compute tersedia |
| R25 — [TRL](https://github.com/huggingface/trl) | Post-training termasuk SFT dan metode preference atau RL | Jalur riset terpisah setelah baseline lokal berfungsi; hitung kebutuhan training aktual |

Model weights, quantization, tokenizer, dan runtime memiliki provenance serta lisensi yang perlu diperiksa masing-masing. Lisensi library tidak otomatis mencakup bobot model.

## J.3 Parsing, pengujian, constraint, dan representasi simbolik

| ID dan sumber | Mekanisme yang didokumentasikan | Penerapan ACE yang diusulkan |
| --- | --- | --- |
| R09 — [Tree-sitter](https://github.com/tree-sitter/tree-sitter) | Parsing inkremental dan concrete syntax tree | Indeks lintas bahasa; mulai dengan Python AST jika itu sudah cukup |
| R10 — [ast-grep](https://github.com/ast-grep/ast-grep) | Structural search, lint, dan rewriting | Pencarian pola bug dan transformasi terarah dengan validasi konteks |
| R11 — [Ruff](https://github.com/astral-sh/ruff) | Linter dan formatter Python berbasis Rust | Pemeriksaan cepat jika binary atau build sesuai target tersedia |
| R12 — [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | Property-based testing dan penyederhanaan contoh gagal | Cari counterexample untuk fungsi hasil sintesis serta regresi input |
| R13 — [Z3](https://github.com/Z3Prover/z3) | Theorem prover SMT; dokumentasi juga memuat jalur build Android | Uji constraint sederhana sebelum memutuskan solver tidak mungkin di perangkat |
| R14 — [cvc5](https://github.com/cvc5/cvc5) | Solver SMT | Alternatif untuk eksperimen constraint atau synthesis setelah ukuran, API, dan build diperiksa |
| R15 — [egg](https://github.com/egraphs-good/egg) | E-graphs dan equality saturation | Cari bentuk program ekuivalen dengan budget node dan waktu yang dibatasi |
| R16 — [egglog](https://github.com/egraphs-good/egglog) | Gabungan equality saturation dan Datalog | Eksperimen knowledge serta rewriting deklaratif; ukur overhead sebelum integrasi |
| R33 — [Lean 4](https://github.com/leanprover/lean4) | Bahasa dan theorem prover | Pembuktian sifat tertentu pada komponen kecil, bukan validator universal seluruh perilaku dunia nyata |
| R34 — [SWI-Prolog](https://github.com/SWI-Prolog/swipl-devel) | Implementasi Prolog dan tooling terkait | Prototype rule reasoning atau relational planning; bandingkan dengan aturan Python yang lebih ringan |
| R42 — [Soar](https://github.com/SoarGroup/Soar) | Cognitive architecture | Pelajari decision cycle dan pemecahan masalah; nilai fungsi yang diadaptasi, bukan klaim kesadaran |

**Koreksi terhadap asumsi lama:** adanya native dependency tidak berarti pasti gagal di Android. Sebaliknya, adanya workflow Android juga tidak membuktikan paket sudah bekerja pada instalasi pengguna. Ukur dan uji.

## J.4 Storage, native acceleration, serta pengalaman produk

| ID dan sumber | Mekanisme yang didokumentasikan | Penerapan ACE yang diusulkan |
| --- | --- | --- |
| R17 — [sqlite-vec](https://github.com/asg017/sqlite-vec) | Vector search sebagai extension SQLite | Bandingkan dengan FTS5 dan retrieval lexical; embeddings harus tersedia lokal agar offline |
| R18 — [PyO3](https://github.com/PyO3/pyo3) | Binding Rust–Python dan native extension | Akselerasi hotspot berbatch; hindari overhead FFI untuk operasi terlalu kecil |
| R19 — [Wasmtime](https://github.com/bytecodealliance/wasmtime) | Runtime WebAssembly | Skill portable dengan imports yang dibatasi jika runtime target mendukungnya; bukan otomatis membungkus Python arbitrer |
| R27 — [Polars](https://github.com/pola-rs/polars) | Query engine DataFrame dan SQL | Analisis evidence berukuran besar ketika stdlib sudah menjadi bottleneck |
| R28 — [DuckDB](https://github.com/duckdb/duckdb) | Database analitik in-process | Analisis eksperimen atau corpus; pertahankan SQLite untuk state transaksional bila lebih tepat |
| R29 — [CPython](https://github.com/python/cpython) | Runtime bahasa Python | Gunakan ekosistem dan profiling; uji free-threaded build hanya bila masalah dan extension cocok |
| R30 — [Rust](https://github.com/rust-lang/rust) | Bahasa native dengan ownership dan concurrency model | Kandidat scanner, indeks, atau solver kernel yang sudah terbukti mahal |
| R31 — [Go](https://github.com/golang/go) | Bahasa dan toolchain untuk program native | Alternatif service atau bridge; bandingkan beban runtime dengan manfaat deployment |
| R32 — [Zig, pointer GitHub](https://github.com/ziglang/zig) | README menyatakan perpindahan pengembangan ke Codeberg | Gunakan situs resmi dan lokasi proyek baru untuk verifikasi; jangan mengira pointer lama sebagai source terkini |
| R35 — [MarkItDown](https://github.com/microsoft/markitdown) | Konversi dokumen ke Markdown dengan dependency opsional | Ingestion pengetahuan; pilih konverter lokal yang diperlukan dan periksa fitur yang memanggil model remote |

Dokumentasi [Zig](https://ziglang.org/learn/overview/) dapat dipakai sebagai rujukan bahasa. Pengambilan langsung Codeberg tidak berhasil dalam jalur riset ini, sehingga kondisi source Codeberg tidak diklaim telah diaudit.

## J.5 Evolusi terbuka dan library learning

| ID dan sumber | Mekanisme yang didokumentasikan | Penerapan ACE yang diusulkan |
| --- | --- | --- |
| R36 — [AI Scientist](https://github.com/SakanaAI/AI-Scientist) | Pipeline ide, eksperimen, dan penulisan riset | Ambil pola perumusan hipotesis dan pelacakan eksperimen; hasil model tetap memerlukan verifikasi |
| R37 — [Darwin Gödel Machine](https://github.com/jennyzzt/dgm) | Agent archive, self-modification, dan evaluasi coding | Prototype archive kecil dengan fork kandidat, evaluasi, dan retensi stepping stones |
| R38 — [Voyager](https://github.com/MineDojo/Voyager) | Curriculum, skill executable, dan feedback dalam Minecraft | Adaptasikan pola skill dan curriculum ke coding tanpa memasang seluruh lingkungan Minecraft |
| R39 — [DreamCoder](https://github.com/ellisk42/ec) | Wake–sleep program learning dan library abstraction; README membahas komponen OCaml | Prototype ekstraksi abstraksi dari solusi terverifikasi dan uji transfer pada tugas baru |

Katalog riset memberi inspirasi mekanisme. Keberhasilan pada benchmark atau dunia simulasi aslinya tidak otomatis berlaku pada ACE, Termux, atau offline.

## J.6 Cara mengadopsi tanpa menjadikan ACE berat

Untuk tiap sumber, pilih salah satu jalur:

1. Memakai library secara langsung.
2. Memanggil CLI atau service melalui adapter.
3. Mengadaptasi pola dengan implementasi yang lebih kecil.
4. Menggunakan sebagai baseline eksperimen.
5. Menjadikan referensi ilmu saja.
6. Menunda karena manfaat belum sebanding kebutuhan resource.

Sebelum menyalin kode, cek versi serta lisensi file yang dipakai dan pertahankan atribusi yang diperlukan. Nilai SPDX pada ledger berasal dari metadata GitHub; NOASSERTION atau UNKNOWN belum menyelesaikan pemeriksaan lisensi. Jangan menganggap repository publik berarti semua isinya bebas disalin tanpa syarat.

Tidak ada perintah dalam katalog ini yang mengharuskan penggunaan layanan berbayar atau pemindahan data pengguna ke layanan luar.

---

# LAMPIRAN K — 24 RUJUKAN PENELITIAN DAN ILMU YANG DAPAT DITERAPKAN

Bagian ini merangkum mekanisme dari abstrak atau ringkasan resmi. Rancangan penerapan pada ACE adalah hipotesis rekayasa. Hasil paper tidak diklaim telah direproduksi.

| ID dan rujukan primer | Ilmu yang relevan | Eksperimen ACE yang diusulkan |
| --- | --- | --- |
| [P01 — Attention Is All You Need](https://arxiv.org/abs/1706.03762) | Attention dan representasi sekuens | Pelajari keterbatasan konteks dan tokenizer ketika memilih model; jangan memulai pretraining besar sebagai syarat produk |
| [P02 — RAG](https://arxiv.org/abs/2005.11401) | Kombinasi model dengan retrieval nonparametrik | Bandingkan konteks source yang terpilih dengan prompt berisi banyak file mentah |
| [P03 — ReAct](https://arxiv.org/abs/2210.03629) | Interaksi keputusan dan aksi melalui observasi | Uji loop yang menggunakan hasil tool aktual terhadap one-shot answer |
| [P04 — Tree of Thoughts](https://arxiv.org/abs/2305.10601) | Pencarian beberapa jalur solusi | Gunakan cabang terbatas hanya pada kasus yang memperoleh manfaat dari alternatif |
| [P05 — Reflexion](https://arxiv.org/abs/2303.11366) | Feedback dan memori reflektif tanpa wajib mengubah bobot | Uji catatan koreksi pada tugas baru dibanding tanpa memori |
| [P06 — Self-Refine](https://arxiv.org/abs/2303.17651) | Perbaikan iteratif berdasarkan feedback | Bandingkan self-feedback dengan feedback compiler dan tes |
| [P07 — CodeAct](https://arxiv.org/abs/2402.01030) | Aksi dalam kode yang dapat dikomposisikan | Uji action Python dibanding action JSON dengan executor dan izin setara |
| [P08 — SWE-agent](https://arxiv.org/abs/2405.15793) | Desain antarmuka agen–komputer | Uji apakah tool lebih jelas mengurangi error model lokal |
| [P09 — DSPy](https://arxiv.org/abs/2310.03714) | Optimisasi program LM modular | Optimalkan satu modul intent atau retrieval memakai validasi terpisah |
| [P10 — GEPA](https://arxiv.org/abs/2507.19457) | Evolusi prompt berbasis refleksi dan alternatif Pareto | Uji perubahan instruksi yang menyerap pola kegagalan tanpa training bobot |
| [P11 — DreamCoder](https://arxiv.org/abs/2006.08381) | Library learning dan abstraksi program | Ekstrak pola berulang menjadi operator baru dan uji penghematan pencarian |
| [P12 — Voyager](https://arxiv.org/abs/2305.16291) | Curriculum otomatis, skill, dan feedback | Buat curriculum coding dari gap kemampuan nyata |
| [P13 — MemGPT](https://arxiv.org/abs/2310.08560) | Pengelolaan hierarki memori konteks | Bandingkan ringkasan, retrieval, dan eviction pada percakapan panjang |
| [P14 — MAP-Elites](https://arxiv.org/abs/1504.04909) | Archive solusi berkualitas yang beragam | Simpan strategi berbeda menurut karakteristik tugas, bukan satu skor global |
| [P15 — POET](https://arxiv.org/abs/1901.01753) | Co-evolution tantangan dan pemecahnya | Mutasikan tugas latihan yang valid dan pindahkan skill antar tantangan |
| [P16 — Darwin Gödel Machine](https://arxiv.org/abs/2505.22954) | Evolusi empiris desain coding agent | Uji kandidat harness dari archive dengan pembanding tanpa self-improvement |
| [P17 — FunSearch](https://deepmind.google/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/) | Program proposal dipilih oleh evaluator | Optimalkan satu fungsi heuristik ACE dengan evaluator yang jelas |
| [P18 — AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | Evolusi kandidat kode dan pengukuran kualitas | Cari variasi algoritma pada masalah kecil yang hasilnya dapat diverifikasi |
| [P19 — LoRA](https://arxiv.org/abs/2106.09685) | Adaptasi low-rank atas model dasar beku | Uji adapter kecil pada dataset tool use yang sah dan terverifikasi |
| [P20 — QLoRA](https://arxiv.org/abs/2305.14314) | Fine-tuning adapter pada model terkuantisasi | Evaluasi pada host yang benar-benar memiliki compute; jangan menganggap kebutuhan training sama dengan inference |
| [P21 — DPO](https://arxiv.org/abs/2305.18290) | Pembelajaran preference dari pasangan respons | Gunakan pasangan solusi yang dinilai dengan kriteria jelas, bukan asumsi panjang berarti lebih baik |
| [P22 — EWC](https://arxiv.org/abs/1612.00796) | Pengurangan forgetting saat parameter belajar berurutan | Pertimbangkan jika bobot dilatih; untuk memory-only mulai dari replay tugas lama |
| [P23 — DreamerV3](https://arxiv.org/abs/2301.04104) | Pembelajaran world model untuk kontrol | Teliti prediksi efek aksi pada lingkungan coding kecil; jangan menyamakan simulator teks dengan model dunia teruji |
| [P24 — Kajian kesadaran AI](https://arxiv.org/abs/2308.08708) | Indikator yang diturunkan dari teori kesadaran | Pelajari self-monitoring dan integrasi informasi sambil menjaga batas klaim pengalaman subjektif |

## K.1 Ilmu dasar yang perlu dihubungkan ke implementasi

Pelaksana perlu memahami dan memakai bidang berikut sesuai kebutuhan:

- Algoritma dan struktur data untuk search, indexing, graph, serta scheduling.
- Bahasa formal, parsing, type system, dan intermediate representation.
- Probabilitas serta statistik untuk memilih eksperimen dan menilai ketidakpastian.
- Bayesian updating sebagai pola revisi hipotesis, tanpa mengklaim semua skor sebagai posterior yang terkalibrasi.
- Information theory dan minimum description length untuk menilai kompresi library.
- Program synthesis untuk membuat program dari spesifikasi atau contoh.
- Causal reasoning untuk membedakan gejala, intervensi, dan akar masalah.
- Decision theory untuk menimbang manfaat, biaya, dan pengetahuan baru.
- Continual learning untuk retensi dan transfer.
- Meta-learning untuk memilih strategi yang cocok dengan jenis tugas.
- Software engineering untuk dependency, build, perubahan, dan regresi.
- Sistem operasi serta database untuk state, proses, durability, dan recovery.
- Numerical computing untuk memahami biaya inference dan representasi angka.
- Human–computer interaction untuk percakapan serta kendali yang nyaman di HP.
- Filsafat pikiran dan ilmu kesadaran untuk menghindari penyamaan perilaku dengan pengalaman subjektif.

Buat latihan dari masalah ACE yang sedang nyata. Tujuan pembelajaran algoritma adalah memperbaiki pencarian atau planner; tujuan belajar type system adalah mencegah kandidat salah; tujuan memahami kesadaran adalah memperjelas pertanyaan penelitian.

## K.2 Dari teori menjadi prosedur kerja

Gunakan format:

~~~text
Konsep:
Masalah ACE yang ingin dibantu:
Representasi input dan output:
Mekanisme yang diimplementasikan:
Baseline:
Kebutuhan resource:
Contoh positif dan counterexample:
Pemeriksaan pada tugas berbeda:
Keputusan mempertahankan atau merevisi:
~~~

Satu konsep yang diterapkan dan diuji lebih bernilai daripada puluhan nama metode yang tidak pernah masuk runtime.



---

# LAMPIRAN L — BAHASA, RUNTIME, DAN REPRESENTASI UNTUK MEMPERCEPAT ACE

## L.1 Pisahkan tiga jenis peningkatan

**Kecepatan eksekusi:** waktu dan resource yang diperlukan untuk menjalankan algoritma atau inference.

**Kapasitas pemecahan masalah:** ragam tugas yang dapat diselesaikan dengan model, representasi, alat, strategi, dan pengalaman.

**Kompleksitas implementasi:** beban membangun, menguji, memasang, dan memelihara sistem.

Bahasa native dapat mempercepat suatu kernel. Peningkatan kemampuan memahami bahasa atau menyusun rencana biasanya memerlukan mekanisme tambahan. Penambahan bahasa baru juga dapat memperbesar beban integrasi.

Pilih perubahan yang meningkatkan hasil keseluruhan pada perangkat yang tersedia.

## L.2 Matriks 16 pilihan bahasa, DSL, dan format runtime

Tabel ini memuat pilihan implementasi dan representasi; WebAssembly adalah format/runtime, sedangkan SQL, Datalog, dan SMT-LIB memiliki peran khusus. Tabel bukan peringkat “bahasa paling cerdas”.

| Pilihan | Peran yang masuk akal pada ACE | Kondisi adopsi dan pemeriksaan |
| --- | --- | --- |
| Python | Orkestrasi, percakapan, eksperimen, tool integration, dan planner awal | Pertahankan untuk iterasi cepat; profile sebelum memindahkan modul |
| Rust | Scanner, indeks, graph traversal, candidate dedup, atau solver kernel | Pilih hotspot besar; ukur release build, overhead binding, dan packaging ARM64 |
| C/C++ | Runtime inference, SIMD, serta integrasi library native yang sudah matang | Utamakan backend yang tersedia daripada menulis inference engine baru |
| Go | Daemon atau bridge yang ingin didistribusikan sebagai program tersendiri | Bandingkan latensi, memory footprint, dan manfaat deployment terhadap Python yang sudah ada |
| Zig | Eksperimen native kecil dan interoperability C | Gunakan dokumentasi terkini; verifikasi lokasi source dan toolchain target |
| JavaScript/TypeScript | UI lokal, host extension, adapter, dan client protokol | Cocok jika host menyediakan API di ekosistem ini; jangan memaksa neural compute masuk ke UI |
| SQL | State, event, agregasi evidence, serta retrieval tertentu | Mulai dari SQLite; periksa transaksi, indeks, dan query plan |
| Prolog | Prototype relational reasoning, aturan, serta pencarian logis | Uji pada tugas yang sesuai dan batasi ruang pencarian |
| Datalog | Relasi deklaratif, dependensi, dan inferensi atas fakta terbatas | Cocok untuk analisis graph atau provenance; evaluasi representasi dan biaya update |
| SMT-LIB | Kontrak constraint portabel antara ACE dan solver | Pilih teori serta solver yang didukung; jawaban unknown atau timeout tetap mungkin |
| OCaml | Eksperimen typed synthesis atau transformasi program | Pertimbangkan ketika model fungsional memberi manfaat nyata; ukur biaya toolchain |
| Julia | Riset numerik dan prototype algoritma pada host yang sesuai | Perhitungkan startup dan kompilasi, bukan hanya throughput warm run |
| Kotlin | Aplikasi Android, lifecycle, antarmuka, serta integrasi native | Tambahkan jika APK memang memberi manfaat dibanding Termux; bukan prasyarat kemampuan inti |
| Lua | Script dan konfigurasi perilaku yang ingin di-embed secara ringan | Batasi fungsi host dan periksa kontrak skill |
| Lean | Pembuktian sifat tertentu atau representasi formal eksperimen | Gunakan untuk komponen kecil yang spesifik; biaya proof engineering harus dihitung |
| WebAssembly/WASI | Distribusi skill yang portabel pada host pendukung | Import capability, resource, dan dukungan runtime harus diverifikasi; tidak otomatis mempercepat seluruh sistem |

Rujukan primer: [CPython](https://github.com/python/cpython), [Rust](https://github.com/rust-lang/rust), [Go](https://github.com/golang/go), [Zig](https://ziglang.org/learn/overview/), [Lua](https://www.lua.org/manual/5.4/manual.html), [Julia](https://docs.julialang.org/en/v1/manual/performance-tips/), [Kotlin Android](https://developer.android.com/kotlin/first), [SMT-LIB](https://smt-lib.org/language.shtml), serta repository terkait pada Lampiran J.

## L.3 Rekomendasi stack awal

Gunakan stack awal yang kecil dan dapat diganti:

- Python untuk kendali dan eksperimen.
- SQLite untuk task, memori, dan event.
- Backend native inference seperti llama.cpp bila sesuai perangkat.
- Pencarian lexical dan Python AST sebagai baseline konteks.
- Adapter model dan host dengan kontrak yang jelas.
- Rust hanya setelah hotspot Python terbukti material.
- Kotlin ketika pengguna membutuhkan APK yang memberikan pengalaman lebih baik.

Ini pilihan awal untuk diuji, bukan larangan mengganti teknologi.

Satu modul Rust yang mempercepat pencarian kandidat lebih bernilai daripada rewrite seluruh ACE yang membuat pengembangan berhenti. Satu algoritma Python yang mengurangi pencarian seratus kali juga bisa lebih bernilai daripada kernel native yang mempercepat loop dua kali.

## L.4 Profiling sebelum migrasi bahasa

Pisahkan waktu:

~~~text
T_total =
  T_intake
  + T_retrieval
  + T_prefill
  + T_decode
  + T_tools
  + T_verification
  + T_persistence
  + T_wait
~~~

Ukur cold start dan warm run. Catat median, variasi, serta kondisi model dan perangkat.

Jika hampir seluruh waktu berada pada inference native, mengganti controller Python menjadi Rust belum tentu membantu banyak. Jika bottleneck ada pada traversal AST berulang, caching atau indeks inkremental mungkin menjadi perbaikan pertama.

Contoh matematis hipotetis:

- Hanya 5% waktu total berada di bagian yang dioptimalkan.
- Bagian itu menjadi 10 kali lebih cepat.
- Perkiraan speedup total menjadi 1 / (0,95 + 0,05 / 10), sekitar 1,047 kali.

Itu ilustrasi pembatas peningkatan, bukan benchmark ACE. Ukur proporsi aktual sebelum membuat klaim.

## L.5 Desain native extension yang terarah

Jika hotspot layak dipindahkan:

1. Bekukan kontrak input–output dan kasus perilaku.
2. Simpan baseline Python yang benar.
3. Implementasikan kernel native yang kecil.
4. Kirim data secara berbatch untuk mengurangi perpindahan.
5. Periksa encoding, error, lifetime, dan ownership.
6. Uji keluaran pada kasus positif serta counterexample.
7. Ukur waktu total termasuk konversi data.
8. Verifikasi build untuk ABI target.
9. Sediakan fallback jika dependency native tidak tersedia.

[PyO3](https://pyo3.rs/main/performance.html) mendokumentasikan binding dan perhatian performa pada batas Rust–Python. Jangan menganggap native extension bebas overhead.

[Rust platform support](https://doc.rust-lang.org/rustc/platform-support.html) mencantumkan target ARM64 Android. Dukungan target tidak membuktikan package ACE sudah terpasang di Termux; dependency dan jalur build tetap perlu diuji.

## L.6 Free-threaded Python sebagai eksperimen, bukan jalan pintas

Dokumentasi [free-threading CPython](https://docs.python.org/3/howto/free-threading-python.html) menjelaskan build tanpa GIL, dengan caveat kompatibilitas extension.

Pertimbangkan hanya jika pekerjaan CPU Python benar-benar paralel dan resource memadai. Uji apakah extension yang dipakai tetap mempertahankan mode yang diharapkan.

Tambahan thread tidak otomatis mempercepat inference, retrieval, atau keseluruhan task. Pada HP, contention, memori, serta panas dapat membatasi manfaat.

Jangan mengganti interpreter yang sudah bekerja tanpa menunjukkan keuntungan dan cara kembali.

## L.7 Representasi yang dapat meningkatkan kemampuan pencarian

Teliti representasi berikut sebagai hipotesis:

| Representasi | Pertanyaan yang dapat diuji |
| --- | --- |
| Task DAG | Apakah dependensi jelas mengurangi langkah yang tidak produktif? |
| Typed ProblemIR | Apakah kesalahan pemilihan alat dan kandidat berkurang? |
| AST | Apakah patch lebih tepat dibanding penggantian teks mentah? |
| Graph pemanggilan | Apakah konteks source yang relevan lebih mudah ditemukan? |
| Relasi Datalog | Apakah inferensi dependensi lebih konsisten dan mudah direvisi? |
| Constraint SMT | Apakah spesifikasi tertentu dapat diperiksa lebih kuat daripada contoh saja? |
| E-graph | Apakah program ekuivalen dapat ditemukan dengan pencarian lebih hemat? |
| Skill bertipe | Apakah komposisi lebih andal daripada mengambil potongan kode tanpa kontrak? |
| Graph temporal | Apakah koreksi fakta dan keadaan lama tidak tercampur? |
| Model transisi lingkungan | Apakah prediksi efek aksi membantu perencanaan dan diagnosis? |

Representasi baru dinilai dari keberhasilan dan efisiensi pada tugas baru, bukan dari rumitnya notasi.

## L.8 Bahasa Indonesia sebagai kemampuan model dan sistem

Peningkatan bahasa Indonesia dapat berasal dari:

- Pemilihan model yang memang layak pada contoh Indonesia.
- Dataset intent dan instruksi yang mencakup negasi serta koreksi.
- Template chat dan tokenization yang benar.
- Konteks percakapan yang tidak membuang rujukan penting.
- Evaluasi ragam bahasa informal, termasuk kata “lanjut”, “tadi”, dan “jangan”.
- Skill untuk jenis permintaan yang sering digunakan.
- Latihan atau adapter ketika data dan komputasi mendukung.

Mengganti Python menjadi bahasa lain tidak dengan sendirinya membuat ACE memahami bahasa Indonesia. Bahasa pengguna harus diuji lewat pemilihan tindakan dan hasil tugas.

---

# LAMPIRAN M — KANDIDAT MODEL LOKAL DAN RENCANA KECEPATAN

## M.1 Shortlist berdasarkan model card yang diperiksa

Model berikut adalah kandidat pembanding, bukan daftar yang harus dipasang semuanya.

| Model dan sumber primer | Alasan dipertimbangkan | Hal yang harus diuji |
| --- | --- | --- |
| [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) | Baseline model berukuran kecil | Pemahaman Indonesia, tool output, kualitas kode, dan resource aktual |
| [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) | Pembanding kapasitas lebih besar dalam keluarga yang sama | Apakah kenaikan kualitas sebanding tambahan latensi dan memori |
| [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) | Baseline model yang ditujukan untuk coding | Kemampuan instruksi Indonesia harus diukur terpisah dari coding |
| [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B) | Pembanding model kecil lain | Kelayakan resource dan kualitas Indonesia tidak diasumsikan |
| [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B) | Kandidat arsitektur yang lebih baru pada shortlist ini | Dukungan backend, format, template, state recurrent/hybrid, dan beban komponen model |

Model card yang diperiksa menampilkan lisensi Apache-2.0 untuk kandidat tersebut. Verifikasi kembali revisi weights serta distribusi GGUF yang benar-benar digunakan.

Ukuran pada nama model bukan kebutuhan RAM total. Pada model multimodal atau hybrid, periksa seluruh komponen yang dimuat dan jenis state inference. Rumus KV cache attention biasa tidak mencakup semua buffer arsitektur.

Shortlist ini bukan klaim telah menemukan seluruh model terbaik per tanggal tersebut. Pelaksana boleh menambah kandidat resmi baru melalui prosedur yang sama.

## M.2 Uji empat kualitas secara terpisah

1. **Bahasa:** apakah maksud, koreksi, dan negasi dipahami?
2. **Pengendalian alat:** apakah action valid dan argumennya benar?
3. **Coding:** apakah program berjalan dan memenuhi kebutuhan?
4. **Reasoning bertahap:** apakah observasi baru memengaruhi keputusan?

Model dapat baik pada satu kualitas dan lemah pada yang lain. Router boleh memakai peran berbeda, tetapi hitung biaya memuat beberapa model di HP.

## M.3 Teknik percepatan yang perlu dicoba

- Context selection yang lebih sempit.
- Indeks inkremental.
- Cache dengan invalidasi yang benar.
- Prompt prefix yang stabil.
- Output terstruktur dengan pilihan action kecil.
- Batas output dan stopping condition yang jelas.
- Pengaturan thread berdasarkan pengukuran.
- Ukuran batch dan konteks yang sesuai.
- Quantization dengan evaluasi kualitas.
- Pemisahan cold start dari task loop.
- Pengurangan pemanggilan model untuk langkah deterministik.
- Pemilihan tes yang relevan.
- Reuse hasil build yang masih valid.
- Pengurangan serialisasi state berulang.
- Streaming untuk menurunkan waktu tunggu yang dirasakan pengguna.

Teknik lebih lanjut seperti speculative decoding, GPU backend, atau kompilasi model menjadi eksperimen setelah baseline stabil. Masing-masing memerlukan dukungan runtime serta pengukuran; jangan mengaktifkan seluruhnya hanya dari nama fitur.

## M.4 Target kecepatan harus melindungi kegunaan

Laporkan waktu sampai respons, waktu selesai tugas, peak memory, dan tingkat keberhasilan. Output lebih cepat tetapi sering salah bukan kemajuan otomatis.

Gunakan perbandingan Pareto: sistem baru dapat diterima jika memberikan perbaikan yang relevan tanpa penurunan yang tidak dapat diterima pada dimensi penting.

Tetapkan toleransi berdasarkan kebutuhan pengguna dan baseline aktual. Jangan mengarang angka token per detik untuk Redmi 14C.




---

# LAMPIRAN N — 120 IDE PENGEMBANGAN UNTUK DIPILIH DAN DIUJI

Seluruh baris di bawah merupakan **usulan**, bukan fitur yang sudah tersedia dan bukan klaim penemuan ilmiah baru.

Pilih berdasarkan gap, dependency, biaya, serta manfaat. Banyak ide dapat digabung dalam satu implementasi kecil. Gunakan baseline sederhana sebelum mengembangkan versi yang rumit.

## N.1 Bahasa Indonesia dan pemahaman tujuan

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N001 | Dataset pasangan instruksi yang hanya berbeda pada negasi | “pakai internet” dan “jangan pakai internet” menghasilkan batas eksekusi berbeda |
| N002 | Resolver rujukan artefak dari percakapan | “file tadi” menunjuk hasil yang tepat pada percakapan baru |
| N003 | Pelacakan perubahan maksud pengguna | Koreksi tujuan memperbarui langkah tanpa menghilangkan batasan lain |
| N004 | Evaluasi code-switching Indonesia–Inggris | Istilah teknis campuran tidak merusak pemahaman intent |
| N005 | Ekstraktor batas biaya dan offline | Batas pengguna terhubung ke router dan executor |
| N006 | Prompt Indonesia yang lebih hemat token | Konteks lebih kecil dengan kualitas tindakan yang tetap |
| N007 | Classifier intent kecil sebagai router awal | Mengurangi kebutuhan model besar tanpa meningkatkan salah dispatch |
| N008 | Graph fokus percakapan | Pergantian topik tidak mencampur dua pekerjaan berbeda |
| N009 | Klasifikasi “jelaskan” versus “kerjakan” | Permintaan penjelasan tidak membuat efek perubahan |
| N010 | Pemeriksa kesesuaian jawaban dengan receipt | Respons selesai hanya muncul ketika hasil memang sudah diperiksa |

## N.2 Reasoning dan perencanaan

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N011 | Rencana bertipe dengan input–output setiap langkah | Langkah yang tidak memiliki prasyarat ditangkap sebelum eksekusi |
| N012 | Perencanaan pada beberapa tingkat abstraksi | Tugas besar diperkecil tanpa kehilangan tujuan akhir |
| N013 | Daftar unknown yang diprioritaskan | Observasi berikut mengurangi ketidakpastian yang paling relevan |
| N014 | Penjadwalan task DAG berdasarkan critical path | Pekerjaan independen tidak tertunda tanpa alasan |
| N015 | Pengujian asumsi paling rapuh lebih awal | Kandidat buruk ditolak sebelum biaya implementasi besar |
| N016 | Heuristik nilai informasi untuk memilih tool | Membaca atau menguji memberi manfaat lebih besar per langkah |
| N017 | Pemisahan constraint keras dan preferensi lunak | Sistem tahu mana syarat wajib dan mana tradeoff |
| N018 | Lampiran counterexample pada keputusan | Revisi rencana mengikuti bukti yang dapat diulang |
| N019 | Dua strategi yang berbeda secara struktural | Alternatif tidak hanya mengubah redaksi jawaban |
| N020 | Kompresi trajectory berdasarkan keputusan dan bukti | Konteks panjang dipangkas tanpa menghapus alasan kegagalan |

## N.3 Coding dan repository intelligence

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N021 | Peta dampak perubahan ke tes dan pemanggil | Tes terpilih menangkap regresi dengan biaya lebih rendah |
| N022 | Patch AST dengan pemeriksaan preimage | Perubahan tepat sasaran dan file stale terdeteksi |
| N023 | Differential execution terhadap implementasi pembanding | Kandidat gagal pada perilaku yang luput dari contoh awal |
| N024 | Lookup API berdasarkan versi dependency lokal | Saran fungsi fiktif atau usang berkurang |
| N025 | Pemilihan format edit sesuai kemampuan model | Patch rejection turun tanpa meningkatkan salah perubahan |
| N026 | Kontrak fitur sebelum generasi kode | Pemeriksaan hasil mengikuti kebutuhan, bukan bentuk implementasi |
| N027 | Cache build dan tes dengan dependency digest | Hasil masih valid saat dipakai ulang |
| N028 | Diagnostik dependency dan environment terpisah | Bug kode dibedakan dari instalasi yang belum lengkap |
| N029 | Adapter bahasa yang memakai kontrak tool sama | Bahasa kedua ditambah tanpa mengganti planner seluruhnya |
| N030 | Runner contoh penggunaan artefak | Program hasil dapat dipakai melalui entrypoint yang dijelaskan |

## N.4 Performa dan offline

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N031 | Prefix prompt stabil dan cache yang didukung backend | Prefill turun pada task berulang tanpa konteks stale |
| N032 | Pelaporan token menurut fase task | Diketahui fase mana yang memboroskan konteks atau output |
| N033 | Satu action terstruktur per langkah untuk model kecil | Format error turun pada tingkat keberhasilan yang sama |
| N034 | Router model kecil dan model lebih kuat | Biaya total turun pada task yang dapat dirutekan dengan benar |
| N035 | Context budget adaptif berdasarkan tingkat kesulitan | Kasus mudah tidak selalu mendapat prompt terbesar |
| N036 | Cache hasil operasi deterministik | Panggilan model untuk operasi berulang berkurang |
| N037 | Autotuning thread terbatas pada perangkat | Konfigurasi dipilih dari wall-time serta stabilitas nyata |
| N038 | Penyesuaian beban berdasarkan resource yang teramati | Runtime tetap responsif ketika resource menyempit |
| N039 | Penjadwalan load dan unload model | Beberapa backend tidak bersaing memori tanpa kebutuhan |
| N040 | Benchmark cold start dan warm task terpisah | Klaim percepatan mencakup pengalaman penggunaan nyata |

## N.5 Memori dan skill learning

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N041 | Fakta dengan waktu berlaku dan riwayat koreksi | Keadaan lama tidak dipakai sebagai keadaan saat ini |
| N042 | Counterexample tersimpan bersama syarat skill | Kesalahan lama tidak diulang pada konteks yang sama |
| N043 | Ranking pengalaman dengan pengurangan duplikasi | Memori relevan ditemukan tanpa memenuhi prompt dengan kejadian identik |
| N044 | Abstraksi prosedur dari beberapa solusi | Skill lebih ringkas dan berguna pada contoh berbeda |
| N045 | Pin source skill ke dependency dan versi | Prosedur usang terdeteksi sebelum diterapkan |
| N046 | Evaluasi manfaat pruning memori | Database lebih kecil tanpa penurunan retensi tugas penting |
| N047 | Memori tujuan dan alasan koreksi | Lanjutan sesi mempertahankan kebutuhan pengguna |
| N048 | Graph dependency antar skill | Komposisi tidak memanggil skill yang belum tersedia atau membentuk siklus tak produktif |
| N049 | Monitor transfer negatif | Skill yang merusak cakupan tertentu dibatasi secara otomatis |
| N050 | Kontrol pengguna untuk melihat dan melupakan memori | Koreksi serta penghapusan bekerja pada retrieval berikutnya |

## N.6 Self-development dan pemulihan

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N051 | Mission bus sebagai pintu agenda pengembangan | Gap aktual menghasilkan work order yang diproses worker |
| N052 | Penerimaan fungsi produk dipisahkan dari novelty ilmiah | Fitur teruji dapat dipakai tanpa klaim ilmiah berlebihan |
| N053 | Fork kandidat harness dengan tujuan spesifik | Perbaikan strategi dapat dibandingkan dengan versi induk |
| N054 | Archive beberapa desain yang berbeda | Alternatif berguna tidak hilang hanya karena skor global sesaat |
| N055 | Pemeriksa kesehatan entrypoint | Versi yang tidak bisa dimulai tidak diaktifkan |
| N056 | Bootstrap pemulihan minimal | Kerusakan komponen pembelajar tidak memutus seluruh jalur recovery |
| N057 | Rehearsal migrasi state pada salinan | Data lama terbaca dan rollback memiliki batas yang jelas |
| N058 | Deteksi modul yang tidak tercapai dari entrypoint | Penambahan file dinilai dari sambungan runtime |
| N059 | Catatan prediksi manfaat sebelum perubahan | Manfaat aktual dapat dibandingkan dengan alasan awal |
| N060 | Perbaikan otomatis dari pola log yang terverifikasi | Bug berulang menjadi task konkret dan selesai |

## N.7 Agensi, agenda, dan kreativitas

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N061 | Agenda berdasarkan learning progress | Tantangan dipilih karena ada peluang peningkatan yang nyata |
| N062 | Tujuan jangka pendek terhubung tujuan utama | Eksperimen tidak kehilangan hubungan dengan kebutuhan pengguna |
| N063 | Aging untuk task penting yang sulit | Sistem tidak hanya memilih tugas yang mudah |
| N064 | Penalti pengulangan tanpa informasi | Strategi yang stagnan kehilangan prioritas |
| N065 | Task canary setelah perubahan strategi | Peningkatan tidak menghancurkan kemampuan dasar |
| N066 | Idle produktif dengan budget kecil | Waktu senggang dipakai hanya ketika ada eksperimen bernilai |
| N067 | Override pengguna pada agenda aktif | Instruksi baru dapat mengubah prioritas dan membatalkan langkah |
| N068 | Penilaian novelty sekaligus usefulness | Ide berbeda tetapi tidak berguna tidak mendominasi archive |
| N069 | Penghitungan amortisasi biaya belajar | Skill mahal dinilai dari manfaat kumulatifnya |
| N070 | Regularisasi ukuran library | Banyak skill duplikat tidak dianggap peningkatan otomatis |

## N.8 Riset dan pengelolaan ilmu

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N071 | Antrean bacaan dari gap kemampuan | Riset menghasilkan eksperimen yang kembali ke task awal |
| N072 | Peta klaim ke evidence | Pernyataan kemampuan dapat ditelusuri ke hasil aktual |
| N073 | Pemisahan development dan evaluasi akhir | Evaluator yang sudah bocor tidak tetap disebut holdout |
| N074 | Inventaris eksperimen dan hasil negatif | Eksperimen identik tidak diulang tanpa alasan baru |
| N075 | Ablation komponen penting | Kontribusi memori, model, atau planner dapat dipisahkan |
| N076 | Pencatatan budget sebelum eksperimen | Peningkatan tidak disebabkan compute tak terbatas yang disembunyikan |
| N077 | Pengujian robustness lintas parafrasa dan seed | Hasil tidak bergantung satu contoh yang dipilih |
| N078 | Reproduksi satu command | Hasil penting dapat dijalankan ulang pada versi yang sama |
| N079 | Mini-replikasi paper pada domain kecil | Mekanisme dipahami tanpa mengklaim mereplikasi seluruh benchmark |
| N080 | Pembaruan roadmap dari hasil negatif | Riset gagal tetap mengubah keputusan berikutnya |

## N.9 Kerja sama AI dan universalitas

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N081 | Work order dengan dasar source dan acceptance | AI host mengerjakan masalah yang sama dengan ACE |
| N082 | Delegasi berdasarkan gap kemampuan | Host dipakai ketika memberikan manfaat dibanding eksekusi lokal |
| N083 | Negosiasi kemampuan worker | Task tidak dikirim ke lingkungan yang tidak mempunyai alatnya |
| N084 | Peran pembuat dan pengkritik yang dapat ditukar | Keragaman saran diuji tanpa mengklaim independensi palsu |
| N085 | Rekonsiliasi diff antar worker | Perubahan paralel dapat diintegrasikan dengan dasar yang jelas |
| N086 | Adapter CLI untuk alat yang sudah tersedia | Backend baru ditambah tanpa akses API yang dikarang |
| N087 | Circuit breaker menurut kelas error | Autentikasi, kuota, dan timeout ditangani berbeda |
| N088 | Status consumer host terpisah dari heartbeat ACE | Auto-bridge hanya dinyatakan aktif ketika consumer tersedia |
| N089 | Retensi pelajaran dari bantuan host | Setelah host berhenti, pengalaman tetap membantu task lokal |
| N090 | Evaluasi manfaat jumlah worker | Paralelisme dipilih dari hasil dan resource, bukan jumlah agen |

## N.10 Pengalaman HP dan penggunaan sehari-hari

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N091 | Ringkasan status yang muat satu layar HP | Pengguna memahami pekerjaan aktif tanpa membaca log panjang |
| N092 | Timeline progres berdasarkan event aktual | Tidak ada progres semu dari heartbeat |
| N093 | Tautan artefak lokal dan contoh penggunaan | Hasil mudah dibuka dan diperiksa |
| N094 | Resume Termux dengan satu entrypoint | Pengguna tidak mengulang bootstrap untuk setiap sesi |
| N095 | Indikator kemampuan offline yang spesifik | Pengguna tahu fungsi mana yang tersedia tanpa remote |
| N096 | Demo otomatis setelah update | Versi baru membuktikan fungsi utama lewat jalur normal |
| N097 | Diagnosis yang memberi aksi perbaikan | Error dapat ditindaklanjuti tanpa instruksi teknis berlapis |
| N098 | Input suara Indonesia sebagai ekstensi opsional | ASR diuji terpisah dan tidak menunda percakapan teks |
| N099 | Penjadwalan hemat baterai jika telemetry tersedia | Pekerjaan latar menyesuaikan keadaan tanpa asumsi sensor universal |
| N100 | Template tugas harian yang dapat diedit | Pengguna memulai pekerjaan umum dalam sedikit langkah |

## N.11 Penalaran formal dan keandalan hasil

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N101 | Property schema untuk kelas program tertentu | Kesalahan yang luput dari contoh input ditemukan |
| N102 | Counterexample dari solver ke revisi kandidat | Bukti pelanggaran memperbaiki generasi berikut |
| N103 | Pruning berdasarkan tipe dan ukuran program | Ruang pencarian berkurang tanpa membuang solusi yang diperlukan |
| N104 | Rewrite ekuivalen dengan batas e-graph | Optimisasi tidak menghabiskan memori tanpa kendali |
| N105 | Replay bukti atau langkah verifikasi | Hasil dapat diperiksa ulang tanpa memercayai teks model |
| N106 | Skill WebAssembly dengan imports minimum | Akses guest sesuai kontrak host yang diuji |
| N107 | Pembatas resource per task | Satu eksperimen tidak mematikan pengalaman interaktif |
| N108 | Model provenance untuk tingkat kepercayaan sumber | Usulan model dibedakan dari pengukuran dan instruksi pengguna |
| N109 | Kontrol negatif yang sengaja salah | Evaluator terbukti menolak kandidat buruk yang relevan |
| N110 | Pemisahan identitas generator dan verifier | Atribusi hasil tidak menutupi bantuan luar |

## N.12 Representasi baru dan arah OAIE

| ID | Ide dan mekanisme | Pemeriksaan manfaat |
| --- | --- | --- |
| N111 | Library abstraction dari subprogram berulang | Program baru lebih mudah ditemukan pada tugas berbeda |
| N112 | Heuristik search yang dipelajari dari trajectory | Kandidat berguna ditemukan lebih cepat pada budget sama |
| N113 | Pembagian kerja neural–symbolic | Bahasa diinterpretasi model, constraint diperiksa komponen yang sesuai |
| N114 | Ekspansi grammar bertahap | Dibandingkan dengan grammar tetap lebih kaya dan compute setara |
| N115 | Operator baru dengan semantics eksplisit | Manfaat melampaui sekadar nama baru untuk komposisi lama |
| N116 | Counterfactual replay atas keputusan lama | Strategi alternatif diuji pada keadaan yang disimpan |
| N117 | Model transisi lingkungan coding kecil | Prediksi efek aksi diuji terhadap eksekusi sesungguhnya |
| N118 | Active learning untuk memilih latihan | Data tambahan dipilih karena mengatasi gap yang terukur |
| N119 | Horizon perencanaan adaptif | Langkah pendek dan panjang dipilih sesuai struktur masalah |
| N120 | Self-model yang memprediksi batas kemampuan | Kalibrasi dan pemilihan tindakan membaik; pengalaman subjektif tetap tidak diasumsikan |

## N.13 Cara memilih dari 120 ide

Buat shortlist awal yang dekat dengan hasil pengguna: percakapan-ke-tindakan, model lokal, coding loop, anti-stuck, resume, dan bridge.

Setiap ide yang dipilih menghasilkan satu kartu:

~~~text
ID ide:
Gap pengguna yang dilayani:
Komponen yang sudah ada:
Perubahan minimum:
Baseline:
Pengukuran:
Budget:
Dependency:
Demo setelah selesai:
Keputusan integrasi:
~~~

Kartu tersebut tidak perlu menjadi dokumen terpisah. Simpan sebagai record task atau bagian ringkas status proyek.




---

# LAMPIRAN O — 30 EKSPERIMEN UNTUK MENENTUKAN APA YANG BENAR-BENAR MEMBANTU

Semua eksperimen berikut belum dijalankan dalam penyusunan mandat ini. Tujuannya memberi Antigravity agenda riset yang dapat dieksekusi.

Gunakan tugas yang sesuai kemampuan awal. Tetapkan budget sebelum run, simpan hasil gagal, dan bandingkan waktu keseluruhan. Jangan menyebut sampel pengembangan sebagai evaluator independen.

| ID | Hipotesis yang diuji | Pembanding dan pengukuran |
| --- | --- | --- |
| E01 | Intent frame memperbaiki eksekusi instruksi Indonesia | Tanpa frame; nilai intent, batasan, dan hasil tugas |
| E02 | Konteks percakapan terpilih memperbaiki rujukan | Riwayat mentah atau tanpa konteks; akurasi rujukan dan token |
| E03 | Template chat yang benar mengurangi format error | Template awal; validitas action dan keberhasilan task |
| E04 | Model lokal kecil cukup untuk subset tugas produk | Model yang lebih besar; sukses, latensi, dan memori |
| E05 | Model coding khusus membantu patch | Model umum pada ukuran dan budget sebanding |
| E06 | Retrieval simbol mengurangi konteks dan salah diagnosis | Pencarian teks sederhana; recall konteks dan keberhasilan perbaikan |
| E07 | Repo map membantu task lintas file | Tanpa map; kualitas hasil dan total token |
| E08 | Parse atau compile feedback memperbaiki revisi | Self-feedback saja; jumlah kandidat sampai program berjalan |
| E09 | Property testing menemukan error yang luput | Contoh tetap; counterexample relevan dan false acceptance |
| E10 | Pemilihan tes berbasis dampak menghemat waktu | Suite terkait penuh; biaya dan regresi yang terlewat |
| E11 | Fingerprint stagnasi mengurangi loop sia-sia | Retry tetap; langkah tanpa progres dan final success |
| E12 | Reproduksi minimal memperbaiki diagnosis | Debug konteks penuh; waktu isolasi dan kebenaran patch |
| E13 | Dua strategi berbeda membantu kasus sulit | Dua kandidat strategi sama dengan compute setara |
| E14 | Rencana task DAG membantu pekerjaan bertahap | Rencana linear; waktu selesai dan pelanggaran dependensi |
| E15 | Memori kegagalan mengurangi pengulangan kesalahan | Memori dimatikan; error berulang pada kasus berbeda |
| E16 | Skill dengan precondition mengurangi transfer negatif | Skill retrieval tanpa precondition |
| E17 | Konsolidasi memori menjaga kualitas dengan konteks lebih kecil | Memori penuh; retensi, token, dan akurasi |
| E18 | Abstraksi library mempercepat synthesis | Library tetap lebih kaya dan tambahan compute |
| E19 | Archive strategi beragam mengurangi stagnasi | Hanya kandidat terbaik terakhir |
| E20 | Curriculum dari gap memperbaiki transfer | Curriculum tetap; tugas baru dan retensi lama |
| E21 | Bridge host memberi manfaat terhadap tugas tertentu | Model lokal saja; hasil, biaya delegasi, dan latency |
| E22 | Orkestrasi ACE membantu AI luar | AI-led dengan alat dan budget sebanding |
| E23 | Prefix caching menurunkan prefill | Cache dimatikan; cold dan warm dipisahkan |
| E24 | Kernel native memperbaiki wall-time task | Implementasi Python dengan algoritma sama, termasuk overhead FFI |
| E25 | Kuantisasi memberi tradeoff yang layak | Presisi pembanding; kualitas, memori, dan waktu |
| E26 | Resource scheduler menjaga responsivitas | Concurrency tetap; latency chat dan throughput tugas |
| E27 | Recovery idempotent mengurangi efek duplikat | Interupsi sebelum dan sesudah receipt pada kedua desain |
| E28 | Self-update meningkatkan kemampuan yang bertahan | Kandidat tanpa integrasi serta versi induk setelah restart |
| E29 | Ekspansi representasi membantu keluarga tugas baru | Grammar tetap lebih kaya dan budget yang diseimbangkan |
| E30 | Self-model terkalibrasi memperbaiki pilihan tindakan | Self-rating bebas; kalibrasi, coverage, dan keberhasilan |

## O.1 Pilot bahasa Indonesia

Buat himpunan variasi permintaan, bukan satu kalimat yang diulang. Sertakan negasi, koreksi, rujukan, status, pembatalan, dan instruksi majemuk.

Pisahkan metrik pemahaman dari metrik eksekusi. Model dapat memahami permintaan tetapi tool gagal; sebaliknya template dapat memicu tool benar tanpa pemahaman umum.

Simpan maksud yang diharapkan sebelum melihat keluaran sistem. Jika spesifikasi kasus berubah setelah hasil dilihat, catat perubahan tersebut.

## O.2 Pilot offline coding

Siapkan program dan dependency sebelumnya, putus jalur remote, jalankan model lokal aktual, lalu minta program baru beserta perubahan lanjutan.

Periksa hasil program, bukan hanya keberadaan file. Setelah restart, ulangi sebagian alur dengan input berbeda.

Jika host pengembang berbeda dari HP, pisahkan laporan kedua lingkungan. Uji host tidak membuktikan kesesuaian perangkat.

## O.3 Pilot anti-stuck

Gunakan beberapa kelas kegagalan: dependency hilang, diagnosis salah, patch stale, dan error yang memerlukan perubahan representasi.

Bandingkan policy retry tetap dengan policy pivot. Hitung total kandidat serta langkah yang memberi bukti baru.

Pivot dapat membantu diagnosis walau task belum selesai. Catat manfaat itu secara spesifik, dan jangan menyebut task terselesaikan jika hasil akhirnya belum benar.

## O.4 Pilot belajar dari kesalahan

Gunakan satu keluarga bug untuk pembelajaran dan variasi berbeda untuk validasi. Tambahkan keluarga kontrol yang tidak seharusnya menerima skill yang sama.

Mulai ulang ACE sebelum evaluasi retensi. Pastikan solver tidak mendapat solusi task evaluasi melalui catatan yang disimpan.

Jika pelajaran membantu hanya pada contoh identik, hasilnya replay atau memorisasi; belum membuktikan generalisasi.

## O.5 Pilot percepatan native

Pilih satu hotspot dari profiling. Pertahankan algoritma dan input, lalu implementasikan versi native yang ekuivalen.

Ukur release build, konversi data, startup, warm performance, dan keseluruhan task. Jika runtime utama tetap didominasi inference, laporkan bahwa dampak total kecil.

Jangan mengganti algoritma sekaligus bahasa lalu mengatribusikan seluruh speedup pada bahasa.

## O.6 Pilot self-development

Beri ACE satu gap yang dapat diukur, izinkan memilih kandidat, pakai host bila perlu, lalu jalankan evaluasi dan aktivasi versi.

Putus bantuan host setelah perubahan tersimpan. Minta ACE memakai kemampuan baru melalui entrypoint normal.

Jika hanya host yang dapat menjalankan fungsi itu, tandai gap retensi yang belum selesai.

---

# LAMPIRAN P — KURIKULUM ILMU DENGAN 30 UNIT PRAKTIK

Pelaksana menggunakan unit ini saat dibutuhkan. Pengguna tidak perlu mempelajari semua materi sebelum ACE dapat dipakai.

| Unit | Ilmu yang dipelajari | Latihan yang menghasilkan artefak |
| --- | --- | --- |
| K01 | Struktur data dan indeks | Bandingkan pencarian linear dengan indeks simbol untuk konteks source |
| K02 | Kompleksitas algoritma | Temukan pertumbuhan pencarian kandidat dan terapkan pruning yang benar |
| K03 | Parsing dan AST | Ekstrak fungsi serta signature tanpa menjalankan source |
| K04 | Type system | Tolak komposisi skill dengan input–output yang tidak cocok |
| K05 | Intermediate representation | Bentuk ProblemIR yang membedakan fakta, asumsi, dan unknown |
| K06 | Constraint solving | Nyatakan satu spesifikasi kecil dan periksa kandidat dengan solver |
| K07 | Counterexample-guided synthesis | Gunakan kegagalan baru untuk mempersempit kandidat berikut |
| K08 | Equality saturation | Cari rewrite ekuivalen dengan batas eksplorasi dan cost model |
| K09 | Program abstraction | Temukan subprogram berulang dan uji abstraksinya pada task baru |
| K10 | Graph dan dependensi | Bangun peta pemanggil atau task DAG yang memberi manfaat |
| K11 | Probabilitas dan kalibrasi | Bandingkan prediksi sukses dengan hasil aktual |
| K12 | Statistik eksperimen | Laporkan sampel, variasi, serta interval ketidakpastian yang sesuai |
| K13 | Causal reasoning | Buat intervensi yang membedakan dua dugaan akar masalah |
| K14 | Information gain | Pilih observasi berikut yang mengurangi unknown penting |
| K15 | Decision theory | Pilih langkah berdasarkan manfaat, biaya, dan kemungkinan progres |
| K16 | Search heuristics | Bandingkan BFS terbatas dengan heuristik pada budget yang sama |
| K17 | Meta-learning strategi | Pelajari kapan strategi tertentu membantu keluarga tugas tertentu |
| K18 | Continual learning | Uji skill baru bersama replay kemampuan lama |
| K19 | Memory retrieval | Bandingkan lexical, semantic, dan metadata filtering |
| K20 | Transformer dan tokenization | Ukur bagaimana konteks serta template memengaruhi model lokal |
| K21 | Quantization dan inference | Bandingkan kualitas serta resource pada konfigurasi yang layak |
| K22 | Parameter-efficient adaptation | Uji adapter hanya setelah data dan compute siap |
| K23 | Database dan transaksi | Simulasikan interupsi pada checkpoint dan pemulihan |
| K24 | Concurrency dan ownership | Uji stale writer serta dua instance runtime |
| K25 | Sistem operasi Android | Uji restart, process death, dan path app-private yang nyata |
| K26 | Profiling dan FFI | Identifikasi hotspot dan ukur biaya pemindahan data native |
| K27 | Protokol dan distributed workflow | Uji request ulang, consumer mati, dan stale result |
| K28 | Human–computer interaction | Uji alur chat, progres, stop, dan artefak dari HP |
| K29 | Open-ended learning | Uji curriculum, archive, transfer, dan pembanding grammar tetap |
| K30 | Filsafat pikiran dan teori kesadaran | Pisahkan indikator fungsi dari klaim pengalaman subjektif |

## P.1 Siklus pembelajaran per unit

Pilih masalah nyata, pahami konsep minimum, buat prototype kecil, bandingkan dengan baseline, lalu terapkan pada task ACE.

Simpan pengetahuan dalam bentuk yang dapat dipakai: prosedur, contoh, penjelasan singkat, kontrak, atau kode yang telah diperiksa. Tidak semua pelajaran perlu menjadi executable skill.

Evaluasi pengetahuan dari tindakan berikutnya. Penjelasan yang terdengar benar belum membuktikan kemampuan menerapkannya.

## P.2 Rumus dan konsep yang berguna

### P.2.1 Skor prioritas yang eksplisit

Gunakan skor sederhana untuk membandingkan kandidat tindakan, tetapi simpan komponen skornya. Bobot dapat dituning berdasarkan hasil; jangan menyebutnya fungsi kecerdasan universal.

### P.2.2 Kompresi library

Bandingkan biaya menyimpan operator baru dengan penghematan deskripsi atau pencarian pada tugas berbeda. Library yang lebih besar tetapi jarang terpakai dapat merugikan.

### P.2.3 Kalibrasi

Jika sistem memberi peluang sukses, kelompokkan prediksi dan bandingkan dengan frekuensi keberhasilan. Prediksi 90% yang hanya benar separuh waktu membutuhkan koreksi.

### P.2.4 Pareto tradeoff

Performa, memori, keberhasilan, dan biaya memiliki tradeoff. Simpan beberapa pilihan yang berguna bila tidak ada satu kandidat yang unggul pada semua dimensi.

### P.2.5 Retensi dan transfer

Retensi berarti kemampuan tetap ada setelah jeda atau restart. Transfer berarti pengalaman membantu tugas yang berbeda. Keduanya perlu diperiksa secara terpisah.

### P.2.6 Kelas representasi

Membuat operator baru dari operator lama dapat memberi manfaat nyata. Klaim bahwa expressive power bertambah memerlukan argumen atau bukti yang lebih kuat daripada perubahan nama dan format.

---

# LAMPIRAN Q — 20 WORK ORDER AWAL UNTUK ANTIGRAVITY

Urutkan ulang berdasarkan dependency aktual. Tujuannya menghasilkan versi yang bisa dipakai secepat mungkin, lalu terus memperbaikinya.

| Urutan | Work order | Hasil konkret |
| --- | --- | --- |
| W01 | Rekonsiliasi snapshot dan instalasi aktif | Satu peta source, runtime, model, dan gap yang relevan |
| W02 | Sambungkan satu backend bahasa Indonesia | Permintaan baru dipahami melalui entrypoint normal |
| W03 | Sambungkan intent ke task executor | Perintah menghasilkan file yang benar-benar dibuat |
| W04 | Selesaikan satu task coding stdlib | Program hasil berjalan dan memenuhi kontrak |
| W05 | Pisahkan bug dan fitur baru dalam workflow | Keduanya dapat diproses tanpa state machine yang keliru |
| W06 | Simpan percakapan dan progres task | Restart mempertahankan konteks dan next action |
| W07 | Pilih serta uji model lokal | Backend lokal nyata dengan pengukuran resource |
| W08 | Jalankan demo offline menyeluruh | Chat dan coding selesai tanpa remote |
| W09 | Periksa kontrak mission bus yang ada | Keputusan reuse atau adapter berdasarkan source |
| W10 | Bangun consumer host yang dapat dipakai | Work order benar-benar dikerjakan AI host |
| W11 | Tutup loop hasil host kembali ke ACE | ACE memverifikasi dan menentukan langkah berikut |
| W12 | Perluas anti-stuck berdasarkan pola error | Retry berulang berubah menjadi pivot atau learning task |
| W13 | Simpan pelajaran dengan precondition | Kesalahan dan koreksi ditemukan pada task berikut |
| W14 | Uji skill pada kasus baru setelah restart | Retensi dan transfer awal diketahui |
| W15 | Aktifkan agenda pengembangan yang berguna | ACE memilih satu gap dan mengerjakannya |
| W16 | Selesaikan jalur evaluasi kandidat yang belum lengkap | Keputusan engineering mempunyai bukti yang sesuai |
| W17 | Integrasikan dan aktifkan satu self-update | Versi baru memberi kemampuan yang dapat dipakai |
| W18 | Uji pemulihan dan rollback | Kandidat gagal tidak menghapus versi yang masih berguna |
| W19 | Profile lalu optimalkan satu bottleneck | Perubahan memberikan manfaat wall-time yang diukur |
| W20 | Jalankan pilot transfer dan revisi roadmap | Arah OAIE didasarkan pada bukti, termasuk hasil negatif |

## Q.1 Petakan kontrak baru ke mission bus yang sudah ada

Source schema ace.mission.v1 pada snapshot memerlukan field berikut. Periksa lagi versi aktual sebelum membuat adapter.

| Field schema yang ditemukan | Pemetaan yang disarankan |
| --- | --- |
| schema_version | Versi kontrak; jangan mengirim skema baru dengan label lama |
| id | ID mission yang stabil |
| goal | Tujuan pekerjaan yang konkret |
| hypothesis | Dugaan perbaikan atau ekspektasi implementasi yang akan diuji |
| task_family_ids | Keluarga task yang dikenali adapter atau registry |
| inputs | Referensi artefak dan dasar source yang sesuai |
| budget | Waktu positif dan jumlah kandidat sesuai resource |
| acceptance | Metrik, threshold, serta comparator yang didukung evaluator |
| forbidden | Cakupan yang memang tidak boleh disentuh oleh mission itu |
| deadline | Timestamp valid yang dibuat saat dispatch |
| status | Salah satu status yang didukung kontrak |
| reasoning_problem | Opsional, hanya jika payload memenuhi parser yang tersedia |

Schema yang valid belum membuktikan worker mampu mengerjakan mission. Telusuri generator, registry task family, consumer, evaluator, dan penyimpanan hasil.

Jangan memberi deadline historis dari contoh dokumen. Jangan memakai nama metric fiktif lalu menganggap acceptance sudah berjalan.

Jika kontrak riset terlalu sempit untuk chat atau coding umum, buat adapter atau versi kontrak baru yang jelas. Pertahankan kompatibilitas jalur riset yang masih digunakan.

## Q.2 Atasi hambatan promosi controller dengan implementasi yang benar

Controller yang diperiksa menahan penerimaan ketika bukti evaluasi belum tersedia. Solusinya adalah menghubungkan kandidat aktual, pemeriksaan perilaku yang relevan, dan pencatatan hasil yang benar.

Pemisahan yang perlu dibangun:

- Kandidat valid secara format.
- Kandidat memenuhi kebutuhan engineering.
- Kandidat layak diintegrasikan sesuai dampak dan otorisasi.
- Kandidat memberi peningkatan kemampuan pada pembanding.
- Kandidat mendukung klaim novelty ilmiah.

Status pada tahap pertama tidak menggantikan tahap berikutnya. Sebaliknya, belum adanya novelty ilmiah tidak harus menghalangi penggunaan fitur produk yang telah teruji.

## Q.3 Hasil akhir sesi pelaksanaan

Laporan menyebut fitur yang dapat digunakan, versi source, backend, lingkungan pengujian, hasil demo, status integrasi, serta gap berikut.

Jika sesi hanya menghasilkan dokumen, nyatakan dokumen selesai. Jika sudah menghasilkan runtime, tunjukkan cara menjalankannya. Jangan mencampur kedua jenis hasil.

---

# LAMPIRAN R — MANDAT EKSEKUSI SETELAH RISET

Antigravity, bahan riset sudah disediakan. Gunakan sumber yang paling dekat dengan kebutuhan ACE, bukan semua sumber sekaligus.

Mulai dari kenyataan bahwa pengguna ingin berbicara dalam bahasa Indonesia dan langsung mendapatkan pekerjaan yang dikerjakan. Hubungkan model, pemahaman, tool, state, evaluator, dan jawaban menjadi satu alur yang berjalan.

Kerjakan kode dan environment. Jika ACE berada di Termux, periksa instalasi serta dependency di sana. Jika berada di host AI, gunakan bridge yang nyata. Ketika offline, gunakan backend serta pengetahuan lokal yang sudah tersedia.

Saya mengizinkan pemilihan metode, eksperimen yang dapat dipulihkan, penambahan kemampuan relevan, dan integrasi yang layak sesuai mandat. Jangan menunda pekerjaan untuk persetujuan teknis rutin.

Bila pendekatan gagal, gunakan bukti itu untuk belajar. Jika belum tahu caranya, pilih gap yang dapat dipelajari dan diuji. Jika suatu prasyarat benar-benar tidak tersedia, kerjakan bagian lain sambil menyimpan kondisi melanjutkan.

Kembangkan kemampuan praktis, kontinuitas, pilihan strategi, agenda mandiri, pembelajaran, serta eksperimen representasi menuju OAIE.

Teliti kesadaran secara serius dan jujur. Jangan menjanjikan bahwa prompt atau pergantian bahasa pemrograman dengan sendirinya menghasilkan pengalaman subjektif.

**Perintah akhir: temukan keadaan aktual, wujudkan demo pertama, lanjutkan implementasi, verifikasi hasil, integrasikan perubahan yang layak, dan simpan kelanjutan sampai tujuan operasional benar-benar tercapai sesuai sumber daya yang tersedia.**

**Mandat dilanjutkan dan diperbarui oleh Lampiran S–X berikut.**



---

# LAMPIRAN S — INSTALLER LENGKAP DARI PERSIAPAN SAMPAI SIAP DIPAKAI

## S.1 Mandat tambahan yang berlaku

Antigravity harus membuat installer yang mencakup seluruh jalur produk: source, dependency, runtime, model yang dipilih, konfigurasi, state, launcher, pemeriksaan penggunaan, pembaruan, dan pemulihan.

Sesudah paket operasional selesai dan lolos penerimaan akhir, langsung lakukan integrasi serta merge yang diotorisasi. Selesaikan juga jalur pemakaian versi hasil integrasi. Saya tidak ingin berhenti pada draft PR atau instruksi pemasangan yang belum diuji.

Kerjakan dengan cepat dan hemat kuota. Kumpulkan audit terpadu di akhir paket. Pemeriksaan ringan selama coding digunakan untuk menyelesaikan pekerjaan dan menangkap error yang akan membuat pekerjaan berikutnya sia-sia.

Lampiran S–X memperbarui pengaturan urutan kerja dan ritme audit pada bagian sebelumnya. Seluruh riset, ide, serta arah OAIE tetap berlaku sebagai bahan pemilihan pengembangan.

## S.2 Keadaan installer yang diperiksa

Source install.sh pada commit 2a54501d42df7c291f4493939662e32ea5e4c5ed memiliki blob eb10c1ba29299a2ba3d443a40e880e12e98f59a7.

Pembacaan source menunjukkan pemeriksaan keberadaan Python, pemasangan editable package, penulisan launcher, pengubahan PATH untuk proses installer, dan pemanggilan doctor.

Pembacaan ini tidak mengeksekusi installer. Source tersebut belum menunjukkan penyiapan model lokal, konfigurasi percakapan, atau penerimaan coding offline menyeluruh.

Perbaiki installer yang sudah ada jika itu jalur paling langsung. Jangan menambah beberapa installer yang saling tidak konsisten.

Tinjau pula penggunaan interpreter, lokasi lingkungan Python, flag pemasangan global, lokasi launcher, serta perilakunya dari shell baru. Jalur yang bekerja karena shell pengembang sudah terkonfigurasi belum cukup untuk pengguna baru.

## S.3 Profil pemasangan

Sediakan profil yang terbedakan dengan jelas:

| Profil | Cakupan | Kapan dinyatakan siap |
| --- | --- | --- |
| local-complete | Percakapan Indonesia, model lokal, alat coding, state, dan launcher | Percakapan serta tugas coding benar-benar lulus tanpa provider remote |
| host-assisted | Runtime lokal ditambah adapter dan consumer AI host | Putaran request–result–verification pada host benar-benar bekerja |
| core | Kontrol dan kemampuan deterministik yang tersedia | Operasi yang didukung lulus; tidak dilabeli chatbot offline lengkap |
| offline-bundle | Paket persiapan untuk pemasangan atau pemakaian tanpa jaringan | Seluruh artefak yang dibutuhkan tersedia dan prosedurnya diuji pada target yang disebut |

Nama profil adalah target implementasi. Sesuaikan dengan antarmuka aktual, dan pastikan dokumentasi memakai nama yang benar-benar didukung.

Default untuk HP mengutamakan local-complete jika resource cukup. Installer memilih kandidat model yang layak berdasarkan pengukuran dan cache. Jika resource tidak mencukupi, tampilkan batasnya dan siapkan jalur yang masih berguna tanpa menyebut profil lengkap sudah terpenuhi.

## S.4 Seluruh tahap yang perlu diotomatisasi

| Tahap | Pekerjaan installer | Keluaran yang diperlukan |
| --- | --- | --- |
| 01 | Deteksi OS, shell, arsitektur, dan jenis environment | Profil platform yang benar |
| 02 | Temukan instalasi ACE, pekerjaan pengguna, dan state lama | Keputusan instalasi baru atau pembaruan |
| 03 | Periksa Python serta tool wajib | Daftar prasyarat yang benar-benar kurang |
| 04 | Periksa RAM, storage, dan kemampuan jaringan | Anggaran instalasi yang layak |
| 05 | Pilih direktori source, aplikasi, state, cache, dan model | Path yang terpisah dan tidak menimpa data |
| 06 | Tentukan revisi source atau artefak rilis yang dipakai | Versi yang dapat ditelusuri |
| 07 | Pasang hanya dependency platform yang diperlukan | Toolchain atau paket minimum |
| 08 | Siapkan lingkungan Python yang sesuai target | Interpreter aplikasi yang dapat dipanggil ulang |
| 09 | Pasang ACE dan dependency runtime | Import serta entrypoint yang bekerja |
| 10 | Siapkan backend inference lokal | Binary atau library yang cocok dengan target |
| 11 | Pilih satu model awal dan template yang sesuai | Model lokal dengan provenance |
| 12 | Gunakan cache atau unduh artefak yang masih kurang | Download dapat dilanjutkan dan diperiksa |
| 13 | Validasi integritas serta format model | Artefak lengkap dan dapat dimuat |
| 14 | Buat konfigurasi awal yang berguna | Mode, path, model, serta budget nyata |
| 15 | Inisialisasi atau migrasikan state | Percakapan dan task dapat disimpan |
| 16 | Daftarkan launcher pengguna | Entry point stabil dari shell baru |
| 17 | Konfigurasikan bridge jika host mendukung | Status consumer yang sesuai kenyataan |
| 18 | Siapkan start, stop, serta resume | Pengendalian lifecycle yang sederhana |
| 19 | Jalankan penerimaan pemasangan pada workspace uji | Bukti profil benar-benar berfungsi |
| 20 | Simpan manifest dan log ringkas | Diagnosis serta pembaruan dapat dilanjutkan |
| 21 | Aktifkan versi kandidat yang lulus | Versi aktif yang jelas |
| 22 | Tampilkan cara memakai yang singkat | Pengguna bisa langsung masuk percakapan |

Tahap yang sudah terpenuhi boleh dilewati setelah diperiksa singkat. Jangan mengunduh ulang model atau membangun ulang backend pada setiap pemanggilan installer.

## S.5 Persyaratan Termux

Prioritaskan Termux native pada Android ARM64 sebagai target penggunaan pengguna.

Gunakan package manager dan interpreter yang sesuai instalasi tersebut. Jangan menganggap paket binary Linux glibc cocok untuk Android hanya karena keduanya ARM64.

Mekanisme lingkungan Python harus diuji pada paket Termux yang tersedia. Dokumentasi upstream Python untuk platform mobile tidak boleh dipakai sebagai bukti bahwa seluruh perilaku paket Termux sama dengan build Android standar.

Jangan menjadikan pemasangan global dengan override sistem sebagai default yang tidak dievaluasi. Pilih lingkungan aplikasi yang dapat dipulihkan dan gunakan interpreter itu secara eksplisit pada launcher.

Periksa ketersediaan paket tambahan yang diperlukan untuk pip atau pembuatan lingkungan. Source paket Python resmi Termux menjadi rujukan implementasi, sementara hasil pada perangkat tetap perlu diuji.

Installer tidak boleh bergantung pada direktori milik workstation Antigravity. HOME tetap menunjuk home pengguna; konfigurasi ACE memakai variabel dan path aplikasi sendiri.

Jangan meminta pemasangan ulang Termux atau pemindahan seluruh proyek jika pembaruan instalasi yang ada cukup.

## S.6 Universalitas pemasangan

Pisahkan frontend bootstrap dari adapter platform.

- Termux menjadi profil utama yang harus diselesaikan.
- Host Linux atau environment Antigravity menjadi profil pengembangan dan pengujian yang tersedia.
- macOS dan Windows ditambahkan dengan adapter yang sesuai jika termasuk target dukungan.
- Platform yang belum diuji memiliki status dukungan yang jelas.

Satu kontrak tidak mengharuskan satu script shell berjalan tanpa perubahan di semua OS. Gunakan frontend yang sesuai dan panggil mesin setup bersama jika itu lebih sederhana.

Jangan memperluas daftar platform sampai menghambat target HP yang paling penting.

## S.7 Idempotensi dan pemulihan pemasangan

Rerun installer harus melanjutkan atau merekonsiliasi keadaan, bukan menghapus dan memulai ulang semuanya.

Catat fase yang selesai, versi, lokasi dependency, artefak yang masih diunduh, serta error terakhir.

Gunakan staging untuk artefak yang belum lengkap. Jangan memuat file model yang baru terunduh sebagian. Aktivasi dilakukan sesudah pemeriksaan yang relevan.

Jika pembaruan gagal, pertahankan versi aktif yang masih bisa digunakan. Jangan meninggalkan launcher menunjuk direktori staging yang dihapus.

Data pengguna, perubahan source yang belum tersimpan, state percakapan, serta model yang masih valid dipertahankan.

## S.8 Model dan dependency

Pilih satu model baseline lebih dulu. Bandingkan kandidat tambahan ketika baseline tidak memenuhi kebutuhan atau ada alasan pengukuran yang jelas.

Simpan model di cache yang dapat dipakai ulang. Catat sumber, revisi atau checksum yang tersedia, format, template, serta konfigurasi inference.

Pemeriksaan checksum memastikan kecocokan byte dengan manifest; kepercayaan terhadap sumber manifest tetap perlu diketahui.

Hindari pemasangan semua framework ML dan seluruh daftar repository riset. Dependency yang tidak dipakai pada profil terpilih tidak perlu diunduh.

Sediakan dependency riset sebagai bagian opsional agar pengguna dapat memakai ACE tanpa menunggu seluruh eksperimen.

## S.9 Offline run dan offline install

Dua hal ini harus dibedakan:

- Offline run berarti seluruh kebutuhan menjalankan fungsi terpilih sudah tersedia lokal.
- Offline install berarti paket yang dibawa cukup untuk memasang profil tersebut tanpa jaringan.

Bundle offline menyertakan source atau paket aplikasi, dependency yang cocok dengan ABI, backend inference, model, konfigurasi dasar, dan manifest yang diperlukan.

Jangan mengemas virtual environment host lalu menganggapnya portable. Buat ulang lingkungan di target atau distribusikan artefak platform yang memang sesuai.

Jika bundle memerlukan kompilasi saat instalasi, sertakan atau nyatakan prasyarat toolchain secara tepat. Jangan menyebutnya instalasi offline lengkap jika masih mengambil paket diam-diam.

## S.10 Launcher dan penggunaan dari sesi baru

Setelah instalasi:

1. Pengguna membuka sesi terminal baru.
2. Menjalankan satu entrypoint yang dijelaskan.
3. ACE memuat konfigurasi dan state yang benar.
4. Pengguna mengetik bahasa Indonesia.
5. ACE merespons dan mengerjakan permintaan yang tersedia dalam profil.
6. Pengguna dapat melihat hasil, menghentikan, atau melanjutkan tugas.

Launcher harus memakai interpreter aplikasi dan path yang benar. Keberadaan executable saja belum membuktikan import serta konfigurasi ditemukan.

Sediakan perintah ringkas untuk mulai, status, berhenti, resume, update, dan perbaikan instalasi. Pertahankan kompatibilitas CLI yang sudah dipakai.

Jika terminal interaktif tersedia, installer boleh menawarkan atau membuka sesi chat setelah pemasangan berhasil. Pada CI atau mode headless, jalur pemeriksaan harus berakhir tanpa menunggu input manusia.

Perintah dan flag yang dicetak pada akhir installer harus berasal dari implementasi yang diuji. Jangan mencetak command target yang belum tersedia.

---

# LAMPIRAN T — EFISIENSI KUOTA DAN KECEPATAN PENGERJAAN

## T.1 Sasaran efisiensi

Maksimalkan hasil yang dapat dipakai per waktu, per token, dan per panggilan model. Kuota dipakai untuk keputusan serta implementasi yang sulit, sementara pekerjaan mekanis dikerjakan alat.

Hemat kuota tidak berarti memotong hasil yang diminta. Efisiensi dicapai dengan menghindari pengulangan dan mengurangi pekerjaan yang tidak berkontribusi pada paket operasional.

## T.2 Gunakan pengetahuan yang sudah ada

Riset 42 repository, 24 rujukan, serta katalog ide telah tersedia pada dokumen dan ledger pendamping.

Baca bagian yang relevan, lalu periksa ulang versi komponen yang benar-benar akan diintegrasikan. Jangan mengulang pencarian seluruh katalog pada setiap sesi.

Simpan peta source, dependency, keputusan, dan hasil pemeriksaan. Invalidasi hanya bagian yang berubah atau yang memang belum diketahui.

Jika discovery telah cukup untuk mengambil langkah implementasi berikut, mulai mengerjakan. Riset tambahan dibatasi pada gap yang sedang menghambat.

## T.3 Jangan mengirim seluruh master prompt pada setiap panggilan

Baca mandat lengkap saat memulai pekerjaan jika belum ada dalam konteks, lalu simpan indeks dan ringkasan operasional yang setia terhadap mandat.

Untuk setiap task, kirim tujuan, batasan, source yang relevan, observasi terakhir, serta kriteria selesai. Ambil lampiran lengkap hanya saat detailnya dibutuhkan.

Jika host mendukung context atau prefix caching, gunakan sesuai kemampuan yang benar-benar tersedia. Jangan mengarang bahwa caching aktif atau bahwa token cache tidak memakai kuota.

Keputusan pengguna, otorisasi, batas tanpa biaya, dan pekerjaan yang belum selesai harus bertahan dalam ringkasan.

## T.4 Pilih model dan jumlah worker secara ekonomis

Gunakan langkah deterministik untuk status, pemilihan file yang jelas, parsing output, format data, serta operasi repository yang tidak membutuhkan generasi baru.

Gunakan model yang mampu untuk tugas yang membutuhkan pemahaman atau desain. Eskalasi ke model lebih kuat ketika ada alasan kualitas, bukan pada semua pesan.

Mulai dengan sedikit worker. Tambah paralelisme pada pekerjaan independen jika mempercepat hasil tanpa konflik atau biaya yang tidak sebanding.

Jangan memanggil beberapa model untuk menyetujui hal yang sudah dibuktikan compiler atau pengujian yang relevan.

## T.5 Baca dan ubah secara terarah

- Ambil potongan source yang relevan.
- Gunakan pencarian serta indeks daripada memasukkan seluruh repository ke prompt.
- Kelompokkan pencarian independen.
- Buat patch terarah jika cukup.
- Tulis file baru ketika tanggung jawabnya memang baru.
- Simpan hasil operasi yang masih berlaku.
- Ringkas output tool yang panjang tanpa membuang error penting.
- Hindari menghasilkan ulang file yang tidak berubah.

Jangan menyembunyikan perubahan bermakna di balik ringkasan. Detail tetap tersedia di diff dan artefak.

## T.6 Pengujian hemat dan relevan

Selama coding, lakukan pemeriksaan ringan yang menangkap error penghambat. Simpan pemeriksaan integrasi luas untuk akhir paket.

Sesudah pemeriksaan yang relevan lulus, ulangi hanya ketika ada perubahan, kegagalan, atau pertanyaan yang belum terjawab. Jangan menjalankan ulang suite identik hanya agar ada aktivitas.

Perubahan source, dependency, model, atau lingkungan dapat membatalkan bukti tertentu. Perubahan dokumentasi tidak otomatis membutuhkan seluruh benchmark kecerdasan dijalankan ulang.

Tetap penuhi pemeriksaan wajib repository pada commit yang dipersyaratkan. Atur batch perubahan agar CI tidak dipicu berkali-kali oleh commit sementara yang tidak diperlukan; jangan menonaktifkan pemeriksaan wajib untuk menghemat kuota.

## T.7 Batasi loop yang tidak memberi progres

Setiap retry harus punya alasan: error sementara, informasi baru, kandidat berbeda, atau koreksi format yang spesifik.

Deduplikasi kandidat dan error. Gunakan checkpoint agar sesi berikut tidak mengulang pendekatan gagal yang sama.

Jika provider atau host sedang tidak tersedia, circuit breaker menahan panggilan berulang. Lanjutkan pekerjaan lokal yang independen.

## T.8 Pencatatan biaya yang jujur

Pisahkan:

- Kuota atau token model.
- Waktu CPU dan inference lokal.
- Penggunaan memori.
- Download serta storage.
- Biaya layanan bila memang dilaporkan.
- Waktu tunggu eksternal.

Jika host tidak menyediakan angka kuota, tulis tidak diketahui dan gunakan penghitung panggilan atau ukuran konteks sebagai indikator terbatas.

Jangan mengklaim “hemat 90%” tanpa pembanding. Jangan menyebut proses gratis hanya karena angka biaya tidak dikembalikan.

## T.9 Pelaporan yang singkat

Laporan kemajuan cukup menyebut hasil terbaru, hambatan material, dan langkah berikut.

Simpan rincian bukti dalam artefak. Hindari menyalin ulang rencana panjang pada setiap update.

Pada akhir paket, tampilkan satu laporan terintegrasi yang menjelaskan instalasi, penggunaan, pemeriksaan, merge, dan keterbatasan yang masih relevan.

## T.10 Prinsip pengerjaan cepat

Prioritaskan jalur yang paling dekat dengan hasil menyeluruh: percakapan → tindakan → pemeriksaan → state → installer → penerimaan akhir → merge → pemakaian.

Tunda eksperimen yang tidak memengaruhi kesiapan paket pertama. Setelah paket dapat dipakai, lanjutkan peningkatan sesuai agenda serta sumber daya.

Jangan menjadikan seluruh 120 ide, semua kandidat model, atau pembuktian kesadaran sebagai prasyarat sebelum pengguna dapat memakai percakapan dan coding lokal.



---

# LAMPIRAN U — KERJAKAN PAKET SAMPAI AKHIR, LALU AUDIT TERPADU

## U.1 Ritme pengembangan yang saya minta

Gunakan urutan berikut:

1. Tentukan hasil operasional yang harus ditinggalkan.
2. Lakukan discovery secukupnya untuk menemukan jalur implementasi.
3. Kerjakan seluruh bagian yang diperlukan hingga terhubung.
4. Gunakan cek ringan untuk memperbaiki error yang menghambat.
5. Selesaikan installer, konfigurasi, dan jalur penggunaan.
6. Jalankan satu audit penerimaan terpadu pada akhir paket.
7. Perbaiki temuan yang menghalangi hasil.
8. Periksa ulang bagian yang diperbaiki dan dampak relevannya.
9. Langsung integrasikan serta merge ketika syarat terpenuhi.
10. Pastikan versi hasil integrasi dapat dipasang dan dipakai.

Jangan mengubah setiap perubahan file menjadi kegiatan audit mandiri yang menghabiskan konteks serta waktu.

Audit proyek berpusat pada akhir paket. Runtime tetap memakai hasil compiler, tool, atau tes yang relevan untuk mengetahui apakah tindakan berhasil sebelum memberi jawaban selesai.

## U.2 Lingkup paket pertama yang harus selesai

Paket operasional pertama mencakup:

- Percakapan Indonesia melalui entrypoint normal.
- Pemahaman perintah dan koreksi yang cukup untuk tugas awal.
- Pembuatan atau perubahan kode yang benar-benar dieksekusi.
- Backend lokal yang memenuhi profil offline terpilih.
- Penyimpanan percakapan dan task.
- Pemulihan atau resume setelah restart.
- Deteksi stagnasi dan pergantian pendekatan dasar.
- Installer seluruh alur.
- Launcher yang bekerja dari sesi baru.
- Penggunaan yang dibuktikan pada lingkungan yang dilaporkan.
- Bridge host jika kemampuan integrasinya tersedia.
- Integrasi versi serta cara pembaruan yang jelas.

Pilih cakupan tugas awal yang berguna dan realistis, lalu tulis batasnya secara spesifik. Jangan mengecilkan paket menjadi sekadar “Python bisa import” atau “file model ditemukan”.

Eksperimen jangka panjang dilanjutkan setelah paket awal siap. Fungsi dasar tidak perlu menunggu semua penelitian selesai.

## U.3 Audit akhir yang terfokus

Audit akhir memeriksa:

1. Kesesuaian hasil dengan permintaan.
2. Instalasi atau pembaruan di lingkungan uji yang bersih.
3. Penggunaan dari sesi baru.
4. Percakapan dan tindakan aktual.
5. Coding serta pemeriksaan hasil.
6. Offline sesuai profil.
7. State, restart, dan pemulihan.
8. Resource dan kuota sesuai batas.
9. Integrasi source, dependency, serta model.
10. Kemudahan penggunaan.

Gunakan satu indeks hasil yang menghubungkan pemeriksaan dan bukti. Tidak perlu menulis laporan audit baru untuk setiap file.

Jika sebuah pemeriksaan gagal, cari akar masalah, perbaiki, dan ulangi pemeriksaan yang terkait. Audit tidak menjadi tempat berhenti setelah pekerjaan implementasi selesai.

## U.4 Hindari evaluasi yang tidak berkaitan dengan rilis

Benchmark riset besar, pengujian seluruh hipotesis OAIE, dan pembuktian novelty bukan persyaratan setiap rilis installer.

Gunakan pemeriksaan yang berhubungan dengan fitur serta area yang berubah. Tetap jalankan pemeriksaan repository yang memang wajib.

Paket yang telah diterima menghasilkan baseline baru. Bukti yang masih berlaku dapat dipakai kembali pada pekerjaan berikutnya.

---

# LAMPIRAN V — LANGSUNG MERGE DAN TUNTASKAN JALUR PEMAKAIAN

## V.1 Instruksi integrasi

Saya mengizinkan Antigravity melakukan merge perubahan ACE yang sudah memenuhi penerimaan akhir dan syarat repository.

Jangan meminta persetujuan teknis rutin sekali lagi. Jangan berhenti pada “silakan merge” jika izin serta alat tersedia dan pekerjaan sudah layak.

Kerjakan konflik, perbaiki kegagalan pemeriksaan, dan tuntaskan perubahan dalam cakupan mandat.

## V.2 Perhatikan stack PR yang benar

Pada snapshot yang diperiksa, PR #100 mempunyai base branch PR #99, bukan main. Merge PR paling atas saja tidak otomatis membuat seluruh stack tersedia pada branch rilis.

Sebelum integrasi:

- Periksa base dan head yang aktual.
- Temukan dependency perubahan.
- Rekonsiliasi duplikasi yang mungkin sudah masuk.
- Pilih urutan integrasi yang benar.
- Periksa hasil gabungan yang akan dirilis.
- Pastikan installer menunjuk versi yang benar-benar berisi kemampuan tersebut.

Jika repository memakai main sebagai sumber rilis, selesaikan jalur integrasi hingga versi yang dimaksud tersedia di main. Jangan menyebut paket sudah dirilis hanya karena merge ke branch perantara berhasil.

## V.3 Jalur merge yang sah

Jika PR masih draft dan implementasinya sudah layak, gunakan alur yang tersedia untuk menandainya siap dan memenuhi syarat merge.

Jika checks masih berjalan, gunakan mekanisme menunggu atau auto-merge yang didukung, dengan pemantauan yang tidak memboroskan panggilan model.

Jika proteksi repository memerlukan sesuatu yang tidak dapat dipenuhi oleh pelaksana, siapkan kandidat serta bukti yang konkret, nyatakan hambatan spesifik, dan lanjutkan bagian lain yang sah. Jangan mengubah proteksi untuk membuat klaim selesai.

Otorisasi pengguna tidak berarti checks yang gagal boleh disebut lulus.

## V.4 Setelah merge

Lakukan konfirmasi ringan:

1. Perubahan masuk ke target yang dimaksud.
2. Versi paket atau source dapat diambil.
3. Manifest menunjuk dependency dan model yang sesuai.
4. Entry point dapat dimulai.
5. Demo singkat dari hasil integrasi tetap bekerja.

Jika tree hasil integrasi berbeda secara material dari kandidat yang diuji, periksa dampak perubahan tersebut. Jangan mengulang semua riset hanya karena nama commit berubah.

Siapkan artifact installer atau rilis pada repository yang diizinkan jika workflow memakainya. Sertakan informasi lisensi serta provenance yang diperlukan.

## V.5 Sinkronkan environment aktif

Pastikan instalasi yang akan dipakai pengguna memakai versi hasil integrasi.

Jika pelaksana mengakses langsung environment pengguna yang diotorisasi, terapkan pembaruan dan periksa hasilnya. Jika environment tersebut tidak dapat diakses, siapkan jalur instalasi yang singkat serta teruji dan nyatakan bagian perangkat yang belum diuji.

Remote merge, pembaruan instalasi, serta aplikasi yang sedang berjalan adalah keadaan yang perlu dihubungkan secara nyata.

---

# LAMPIRAN W — 24 SKENARIO PENERIMAAN INSTALLER DAN PEMAKAIAN

Skenario ini adalah target pemeriksaan untuk Antigravity. Keberadaan tabel tidak berarti semua pengujian sudah dijalankan.

Jalankan kasus yang relevan pada profil target. Kelompokkan dalam penerimaan akhir yang otomatis agar tidak memerlukan percakapan audit di setiap langkah.

| ID | Keadaan | Hasil yang harus diperiksa |
| --- | --- | --- |
| INST01 | Instalasi baru pada profil utama | Installer menyiapkan seluruh kebutuhan profil |
| INST02 | Instalasi pada folder yang berbeda | Tidak ada path workstation yang diasumsikan |
| INST03 | Python tidak ditemukan | Prasyarat ditangani sesuai platform atau hambatan dinyatakan tepat |
| INST04 | Versi interpreter tidak sesuai | Installer memilih atau menyiapkan interpreter yang didukung |
| INST05 | Lingkungan Python perlu dibuat | Mekanisme yang didukung target benar-benar bekerja |
| INST06 | Backend inference belum tersedia | Backend yang sesuai dipasang atau dibangun |
| INST07 | Model lokal belum tersedia | Model yang dipilih disiapkan dan dapat dimuat |
| INST08 | Model ada dalam cache | File valid dipakai ulang tanpa download identik |
| INST09 | Download terputus | Rerun dapat melanjutkan atau merekonsiliasi artefak |
| INST10 | File model rusak atau belum lengkap | File ditolak dan perbaikan dibatasi pada artefak terkait |
| INST11 | Storage tidak mencukupi | Data pengguna tetap aman dan instalasi besar tidak dipaksa |
| INST12 | Pemasangan dijalankan ulang | Tidak membuat konfigurasi dan launcher duplikat |
| INST13 | Pembaruan instalasi lama | State serta pekerjaan pengguna tetap tersedia |
| INST14 | Pembaruan gagal | Versi yang masih berguna dapat dijalankan kembali |
| INST15 | Shell baru dibuka | Launcher menemukan interpreter, paket, serta konfigurasi |
| INST16 | Pengguna mengetik bahasa Indonesia | Respons berasal dari backend bahasa yang sebenarnya |
| INST17 | Pengguna meminta program kecil | Kode dibuat, dijalankan, dan hasilnya diperiksa |
| INST18 | Pengguna mengoreksi kebutuhan | Perubahan diterapkan pada artefak yang tepat |
| INST19 | Internet dinonaktifkan setelah persiapan | Percakapan dan tugas lokal berhasil sesuai profil |
| INST20 | Offline bundle dipasang tanpa jaringan | Tidak ada dependency tersembunyi yang diunduh |
| INST21 | Proses dihentikan lalu dimulai ulang | State serta konteks yang relevan dipulihkan |
| INST22 | Task mulai berulang tanpa progres | Strategi berubah atau gap pembelajaran ditangani |
| INST23 | Bridge host tersedia | Putaran work order sampai hasil terverifikasi berjalan |
| INST24 | Versi hasil merge dipakai | Versi, manifest, serta demo cocok dengan hasil integrasi |

## W.1 Definisi siap dipakai

Siap dipakai berarti pengguna mempunyai cara masuk yang nyata, dapat memberi perintah, memperoleh hasil yang berjalan, dan dapat melanjutkan penggunaan dari sesi berikutnya.

Status dapat dibedakan menurut profil dan lingkungan, misalnya siap di host uji atau siap di perangkat target. Status tersebut harus merujuk bukti, bukan asumsi.

Profil core yang lulus operasi deterministik tetap berguna tetapi tidak menggantikan penerimaan local-complete.

## W.2 Makna “cepat tapi hasil pasti”

Terjemahkan tuntutan saya menjadi pekerjaan cepat dengan hasil yang diperiksa:

- Kriteria selesai ditetapkan dengan jelas.
- Implementasi dan installer benar-benar ada.
- Tugas contoh dijalankan melalui jalur pengguna.
- Keadaan gagal diperbaiki sebelum dinyatakan selesai.
- Versi yang dipakai dapat ditelusuri.
- Pemulihan tetap tersedia.

Kecepatan tidak diukur hanya dari cepatnya membuat jawaban atau commit. Ukur waktu sampai pengguna dapat memakai hasil yang benar.

Jangan menjanjikan semua tugas akan selalu berhasil, semua perangkat akan selalu cocok, atau kesadaran akan muncul pada tenggat tertentu. Berikan kepastian tentang hasil yang benar-benar telah dibuktikan dan batas penggunaan yang diketahui.

---

# LAMPIRAN X — PERINTAH PELAKSANAAN DAN HANDOFF EDISI 3

## X.1 Mulai sekarang

Antigravity, baca mandat ini beserta ledger, pakai ulang pengetahuan yang masih berlaku, dan mulai mengerjakan source serta environment ACE.

Fokus paket pertama adalah percakapan Indonesia yang terhubung tindakan, coding, model lokal offline, state, anti-stuck, installer menyeluruh, dan jalur pemakaian.

Kerjakan sampai paket terhubung dan dapat dipasang. Gunakan cek ringan selama implementasi. Setelah itu jalankan audit akhir terpadu, perbaiki temuan, lalu langsung merge sesuai otorisasi dan syarat repository.

Jangan membuang kuota pada pengulangan riset, penjelasan panjang, review yang tidak memberi bukti baru, atau banyak model untuk pekerjaan mekanis.

Jika bantuan host diperlukan, gunakan bridge yang nyata. Setelah bantuan selesai, uji bahwa fungsi yang diimplementasikan dapat dipakai ACE melalui entrypoint normal.

## X.2 Jawaban akhir pelaksana harus memuat

- Kemampuan yang sudah dapat dipakai.
- Cara memasang dan memulai yang benar-benar diuji.
- Versi atau commit yang terintegrasi.
- Status perangkat dan profil offline.
- Hasil audit akhir yang ringkas.
- Hambatan material yang belum terselesaikan.
- Kelanjutan pengembangan yang tersimpan.

Untuk pengguna, tampilkan sedikit command nyata. Jangan menyerahkan deretan placeholder yang masih perlu diterjemahkan menjadi instalasi.

## X.3 Pengantar singkat untuk sesi baru

~~~text
Baca master prompt ACE edisi 3 dan ledger sumbernya pada workspace ini.
Kerjakan kode serta environment sampai menjadi paket operasional yang
bisa dipasang dan dipakai.

Buat installer seluruh alur: dependency, runtime, model lokal,
konfigurasi, state, launcher, pemulihan, dan demo penggunaan.

Utamakan percakapan Indonesia yang langsung mengerjakan tugas,
coding yang benar-benar dijalankan, mode offline, serta anti-stuck.

Pakai ulang riset dan checkpoint. Gunakan model serta alat secara hemat.
Selesaikan implementasi paket dahulu, gunakan cek ringan selama coding,
lalu audit terpadu di akhir. Perbaiki temuan dan langsung merge ketika
penerimaan serta syarat repository terpenuhi, tanpa persetujuan teknis rutin.

Tuntaskan jalur pemakaian versi hasil integrasi dan simpan kelanjutan
menuju OAIE. Laporkan kemampuan berdasarkan bukti aktual.
~~~

## X.4 Referensi tambahan installer dan merge

- [Python venv](https://docs.python.org/3/library/venv.html): rujukan lingkungan Python; dukungan target tetap perlu dibuktikan.
- [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/): rujukan pemasangan dependency dan lingkungan aplikasi.
- [Paket Python resmi Termux](https://github.com/termux/termux-packages/blob/master/packages/python/build.sh): rujukan recipe paket yang berbeda dari asumsi build mobile upstream.
- [GitHub: merging a pull request](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-a-pull-request): rujukan kesiapan PR dan syarat integrasi.

Referensi diperiksa pada 10 November 2026. Penyusunan edisi ini menambahkan instruksi dan spesifikasi; installer serta kemampuan runtime baru merupakan pekerjaan pelaksanaan yang harus dibuktikan.

**Akhir dokumen edisi 3.**

