# EVO 0057 · Institut riset lokal

Basis main `51521d5`. Input penelitian berasal dari berkas lokal
yang ditunjuk pemanggil. Hasil perhitungan menyertakan nomor baris
atau rujukan sumber serta hash. Format tabel hasil di
`test_paper_reader.py` menjelaskan subset Markdown yang didukung.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `research_planner.py` | Metode bertipe, falsifier, urutan prasyarat, dan anggaran |
| 2 | `source_collector.py` | Relevansi dari baris aktual, umur, custody hash, dan grup independen |
| 3 | `paper_reader.py` | Tabel hasil teranotasi, konversi satuan, interval dan baris yang ditahan |
| 4 | `literature_reviewer.py` | Median per grup serta konflik/ketiadaan bukti yang dibedakan |
| 5 | `claim_checker.py` | Pemeriksaan klaim angka dengan populasi, konteks, sampel, dan sumber |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_research_institute -t code -q
```
