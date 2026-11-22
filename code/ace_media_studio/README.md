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

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_media_studio -t code -q
```

Format arahan gambar menggunakan baris `CANVAS` diikuti
`RECT`, `ELLIPSE`, `LINE`, `GRADIENT`, atau `POLYGON`.
Lihat fixture di `test_image_generator.py`.
