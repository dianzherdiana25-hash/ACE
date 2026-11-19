# Akuntansi pembangunan ronde 2

**Ronde terbuka.** WS-4 memiliki tiga draf dengan tes. Penutupan ronde masih memerlukan WS-2. Dasar pemeriksaan repo adalah [main pada 478848d](https://github.com/dianzherdiana25-hash/ACE/tree/478848d1221bba8988980b8aba655e772ad4d243).

| Butir | Bukti implementasi dan tes | Hasil pada revisi tersebut |
| --- | --- | --- |
| WS-4 8 · distiler pola | [PR #328](https://github.com/dianzherdiana25-hash/ACE/pull/328) · [tes distiler](https://github.com/dianzherdiana25-hash/ACE/blob/2cda38757103b553e1f34fa1838409f3bea2e1c0/tools/test_pattern_distill.py) | Badan PR mencatat 42 tes terpilih lulus. |
| WS-4 9 · pengusul kurikulum | [PR #329](https://github.com/dianzherdiana25-hash/ACE/pull/329) · [tes pengusul](https://github.com/dianzherdiana25-hash/ACE/blob/68c105687d08a0d604154d2abc779bc47526bdeb/tools/test_curriculum_propose.py) | Badan PR mencatat 14 tes terpilih lulus dan 7 tes baru lulus saat diulang dengan distiler #328. |
| WS-4 10 · lab historis | [PR #330](https://github.com/dianzherdiana25-hash/ACE/pull/330) · [tes lab](https://github.com/dianzherdiana25-hash/ACE/blob/75783e981cc1e3a9516e97134f1220594d4cb6ed/tools/test_curriculum_lab.py) | Pengulangan pada commit lab menghasilkan 24 tes lulus. |
| WS-2 · verifikator dan laporan | [Pelacak royalti CSV pada basis audit](https://github.com/dianzherdiana25-hash/ACE/blob/478848d1221bba8988980b8aba655e772ad4d243/tools/royalty_track.py) | TIDAK TAHU rel mana yang harus diverifikasi, bukti wajib per rel, dan aturan penerimaannya. Pelacak yang ditemukan mengagregasi penjualan dan royalti per bulan. |

## Uji ulang WS-4

Jalankan dari akar checkout commit lab `75783e981cc1e3a9516e97134f1220594d4cb6ed`. Kelompok tes antar-PR saling tumpang tindih. Suite penuh gabungan ronde 2 belum dijalankan.

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

**SELESAI** — bukti WS-4 butir 8–10 terpetakan dan tes gabungan terpilih diulang pada commit lab.

**TERSISA** — WS-2, pengujian gabungan setelah WS-2 tersedia, dan penutupan ronde sebelum Fase 3.

**PENGHAMBAT** — perlu rujukan penugasan WS-2 dengan rel yang dicakup dan kriteria bukti terverifikasi per rel.
