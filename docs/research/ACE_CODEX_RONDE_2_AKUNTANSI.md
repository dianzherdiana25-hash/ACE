# Akuntansi pembangunan ronde 2

Serahan pembangunan ronde 2 tersedia sebagai PR draf. Penyaringan mengikuti jalur review per PR. Dasar pemeriksaan repo adalah [main pada 478848d](https://github.com/dianzherdiana25-hash/ACE/tree/478848d1221bba8988980b8aba655e772ad4d243).

| Butir | Bukti implementasi dan tes | Hasil pada revisi tersebut |
| --- | --- | --- |
| WS-4 8 · pelengkapan distiler pola (`--max-chars`) | [PR #328](https://github.com/dianzherdiana25-hash/ACE/pull/328) · [tes distiler](https://github.com/dianzherdiana25-hash/ACE/blob/2cda38757103b553e1f34fa1838409f3bea2e1c0/tools/test_pattern_distill.py) | `tools/pattern_distill.py` sudah ada di `main` sebelum ronde 2 (commit `ca91d9f`, PR #276); PR #328 melengkapinya dengan batas panjang `--max-chars` (default 2048), validasi ketat `ratified is True`, fallback `validator.parsed.reasons`, dan 6 tes fixture tambahan (bukan membangun dari nol). Badan PR mencatat 42 tes terpilih lulus. |
| WS-4 9 · pengusul kurikulum | [PR #329](https://github.com/dianzherdiana25-hash/ACE/pull/329) · [tes pengusul](https://github.com/dianzherdiana25-hash/ACE/blob/68c105687d08a0d604154d2abc779bc47526bdeb/tools/test_curriculum_propose.py) | Badan PR mencatat 14 tes terpilih lulus dan 7 tes baru lulus saat diulang dengan distiler #328. |
| WS-4 10 · lab historis | [PR #330](https://github.com/dianzherdiana25-hash/ACE/pull/330) · [tes lab](https://github.com/dianzherdiana25-hash/ACE/blob/75783e981cc1e3a9516e97134f1220594d4cb6ed/tools/test_curriculum_lab.py) | Pengulangan pada commit lab menghasilkan 24 tes lulus. |
| WS-2 · verifikator dan laporan | [Spesifikasi #332](https://github.com/dianzherdiana25-hash/ACE/pull/332) · [PR #333](https://github.com/dianzherdiana25-hash/ACE/pull/333) · [tes verifikator](https://github.com/dianzherdiana25-hash/ACE/blob/94273ed0b8d16e775750a1f43283a693fd547c79/tools/test_revenue_verify.py) | 21 tes lulus dan uji kedua CLI pada fixture Fastwork lulus. |

## Daftar lengkap ronde 1 (WS-1 s.d. WS-9 + parser validator)

Tabel berikut mencatat seluruh workstream ronde 1 dan pekerjaan parser validator fleksibel EVO 0007 apa adanya sesuai PR draf yang dibuka.

| Workstream | PR & commit | Ringkasan serahan & hasil tes |
| --- | --- | --- |
| WS-1 · antrean lokal KBM | [PR #326](https://github.com/dianzherdiana25-hash/ACE/pull/326) (`codex/ws1-kbm-local-queue`, `7136ef8`, di atas #322) | Memecah naskah, mengecek bab + sampul ketat WS-3, dan mengantrekan paket ke SQLite lokal (`tools/kbm_production_queue.py`, `tools/kbm_pipeline.py`). Badan PR mencatat 23 tes lokal lulus dan 132 tes suite pilihan gabungan 7 workstream lulus. |
| WS-2 · verifikasi pendapatan | Ditunda di ronde 1 → spesifikasi [PR #332](https://github.com/dianzherdiana25-hash/ACE/pull/332), implementasi [PR #333](https://github.com/dianzherdiana25-hash/ACE/pull/333) (`codex/ws2-revenue-verification`, `94273ed`) | Pada ronde 1 belum selesai karena menunggu spesifikasi rel & kriteria bukti per rel (`handover/SPESIFIKASI_WS2_REL_DAN_BUKTI.md`); diselesaikan penuh di ronde 2 (`tools/revenue_verify.py`, `tools/revenue_report.py`; 21 tes lulus). |
| WS-3 · wiring dimensi sampul | [PR #322](https://github.com/dianzherdiana25-hash/ACE/pull/322) (`codex/ws3-cover-wiring`, `f441476`) | Menambah `--strict-cover` pada `tools/kbm_pack_check.py` dan inventaris seam (`docs/research/ACE_WS3_WIRING_INVENTORY.md`). Badan PR mencatat 11 tes lulus. |
| WS-4 · distilasi & kurikulum | Ditunda di ronde 1 → diselesaikan di ronde 2 pada [PR #328](https://github.com/dianzherdiana25-hash/ACE/pull/328), [PR #329](https://github.com/dianzherdiana25-hash/ACE/pull/329), [PR #330](https://github.com/dianzherdiana25-hash/ACE/pull/330) | Dipindahkan ke ronde 2: pelengkapan `--max-chars` pada `tools/pattern_distill.py` yang sudah ada di `main` (#328), `tools/curriculum_propose.py` (#329), dan `tools/curriculum_lab.py` (#330). |
| WS-5 · batch kandidat corpus | [PR #320](https://github.com/dianzherdiana25-hash/ACE/pull/320) (`codex/ws5-candidate-corpus`, `d55d208`) | Generator + validator batch kandidat kode dan bahasa (`tools/candidate_corpus_batch.py`, `evidence/candidate_corpus_batch/quality.json`; 224 episode, 96 sampel bahasa). Badan PR mencatat 31 tes lokal lulus. |
| WS-6 · audit ketahanan slate | [PR #324](https://github.com/dianzherdiana25-hash/ACE/pull/324) (`codex/ws6-slate-audit`, `4c57a5b`) | Audit baca-saja dependensi slate lokal dan bridge draf #319 (`docs/research/ACE_WS6_SLATE_RESILIENCE.md`). Badan PR mencatat 16 tes lokal routing/parsing/registry/wake tiruan lulus. |
| WS-7 · latihan migrasi bundle | [PR #325](https://github.com/dianzherdiana25-hash/ACE/pull/325) (`codex/ws7-migration-rehearsal`, `2bee3dd`) | Pemeriksa bundle terpin + uji restore sementara terisolasi (`tools/migration_rehearsal.py`). Badan PR mencatat 8 tes lokal lulus. |
| WS-8 · preflight PR draf | [PR #323](https://github.com/dianzherdiana25-hash/ACE/pull/323) (`codex/ws8-draft-preflight`, `bece9c2`) | Pembentuk & validator envelope PR draf lokal dari dua commit pin (`tools/draft_release_preflight.py`). Badan PR mencatat 5 tes lokal lulus. |
| WS-9 · gelombang tepi loop & agenda | [PR #321](https://github.com/dianzherdiana25-hash/ACE/pull/321) (`codex/ws9-loop-edge-tests`, `03212dd`) | Mengembalikan `SEARCH_SPACE_EXHAUSTED` untuk agenda kosong (`code/ace_self_dev/agenda_engine.py`) + 12 tes tepi (`code/ace_operational/test_loop_boundary_wave.py`). Badan PR mencatat 46 tes gabungan lulus. |
| EVO 0007 · parser validator fleksibel | [PR #327](https://github.com/dianzherdiana25-hash/ACE/pull/327) (`codex/evo0007-flexible-validator`, `ec92a9f`, basis `feat/ace-evo0007-runner-20261118`) | Menambahkan `parse_validator_output()` di `code/ace_operational/evo0007_run.py` + 12 tes baru (`code/ace_operational/test_evo0007_run.py`). Badan PR mencatat 33 tes `ace_operational.test_evo0007_run` lulus. |

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
