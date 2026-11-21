# EVO 0053 · Persepsi lokal

Draf dari `main` pada `42f0102`. Bentuk font dan raster fixture ada di `test_ocr_engine.py`.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `ocr_engine.py` | OCR geometri dua jalur dengan boks sumber, ambiguitas, dan pembatas decoder PGM |
| 2 | `document_extractor.py` | Klaim teks, jumlah, desimal eksak, dan tanggal dengan zona sumber serta ketidakpastian |
| 3 | `screen_understanding.py` | Geometri frame, induk, label interior, dan boks glyph dalam koordinat layar |
| 4 | `diagram_reader.py` | Grafik batang bertanda, kalibrasi rasional, dan bukti per kategori |
| 5 | `audio_pipeline.py` | Segmen PCM dan pertautan token bertimestamp dari receipt yang terikat ke sumber |
| 6 | `speaker_diarization.py` | Klaster anonim berbasis spektrum dengan abstain dan boks waktu |
| 7 | `perceptual_memory.py` | Indeks persepsi tertambat, recall lintas modalitas, serta konflik satu lokasi |
| 8 | `confidence_calibrator.py` | Kalibrasi per pita dan modalitas dengan ECE/Brier pada keluarga held-out |
| 9 | `image_classifier.py` | Voting gambar dari receipt organ, kuorum, coverage, dan margin |
| 10 | `handwriting_reader.py` | Jarak bentuk cetakan tangan per kotak dan dukungan lintas penulis |
| 11 | `table_extractor.py` | Grid bergaris, pemeriksaan perpotongan, OCR per sel, dan koordinat sumber |
| 12 | `form_reader.py` | OCR label/nilai terpisah serta verifikasi jenis dan outline checkbox |
| 13 | `chart_digitizer.py` | Digitasi seri garis per kolom dengan kalibrasi eksak dan bukti jejak |
| 14 | `scene_describer.py` | Komponen gambar, atribut bentuk dan intensitas, serta relasi boks |
| 15 | `change_detector.py` | Registrasi translasi, boks perubahan, dan ukuran wilayah yang terbanding |
| 16 | `scan_enhancer.py` | Stretch percentile, filter speckle, dan binarisasi lingkungan |
| 17 | `page_stitcher.py` | Susun raster berurutan dengan sambungan terukur dan jejak halaman |
| 18 | `pdf_rasterizer.py` | Render Poppler lokal berbatas dan verifikasi roster raster PGM |
| 19 | `audio_denoiser.py` | Gate gain bertransisi dari profil noise WAV yang ditunjuk |
| 20 | `silence_segmenter.py` | Interval hening histeresis, komplemen, dan usulan titik potong |
| 21 | `audio_language_detector.py` | Bahasa segmen lewat penanda bersumber pada receipt tertambat |
| 22 | `video_frame_sampler.py` | Keyframe video lokal dengan cap waktu probe dan render yang saling dicek |
| 23 | `media_redactor.py` | Redaksi opak raster berdasarkan anotasi wajib tertambat dan verifikasi |
| 24 | `media_forensics.py` | Statistik seam, blok berulang, dan delta piksel terhadap referensi |
| 25 | `ocr_confidence_map.py` | Peta tile dari jarak vote, margin, dan cakupan boks glyph |
| 26 | `perception_cache.py` | Cache imutabel media/config, checksum entry, dan pemeriksaan umur |
| 27 | `batch_perception_runner.py` | Antrean OCR/adegan/hening dengan anggaran, hash input, dan kegagalan per tugas |
| 28 | `media_intake.py` | Jendela izin, tujuan, hash dan arsip media lokal berbasis isi |
| 29 | `perception_bench.py` | Akurasi bidang/sel dan WER dari roster held-out yang ditambatkan |
| 30 | `perception_eval_runner.py` | Putaran eval berkala dari receipt dengan ambang, delta, dan kalender |
| 31 | `code_reader.py` | Decode barcode dan QR lewat libzbar lokal dengan mode hash-only |
| 32 | `plate_reader.py` | OCR plat terlokalisasi, pembuktian format, dan penyembunyian default |
| 33 | `gauge_reader.py` | Estimasi jarum annulus dalam sweep terkalibrasi dengan ambiguitas |
| 34 | `map_reader.py` | Graf ruang dari grid raster dan rute ketika landmark terhubung |
| 35 | `sheet_music_reader.py` | Deteksi staf, notehead berisi, dan pitch diatonik dari clef deklaratif |
| 36 | `formula_reader.py` | OCR rumus linear dan AST bertata bahasa dengan offset galat |
| 37 | `signature_presence.py` | Tinta tambahan relatif terhadap formulir kosong yang tertambat |
| 38 | `object_flagger.py` | Aturan objek per wilayah dari receipt dengan penolakan bukti tipis |
| 39 | `object_counter.py` | Kandidat tunggal, komponen berimpit, hitungan berbatas luas, dan inti erosi |
| 40 | `spatial_reasoner.py` | Relasi boks, jarak kuadrat pusat/tepi, dan IoU berkalibrasi |
| 41 | `photo_sequencer.py` | Urutan parsial waktu dan presedensi, pilihan ambigu, serta siklus |
| 42 | `codeswitch_transcriber.py` | Bahasa per kata pada transkrip tertambat dan cap waktu peralihan |
| 43 | `keyword_spotter.py` | Kecocokan contoh WAV berbasis spektrum dengan jendela dan skor |
| 44 | `meeting_summarizer.py` | Kutipan rapat berbukti untuk frasa keputusan, tugas dan topik |
| 45 | `audio_quality_gate.py` | Cek RMS, clip, DC, hening dan rasio energi terhadap profil noise |
| 46 | `media_sync.py` | Penjajaran transkrip dan frame dengan drift serta cap waktu tertambat |
| 47 | `audio_describer.py` | Jadwal narasi aksesibilitas dan penyusunan PCM dari klip yang ditambatkan |
| 48 | `alt_text_writer.py` | Alt text geometri berbatas karakter dan rujukan wilayah |
| 49 | `visual_fact_check.py` | Pemeriksaan bukti visual lintas asal dan hash, termasuk sanggahan |
| 50 | `near_dup_image.py` | Perbandingan gradien raster dengan guard intensitas dan rotasi |
| 51 | `perception_priority.py` | Ranking aging, deadline kumulatif, deduplikasi, dan kuota kelas |
| 52 | `perception_costing.py` | Biaya unit internal per receipt dan status cakupan tarif |
| 53 | `lean_perception.py` | Raster beranggaran dengan averaging area dan gerbang OCR opsional |
| 54 | `perception_evidence.py` | Bundel artefak lokal dengan DAG provenance, head eksternal, dan hash |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_perception -t code -q
PYTHONPATH=code python3 -m ace_perception.ocr_engine fixture.pgm font.json
```

OCR menerima PGM P2/P5 hingga 8 bit dan template satu font dengan
grid biner berukuran sama. Input ideal berisi baris horizontal
dan glyph yang dipisah kolom kosong. Angka `word_gap` diukur dalam
piksel. Dua penilai wajib sepakat di bawah batas jarak. Karakter
`�` berarti bukti belum cukup untuk mengenali bentuk. Boks menyimpan
koordinat asli dengan tepi kanan dan bawah eksklusif.

Verifier menggunakan font sintetis yang tidak menyerupai data pemilik.
Batas pengenalan ditunjukkan lewat bentuk asing, nilai ambang, skala,
kontras, dan input rusak.

`document_extractor.py` menerima gambar, font, dan layout JSON dari
pemanggil. Setiap aturan mencari satu baris dalam zona yang ditetapkan
dengan prefiks literal. Zona kosong berarti seluruh gambar. Angka
desimal ditulis sebagai integer dan jumlah digit desimal. Baris yang
bersaing atau belum terbaca sepenuhnya menahan klaim. Fixture memakai
pemisah kata empat piksel dan batas jarak nol.

`screen_understanding.py` membaca frame sumbu sejajar dari raster.
Teks OCR pada interior membuat wilayah menjadi kandidat kontrol.
Jenis tindakan masih perlu sumber lain. Frame dengan anak memperoleh
hubungan induk dari boks terkecil yang mencakupnya.

`diagram_reader.py` memakai daerah plot tanpa sumbu, pita kategori,
dan dua tanda skala yang dirujuk. Satu batang perlu bertemu baseline
nol. Komponen ganda, melewati nol, lepas dari baseline, atau di luar
kalibrasi tetap terbuka. Nilai hasil disimpan sebagai pecahan eksak.

`audio_pipeline.py` membaca WAV PCM 8/16 bit. Roster segmen berasal
dari energi per jendela, durasi minimum, dan batas jeda. Receipt yang
sudah direkam harus menunjuk hash WAV dan roster. Kata membawa
interval sampel dan mikrodetik. Dekode bahasa berada di pihak
pencatat receipt.

`speaker_diarization.py` memakai tiga jendela spektral per segmen
bila panjangnya memungkinkan. Label anonim berlaku dalam satu WAV.
Bagian tanpa energi yang cocok, jarak meyakinkan, atau slot klaster
tetap terbuka. Verifier memakai nada buatan. Kinerja pada rapat
dan tumpang tindih pembicara belum diukur.

`perceptual_memory.py` menyegel indeks JSON mandiri. Pencarian
memerlukan head eksternal dan menampilkan rujukan receipt serta
boks/waktu. Beberapa kutipan berbeda pada wilayah media yang sama
dilaporkan sebagai konflik. Indeks terpisah dari store runtime.

`confidence_calibrator.py` memisahkan train dan held-out berdasarkan
keluarga. Frekuensi posterior per pita memakai prior eksplisit dan
minimum dukungan. Brier dan ECE memakai kasus yang sama pada kedua
lengan dengan confidence dikalibrasi masuk ulang ke pita metrik.

`image_classifier.py` menggabungkan vote tercatat atas byte gambar
yang diikat ke roster. Coverage, dukungan, dan margin dihitung
terhadap bobot seluruh organ terdaftar. Vote kurang percaya, abstain,
dan absen muncul terpisah. Seri menahan putusan.

`handwriting_reader.py` memakai lokasi satu glyph per kotak dan
contoh berkode penulis. Jarak mencakup silhouette, profil elastis,
dan aspek. Kata dibentuk sesuai urutan kotak. Pemanggil dapat
mengeluarkan satu penulis dari sumber contoh sebelum ranking.

`table_extractor.py` menerima zona tabel dan density minimum untuk
pemisah serta jumlah baris dan kolom opsional. Jumlah yang meleset
atau pemisah yang tidak bertemu menahan seluruh grid. Sel kosong
tetap memiliki posisi. Sel dengan glyph tak yakin berstatus partial.

`form_reader.py` mengecek label yang terbaca sebelum menerbitkan
nilai. Kotak label dan nilai harus terpisah. Nilai digits
mempertahankan nol awal. Checkbox membutuhkan outline, lalu
mengklasifikasikan kepadatan tanda dalam interior.

`chart_digitizer.py` memakai kalibrasi linear dua titik per sumbu,
pita abu per seri, dan interval setiap jejak. Pencabangan, hilangnya
jejak, ketebalan berlebih dan di luar kalibrasi ditandai per kolom.

`scene_describer.py` membangun deskripsi komponen terukur. Isi
komponen dan isi boks diukur terpisah agar wilayah bersarang dapat
ditelaah. Relasi menyatakan geometri koordinat piksel.

`change_detector.py` membandingkan raster dengan dimensi sama
setelah normalisasi tingkat abu. Shift opsional membutuhkan bukti
perbaikan unik pada inti yang sama. Perubahan dan tepi yang luput
dari perbandingan tercatat terpisah.

`scan_enhancer.py` mendukung stretch kontras dan binarisasi adaptif.
Filter speckle opsional memakai lingkungan asli. Percentile rata
dipertahankan sebagai grayscale dan mendapatkan status tersendiri.

`page_stitcher.py` mendukung mode gap serta overlap terukur tetap
atau otomatis. Ambiguitas, area rata, dan mismatch menahan hasil.
Boks hasil menunjuk halaman asli dan checksum.

`pdf_rasterizer.py` membutuhkan `pdftoppm` lokal dari Poppler.
Renderer memakai direktori sementara dengan batas halaman, dimensi,
dan durasi. Manifest berisi ukuran serta SHA-256 tiap raster. Tes
renderer memakai PDF dua halaman yang dibangun sendiri.

`audio_denoiser.py` mengambil interval noise WAV eksplisit dan
membuat WAV mono 16-bit baru. Gain menuju target secara bertahap.
Laporan mencatat energi dan kanal sumber, serta pengolahan profil.

`silence_segmenter.py` membedakan ambang mulai/akhir hening dan
mengeluarkan komplemen yang mencakup interval suara. Potongan
disarankan di tengah jeda internal yang memenuhi durasi.

`audio_language_detector.py` memakai penanda dengan sumber yang
diberikan pemanggil. Penanda lintas bahasa dikeluarkan. Teks campur,
dukungan tipis, dan receipt yang belum tersedia dilaporkan berbeda.

`video_frame_sampler.py` membutuhkan `ffprobe` dan `ffmpeg` lokal.
Probe memakai demuxer tertentu dan protokol file. Ekspor PGM mencocokkan
cap waktu frame render dengan probe dan menyimpan hash per frame.

`media_redactor.py` menutup kotak anotasi wajah, plat, atau teks dengan
nilai opak. Anotasi menyebut hash sumber dan daftar area wajib. Verifikasi
mengulang pembuatan byte raster dan mengecek hasil. Deteksi otomatis
wajah dan plat tetap memerlukan penghasil anotasi tersendiri.

`media_forensics.py` menghitung gejala statistik raster dan perbedaan
terhadap referensi ber-hash. Angka tersebut hanya menyatakan apa yang
terlihat di piksel, dengan provenance tetap unknown.

`ocr_confidence_map.py` memetakan jarak geometris vote OCR ke tile.
Area glyph yang tak sepakat tetap tanpa skor. Opsi preview menghasilkan
PGM dengan warna abu-abu yang dibedakan dari tile kosong.

`perception_cache.py` memakai hash isi media, revisi algoritme, serta
konfigurasi kanonis. Cache memverifikasi hasil dan entry saat membaca.
Cap waktu dari pemanggil memungkinkan pemeriksaan umur yang deterministik.

`batch_perception_runner.py` menjalankan daftar operasi tetap dengan
anggaran jumlah usaha dan byte. Pembacaan input relatif root menolak
symlink. Sumber harus cocok ukuran dan checksum sebelum decode.

`media_intake.py` memerlukan izin yang meliputi tujuan dan waktu
evaluasi sebelum membaca media. PGM/WAV didekode saat diperiksa.
PDF dan kontainer video menerima pemeriksaan header yang diberi label.

`perception_bench.py` menghitung kecocokan bidang dokumen dan sel tabel
dengan penalti unit ekstra. WER memakai edit distance dan jumlah kata
gold. Receipt kosong dan hasil salah tetap dibedakan.

`perception_eval_runner.py` mengevaluasi satu bukti terikat per
jendela UTC. Putaran yang hilang, rusak, atau kurang cakupan tetap
terlihat. Delta hanya diterbitkan antarjendela bersebelahan yang
masing-masing mempunyai metrik.

`code_reader.py` menggunakan libzbar lokal. Format harus terdaftar.
Payload hasil decode diperlakukan sebagai teks atau byte dan dapat
diganti hash saja. Verifier memakai EAN13 dan QR versi 1 yang dibuat
dengan fixture mandiri.

`plate_reader.py` menerapkan OCR ke boks yang sudah ditandai dan
memeriksa panjang grup huruf atau angka. Nilai teks tersembunyi
secara default. Verifier memakai raster dan grammar sintetis.

`gauge_reader.py` mengukur jarum dari piksel di antara dua radius.
Sumber kalibrasi menetapkan sudut, arah, dan satuan. Puncak ganda atau
dukungan rendah menahan nilai.

`map_reader.py` mengukur coverage jalan pada kotak piksel dan
membangun graf empat arah. Rute unit memakai BFS dengan urutan
koordinat yang tetap.

`sheet_music_reader.py` membaca pitch diatonik notehead hitam pada
satu staf. Clef ditetapkan pemanggil. Ritme dan accidental belum
diidentifikasi.

`formula_reader.py` membutuhkan satu baris per zona. AST mendukung
operator dasar, pangkat asosiatif kanan dan satu persamaan. Boks
OCR serta offset token tetap tercatat.

`signature_presence.py` memakai formulir kosong dengan hash dan
geometri yang cocok. Hilangnya tinta rujukan di atas ambang menahan
kesimpulan keberadaan tanda.

`object_flagger.py` menilai observasi yang sudah direkam terhadap
aturan per zona. Nilai confidence di bawah ambang dan zona absen
tetap terlihat. Pendeteksi objek menyuplai receipt di luar alat ini.

`object_counter.py` mengukur komponen tinta. Luas per objek menjadi
asumsi eksplisit untuk estimasi serta tidak mencampurkan inti erosi
dengan jumlah yang sudah didukung.

`spatial_reasoner.py` menerima boks sumber dan memberi relasi dua
dimensi. Jarak kuadrat dan kalibrasi dinyatakan sebagai pecahan agar
mempertahankan nilai eksak.

`photo_sequencer.py` mengikat receipt waktu dengan byte foto lokal.
Jika beberapa urutan konsisten, beberapa pilihan tetap tercatat.
Kontradiksi relasi menahan urutan lengkap.

`codeswitch_transcriber.py` memelihara kata dan waktunya dari receipt.
Label kata berasal dari penanda unik atau konteks terbatas yang
kebijakannya diterbitkan. Pergantian yang waktu pastinya tak diketahui
tetap ditahan.

`keyword_spotter.py` menilai deret spektral terhadap contoh WAV
yang disediakan. Kecocokan adalah kandidat dengan jarak dan waktu.
Verifier memakai nada sintetis yang mempunyai pola terukur.

`meeting_summarizer.py` memakai aturan frasa eksplisit untuk memilih
kutipan yang sudah ada. Catatan menyimpan segmen, jendela kata, cap
waktu, dan jumlah kutipan yang terkena batas keluaran.

`audio_quality_gate.py` mengukur PCM mono hasil decode. Rasio energi
membandingkan interval noise dengan sisa audio. Noise nol menghasilkan
status tak terdefinisi yang terpisah dari kegagalan ambang.

`media_sync.py` menguji drift dan residual anchor sebelum memilih
frame yang terdekat dengan tengah kata. Byte frame diverifikasi
terhadap manifest dan gap berlebihan menahan pasangan.

`audio_describer.py` menempatkan narasi di jendela hening bersumber.
Track WAV dibuat bila seluruh cue muat dan setiap klip terikat ke
kutipan tertulis. Teks yang belum mempunyai rekaman tetap rencana.

`alt_text_writer.py` menulis deskripsi dalam batas karakter dari
atribut geometri yang terukur. Wilayah yang tidak muat dihitung.

`visual_fact_check.py` membutuhkan kelompok asal dan hash media
yang berbeda untuk tiap dukungan. Sanggahan tetap tampil bersama
dukungan. Kelompok asal berasal dari receipt.

`near_dup_image.py` menyimpan skor Hamming gradien dan selisih
intensitas grid. Kandidat melaporkan orientasi terbaik dari yang
dipertimbangkan, dan hash byte identik mendapat status tersendiri.

`perception_priority.py` menyusun daftar dari cap waktu, aging,
kuota kelas, anggaran, dan deadline yang dinilai atas antrean serial.

`perception_costing.py` memakai unit internal yang ditetapkan di
rencana. Total lengkap hanya tersedia jika semua receipt dalam
jendela punya tarif dan metrik yang diperlukan.

`lean_perception.py` memperkecil raster dengan rata-rata area di
bawah batas sisi dan piksel. Font dan batas edit dapat mengaktifkan
probe retensi OCR lokal.

`perception_evidence.py` menyegel artefak dalam urutan DAG. Mode
verifikasi membaca semua byte kembali dengan head eksternal dan
membedakan file hilang serta file yang tidak cocok.
