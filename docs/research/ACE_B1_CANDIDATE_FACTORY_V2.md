# Garis B1 · Pabrik Kandidat v2 (`tools/candidate_factory_v2.py`)

Perluasan generator kandidat mandiri dengan prefix baru (`grav_lang_id_*`, `grav_lang_ml_*`, `grav_code_v2_*`) di atas aturan validasi `tools/corpus_lint.py` tanpa mengubah korpus beku atau generator v1.

## Cakupan
1. **Kendala bahasa bertingkat yang dapat diatur (`--constraints-per-episode`, 2..6)**: `word_count`, `sentence_count`, `required_phrases`, `forbidden_words` (ekspansi afiks Bahasa Indonesia + infleksi multibahasa), `required_order`, dan `surface_hygiene` (tanpa digit, batas panjang kata, token penutup).
2. **Dua gelombang bahasa**: gelombang Bahasa Indonesia baru (6 domain operasional) + gelombang multibahasa (`id`, `en`, `es`, `de`, `fr` — menegakkan aturan program ≥4 bahasa).
3. **Kandidat kode komposit**: menggabungkan 4 pilar eksplisit dalam satu instruksi & sidecar (`algorithm`, `complexity_time`/`complexity_space`, `forbidden_tools`, `exact_signature` + `exact_return_format` + `"Sertakan docstring Bahasa Indonesia."`).
4. **Validasi internal fail-closed + sensus kesiapan**: kandidat yang gagal cek skema/lint/mekanis/duplikat/frozen tidak ditulis ke keluaran, dan ringkasan kesiapan per gelombang ditulis ke `readiness_census.json`.

## Verifikasi
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_candidate_factory_v2 tools.test_corpus_lint
python3 tools/verify_sources.py
```
