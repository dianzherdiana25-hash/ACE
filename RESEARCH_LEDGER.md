# Ledger penelitian ACE

Rujuk [Master Record historis](ACE_RESEARCH_MASTER_RECORD_v1.0.md) untuk angka dan tautan ke arsip. Angka antar fase memakai tugas dan denominasi berbeda.

| Tahap | Hipotesis atau pemeriksaan | Temuan dan keputusan |
| --- | --- | --- |
| F0 | Eksekusi CPU, integritas dan pemulihan | Pipeline lokal dan pemulihan simulasi lulus. Durabilitas jangka panjang tetap terbuka. |
| F1 | Baseline tetap dapat direproduksi | 83/108 benar. Menjadi pembanding awal. |
| F2 | Pemilihan strategi dari katalog membantu | Adaptive 94/96, Fixed 79/96 pada pilot internal. |
| F3 | Seleksi feedback memberi manfaat di luar mutasi | Kontrol generasi terakhir menyamai 96/96. Klaim kausal ditahan. |
| F3.1 | Arah pencarian dari feedback mengungguli pencarian buta | Guided kalah dari blind+best meski lintasannya berubah. |
| F3.2 | Arsip tetangga membantu pencarian | Unggul atas blind+best dan kalah dari Guided Best. |
| F3.3 | Macro komposit memperbaiki performa | Macro terbentuk dan interval efek mencakup nol. |
| F4a | Macro berpindah ketika struktur DSL berubah | Manfaat belum konklusif. |
| F4b | Kemampuan berpindah ke TREE/DAG | Transfer positif pada motif relevan. Bukti untuk motif baru belum didapat. |
| F5 | Kelayakan melanjutkan penelitian | [Sintesis](docs/ACE_F5_Research_Synthesis_and_Decision_v0.1.md) menetapkan `CONTINUE_RESEARCH_WITH_SCOPE_LIMITS`. |
| E1 | Metode yang dipelajari berpindah ke komposisi baru | Positif pada motif relevan. Pada motif baru C 0/480 dan B 40/480. [Laporan](docs/E1_Research_Report_v0.1.md) |
| E1.1 | Evolusi prosedur unggul atas pembanding kuat | EVOLVE mengungguli RANDOM dan SHAM. Keunggulan atas BEAM inkonklusif. [Laporan](docs/E11_Research_Report_v0.1.md) |
| E1.2 | Operator terinduksi dapat diwariskan | REUSE dan STRUCTURED sama-sama 640/640 pada RELATED. REUSE kalah dari TARGET_ONLY pada UNRELATED. Pertanyaan grammar tersembunyi dibawa ke E1.3. [Laporan](docs/E12_Research_Report_v0.1.md) |
| E1.3 kontrak awal | Pemisahan fit dan penilaian dapat ditegakkan | 18 tes dan 6 probe publik lulus di `0bb5c7d`. Bukti rekayasa untuk katalog tetap. [Harness](code/e13/README.md) |
| E1.3 kontinuitas | Checkout lokal bisa direkonsiliasi tanpa mengulang eksperimen | Kepala GitHub identik dengan checkpoint yang diharapkan. Manifest 45/45 dan regresi 14/14. Piagam, status, ledger, dan aksi menjadi pintu masuk lintas sesi. |
| E1.3 bank development | Contoh membedakan aturan publik dan audit mendeteksi salinan lintas split | 24 episode, 12 blok, 121 saksi simbolik dan 127 saksi graf. Seluruh 23 tes lulus. Kontrol tabrakan sintetis ditolak. Pemisahan bank selection dan hasil ilmiah masih terbuka. [Bukti dan perintah](code/e13/README.md#bank-development) |
