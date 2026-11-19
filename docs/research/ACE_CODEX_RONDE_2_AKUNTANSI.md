# Akuntansi pembangunan ronde 2

Serahan pembangunan ronde 2 tersedia sebagai PR draf. Penyaringan mengikuti jalur review per PR. Dasar pemeriksaan repo adalah [main pada 478848d](https://github.com/dianzherdiana25-hash/ACE/tree/478848d1221bba8988980b8aba655e772ad4d243).

| Butir | Bukti implementasi dan tes | Hasil pada revisi tersebut |
| --- | --- | --- |
| WS-4 8 · distiler pola | [PR #328](https://github.com/dianzherdiana25-hash/ACE/pull/328) · [tes distiler](https://github.com/dianzherdiana25-hash/ACE/blob/2cda38757103b553e1f34fa1838409f3bea2e1c0/tools/test_pattern_distill.py) | Badan PR mencatat 42 tes terpilih lulus. |
| WS-4 9 · pengusul kurikulum | [PR #329](https://github.com/dianzherdiana25-hash/ACE/pull/329) · [tes pengusul](https://github.com/dianzherdiana25-hash/ACE/blob/68c105687d08a0d604154d2abc779bc47526bdeb/tools/test_curriculum_propose.py) | Badan PR mencatat 14 tes terpilih lulus dan 7 tes baru lulus saat diulang dengan distiler #328. |
| WS-4 10 · lab historis | [PR #330](https://github.com/dianzherdiana25-hash/ACE/pull/330) · [tes lab](https://github.com/dianzherdiana25-hash/ACE/blob/75783e981cc1e3a9516e97134f1220594d4cb6ed/tools/test_curriculum_lab.py) | Pengulangan pada commit lab menghasilkan 24 tes lulus. |
| WS-2 · verifikator dan laporan | [Spesifikasi #332](https://github.com/dianzherdiana25-hash/ACE/pull/332) · [PR #333](https://github.com/dianzherdiana25-hash/ACE/pull/333) · [tes verifikator](https://github.com/dianzherdiana25-hash/ACE/blob/94273ed0b8d16e775750a1f43283a693fd547c79/tools/test_revenue_verify.py) | 21 tes lulus dan uji kedua CLI pada fixture Fastwork lulus. |

## Uji ulang WS-4

Jalankan dari akar checkout commit lab `75783e981cc1e3a9516e97134f1220594d4cb6ed`. Kelompok tes antar-PR saling tumpang tindih.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q \
  tools.test_curriculum_lab tools.test_curriculum_propose \
  tools.test_pattern_distill tools.test_curriculum_gen
```

Tes ringkasan berikut memeriksa keluaran Markdown terhadap arsip yang sama dengan uji historis pada #330. Sumbernya adalah [episode EVO 0006](https://github.com/dianzherdiana25-hash/ACE/blob/75783e981cc1e3a9516e97134f1220594d4cb6ed/evidence/evo0006/screen_code.jsonl) dan [korpus instruksinya](https://github.com/dianzherdiana25-hash/ACE/blob/75783e981cc1e3a9516e97134f1220594d4cb6ed/handover/EVO_0006_CORPUS_CANDIDATES_V1.jsonl).

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
from tools.curriculum_lab import run_lab

report = run_lab(
    Path("evidence/evo0006/screen_code.jsonl"),
    corpus=Path("handover/EVO_0006_CORPUS_CANDIDATES_V1.jsonl"),
    max_chars=2048,
)
lines = report.splitlines()
for line in ("- Pola terdistilasi — 11", "- Usulan — 1", "- Celah terbuka — 2"):
    assert lines.count(line) == 1, line
PY
```

## Uji gabungan WS-2 dan WS-4

Checkout pengujian `94490e2` dibuat dari commit lab `75783e9` dengan
cherry-pick `94273ed`. Gunakan Python 3.12 dan NumPy 2.1.3 untuk reproduksi
kelompok yang memerlukannya.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest -q   tools.test_curriculum_lab tools.test_curriculum_propose   tools.test_pattern_distill tools.test_curriculum_gen   tools.test_revenue_verify tools.test_revenue_report tools.test_royalty_track
```

| Kelompok | Hasil teramati |
| --- | --- |
| Tes gabungan terpilih di atas | 45 lulus. |
| Semua modul `tools/test_*.py` | 261 tes dengan tiga kegagalan fuzz dan satu galat socket HTTP dashboard. Tiga kegagalan fuzz yang sama muncul saat `tools.test_fuzz_parsers` diulang di `478848d`. Uji dashboard lulus saat diulang dengan akses loopback. |
| Discovery `tests/` | 188 lulus. |
| Proyek sistem manajemen usaha | Pengujian awal tertahan saat membuka socket. Pengulangan loopback menghasilkan 6 lulus. |
| Fixture proyek pengelola keuangan | 6 lulus. |
| Harness lineage, lewat eksekusi langsung berkas tes | 12 lulus. |
| Discovery semua modul tes di `code/` | 1.765 tes pada `75783e9` dengan 1 kegagalan installer, 27 galat, dan 17 skip. Installer dan kelompok yang terhalang saat membuka socket lulus saat diulang dengan izin loopback, cache fixture kosong, dan 98 tes terpilih. Delta WS-2 hanya menambah berkas perkakas dan dokumen. |

**SELESAI** — seluruh serahan WS-2 dan WS-4 tersedia sebagai draf dengan bukti tes di atas.

**TERSISA** — penyaringan draf. Perbaikan fuzz dijadwalkan di Garis D.

**PENGHAMBAT** — nihil untuk serahan ronde. PR #332 menyediakan kriteria verifikasi WS-2.
