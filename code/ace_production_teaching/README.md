# EVO 0058 · Produksi dokumen dan pengajaran

Basis main `51521d5`. Rencana dan artefak baru hanya memakai masukan
lokal ber-anchor. Backend slide `python-pptx` bersifat lokal.
Verifier `python-docx`, `pypdf`, `openpyxl`, dan `python-pptx`
membaca kembali artefak yang ditulis pada fixture.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `tabular_engine.py` | Join many-to-one, pivot, agregasi, sel kosong dan lineage CSV |
| 2 | `document_builder.py` | Templat berisi binding bersumber ke DOCX dan PDF asli |
| 3 | `sheet_builder.py` | XLSX dengan formula hidup, cache nilai, dan deteksi siklus |
| 4 | `slide_builder.py` | PPTX tiga tata letak, teks, tabel editable dan sumber per slide |
| 5 | `chart_builder.py` | Grafik bar dengan baseline nol, grafik garis, skala dan sitasi per titik |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_production_teaching -t code -q
```
