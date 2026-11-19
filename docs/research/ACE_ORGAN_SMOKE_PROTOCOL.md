# Protokol Smoke Harness Organ EVO 0009 (E3)

Protokol standar untuk menguji kontrak layanan jembatan/organ EVO 0009 secara **strictly offline** via `tools/organ_smoke_harness.py` (`0` panggilan HTTP/socket dari harness ini).

## Kontrak yang Diuji (§2.5 Rancangan EVO 0009)

1. **`GET /health`**: Mengembalikan `200` dengan `ok: true` atau `status: "ok"`.
2. **`GET /v1/models`**: Mengembalikan `object: "list"` dengan daftar model non-kosong ber-`id`.
3. **`POST /v1/chat/completions`** (peran `front`, `coder`, `validator`, `judge`):
   - Memakai `chat_template_kwargs={"enable_thinking": false}` bagi pemanggil terstruktur untuk mencegah pengurasan budget pada channel reasoning kosong (preseden uji Front 2026-11-16).
   - Wajib menyertakan `brain_of_origin` (`"<provider>/<model>"`) dan `choices[0].message.content` non-kosong.
4. **`POST /v1/embeddings`** (peran `embedding`):
   - Vektor non-kosong berisi angka finit (menolak `NaN`/`Inf`/`bool`) + `brain_of_origin`.
5. **Penolakan `a3b` di mode bridge**: Permintaan peran `a3b` melalui bridge wajib ditolak terkontrol karena `a3b` adalah organ lokal on-demand.
6. **Latihan Fail-Closed (Injeksi Gangguan)**:
   - HTTP `429` (`budget_exhausted`), `502` (`organ_unavailable`), payload tanpa `brain_of_origin`, overflow reasoning berkonten kosong, serta vektor embedding mengandung `NaN` harus selalu gagal terkontrol tanpa mengarang jawaban.

## Pemakaian

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/organ_smoke_harness.py --format markdown
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest tools.test_organ_smoke_harness -v
```
