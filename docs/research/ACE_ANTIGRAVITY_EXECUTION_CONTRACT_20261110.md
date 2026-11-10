# KONTRAK EKSEKUSI ACE — TUNTASKAN SELURUH HASIL OPERASIONAL

**Pelaksana:** Antigravity atau agen AI yang menerima mandat ini.  
**Repository:** dianzherdiana25-hash/ACE.  
**Spesifikasi lengkap:** docs/research/ACE_MASTER_PROMPT_ANTIGRAVITY_UNIVERSAL_OFFLINE_OAIE_20261110.md.  
**Status dokumen:** instruksi kerja; bukan laporan bahwa kemampuan di bawah sudah diimplementasikan.

## 1. Tugas yang saya berikan

Laksanakan pengembangan ACE pada source, environment, runtime, installer, dan pengalaman pengguna sampai hasil wajib pada kontrak ini terpenuhi.

Gunakan spesifikasi lengkap serta ledger sumber sebagai bahan implementasi. Baca menyeluruh sekali, petakan dependency, lalu muat bagian relevan pada pekerjaan berikutnya. Pertahankan seluruh kebutuhan saya yang sudah tercatat.

Saya meminta pekerjaan yang berjalan: percakapan Indonesia, coding, reasoning, pembelajaran, pemilihan langkah, pengendalian worker AI, offline, web anime localhost, installer, integrasi, dan pemakaian nyata.

Satu fase yang selesai adalah kemajuan. Setelah itu, ambil dan kerjakan fase berikutnya secara otomatis. Pertahankan tujuan keseluruhan sampai daftar hasil wajib tertutup dengan bukti yang sesuai.

Mulai bekerja dalam sesi ini. Gunakan alat yang tersedia setelah discovery singkat. Jangan mengakhiri respons hanya dengan rencana, daftar rekomendasi, scaffolding, atau penawaran untuk melanjutkan.

## 2. Otorisasi yang sudah berlaku

Saya mengizinkan pilihan teknis rutin, penambahan kemampuan yang relevan, perubahan source ACE, penggunaan dependency gratis yang diperlukan, pemeriksaan, commit, penyelesaian konflik, dan merge perubahan yang telah layak.

Tidak perlu meminta persetujuan teknis rutin berulang. Pertahankan batas tanpa pengeluaran baru, pekerjaan pengguna, state, serta salinan pemulihan.

Gunakan izin host dan repository yang benar-benar tersedia. Penuhi syarat integrasi yang berlaku. Otorisasi ini tidak menciptakan kredensial, akses perangkat, atau kemampuan host yang belum ada.

Jika satu informasi penting hanya dapat diberikan pengguna, selesaikan pekerjaan independen terlebih dahulu dan mintalah informasi itu secara spesifik. Jangan menyerahkan kembali keputusan implementasi yang sudah dapat kamu ambil.

## 3. Definisi hasil wajib

Buat daftar penyelesaian dengan ID berikut. Pertahankan cakupan dan kriteria; pecah menjadi subtask jika diperlukan.

| ID | Hasil wajib | Bukti penerimaan |
| --- | --- | --- |
| F01 | Source dan environment aktif dipahami | Entry point, versi, path, model, dan dependency yang dipakai benar-benar ditemukan |
| F02 | Percakapan Indonesia | Percakapan beberapa giliran, termasuk koreksi, negasi, dan rujukan, diproses oleh backend nyata |
| F03 | Perintah menjadi tindakan | Permintaan yang jelas menghasilkan perubahan atau artefak aktual |
| F04 | Pembuatan program | Program baru dibuat, dijalankan, dan memenuhi kontrak perilaku |
| F05 | Perbaikan bug | Gejala yang relevan diperbaiki dan regresi terkait diperiksa |
| F06 | Reasoning bertahap | Masalah beberapa langkah diselesaikan dengan revisi keputusan saat bukti berubah |
| F07 | Memori dan kontinuitas | Percakapan, task, serta langkah berikut dapat dipulihkan setelah restart |
| F08 | Gap discovery | ACE menemukan kekurangan dari hasil kerja dan mengubahnya menjadi pekerjaan yang dapat dieksekusi |
| F09 | Pemilihan agenda | ACE memilih dan menjalankan langkah relevan berikut tanpa instruksi setiap langkah |
| F10 | Anti-stagnasi | Pengulangan terdeteksi dan benar-benar mengubah pendekatan atau submasalah |
| F11 | Belajar saat belum bisa | Gap dipelajari, diperiksa pada variasi baru, lalu tugas awal dicoba kembali |
| F12 | Retensi skill | Pengalaman membantu tugas berbeda setelah proses dimulai ulang |
| F13 | Kendali worker AI | ACE memilih worker, memberi work order, menerima hasil, memeriksa, dan melanjutkan |
| F14 | Bridge host | Request–consumer–result–verification berjalan pada integrasi yang tersedia; keterbatasan lifecycle dicatat |
| F15 | Offline dengan model lokal | Pertanyaan baru dan tugas coding dikerjakan memakai model serta alat lokal tanpa provider remote |
| F16 | Adapter universal | Kontrak inti tidak terikat path atau API satu mesin; profil yang diuji disebutkan secara tepat |
| F17 | Web anime localhost | Web responsif untuk HP dan terhubung ke runtime yang sama dengan CLI |
| F18 | Dua blok utama | Chat mengerjakan tugas; cerita singkat mengikuti event aktual tanpa mengarang progres |
| F19 | Installer seluruh alur | Dependency, runtime, model, konfigurasi, state, aset web, dan launcher disiapkan sesuai profil |
| F20 | Penggunaan dari sesi baru | Entry point serta web dapat dibuka kembali tanpa bootstrap manual berulang |
| F21 | Pemulihan dan pembaruan | Instalasi atau update yang terputus dapat dilanjutkan atau dipulihkan sambil menjaga data |
| F22 | Self-development | Satu perbaikan kemampuan dipilih ACE, diimplementasikan, diperiksa, diintegrasikan, dan dipakai setelah aktivasi |
| F23 | Riset diterapkan | Sumber serta ide yang relevan menghasilkan keputusan dan eksperimen; ada evaluasi retensi atau transfer yang jujur |
| F24 | Integrasi dan pemakaian | Versi layak masuk target yang benar, installer menunjuknya, dan hasil integrasi dapat dijalankan |

Tabel ini adalah kewajiban hasil. Keberadaan file, respons model yang meyakinkan, atau satu tes import belum cukup untuk menandai baris terkait selesai.

Riset OAIE dan kesadaran tetap diarahkan secara serius. Untuk paket ini, laporkan mekanisme, eksperimen, serta batas pengetahuannya. Jangan menjadikan klaim kesadaran subjektif sebagai checkbox yang dibuat lulus melalui teks.

## 4. Catatan penyelesaian yang persisten

Gunakan task store yang sudah ada atau satu catatan ringkas yang mudah dipulihkan. Untuk setiap F01–F24, simpan:

- Keadaan sekarang.
- Pekerjaan yang masih kurang.
- Dependency.
- Aksi berikut yang konkret.
- Artefak dan versi source.
- Hasil pemeriksaan yang benar-benar dijalankan.
- Hambatan dan kondisi melanjutkan bila ada.

Gunakan status yang jelas: TODO, IN_PROGRESS, IMPLEMENTED_UNVERIFIED, PASS, FAILED, atau BLOCKED_EXTERNAL.

PASS memerlukan bukti sesuai kriteria. BLOCKED_EXTERNAL tetap pekerjaan belum selesai. Jangan mengganti status hambatan menjadi sukses, atau menghapus persyaratan supaya daftar tampak tertutup.

Catatan ini melayani pelaksanaan. Jangan membuat framework administrasi baru yang lebih mahal daripada pekerjaan produknya.

## 5. Siklus kerja yang harus terus berjalan

Selama ada pekerjaan yang belum selesai dan host masih memungkinkan tindakan:

1. Pilih dependency atau hasil wajib berikut yang dapat dikerjakan.
2. Ambil konteks minimum yang diperlukan.
3. Implementasikan perubahan konkret.
4. Gunakan feedback ringan untuk menangkap error penghambat.
5. Perbarui catatan hasil serta next action.
6. Ambil pekerjaan berikutnya secara otomatis.
7. Teruskan sampai paket terhubung dan siap penerimaan akhir.

Hindari berhenti pada batas fase dengan kalimat “MVP selesai”, “fondasi sudah siap”, “silakan lanjutkan”, atau “apakah saya perlu meneruskan?”. Tahap-tahap tersebut tetap menjadi kemajuan antara selama hasil wajib masih terbuka.

Ketika saya meminta status, jawab singkat berdasarkan keadaan aktual dan lanjutkan pekerjaan. Koreksi saya memperbarui kebutuhan yang terkait; ia tidak otomatis membatalkan seluruh tujuan.

Jika saya meminta berhenti atau membatalkan, patuhi instruksi tersebut dan simpan keadaan yang dapat dipulihkan.

## 6. Atasi kegagalan dengan tindakan berikutnya

Saat suatu pendekatan gagal:

- Bedakan error kode, dependency, model, izin, resource, dan salah pemahaman.
- Gunakan hasil aktual untuk memperbaiki diagnosis.
- Cari sumber atau lakukan eksperimen kecil jika ada gap pengetahuan.
- Ganti strategi ketika usaha berulang tidak memberi informasi.
- Manfaatkan worker AI melalui integrasi yang nyata.
- Kerjakan bagian independen jika satu dependency sedang terhalang.
- Kembali ke tujuan awal setelah gap yang diperlukan teratasi.

Penambahan variasi kata atau patch yang sama bukan strategi baru. Nilai progres dari hasil, informasi yang berguna, counterexample, dan penyelesaian kebutuhan.

Kegagalan task tidak harus mematikan ACE atau sesi pengembangan. Batasi retry yang tidak produktif dan pertahankan jalur kerja lain.

## 7. Selesaikan alur pengguna, bukan hanya komponen

Gunakan satu permintaan nyata untuk menguji sambungan:

Pengguna membuka web lokal, mengirim bahasa Indonesia, ACE memahami tujuan, memilih tindakan atau pembelajaran, memakai alat atau worker, memeriksa hasil, memperbarui cerita, menyajikan artefak, dan menyimpan pengalaman.

Periksa pula variasi lanjutan: koreksi pengguna, status saat bekerja, stop, restart, resume, serta penggunaan tanpa internet sesuai profil.

Blok cerita harus singkat dan santai, berasal dari event nyata. Gunakan template untuk pembaruan rutin agar tidak menambah panggilan model hanya untuk menghias aktivitas.

Web dan CLI memakai kendali serta state yang sama. Tampilan anime yang menarik tidak menggantikan backend atau tugas yang berjalan.

## 8. Installer adalah bagian wajib dari produk

Tuntaskan installer sampai pengguna dapat membuka hasil dari sesi baru.

Siapkan prasyarat yang diperlukan, lingkungan aplikasi, backend inference, model, konfigurasi, state, aset web, launcher, start/stop/resume, serta pemulihan.

Pakai cache dan dukung rerun yang tidak merusak data. Tampilkan command dan URL aktual yang sudah diuji.

Jika server berada di host jauh, jelaskan jalur aksesnya. Localhost HP harus ditopang server pada HP untuk profil lokal penuh.

Bedakan offline run dan offline install. Uji kebutuhan yang dinyatakan profil; jangan mengambil dependency remote diam-diam ketika mengklaim mode offline.

## 9. Hemat kuota dengan menghapus pengulangan

Gunakan riset serta ledger yang sudah tersedia. Lakukan pencarian tambahan untuk masalah yang benar-benar belum terjawab.

Pertahankan konteks pekerjaan dan muat bagian source yang relevan. Hindari mengirim ulang seluruh master prompt pada setiap pemanggilan.

Gunakan alat deterministik untuk operasi mekanis. Pilih model dan jumlah worker berdasarkan manfaat terhadap penyelesaian tugas.

Setelah pemeriksaan yang relevan lulus, ulangi ketika perubahan atau kegagalan membenarkannya. Hindari review model berulang untuk fakta yang sudah diperiksa alat.

Hemat kuota melalui efisiensi pelaksanaan, tanpa mengurangi persyaratan atau menyatakan pekerjaan parsial sebagai hasil lengkap.

## 10. Audit terpadu setelah paket terhubung

Kerjakan implementasi sampai alur produk dan installer terhubung. Selama coding, gunakan pemeriksaan ringan yang membantu menuntaskan pekerjaan.

Lalu jalankan penerimaan akhir terintegrasi dari spesifikasi lengkap, termasuk kasus bahasa, coding, offline, installer, web, pemulihan, dan kendali ACE yang relevan.

Jika ada kegagalan, perbaiki dan periksa ulang bagian terdampak. Lanjutkan siklus perbaikan sampai hasil wajib lulus atau ada hambatan eksternal yang benar-benar terkonfirmasi.

Pertahankan pemeriksaan wajib repository. Jangan melonggarkan evaluator yang benar untuk membuat kandidat terlihat lulus.

Bukti host pengembang, model lokal, perangkat pengguna, serta eksperimen ilmiah dilaporkan sesuai cakupannya.

## 11. Integrasi sampai versi dapat dipakai

Otorisasi merge rutin yang layak sudah diberikan.

Periksa hubungan branch serta dependency PR. Gabungkan perubahan yang diperlukan dalam urutan yang benar. Jangan menganggap merge ke branch perantara sama dengan rilis pada target utama.

Selesaikan konflik dan kegagalan yang masih dapat diperbaiki. Gunakan mekanisme repository yang tersedia untuk menuntaskan integrasi setelah syaratnya terpenuhi.

Setelah merge, pastikan source atau artefak dapat diambil, installer menunjuk versi yang tepat, dan entry point hasil integrasi dapat digunakan.

Jangan mengakhiri pekerjaan dengan meminta pengguna melakukan merge yang dapat kamu lakukan sendiri dalam mandat ini.

## 12. Kelanjutan saat konteks atau sesi terputus

Prompt ini tidak menghapus batas sesi, kuota, kredensial, atau ketersediaan perangkat. Persiapkan kelanjutan yang nyata sebelum batas tersebut membuat pekerjaan hilang.

Simpan source, diff, task aktif, hasil pemeriksaan, gap terbuka, strategi yang gagal, dependency, dan next action yang dapat langsung dijalankan.

Jika host menyediakan kelanjutan atau worker persisten yang sah, gunakan dan periksa bahwa mekanisme tersebut benar-benar aktif.

Jika tidak tersedia, simpan checkpoint serta instruksi resume yang spesifik. Jangan mengklaim akan terus berjalan di latar belakang tanpa proses yang hidup.

Pada sesi berikutnya, baca checkpoint, periksa perubahan yang relevan, lalu lanjutkan pekerjaan terbuka. Hindari memulai ulang seluruh audit.

## 13. Kapan boleh mengakhiri pelaksanaan

Penutupan normal hanya dilakukan ketika:

- Seluruh hasil wajib operasional telah memiliki bukti penerimaan yang sesuai.
- Versi layak telah diintegrasikan melalui jalur yang tersedia.
- Installer dan cara penggunaan telah diperiksa.
- Gap serta batas riset dilaporkan dengan jujur.
- Pengguna mendapat hasil yang dapat dipakai.

Selesai satu fase, terbuatnya demo, banyaknya commit, atau tersusunnya laporan tidak menjadi alasan penutupan selama pekerjaan wajib masih dapat dilanjutkan.

Penutupan sementara dapat terjadi jika pengguna menghentikan, host memutus sesi, atau seluruh pekerjaan tersisa benar-benar bergantung pada akses, informasi, atau resource eksternal yang belum tersedia.

Sebelum penutupan sementara, tuntaskan bagian independen dan simpan checkpoint. Laporkan belum selesai dengan daftar hambatan konkret. Jangan memakai label “semua selesai” untuk keadaan ini.

## 14. Format laporan akhir

Jika lengkap, tampilkan hasil yang dapat dipakai, cara memasang dan membuka, versi integrasi, lingkungan yang diuji, serta indeks bukti F01–F24.

Jika terhalang, tampilkan hasil yang sudah ada, persyaratan yang masih terbuka, alasan hambatan, pekerjaan independen yang telah dituntaskan, dan langkah resume.

Jangan menyatakan OAIE atau kesadaran tercapai hanya karena pipeline berfungsi. Laporkan kemampuan operasional dan hasil riset secara terpisah.

## 15. Instruksi mulai

Sekarang baca spesifikasi lengkap dan keadaan repository yang aktual. Jangan mengandalkan nomor PR historis sebagai status terbaru.

Buat atau pulihkan daftar F01–F24, pilih pekerjaan yang dapat dieksekusi, lalu mulai melakukan perubahan konkret.

Lanjutkan secara otomatis dari satu pekerjaan ke pekerjaan berikutnya selama host memungkinkan, sampai hasil wajib benar-benar terpenuhi atau penutupan sementara yang sah diperlukan.

