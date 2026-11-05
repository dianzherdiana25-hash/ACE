# Keadaan ACE saat ini

## Issue #13 — shared four-label budget infrastructure (engineering-only)

A new evaluator-side `SharedLabelBudget` reserve/settle/reuse journal and 12 focused Python unit tests were added. **12/12 local unit tests PASS on Python 3.13.5**, with Git blob byte-identity checked. This is only **engineering groundwork** for Issue #13: it does not integrate, score, replay or accept the new branching-graph experiment. The 114-test repository regression was not run in this host. [Engineering contract](docs/ACE_E14_SHARED_LABEL_CONTRACT_v1.md) · [module](code/e14/e14_shared_budget.py) · [tests](code/e14/test_e14_shared_budget.py). E1.4o graph HOLD, E1.4s NATURAL_HOLD, and all frozen historical decisions remain unchanged.


## E1.4s — kualifikasi warisan GO dalam grammar terbatas

Pada 888.832 pasangan motif, satu label menerima 18.654 pasangan yang salah. Dengan maksimum tiga label, penjaga menerima seluruh 2.688 pasangan yang cocok dan tidak menerima motif yang salah. Pada dua label, penjaga menerima 926/2.688 dan menahan sisanya. Replay identik, audit terpisah cocok, regresi bersih 114/114. **NATURAL_HOLD.** Loop graf E1.4o masih HOLD. [Hasil](design/e1.4/E14S_RESULT_v1.md) · [Bukti](evidence/e14/e14s_verification_v1.json) · [Kelanjutan #13](https://github.com/dianzherdiana25-hash/ACE/issues/13).

## E1.4s — checkpoint historis pra-penilaian

Penjaga baru mempertahankan kandidat motif pendek yang masih cocok setelah satu label. Dengan batas dua atau tiga label, strategi membandingkan urutan prefiks/sufiks tetap dan pemilihan yang mencakup kandidat terbanyak. Protokol enumerasi grammar terbatas dan pemeriksaan isolasi beku, tes 2/2. [Protokol](design/e1.4/E14S_PROTOCOL_v1.md) · [Issue #12](https://github.com/dianzherdiana25-hash/ACE/issues/12).

## E1.4r — pemilihan interpretasi GO, ketahanan warisan HOLD

Graf diagnostik memilih interpretasi yang benar pada 36/36 dunia yang mengikuti tiga interpretasi yang disediakan, dibanding 12/36 untuk rantai dan kalibrasi pasif. Dua metode diagnostik menahan prediksi pada semua 12 pergeseran komplemen. Pada motif lebih pendek dengan biaya sama, graf menerima 51 prediksi salah dari 120 probe. Audit lanjutan menemukan 217 dari 3.200 pasangan motif pendek–silsilah bisa meniru biaya suatu interpretasi. **Robust HOLD · NATURAL_HOLD.** Replay cocok, regresi 112/112. [Hasil](design/e1.4/E14R_RESULT_v1.md) · [Bukti](evidence/e14/e14r_verification_v1.json).

## E1.4r — checkpoint historis pra-penilaian

Dua belas artefak E1.4p diaudit dan digunakan kembali pada 60 dunia target baru yang berpasangan. Satu label biaya membandingkan kalibrasi netral, rantai terarah, dan graf dengan tiga jalur bertarif berbeda. Gerbang interpretasi yang tersedia dipisahkan dari ketahanan terhadap motif yang lebih pendek dengan label sama. Tes 2/2. [Protokol](design/e1.4/E14R_PROTOCOL_v1.md) · [Issue #11](https://github.com/dianzherdiana25-hash/ACE/issues/11).

## E1.4q — pertanyaan graf bercabang GO dalam kondisi terkontrol

Pada awalan bersama, satu label biaya memisahkan keempat hipotesis pada 6/6 blok. Kasus lengkap 24/24, dibanding 6/24 untuk rantai dan 5/24 untuk graf acak. Awalan campuran hanya 12/24 dengan graf terarah. Per query terarah perlu 16 sisi dibanding delapan pada rantai. Himpunan hipotesis disediakan. HOLD loop rantai E1.4o dan NATURAL_HOLD tetap berlaku. Replay cocok, audit 12 blok, regresi 110/110. [Hasil](design/e1.4/E14Q_RESULT_v1.md) · [Bukti](evidence/e14/e14q_verification_v1.json).

## E1.4q — checkpoint historis pra-penilaian

Bank publik baru terdiri dari 12 blok dan 48 dunia berpasangan. Satu label biaya graf membandingkan pertanyaan bercabang terarah, rantai tunggal, dan cabang acak. Dua tes pra-penilaian lulus. [Protokol](design/e1.4/E14Q_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14Q_LOCK_v1.json).

## E1.4p — pewarisan selaras GO, pergeseran tersembunyi belum teratasi

Pendahulu simbol menghasilkan 12/12 artefak bertipe yang dapat dipakai kembali pada tugas biaya minimum graf bercabang dengan pemetaan yang disediakan. Satu label target menghasilkan 12/12 kasus selaras lengkap versus 1/12 untuk cold dan sham. Label diagnostik menolak artefak salah pada 12/12 pergeseran yang tampak. Pada pergeseran tersembunyi, warisan menerima 48/48 prediksi salah. **NATURAL_HOLD.** Replay dan audit cocok, regresi 108/108. [Hasil](design/e1.4/E14P_RESULT_v1.md) · [Bukti](evidence/e14/e14p_verification_v1.json).

## E1.4p — checkpoint historis pra-penilaian

Dua belas pendahulu simbol, 30 dunia graf bercabang, dan satu label target. Artefak pewarisan bertipe diuji terhadap cold dan sham. Tes 3/3. [Protokol](design/e1.4/E14P_PROTOCOL_v1.md).

## E1.4o — loop aktif direproduksi, gerbang gabungan HOLD

Simbol pulih penuh 8/9 dan graf 1/9 pada kasus terjangkau. Graf gagal ambang 5/9. Tidak ada pemicu keliru pada kasus dalam model. Uji timeout menyimpan tiga dunia dan melanjutkan ke 48 dunia, dengan replay cocok. [Hasil](design/e1.4/E14O_RESULT_v1.md) · [Bukti](evidence/e14/e14o_verification_v1.json).

## E1.4o — checkpoint historis pra-penilaian

Bank baru 40 blok, 48 dunia. Rangkaian aktif E1.4m dan E1.4n memakai batas bersama empat label. Tes 2/2. [Protokol](design/e1.4/E14O_PROTOCOL_v1.md).

## E1.4n — pemulihan bersyarat selesai dan direproduksi

**Repair GO.** Terarah dan enumerasi berhasil pada 18/18 dunia dengan label yang disediakan. Fixed-7 berhasil 6/18. Terarah mempertahankan kandidat identik dengan enumerasi sambil memeriksa 540 kandidat dibanding 879.810 pada strata repair. Semua delapan kasus tanpa solusi menahan prediksi. **Rare HOLD · NATURAL_HOLD.**

HEAD `2438eeb` dipulihkan dengan tree identik. Scoring dan replay memakai freeze `fb9ac72` dan worker Bubblewrap native yang lolos canary serta verifikasi batas proses. [Hasil](design/e1.4/E14N_RESULT_v1.md) · [Bukti](evidence/e14/e14n_verification_v1.json) · [Runtime sprint](docs/ACE_SPRINT_RUNTIME.md).

### Catatan historis E1.4n Linux namespace capability probe (4 November 2026)

A **separate** host-level canary executed inside real Linux user/mount/net/PID namespaces with read-only solver, private rootfs, and scrubbed environment. **Six of six** canary checks passed, including private evaluator-file and host-loopback denial. [Source](tools/ace_namespace_capacity_probe.py) · [Observed result](evidence/e14/e14n_namespace_capacity_v1.json) · [Limitations](docs/ACE_E14N_NAMESPACE_CAPACITY_v1.md). This **does not** establish equivalence to the frozen Bubblewrap worker or complete ACE evaluator confidentiality. E1.4n remains **PRE-SCORE / BLOCKED_ENV in this local host**; no scoring or replay was run.


## Catatan historis E1.4n — host-specific recovery audit before scoring (4 November 2026)

An independent GitHub **SHA-256 readback of all 8 frozen manifest files passed 8/8** for frozen source `fb9ac72`; this includes bank gzip and E1.4m upstream lock. [Static audit](evidence/e14/e14n_integrity_readback_v1.json). **Scientific status unchanged: PRE-SCORE FROZEN.** This ChatGPT local container has no native Bubblewrap or complete current private repository checkout, so E1.4n scoring was **not run**; local preflight is `BLOCKED_ENV`. [Environment record](evidence/e14/e14n_local_environment_preflight_v1.json). This is a host-specific execution barrier, **not** a scientific GO/HOLD or E1.4n failure. Use the existing original frozen runner and a verified sandbox-capable host, preserve fresh score/replay/audit and commit with readback. Work's prior prescore 4/4 tests were not rerun in this host.


## E1.4n — checkpoint pra-penilaian

Bank baru 56 blok, 72 dunia dan 2.322 input mentah. Perluasan DSL dipicu oleh habisnya kelas lama. Tiga pencarian dan satu kebijakan menahan prediksi menerima bukti yang sama. Tes pra-penilaian 4/4. [Protokol](design/e1.4/E14N_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14N_LOCK_v1.json).

## E1.4m — deteksi kontra-contoh terjangkau lulus

**Reachable GO.** Falsifikasi menggugurkan seluruh hipotesis pada 8/8 target simbol dan 7/8 target graf terjangkau. Kedua pembanding 0/8 di masing-masing keluarga. Seluruh 40 kasus dalam model bertahan di setiap lengan. Pada kondisi langka, semua lengan 0/16. **Rare HOLD · NATURAL_HOLD.**

[Hasil](design/e1.4/E14M_RESULT_v1.md) · [Bukti](evidence/e14/e14m_verification_v1.json) · [Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/835016481e61261386a02ae4867ece580d4cd1cd). Berikutnya, uji apakah kontra-contoh bisa memicu perluasan representasi yang tervalidasi.

## E1.4m — checkpoint historis pra-penilaian

Bank baru 56 blok, 72 dunia dan 2.240 input. Uji memisahkan target dalam model, target tujuh kejadian terjangkau dari contoh negatif, dan target langka. Tes pra-penilaian 4/4. [Protokol](design/e1.4/E14M_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14M_LOCK_v1.json).

## E1.4l — ranking lolos, gerbang biaya dan selektif HOLD

Ranking satu-label lolos pada packable. Simbol seri 5/5 dan graf 3/5 melawan 2/5 minimax. Ambang hemat menurunkan diagnosis dalam model dari 40 ke 29. Cakupan selektif simbol hanya 96/256. Pada uji aturan di luar model, semua 32 prediksi yang diterima lengan ambang salah. **NATURAL_HOLD** untuk transfer.

[Hasil](design/e1.4/E14L_RESULT_v1.md) · [Bukti](evidence/e14/e14l_verification_v1.json) · [Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/904dcc62d94bcbfdd6070437af434ec7cce25730). Tahap berikutnya mencari bukti untuk menggugurkan seluruh kelas hipotesis.

## E1.4l — checkpoint historis pra-penilaian

Bank baru berisi 52 blok, 72 dunia, dan 2.080 input mentah. Tiga strategi memakai generator yang sama saat keadaan sama. Delapan dunia di luar model menguji kesepakatan yang keliru. Tes pra-penilaian 4/4. [Protokol](design/e1.4/E14L_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14L_LOCK_v1.json).

## E1.4k — pertanyaan majemuk lulus pada cakupan terkontrol

**COMPOUND_DEVELOPMENT_GO.** Dengan satu label, majemuk terarah mendiagnosis panjang pada 6/6 kasus simbol dan 4/6 kasus graf packable. Kedua kontrol mencapai 0/6 per keluarga. Pada simbol alami, majemuk dan pendek sama-sama mencapai 2/12 diagnosis dan 90/96 probe tepat. Untuk 11 label, majemuk memakai 132 kejadian dibanding 62. **NATURAL_HOLD** untuk transfer.

[Hasil](design/e1.4/E14K_RESULT_v1.md) · [Bukti](evidence/e14/e14k_verification_v1.json) · [Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/ae73b9c9d69366d5a503fd1529ced1b11c716dd8). Tahap berikutnya menguji aturan pemeringkatan dengan biaya dan risiko fallback yang diukur.

## E1.4k — checkpoint historis pra-penilaian

Bank baru berisi 48 blok, 72 dunia, dan 1.920 input mentah. Pembanding memakai pertanyaan pendek terarah, panjang acak, dan majemuk terarah. Tes pra-penilaian 4/4. [Protokol](design/e1.4/E14K_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14K_LOCK_v1.json).

## E1.4j — pembuatan pertanyaan lulus pada uji terkontrol

**SYNTHESIS_DEVELOPMENT_GO.** ACE menyusun pertanyaan dari hipotesis yang cocok dengan contoh. Dengan satu label, 16/16 kasus satu-saksi terdiagnosis. Pada kondisi berurutan, delapan kasus aturan panjang baru terdiagnosis setelah label kedua. Pada kondisi di luar jaminan dua label, delapan kasus panjang tetap abstain. Pada simbol alami, diagnosis naik dari 1/12 ke 8/12 dengan satu label, tetapi akurasi probe tetap 95/96. **NATURAL_HOLD** untuk transfer.

[Hasil](design/e1.4/E14J_RESULT_v1.md) · [Bukti](evidence/e14/e14j_verification_v1.json) · [Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/f62d4cf65d8a9e6b54e9062698378560a2881b95). Berikutnya, uji apakah pertanyaan lebih panjang dapat menutup banyak hipotesis dengan biaya yang sepadan.

## E1.4j — checkpoint historis pra-penilaian

Bank publik baru berisi 48 blok, 72 dunia, dan 2.304 input. Uji pembuatan pertanyaan membandingkan guided, pool tetap, dan acak, dengan nol, satu, dan dua label. Empat tes pra-penilaian lulus. [Protokol](design/e1.4/E14J_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14J_LOCK_v1.json).

## E1.4i — selesai dan direproduksi

**WITNESS_DEVELOPMENT_GO.** Ketika dua grammar sama-sama cocok dengan demo, satu pertanyaan pembeda menentukan panjang pada 24/24 dunia terkontrol dan menghasilkan 96/96 probe tepat per keluarga. Ketika saksi dikeluarkan, sistem menunda diagnosis dan membeli nol label pada 24/24 dunia. **NATURAL_HOLD** tetap berlaku. Di 12 kasus alami ambigu, hanya dua dapat dipecahkan dengan satu label dari pool. Audit lanjutan menunjukkan satu label tidak dapat menjamin diagnosis pada enam kasus simbol untuk input mana pun yang sah.

[Hasil](design/e1.4/E14I_RESULT_v1.md) · [Bukti](evidence/e14/e14i_verification_v1.json) · [Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/63aeaf63f1762dc766c13a8188c15a2996316daf). Dua run 72 dunia selesai dengan hasil deterministik sama. Regresi lulus 83/83. Langkah berikutnya menguji pembuatan pertanyaan dan pengendalian anggaran saat bukti satu label tidak cukup.

## E1.4i — checkpoint historis pra-penilaian

Bank publik baru memisahkan kasus alami dan dua kondisi berpasangan. Kondisi terkontrol memakai demo dan probe yang sama dengan dua item pool yang berbeda. Empat tes pra-penilaian lulus. Penilaian dimulai setelah verifikasi commit pembekuan di GitHub. [Protokol](design/e1.4/E14I_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14I_LOCK_v1.json).

## E1.4h — pemilihan representasi lulus pada diagnostik

**ROUTING_DEVELOPMENT_GO.** Sistem memilih panjang aturan dari kecocokan dua grammar pada demo. Dalam bank peluang, pemilihan adaptif benar 192/192 per keluarga pada dua panjang, dibanding 144/192 untuk masing-masing pilihan tetap. Pada simbol alami panjang enam, sistem hanya mengenali kebutuhan beralih pada 1/6 blok. Seluruh pool dan probe di sel itu tidak memuat kata target, jadi akurasi tinggi saja dapat menutupi kegagalan diagnosis.

[Hasil](design/e1.4/E14H_RESULT_v1.md) · [Bukti](evidence/e14/e14h_verification_v1.json) · [Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/d6db8d065104ada75e676801bed62daa26cf094a). **NATURAL_HOLD** masih membatasi transfer. Langkah berikutnya ialah menguji pencarian saksi ketika dua representasi sama-sama cocok, sebelum membuat klaim tentang kemampuan menemukan representasi baru.

## E1.4h — checkpoint historis pra-penilaian

Grammar lima dan enam akan dibandingkan pada bank publik baru. Pemilih hanya menerima jumlah kecocokan demo dari kedua grammar saat menentukan representasi. [Protokol beku](design/e1.4/E14H_PROTOCOL_v1.md) · [Manifest](design/e1.4/E14H_LOCK_v1.json). Tes pra-penilaian 2/2. Penilaian dimulai setelah verifikasi commit pembekuan di GitHub.

## E1.4g — selesai dan direproduksi

**BENCHMARK_DEVELOPMENT_GO** untuk bank yang sengaja menyediakan peluang belajar. Pemilih aktif mencapai 96/96 di masing-masing keluarga dengan satu label tambahan, dibanding ekspektasi acak 60/96. Pada tugas enam kejadian, semua pemilih dengan grammar lima mencapai paling banyak 48/96 per keluarga. Acuan yang tahu panjang mencapai 96/96. **NATURAL_HOLD** terpisah. Hanya 1/6 blok simbol dan 0/6 blok graf alami pada panjang lima memberi peluang perbaikan.

[Protokol beku](https://github.com/dianzherdiana25-hash/ACE/commit/129b5b8505c6b747efd5f3d4b64a412f16f4c8e2) · [Hasil](design/e1.4/E14G_RESULT_v1.md) · [Verifikasi](evidence/e14/e14g_verification_v1.json). Lima canary isolasi lulus, dan replay serta auditor mencocokkan 72 dunia. Tahap E1.4h menguji pemilihan grammar tanpa mengetahui panjang aturan, dengan bank baru. Visi dan batas mandat ada di [piagam](PROJECT_CHARTER.md).

## E1.4g — checkpoint pra-penilaian

Bank publik memisahkan tugas sintetis alami dari tugas dengan peluang belajar yang dibangun sejak awal. Ada 48 blok dan 72 dunia. Delapan tes pra-penilaian lulus, termasuk batas representasi dan lima pemeriksaan isolasi. Snapshot historis `b34b316` cocok dengan tree GitHub. Regresi yang dapat dipulihkan dari snapshot tersebut lulus 69/69. Catatan historis E1.4f tetap menyimpan 84/84.

Baca [protokol](design/e1.4/E14G_PROTOCOL_v1.md) dan [manifest pembekuan](design/e1.4/E14G_LOCK_v1.json). Penilaian baru dimulai setelah checkpoint pembekuan terverifikasi di GitHub.

## E1.4f benchmark opportunity audit — 4 November 2026

**BENCHMARK_HOLD_REDESIGN.** New 24-task S/G in-basis/out-of-basis public study was hash-frozen at `5d44ed7` before scores. Main represented+curated+diagnostic strata: S hindsight-positive **2/6**, feasible Max-Gini positive **1/6**, summed gain +4/48; G hindsight-positive **2/6**, Max-Gini **1/6**, gain +2/48; strict prescored thresholds ≥3/6 and ≥2/6 failed. Replay byte-identical; prescore 8/8, independent auditor 10/10, and restored full E1.4 regression **84/84** passed. The 816 newly measured labels came from exhaustive development oracle calls; curated pool has more unlabeled compute. No worker isolation or external semantic confirmation. [Result](design/e1.4/E14F_OPPORTUNITY_RESULT_v1.md), [raw gzip](evidence/e14/e14f_public_development_v1.json.gz). Source archive now attached and Git-verified at [code/e14/e14f_frozen_source_2026-11-04.tar.xz](code/e14/e14f_frozen_source_2026-11-04.tar.xz); prescore hash unchanged. Next **E1.4g benchmark opportunity distribution redesign**, not another policy tuning round.


## E1.4e (4 November 2026): HOLD after separated meta validation

Frozen pre-score SHA manifest at `73a428e`; 12 source train / 6 meta / 12 target five-event tasks. Gross-gain G/low-ambiguity source strategy `first_disagreement` had meta validation gain 0 across two independent examples, and was rejected by a frozen strict-positive rule. All 12 targets abstained. Inherited **81/96**, task-local and minimax **80/96**, no-label **81/96**, exact one-label uniform expectation **80.875/96**. Four-stratum GO failed. Frozen replay matched; 8/8 prescore, 12/12 report auditor. Cost: 324 source/meta label events + 216 distinct target-side labels = 540 unique experimental labels; instrumented calls 636 (96 duplicated target full-fit queries). Full E1.4 regression was interrupted and had a partial `E`, so it is not verified. Same-process evaluator, no independent isolation. [Result](design/e1.4/E14E_META_VALIDATED_QUERY_RESULT_v1.md) | [code](code/e14/e14e_frozen_source_2026-11-04.tar.gz) | [gzip evidence](evidence/e14/e14e_public_development_v1.json.gz). Next: E1.4f identifiability/value-of-information audit before another transfer pilot.


## E1.4d (4 November 2026) — context-conditioned transfer result: HOLD

Frozen source `32f73d7`; new S/G five-event grammar tasks. Source meta-policy selected `ABSTAIN` on **12/12** target episodes. Correct target predictions: inherited **77/96**, task-local max-partition **79/96**, minimax one-label **79/96**, sham **77/96**, uniform one-label expected **78.25/96**, no label **77/96**, full eight-label target reference **87/96**. Strict four-stratum GO gate failed. Replay exact; local regression 46/46, audit 10/10, prescore 7/7. Corrected full source information acquisition = **216** labels, not narrow intervention subtotal 96. Candidate/evaluator lack independent process isolation; development only. [Report](design/e1.4/E14D_CONTEXT_POLICY_RESULT_v1.md); [raw JSON gzip](evidence/e14/e14d_public_development_v1.json.gz). **Next: E1.4e source/meta-validation and abstention diagnosis**.


## E1.4c-v2 corrected-pool replication (4 November 2026)

Scientific HOLD even after separating query-pool RNG from target-dependent demonstrations. Frozen source caedbe7. Twelve sources and twelve targets, 432/432 new inputs with no earlier public/v1 duplicates; 96 source training labels plus 96 target counterfactual oracle calls. Scores inherited vs local: S related 12/24 vs 15/24, S unrelated 12/24 vs 12/24, G related 16/24 vs 16/24, G unrelated 16/24 vs 11/24. Inherited pooled 56/96 vs local 54/96 but strict four-stratum gate fails. Counterfactual pool-invariance 4/4, E1.4 regression log 29/29 OK, arithmetic audit 8/8, deterministic replay exact. This corrective study is not independent confirmation; candidate/evaluator share a process and training costs are not amortized. [v2 report](design/e1.4/E14C_V2_POOL_INDEPENDENCE_RESULT_v1.md), [raw](evidence/e14/e14c_v2_public_development_v1.json).


## ACE E1.4c first pilot — HOLD (4 November 2026)

**Prescored frozen checkpoint `3025d7f`**: 12 source episodes teach one of 8 query policies; 12 target episodes (6 S/6 G) test new four-event rules. The inherited policy does **not** consistently beat task-local, sham and random controls across four predeclared strata. Key G/related result: 11/24 inherited vs 16/24 task-local and 15/24 sham. 96 source training labels and 96 exhaustive target counterfactual labels were used; one-label deployed cost excludes training. **Additional methodological flaw discovered post-score:** the target-dependent negative-demo rejection advances the same RNG stream later used for unlabeled question pools, potentially introducing indirect pool dependence. Thus the HOLD is diagnostic, not an independent causal transfer conclusion. Replay JSON normalization patch (tuple/list) repaired a false verification mismatch; 24/24 E1.4 package tests and 7/7 evidence-audit tests pass. [Full report](design/e1.4/E14C_CROSS_EPISODE_RESULT_v1.md), [raw evidence](evidence/e14/e14c_public_development_v1.json), [prior frozen prescore protocol](design/e1.4/E14C_CROSS_EPISODE_PRELOCK_v1.md). Next: **E1.4c-v2** with RNG-separated preallocated pools frozen before scoring.


## Checkpoint E1.4b — replikasi pool tanpa penyaringan (4 November 2026)

**Terbaru:** Replikasi *public development* pada snapshot beku `38b1c3b` selesai; 12 episode, 96 cabang satu-label, 132 fit. Pada simbol, pertanyaan aktif 27/48 vs acak ekspektasi 20,25/48 dan tanpa label 17/48; pada graf 28/48 vs acak 25/48 dan tanpa label 24/48. Kriteria GO pengembangan dua keluarga terpenuhi, **belum** bukti inferensial atau evolusi terbuka. Tes beku 70/70, bank 2/2, auditor 17/17, anti-stuck 7/7; replay deterministik cocok. Analisis eksploratori gabungan meliputi nol. Lingkungan uji memakai pengganti Bubblewrap terbatas; **validasi dengan binary resmi tetap terbuka**. Semua hasil beku E1.3 v1 NO-GO tetap berlaku, tidak ada pembukaan konfirmasi tersegel. [Hasil](design/e1.4/E14_QUERY_REPLICATION_RESULT_v1.md) · [Bukti](evidence/e14/query_replication_v1.json) · [Kontrak pemulihan](docs/ACE_WORKFLOW_RECOVERY.md).


**Status untuk pembaca umum.** E1.3 v1 ditutup dengan NO-GO ilmiah; E1.4 menguji pemilihan representasi dan pertanyaan. Replikasi E1.4b pada pool baru melewati gerbang pengembangan, tetapi transfer lintas episode dan generalisasi masih terbuka.

- **Proyek** [Piagam ACE](PROJECT_CHARTER.md) dan visi OAIE.
- **Branch** [`research/e1.3-design`](https://github.com/dianzherdiana25-hash/ACE/tree/research/e1.3-design). SHA checkpoint terkini adalah kepala branch tersebut. Checkpoint implementasi yang direkonsiliasi adalah [`0bb5c7d`](https://github.com/dianzherdiana25-hash/ACE/commit/0bb5c7d9fcd04abb361fe28b12b1b6c14560d2d9), yang memiliki tree sama dengan sumber lokal `6c1f6e3`. `main` berada di luar alur perubahan.
- **Bukti teknis** Manifest historis 45/45, regresi unit E1.2 14/14, tes E1.3 59/59 dan E1.4 3/3, smoke publik 6/6. Pemeriksaan mencakup isolasi berkas, lingkungan, dan jaringan worker. Perintah ada di [README E1.3](code/e13/README.md).
- **Status ilmiah** [F5](docs/ACE_F5_Research_Synthesis_and_Decision_v0.1.md) melanjutkan riset dengan batas klaim. [E1.2](docs/E12_Research_Report_v0.1.md) menunjukkan induksi dalam grammar buatan manusia dan transfer negatif pada aturan tidak terkait. E1.3 v1 ditutup dengan keputusan NO-GO untuk konfirmasi kandidat beku.
- **Sedang dikerjakan** Bank development sudah menghasilkan 24 episode dalam 12 blok aturan. Oracle evaluator, pemeriksaan keterbedaan contoh, dan audit tabrakan lintas split lulus pada kasus uji. Pilot engineering selesai untuk empat kebijakan. Pembanding buta benar 269/288, beam 165/288, katalog 109/288, dan fixed 77/288 pada bank publik. Seluruh kesalahan dipertahankan. 96 baris deterministik cocok pada replay. [Desain E1.3](design/e1.3/E13_DESIGN_v0.1.md) mendefinisikan gerbang riset.
- **Bukti terbaru** [Pilot v0.2](evidence/e13/development_pilot_v0.2.json), [audit kapasitas](evidence/e13/development_capacity_v0.1.json), dan [perintah replay](code/e13/README.md#pilot-development-v02). Semua 12 aturan publik punya program dalam vocabulary sekarang yang cocok pada saksi terbatas. Bank itu untuk rekayasa. [Diagnostik batas representasi](evidence/e13/development_representation_boundary_v0.1.json) menambahkan dua aturan publik terpisah. Setiap aturan memerlukan lima keadaan yang dapat dibedakan, di atas batas empat keadaan pembanding saat ini. Program diagnostik dibuat manual.
- **Implementasi terbaru** Empat kondisi C tersedia di worker. Definisi transisi bertipe dapat dipelajari dari demo sumber, diserialisasi, diperiksa hash-nya dan dipakai oleh worker baru untuk fit target. Pilot diagnostik publik meliputi 12 episode dan delapan kebijakan. C_EXTEND benar 32/32 pada kapasitas, 29/32 pada target terkait, dan 7/32 pada target tak terkait. Kontrol tanpa warisan benar 19/32, 1/32, dan 29/32 pada ketiga kelompok. Seluruh 24 replay fit target pada proses baru cocok. [Bukti](evidence/e13/development_transfer_pilot_v0.1.json) dan [interpretasi](code/e13/README.md#pilot-sintesis-dan-pewarisan-v01).
- **Pembanding terbaru** Terstruktur, enumeratif, dan beam diuji terpisah di kedua keluarga. Pada bank development awal hasilnya 269/288, 211/288, dan 165/288. Pada diagnostik hasilnya 33/96, 33/96, dan 42/96. Enam fit enumeratif mencapai batas langkah dan AST cadangannya tetap dinilai. [Bukti pembanding](evidence/e13/development_closed_comparators_v0.1.json).
- **Keputusan selection internal** Bank evaluator di luar checkout lulus audit pada 12 blok target dan uji isolasi. Beam ditetapkan sebagai B* untuk kandidat beku `2d9d86c`. Beam benar 50/96, enumeratif 48/96, dan terstruktur 42/96. Replay mencocokkan semua 36 arm. [Bukti agregat](evidence/e13/selection_summary_v1.json).
- **Batas bukti** Bank disusun sesudah kode kandidat dibekukan dalam jalur evaluator proyek yang sama. Pemisahan berkas dan worker teruji. Selisih dua probe memilih pembanding pada bank ini. Generalisasi dan ekuivalensi di luar domain saksi masih terbuka.
- **Reproduksi selection** Pekerjaan teknis terpisah dari implementasi kandidat mencocokkan 36 arm, digest bank dan urutan B*. [Bukti](evidence/e13/selection_reproduction_v1.json).
- **Perencanaan konfirmasi** Simulasi memilih 48 blok per keluarga per rezim pada asumsi efek +15 poin. Pada efek tepat +10 poin, aturan keputusan penuh lolos sekitar separuh simulasi. Profil publik 288 arm dan metode bootstrap berpasangan sudah tercatat. [Prelock](design/e1.3/E13_PRELOCK_v0.1.md).
- **Pemulihan evaluator** Ledger transaksional lulus uji interupsi pada worker publik. Arm terminal dilewati pada resume dan perubahan digest ditolak. [Cara uji](code/e13/README.md#checkpoint-arm-evaluator).
- **Keputusan E1.3 v1** Semua 99 tabel simbol dan 106 tabel graf kolaps pada saksi urutan berpasangan. Runner dan pembanding berinformasi lulus dry-run publik. Konfirmasi kandidat ini NO-GO. Efek konfirmatori tetap belum diketahui. [Keputusan](design/e1.3/E13_DECISION_v1.md).
- **E1.4 aktif** Kandidat mendiagnosis inkonsistensi hitung dari demo dan berpindah ke mesin urutan pada 6/6 episode bersaksi. Skor adaptif 48/48 di strata itu, 42/48 pada hitung, dan 22/48 pada urutan ambigu. Pilot 72 arm direproduksi. [Hasil](design/e1.4/E14_ROUTING_RESULT_v1.md).
- **E1.4b** Pada pool bersaksi, satu label aktif mencapai 48/48 dibanding nilai harapan acak 30/48 dan tanpa label 24/48. Pool kurang informasi memberi seri 24/48. Audit di luar basis menunjukkan batas representasi tetap. GO ke replikasi pool yang lebih beragam. [Hasil](design/e1.4/E14_QUERY_RESULT_v1.md). [Pekerjaan GitHub #1](https://github.com/dianzherdiana25-hash/ACE/issues/1) melacak gerbang berikutnya.

Baca [ledger](RESEARCH_LEDGER.md) untuk hasil positif dan negatif, serta [aksi berikutnya](NEXT_ACTION.md) untuk memulai kerja.
