# EVO 0052 · Bahan tempa dan provenance

Draf pembangunan dari main `42f0102`. Peta mengikuti penomoran rencana EVO 0052.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `dataset_forge.py` | Promosi dari indeks verifier terpisah, deduplikasi, isolasi partisi serta JSONL deterministik |
| 2 | `dataset_custody.py` | SHA-256 per baris dan rantai provenance, penolakan perubahan relatif terhadap anchor eksternal |
| 3 | `synthetic_data_generator.py` | Tiga keluarga tugas berseed, cek mekanis mandiri, dan laporan shortfall |
| 4 | `curriculum_distiller.py` | Distilasi urutan dari demonstrasi berkustodi, konflik, dan isolasi held-out |
| 5 | `lora_trainer.py` | Optimasi dua faktor pada aktivasi dense beku, gradien numerik, dan loss train |
| 6 | `preference_trainer.py` | DPO readout fitur tetap, log-ratio relatif referensi, dan gradien |
| 7 | `forgetting_guard.py` | Akurasi berpasangan per domain, penurunan kritis, dan bukti yang kurang |
| 8 | `merge_lab.py` | Interpolasi, delta terhadap basis, layout identik, dan jarak bobot |
| 9 | `model_registry_v2.py` | Replay registry tertambat, lineage, review, dan retire tanpa mutasi |
| 10 | `brain_bench.py` | Perbandingan kualitas dan sumber daya, hash artefak, dan diagnosis per kasus |
| 11 | `data_quality_scorer.py` | Rubrik mekanis berbobot, status unscored, dan contoh berkustodi |
| 12 | `near_dup_detector.py` | Jaccard shingle eksak lintas dataset, cluster, dan kebocoran partisi |
| 13 | `mixture_planner.py` | Minimum per tugas, apportionment berbobot, ambang skor, dan shortfall |
| 14 | `train_runner.py` | Orkestrasi optimizer fixture dan kelanjutan pada batas checkpoint pekerjaan |
| 15 | `hyperparam_searcher.py` | Successive halving dari receipt, reservasi kredit, dan cutoff per rung |
| 16 | `eval_harness.py` | Protokol bersama, gerbang target/regresi, dan frontier kualitas/sumber daya |
| 17 | `regression_diff.py` | Transisi per kontrak, regresi bernama, serta kehilangan cakupan |
| 18 | `token_budgeter.py` | Token per batch dan pengulangan, cadangan bertarif eksak, serta ambang |
| 19 | `experiment_tracker.py` | Replay receipt, pause/resume, checkpoint, dan overspend internal |
| 20 | `safety_data_filter.py` | Aturan berbasis bidang, penanda sensitif, dan saringan tanpa kutipan |
| 21 | `license_guard.py` | Cabang ekspresi lisensi, kebijakan izin, kewajiban notice, dan provenance |
| 22 | `model_card_writer.py` | Kartu Markdown/JSON dari receipt dan bench tertambat, termasuk gap |
| 23 | `quantization_lab.py` | Kode signed 4/8 bit, rekonstruksi, dan error probe matriks |
| 24 | `inference_profiler.py` | Latensi, throughput, peak byte, dan coverage penilaian per pita konteks |
| 25 | `organ_ab_router.py` | Alokasi A/B deterministik per strata dan audit receipt |
| 26 | `model_rollback.py` | Kandidat rollback berdasarkan riwayat, registry, domain, dan hash byte |
| 27 | `knowledge_probe.py` | Verdict per soal, aturan jawaban, coverage, dan ringkasan per domain |
| 28 | `distill_bench.py` | Held-out bebas overlap dan retensi keberhasilan guru pada pasangan |
| 29 | `forge_scheduler.py` | Cek horizon, reserve RAM, urutan prioritas, dan alokasi kontigu |
| 30 | `checkpoint_keeper.py` | Manifest rantai SHA-256, ukuran file, dan verifikasi terhadap head eksternal |
| 31 | `bilingual_balance.py` | Paritas ID–EN per keluarga, jenis tugas, dan split pada data berkustodi |
| 32 | `code_reasoner_forge.py` | Ranker preferensi AST dan evaluasi pada keluarga held-out |
| 33 | `judge_forge.py` | Kalibrasi isotonic per domain dan rubrik, MAE berpasangan |
| 34 | `summarizer_forge.py` | Pelatihan ekstraksi, urutan sumber, anggaran karakter, dan precision/recall |
| 35 | `translator_forge.py` | Tabel frasa ID–EN, segmentasi global, dan cakupan held-out |
| 36 | `multitask_merge.py` | Komposisi matematis adaptor LoRA, bentuk faktor, dan drift per probe |
| 37 | `transfer_probe.py` | Matriks sumber × target dengan baseline bersama dan coverage per sel |
| 38 | `staged_curriculum.py` | Pita sulit terpisah, replay, kuota, dan ekspor per tahap |
| 39 | `recipe_ablation.py` | Satu jalur parameter berubah dan selisih skor/token berpasangan |
| 40 | `poison_detector.py` | Sinyal perubahan label, irisan keluarga, drift bukti, dan konsentrasi |
| 41 | `dataset_rebalancer.py` | Pembobotan invers frekuensi, share efektif, serta ESS eksak |
| 42 | `negative_miner.py` | Kontras dari taksonomi tertutup, alias, dan ranking jarak edit |
| 43 | `difficulty_scorer.py` | Kesulitan posterior, coverage solver, sensitivitas, dan anotasi tahap |
| 44 | `dataset_versioning.py` | Snapshot, graf parent, dan diff metadata/konten tanpa menyalin payload |
| 45 | `lean_forge_runner.py` | Worker numerik lokal dengan batas address space, waktu, dan prefix checkpoint |
| 46 | `quant_matrix.py` | Roster dan baseline bersama, loss per tugas, serta frontier ukuran dan waktu |
| 47 | `trap_bench.py` | Trap berpasangan dengan kontrol, abstain, dan kesalahan confidence tinggi |
| 48 | `forge_report.py` | Laporan per eksperimen dari ledger, prefix checkpoint, dan bench held-out |
| 49 | `forge_priority_queue.py` | Admit berdasar prioritas bertambah karena usia, tenggat, dependensi, dan kapasitas |
| 50 | `failure_archive.py` | Arsip terminal terdeduplikasi, hash per catatan, dan konflik klasifikasi |
| 51 | `adapter_zoo.py` | Katalog LoRA dense, versi, bentuk matematis, lineage dan review per artefak |
| 52 | `adapter_router.py` | Routing kompatibel basis/layout dengan ranking, fallback eksplisit, dan cakupan |
| 53 | `active_drift_check.py` | Audit selector, review registry, hash byte, usia receipt dan drift runtime |
| 54 | `smoke_test_model.py` | Verifikasi roster smoke, tiga aturan jawaban, dan jendela maksimal 60 detik |
| 55 | `activation_ladder.py` | Replay persetujuan per peran dengan receipt/hash bukti, veto, dan tahap pending |
| 56 | `owner_correction_forge.py` | Readout koreksi kategoris dan evaluasi keluarga held-out terpisah |
| 57 | `receipt_preference_miner.py` | Pasangan DPO dari receipt verified, margin runner-up, dan isolasi held-out |
| 58 | `long_forgetting_probe.py` | Retensi per checkpoint dengan baseline sama, kehilangan tertunda dan pemulihan |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_forge -t code -q
PYTHONPATH=code python3 -m ace_forge.dataset_forge candidate.json --verified-index verify.json > dataset.jsonl
PYTHONPATH=code python3 -m ace_forge.dataset_custody seal dataset.jsonl --dataset-ref fixture/dataset > manifest.json
PYTHONPATH=code python3 -m ace_forge.dataset_custody verify dataset.jsonl manifest.json --expect-head "$SHA256"
```

Bentuk input `candidate.json` dan `verify.json` ada di
`test_dataset_forge.py`. Verifier asal menerbitkan indeks yang menyatakan
status, rujukan bukti, lisensi, dan SHA-256 atas payload kanonis.
Kebijakan lisensi berasal dari masukan. Rujukan dan hash dicatat sesuai
artefak yang diberikan pemanggil. Simpan head terverifikasi di saluran
terpisah sebelum menjalankan mode verify. Data fixture menguji mekanisme
penyegelan dan penerimaan.

Pembagian train/held-out memakai hash seed + ID keluarga. Rasio masukan
adalah ambang hash dan proporsi akhir dipengaruhi jumlah contoh di tiap
keluarga. Cek duplikat menggabungkan bentuk Unicode kanonis serta spasi
yang berbeda pada prompt. Cek yang lebih luas untuk contoh nyaris duplikat
termasuk butir 12.

`synthetic_data_generator.py` mengeluarkan calon pada skema masukan
`dataset_forge`. Laporan internalnya mencatat penolakan dan shortfall.
Calon memerlukan indeks terpisah untuk promosi.

`curriculum_distiller.py` menerima dataset JSONL, metadata langkah per
contoh, `--manifest`, dan `--expect-head`. Contoh masukan ada di
`test_curriculum_distiller.py`. Pemeriksa belajar urutan hanya dari
langkah demonstrasi train yang melewati ambang dukungan. Laporan
memuat konflik urutan beserta ID pendukung. Baris held-out membawa
soal dan pointer verifier, sementara jawaban disimpan di dataset
kustodi untuk penilai. Pengaruh terhadap hasil belajar belum dinilai.

`forgetting_guard.py` menerima protokol dan hasil boolean berpasangan,
dengan komitmen protokol yang diteruskan lewat
`--expect-protocol-sha256`. `brain_bench.py` mengunci roster kasus,
rubrik, identitas artefak, dan ambang sampel lewat `--expect-bench-sha256`.
Bench menerima skor 0–10.000 serta waktu dalam mikrodetik dan peak dalam
byte, lalu menghitung dua lengan dari observasi yang sama-sama tersedia.
Untuk persetujuan tempa, jalankan pemeriksa regresi terpisah pada domain
umum. Kedua program menerima pengukuran yang sudah direkam. Butir 7
dan 10 dikerjakan sebelum pelatihan agar penerimaan hasil dapat diuji
tanpa mengaktifkan organ.

`lora_trainer.py` menerima resep dan snapshot aktivasi dense dari
artefak asal, beserta anchor `--expect-dataset-sha256`. Keluaran berisi
matriks A/B dan jejak MSE train. `preference_trainer.py` menerima pasangan
pilihan dengan fitur tetap dan log-probabilitas baseline serta referensi.
Anchor dimasukkan lewat `--expect-pairs-sha256`. Hasilnya adalah delta
linear pada fitur tersebut dan trace loss DPO. Keduanya menguji optimizer
dengan fixture numerik. Ekstraksi aktivasi, fitting model penuh, integrasi
runtime, dan gain held-out memerlukan proses atau bukti terpisah.

`merge_lab.py` menerima resep, daftar snapshot tensor JSON, dan
`--expect-recipe-sha256`. Input dapat mencakup snapshot basis pada mode
delta. Nama, shape, dan arsitektur tensor harus cocok. Jarak dalam
receipt adalah diagnostik perubahan bobot. `model_registry_v2.py`
membaca JSONL kanonis dengan `--expect-head`. Mode `--propose-event`
mencetak baris baru untuk disaring, dengan status review berasal
dari receipt penilai yang dirujuk. Registry ini hanya katalog lokal.

`data_quality_scorer.py` membaca dataset berkustodi dan rubrik eksplisit
untuk panjang, bentuk jawaban, label bahasa, dan pemeriksaan teks.
Rujukan, skor, serta blocker keluar per baris. `near_dup_detector.py`
mencari pasangan lintas dataset, dengan irisan partisi train/held-out
ditandai dan daftar cluster transitif tetap membawa anggota bersumber.
Ambang Jaccard bersifat leksikal dan tidak menilai kesetaraan semantik.

`mixture_planner.py` mengambil baris skor yang diproyeksikan ke ID,
jenis tugas, partisi, status, skor dan rujukan bukti. Kebijakan target
serta stok kandidat diikat dengan `--expect-input-sha256`. Bila minimum
atau jumlah target tidak terpenuhi, report menahan rencana.

`train_runner.py` memakai rencana dan bundel resep numerik terikat
`--expect-plan-sha256`. Program mencetak checkpoint JSONL ketika tiap
pekerjaan selesai. Berkas checkpoint bisa diperiksa lewat
`--checkpoint-from` dan `--expect-head`. Resume hanya mencetak record
baru. Pekerjaan yang belum memiliki checkpoint diulang dari awal.

`hyperparam_searcher.py` mengeluarkan slot trial berikutnya dari
kebijakan terikat `--expect-policy-sha256` serta receipt yang sudah
tersedia. Kredit adalah unit abstrak per trial. Rung parsial menahan
eliminasi.

`eval_harness.py` mengikat rencana lewat `--expect-plan-sha256`.
Artefak dinilai dari paket bench dan guard yang masuk, dengan rubrik
dan roster kasus tetap serta domain target dan umum yang terpisah.
Frontier mempertahankan kandidat yang tidak dikalahkan di gabungan
kualitas, durasi, dan peak byte. Pemeriksa tidak mengaktifkan artefak.

`regression_diff.py` memakai dua snapshot terikat `--expect-before`
dan `--expect-after`. Pemeriksaan dipasangkan hanya ketika hash kontraknya
sama dan kedua rujukan observasi terpisah. Kehilangan cakupan dilacak
termasuk hasil yang belum dijalankan.

`token_budgeter.py` membaca ukuran contoh yang sudah dicatat beserta
resep batch dan tarif unit internal lewat `--expect-input-sha256`. Report
memisahkan token nyata, padding, dan cadangan yang dibulatkan per tahap.
Anggaran dihitung dari data masukan tanpa akses rekening atau layanan.

`experiment_tracker.py` menerima snapshot receipt dengan
`--expect-sha256` dan mengurutkan state per eksperimen menurut log.
Ledger merekam kredit internal yang digunakan, termasuk overspend pada
eksperimen gagal. Resume terikat ke checkpoint terakhir.

`safety_data_filter.py` memeriksa berkas calon sebelum promosi. Aturan
frasa dan kategori penanda sensitif dideklarasikan dalam kebijakan
dengan `--expect-policy-sha256`. Mode bawaan mengeluarkan temuan per ID,
aturan, dan bidang. Mode `--filtered` menghasilkan calon yang lolos
pemeriksaan mekanis untuk diproses oleh `dataset_forge`. Byte payload yang dipertahankan tetap cocok
dengan hash verifier asal. Cakupan aturan dan bahasa bergantung
pada kebijakan.

`license_guard.py` membaca dataset berkustodi, katalog izin
terikat, serta indeks sumber dengan pointer notice/atribusi. AND
menggabungkan kewajiban, OR mengevaluasi alternatif, dan WITH memerlukan
aturan pengecualian eksplisit. Report mencerminkan kebijakan yang
diberikan pemanggil.

`model_card_writer.py` membuat Markdown atau JSON dari profil artefak,
receipt, dan input bench terikat `--expect-input-sha256`. Angka bench
diputar ulang lewat pemeriksa pasangan. Bagian yang belum punya
bukti tercatat sebagai TIDAK TAHU.

`quantization_lab.py` membaca snapshot numerik dan resep dengan
`--expect-recipe-sha256`. Artefak menyimpan kode 4/8 bit serta skala.
Report mencatat error rekonstruksi dan probe matvec yang tersedia.
Ukuran payload merujuk ke kode yang dikemas, di luar metadata dan skala.

`inference_profiler.py` membaca receipt terikat
`--expect-input-sha256`. Pita konteks mencatat jumlah warmup dan
pengukuran terpisah. Kuantil nearest-rank, throughput, dan cakupan
penilaian memakai observasi yang dapat diperiksa di receipt.

`organ_ab_router.py` memisahkan tugas memenuhi syarat dari tugas di
luar perbandingan, kemudian menghasilkan receipt alokasi yang bisa
diperiksa ulang dengan `--verify`. Alokasi adalah rencana offline.

`model_rollback.py` membaca selector, registry, permintaan, dan folder
artefak. Head registry dan hash selector ditambatkan lewat argumen.
Versi terdahulu yang memenuhi domain dan status diperiksa terhadap
SHA-256 byte artefak, lalu usulan selector dicetak ke stdout.

`knowledge_probe.py` memakai kunci dan roster terikat
`--expect-protocol-sha256`. Receipt jawaban dinilai secara eksak,
normalisasi teks, atau integer kanonis sesuai tipe pertanyaan.
Output memuat hasil dan rujukan.

`distill_bench.py` memakai roster bahan distilasi dan held-out agar
tabrakan ID, prompt, rujukan, dan keluarga bisa diperiksa. Retensi,
akurasi dua lengan, dan uji tanda eksak dari pasangan diskordan
membawa jumlah sampel dan sumber observasi masing-masing.

`forge_scheduler.py` mengalokasikan pekerjaan pada slot pertama
yang memenuhi kebutuhan RAM bersamaan dengan tenggat. Ketersediaan
berasal dari kalender yang didaftarkan. Hasil menggunakan alokasi greedy berdasarkan prioritas dan mencatat
kapasitas rencana per jendela.

`checkpoint_keeper.py` membaca rencana artefak yang ditambatkan dan
mencetak manifest SHA-256. Mode verify memerlukan manifest dan head
eksternal. File checkpoint dan selector rollback dibaca di bawah root
yang disediakan dengan path relatif, tanpa mengikuti symlink.

`bilingual_balance.py` membaca dataset berkustodi serta kuota pasangan
ID–EN per jenis dan partisi. Keluarga yang memenuhi syarat dipilih secara
round robin dengan urutan dari seed. Mode `--export` mengekspor byte
record kanonis ketika semua kuota terpenuhi.

`code_reasoner_forge.py` mempelajari readout ranking dari fitur AST
dan preferensi yang sudah direkam. Mode `--adapter` menilai kandidat
pada query tak berlabel. Sumber kandidat diparse sebagai data. Penilaian
fungsional tetap berasal dari receipt terpisah.

`judge_forge.py` mengkalibrasi skor yang sudah direkam per domain
dan rubrik. Interpolasi terbatas pada rentang train. MAE membandingkan
kedua lengan pada kasus held-out yang tercakup.

`summarizer_forge.py` mempelajari bobot token dari anotasi kalimat.
Mode `--adapter` mengekspor kalimat persis dalam urutan sumber
dan menyimpan rujukan per kalimat. Skor held-out mengikuti anotasi
ekstraktif yang dirujuk.

`translator_forge.py` fit tabel dari pasangan berarah dengan dukungan
unik. Bagian tak tercakup ditandai di keluaran. Posisi segmen mengacu
pada code points NFC.

`multitask_merge.py` menggabungkan faktor LoRA kompatibel dengan
penskalaan alpha/rank per sumber. Probe membandingkan adaptor gabungan
terhadap delta asli tugas, dengan batas perubahan dari resep.

`transfer_probe.py` mengikat roster ke hash protokol. Satu baseline
per kasus dipakai di semua sel, dengan pasangan adaptasi terpisah.
Rerata within/cross menyebut coverage sel yang masuk.

`staged_curriculum.py` memilih contoh dari dataset berkustodi dan
anotasi kesulitan. Mode `--export-stage` menulis JSONL ke stdout
saat semua kuota terpenuhi, dengan record asli dan replay terbatas.

`recipe_ablation.py` memeriksa jalur parameter yang berubah dan
memakai baseline kasus bersama. Array parameter dianggap satu nilai
berurutan. Delta memerlukan coverage lengkap sesuai protokol.

`poison_detector.py` membandingkan dua snapshot berkustodi.
Perubahan label dan partisi dicatat dengan hash serta rujukan.
Konsentrasi dibandingkan di dalam jenis tugas. Sinyal adalah masukan
untuk telaah manusia.

`dataset_rebalancer.py` menghitung bobot contoh train berkustodi
sesuai target dan cap per jenis tugas serta bahasa. Report mengukur
distribusi efektif dan ukuran sampel efektif.

`negative_miner.py` hanya memakai target train yang bisa ditautkan ke
taksonomi eksklusif. Kandidat kontras membawa label dan rujukan kedua
sisi serta sumber aturan. Record hasil memakai skema contrastive.

`difficulty_scorer.py` mengeluarkan anotasi dari verdict satu per
solver per contoh, dengan prior eksplisit dan cutoff sampel.
Anotasi menyambung ke pita `staged_curriculum.py` melalui ID dataset.

`dataset_versioning.py` memakai mode `snapshot`, `diff`, dan
`lineage` dengan anchor eksternal masing-masing. Versi mencatat hash
konten, split, lisensi, serta rujukan bukti tanpa menyalin payload.

`lean_forge_runner.py` menjalankan optimizer numerik pada proses
lokal Linux dengan `RLIMIT_AS` dan timeout. Parent memeriksa setiap
checkpoint yang tersisa. Resume memakai prefix JSONL dan head eksternal.

`quant_matrix.py` membaca receipt kualitas, waktu, dan ukuran artefak.
Satu baseline per kasus dipakai di semua varian. Batas loss diperiksa
per tugas sebelum kandidat masuk frontier.

`trap_bench.py` menilai jawaban yang direkam terhadap kontrol pada
keluarga yang sama. Perbandingan akurasi memakai pasangan lengkap.
Kesalahan dengan confidence tinggi termasuk respons trap yang tersedia
pada pasangan tidak lengkap.

`forge_report.py` memvalidasi replay ledger dan prefix checkpoint.
Bench wajib menunjuk artefak yang muncul pada checkpoint run.
Laporan Markdown dan JSON membawa rujukan dan gap yang masih terbuka.

`forge_priority_queue.py` merekomendasikan satu batch dengan anggaran
RAM, slot, dan unit yang tersisa. Aging bertambah dalam jendela penuh.
Tenggat, waktu daftar, dan ID memecah skor seri. Receipt selesai dalam
snapshot membuka pekerjaan dependen pada keputusan berikutnya.

`failure_archive.py` mengambil event terminal gagal dari ledger
yang sudah disegel. Snapshot berulang menambah pointer asal pada
kegagalan yang sama. Konflik kategori tercatat beserta kedua anotasi.

`adapter_zoo.py` menambatkan katalog ke SHA-256 payload kanonis.
Versi berurutan perlu parent dan layout yang sama. Katalog menampilkan
versi terbaru dan versi qualified terbaru secara terpisah.

`adapter_router.py` memeriksa basis, lapisan, dimensi, label kemampuan,
status review, dan batas rank. Urutan memilih domain, lebih sedikit
label di luar kebutuhan, rank lebih kecil, nama, lalu versi terbaru
dengan nama itu. Fallback domain umum memerlukan izin dari query.

`active_drift_check.py` mencocokkan selector tertambat dengan
registry, byte artefak, dan snapshot runtime. Masing-masing sisi
punya diagnosis sendiri. Mode ini membaca sumber yang disediakan.

`smoke_test_model.py` memeriksa hasil smoke yang sudah direkam.
Satu batch memakai waktu mulai bersama dan ambang sampai 60 detik.
Aturan terdaftar ialah teks eksak, integer, atau hash JSON kanonis.

`activation_ladder.py` memakai policy dan ledger yang masing-masing
tertambat. Satu penolakan mengakhiri urutan. Persetujuan selesai berarti
receipt yang diminta tersedia untuk telaah.

`owner_correction_forge.py` menerima kode anonim dan rujukan izin.
Konteks dengan koreksi sepakat dari cukup keluarga mendapat label
usulan. Perbandingan pada keluarga held-out memakai baseline yang sama.

`receipt_preference_miner.py` mengunci roster, rubrik, snapshot
receipt, identitas artefak, dan representasi fitur. Mode `--dataset`
mengeluarkan pasangan berformat `preference_trainer.py` dari train.

`long_forgetting_probe.py` memakai baseline yang sama untuk semua
checkpoint. Rentetan penurunan putus saat coverage hilang. Keluaran
membawa pointer kasus, penilaian, dan checkpoint.
