# EVO 0056 · Studio media lokal

Basis `main` `51521d5`. Paket ini menerima rencana yang di-anchor
dan menghasilkan artefak baru di direktori yang ditunjuk.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `image_generator.py` | Arahan teks geometri, RGBA, kliping, empat sampel dan round trip PNG/PPM |
| 2 | `image_editor.py` | Crop, resize, rotasi, exposure, penutup, tint dan blur atas raster |
| 3 | `image_qa.py` | Luminans, clipping, tepi dan kontras pada anotasi teks |
| 4 | `style_series.py` | Render palet dan motif tetap, layout berbeda, serta verifier piksel |
| 5 | `voice_generator.py` | WAV PCM16 deterministik dari formant dan aturan fonem Indonesia |
| 6 | `voice_style.py` | Izin eksplisit dan estimasi prosodi pada sampel sintetis berfrekuensi acuan |
| 7 | `podcast_producer.py` | Narasi WAV, klip berlisensi dan ber-hash, cue bab serta jeda yang sesuai durasi |
| 8 | `audio_mixer.py` | Mix dialog/bed/efek, ducking berbasis sampel, pan, fade dan batas headroom |
| 9 | `video_composer.py` | Pan kamera per frame, potongan adegan dan soundtrack yang terukur dengan FFmpeg |
| 10 | `animation_renderer.py` | Render Blender Cycles CPU dan verifikasi perpindahan objek pada frame MP4 |
| 11 | `scene_director.py` | Timeline storyboard, batas dialog, continuity kamera dan wardrobe |
| 12 | `character_keeper.py` | Empat pose orisinal dan audit landmark piksel terhadap bible karakter |
| 13 | `script_writer.py` | Seleksi kartu sumber relevan dan batas durasi narasi berdasar laju baca |
| 14 | `subtitle_maker.py` | Dua WebVTT dari transkrip tersumber dan pengukuran aktivitas PCM |
| 15 | `media_localizer.py` | Lokalisasi dengan tabel tersumber, audit angka, istilah, placeholder dan durasi |
| 16 | `cover_maker.py` | Gambar sampul PNG dengan tipografi bitmap dan verifikasi kontras dari piksel |
| 17 | `music_generator.py` | Musik latar PCM dengan progresi MIDI, tempo, determinisme dan headroom |
| 18 | `audio_restorer.py` | Noise gate, koreksi bias DC, kanal stereo dan pengukuran RMS sebelum/sesudah |
| 19 | `video_assembler.py` | Trim dan gabung MP4, baca ulang urutan frame dan panjang audio |
| 20 | `media_compressor.py` | Profil ukuran dan dimensi, sampel PSNR dari hasil decode, tahan keluaran gagal |
| 21 | `upload_metadata_writer.py` | Draf untuk platform dengan batas field, persetujuan dan sumber per baris |
| 22 | `media_scheduler.py` | Penjadwalan deterministik dengan batas RAM dan slot, serta prasyarat |
| 23 | `asset_library.py` | Simpan objek berdasarkan hash, provenance per entri dan deteksi perubahan byte |
| 24 | `consistency_checker.py` | Ukur irisan palet dan audit landmark independen untuk mendeteksi pergeseran |
| 25 | `infographic_maker.py` | Raster grafik bar dengan skala nol, nilai CSV dan verifikasi piksel |
| 26 | `template_composer.py` | Templat lokal, caption, penjagaan area, dan kontras yang diukur |
| 27 | `preview_renderer.py` | Contact sheet gambar dan frame MP4 dengan waktu, ukuran, serta hash |
| 28 | `studio_bench.py` | Paket klip beranimasi, audio, sampul dan audit karakter pada fixture tertutup |
| 29 | `project_archiver.py` | ZIP deterministik berisi resep, aset dan bukti dengan verifier manifest |
| 30 | `variation_engine.py` | Variasi palet, posisi dan bentuk terstratifikasi dengan hash per PNG |
| 31 | `explainer_maker.py` | Video penjelasan dengan kutipan artikel relevan serta pointer baris |
| 32 | `listicle_maker.py` | Urutan hitung mundur, durasi tiap bagian dan video kartu |
| 33 | `whiteboard_animator.py` | Pengungkapan stroke bertahap dan verifikasi piksel akhir |
| 34 | `data_motion.py` | Interpolasi angka, skala divergen tetap dan jejak keyframe |
| 35 | `loop_maker.py` | Gerak periodik dan pengukuran selisih pada sambungan loop |
| 36 | `talking_avatar.py` | Avatar orisinal dengan bentuk mulut pada timeline sampel narasi sintetis |
| 37 | `dubbing_maker.py` | Dua MP4 dengan rekaman bahasa yang berbeda pada timeline video yang sama |
| 38 | `aspect_adapter.py` | Turunan portrait/landscape dengan crop fokus dan cek piksel |
| 39 | `highlight_reel.py` | Pemilihan jendela aktif RGB, jarak antar pilihan dan trim audio |
| 40 | `teaser_maker.py` | Potongan babak yang menjaga anchor dan kartu penutup |
| 41 | `series_cover_system.py` | Pita yang konsisten, kode episode berbeda dan kontras terukur |
| 42 | `sticker_maker.py` | Stiker RGBA dari pose karakter, alpha dan garis luar terukur |
| 43 | `still_poster.py` | Poster berjudul dari frame dan cap waktu video terpilih |
| 44 | `audio_drama.py` | Dialog multikarakter, efek berizin, overlap cue dan pointer episode |
| 45 | `scene_scorer.py` | Motif audio unik dengan interval nada, cue sampel dan jeda terukur |
| 46 | `sfx_generator.py` | Foley sintetis lokal dengan seed, envelope dan puncak terverifikasi |
| 47 | `voice_consistency.py` | Ukur selisih pitch dan jeda dari WAV berizin yang tertambat |
| 48 | `brand_safety_qa.py` | Saring kategori, frasa dan timeline anotasi yang belum tercakup |
| 49 | `asset_rights.py` | Cakupan grant atas hash, tujuan, atribusi, wilayah dan tanggal |
| 50 | `release_packager_media.py` | Preflight profil dan laporan QA yang terikat hash video, draf lokal |
| 51 | `text_legibility_qa.py` | Kontras wilayah teks pada frame terdecode, tinggi glyph dan gap sampling |
| 52 | `scene_retention_predictor.py` | Proxy retensi naskah, bobot eksplisit dan jejak fitur per adegan |
| 53 | `thumbnail_ab.py` | Dua PNG satu faktor, penugasan berimbang dan hasil eksperimen kosong |
| 54 | `render_recipe.py` | Bekukan profil, kontrak, build lokal dan persamaan byte hasil replay |
| 55 | `night_render_queue.py` | Filter jendela UTC, estimasi energi/daya dan replay serial yang eksplisit |
| 56 | `catalog_search_media.py` | Pencarian BM25 atas transkrip lokal terikat hash dan nomor baris |
| 57 | `reverse_storyboard.py` | Deteksi pergantian shot dan ekstraksi thumbnail representatif |
| 58 | `originality_checker.py` | Pisahkan duplikat byte dari kemiripan struktur dan warna teknis |
| 59 | `campaign_packager.py` | Draf kampanye lokal dari bukti izin per tanggal, aset dan jadwal dependen |
| 60 | `studio_season_report.py` | Rekap dari baris receipt, celah bukti per episode dan delta antar-musim |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_media_studio -t code -q
```

Format arahan gambar menggunakan baris `CANVAS` diikuti
`RECT`, `ELLIPSE`, `LINE`, `GRADIENT`, atau `POLYGON`.
Lihat fixture di `test_image_generator.py`.


## Bench tertutup

Rencana ada di `fixtures/closed_studio_bench.json`. Arsip bukti berisi
MP4, WAV campuran, sampul PNG, empat pose karakter, dan report dengan
hash per aset di `fixtures/closed_studio_evidence/`. Nilai pengukuran
berlaku untuk fixture itu. Kontras memakai sampel glyph, narasi memakai
formant aturan, dan konsistensi diukur dari lima landmark per pose.

```sh
PYTHONPATH=code:. python3 -m ace_media_studio.studio_bench \
  code/ace_media_studio/fixtures/closed_studio_bench.json ./bench-replay \
  --expect-sha256 2791b40f488b6ec61de645e1ec356fca06a6103ac223647e7b1001394bfb8d78
```


## Gerbang integrasi

`step_capability_report` dapat melampirkan ringkasan fixture setelah
`ACE_EVO0056_MEDIA_STUDIO=1` disetel dan isi
`evo0056_media/bench_report.json` di workspace cocok dengan
`ACE_EVO0056_REPORT_SHA256`. Gerbang mati secara bawaan. Hook baru
hanya melakukan pembacaan. Rencana narasi, gambar, dan render lain
dijalankan secara mandiri melalui CLI paket.

Lingkup verifikasi mencakup geometri terstruktur, narasi formant,
prosodi berizin, karakter orisinal, WebVTT dengan transkrip masukan,
dan sulih suara dari rekaman masukan. Antrean render memeriksa
perkiraan watt dan watt-detik yang dideklarasikan, tanpa pengukuran
daya perangkat. Skor proxy retensi belum dikalibrasi terhadap
perilaku penonton.
