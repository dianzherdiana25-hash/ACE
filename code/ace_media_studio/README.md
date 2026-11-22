# EVO 0056 · Studio media lokal

Basis `main` `51521d5`. Paket ini menerima rencana yang di-anchor
dan menghasilkan artefak baru di direktori yang ditunjuk.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `image_generator.py` | Arahan teks geometri, RGBA, kliping, empat sampel dan round trip PNG/PPM |
| 2 | `image_editor.py` | Crop, resize, rotasi, exposure, penutup, tint dan blur atas raster |
| 3 | `image_qa.py` | Luminans, clipping, tepi dan kontras pada anotasi teks |
| 4 | `style_series.py` | Render palet dan motif tetap, layout berbeda, serta verifier piksel |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_media_studio -t code -q
```

Format arahan gambar menggunakan baris `CANVAS` diikuti
`RECT`, `ELLIPSE`, `LINE`, `GRADIENT`, atau `POLYGON`.
Lihat fixture di `test_image_generator.py`.
