# Garis A Tranche 2 (A3) — Pemetaan Bentuk Klaim Prosa Historis Director

Menindaklanjuti usulan tranche 2 butir 3 pada [ACE_GARIS_A_AKUNTANSI.md](ACE_GARIS_A_AKUNTANSI.md), lima artefak historis ACE (`docs/validation/ACE_FULL_SYSTEM_VERIFICATION_20261107.md`, `docs/validation/ACE_OAIE_REVIEW_20261110.md`, `docs/validation/ACE_OAIE_CLOSED_LOOP_VERDICT_20261114.md`, `handover/EVO_0005_KONSOLIDASI_20261116.md`, dan `handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md`) diuji terhadap `director_asset_check.py` dan `director_value_check.py`.

## Temuan awal sebelum perluasan

1. Tautan Markdown relatif (`[label](../code/ace_operational/store.py)`) tidak diselesaikan terhadap direktori dokumen asal, sehingga memicu `ambiguous / invalid_repo_path`.
2. Token backtick berupa SHA hex (`4b8226916dfa`) atau konstanta status huruf besar (`BLOCK_RELEASE`, `VERIFIED_OFFLINE_CLOSED_LOOP`) dibaca sebagai klaim `module` dan menghasilkan puluhan alarm palsu `not_found`.
3. `director_value_check.py` hanya membaca baris `- claim: {...}` dan mengembalikan `0` klaim pada seluruh dokumen historis yang memakai rasio `N/M`, tabel Markdown, penugasan `k=v`, atau pengali/persentase.

## Bentuk yang disetujui (masing-masing disertai fixture tersendiri)

| Bentuk | Contoh historis | Cakupan parser |
|---|---|---|
| `relative_markdown_link` | `[store](../code/ace_operational/store.py#L1)` | Diselesaikan terhadap direktori dokumen di dalam repo (`director_asset_check.py`); jalur keluar repo tetap ditolak. |
| `symbol_or_status_token` | `` `BLOCK_RELEASE` ``, `` `4b8226916dfa` `` | Dipisahkan ke `symbol_tokens` pada `director_prose_audit.py` agar tidak salah diklasifikasikan sebagai modul Python yang hilang, sambil menjaga `module:nama` dan modul bertitik tetap diperiksa. |
| `ratio_claim` | `3/4`, `7/8 = 0.875`, `G0: 4/16 (25.0%)` | Diekstrak deterministik sebagai `{numerator, denominator, value}` plus nilai desimal/persen jika tertulis. |
| `kv_metric_claim` | `forgetting_count = 0`, `N=8`, `macro_hits=2` | Diekstrak menjadi `{label, value}` di luar URL dan blok kode. |
| `table_numeric_cell` | `\| **TOTAL** \| **18 Modules** \| **179** \| ... \| **257.98s** \|` | Diekstrak per sel dengan label baris & koordinat `L:C`. |
| `percent_or_multiplier_claim` | `2.225x`, `45.05%` | Diekstrak dengan satuan `x` atau `%`. |
| `unrecognized_prose` (batas negatif) | `Snapshot awal mencakup 89 ref branch...` | Prosa bebas bernomor di luar bentuk di atas tetap ditandai eksplisit sebagai `unrecognized_prose`, bukan ditebak secara diam-diam. |

## Cara menjalankan tes

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest -v \
  tools.test_director_audit tools.test_director_historical_shapes
python3 tools/director_prose_audit.py handover/EVO_0005_KONSOLIDASI_20261116.md --repo .
```
