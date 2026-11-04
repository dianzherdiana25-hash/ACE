# ACE E1.2 — Bounded Primitive Induction & Transfer

Hasil riset dan kode untuk evaluasi pembentukan operasi dari contoh, lalu pemakaian ulang pada tugas baru.

## Jalankan di Python 3.11+ (tanpa library tambahan)

```bash
python -m unittest test_e12.py -v
python run_e12.py --out rerun --seed-start 12501 --episodes 40
python audit_e12.py --folder rerun
```

Periksa `rerun/summary.json` dengan `confirmation/summary.json`, juga `last_sha256`.

## Batas klaim

Keberhasilan pada operator yang sama adalah transfer **di grammar buatan peneliti**, bukan AI yang menemukan primitive fundamental baru. STRUCTURED mencapai 100% baik tugas terkait maupun tak terkait, sehingga keunggulan atas metode analitis tidak terbukti. Tidak ada API key, biaya API, maupun kode Python yang dibuat lalu dieksekusi tanpa sandbox.

`preconfirm_lock.json` mencatat hash dan penguncian lokal sebelum konfirmasi. `posthoc_stats.py` dan statistik dibuat setelah konfirmasi; tidak memengaruhi pemilihan kandidat. `independent_eval.py` dan `audit_e12.py` tersedia untuk menilai semantik hasil.
