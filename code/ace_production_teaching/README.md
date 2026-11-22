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
| 6 | `report_composer.py` | Metrik dari observasi bersumber, rekonsiliasi satuan dan binding yang sama di seluruh laporan |
| 7 | `artifact_qa.py` | Gate hash, struktur native, syarat minimum dan fitur aktif yang ditahan |
| 8 | `data_anonymizer.py` | Kebijakan drop/mask/keep/pseudonim per kolom, HMAC lingkup lokal dan audit tanpa nilai |
| 9 | `schema_validator.py` | Validasi data bertingkat dengan JSON Pointer dan kaidah nilai berhingga |
| 10 | `document_merger.py` | Transfer paragraf, tabel dan daftar isi DOCX dengan bookmark yang dapat diklik |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_production_teaching -t code -q
```
