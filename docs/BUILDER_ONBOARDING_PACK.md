# Paket Onboarding Kontributor Builder ACE — ACE

> Dibangun deterministik oleh `tools/builder_onboarding_pack.py` (`ace.builder-onboarding-pack.v1`). Seluruh status berkas, checksum, dan batas wilayah terlarang dipindai langsung dari disk.

## 1. Aturan Jalur & Kontrak Kerja (Tidak Dapat Ditawar)

- **Namespace Branch:** wajib `gravity/<slug>`, bercabang bersih dari `origin/main`.
- **Kebijakan PR:** `1 PR = 1 serahan + unit tes`, selalu dibuka sebagai **Draft PR** ke `main`, tidak pernah merge.
- **Jaringan & Bytecode:** selalu ekspor `PYTHONDONTWRITEBYTECODE=1`, `0` panggilan HTTP live di perkakas/tes.
- **Verifikasi Overlay Gabungan:** gunakan worktree terpisah `git worktree add --detach /tmp/<combo> origin/main (Cwd=/tmp/<combo>, segera hapus sesudah uji)` agar `PYTHONPATH` terisolasi dari working directory utama.
- **Standar Fuzz Parser:** `python3 tools/fuzz_parsers.py --seeds 20261117,20261118,20261119 --iterations 300` (`0` crash tak tertangani).
- **Verifikasi Sumber Impor:** `python3 tools/verify_sources.py` — status saat ini **PASS** (25/25 blob cocok).

## 2. Daftar Dokumen Kontrak Inti

| Berkas | Status | Baris | SHA-256 | Peran |
| --- | --- | ---: | --- | --- |
| `handover/GOVERNANCE_RULES_20261115.md` | `PRESENT` | 55 | `6ba6d9b54568` | Dua aturan tetap: hidup+tes hijau, & ratifikasi independen |
| `tools/FUZZ_STANDARD.md` | `PRESENT` | 47 | `89c9c1ccdb92` | Standar matriks fuzz 3 seed x 300 iterasi (0 crash tak tertangani) |
| `tools/verify_sources.py` | `PRESENT` | 48 | `dacdda4d6992` | Verifikator luring SHA-1 blob berkas impor hulu |
| `docs/UPSTREAM_SOURCES.json` | `PRESENT` | 106 | `cf6ffc77386a` | Manifes 25 berkas impor terpin blob Git |
| `STATUS.md` | `PRESENT` | 101 | `7a88f0703c5e` | Papan status & aturan konsolidasi |
| `PROJECT.md` | `PRESENT` | 81 | `e7a6b1e072e3` | Ringkasan arsitektur & cakupan repositori ACE |

## 3. Wilayah Terlarang (Hanya Engineer Utama — Jangan Disentuh)

- Jalur eksak dipantau (`13` berkas) + `4` modul produksi `code/ace_evaluator/` + `3` corpus beku `handover/*.jsonl` + jalur direktori staging aktif EVO 0007.

| Berkas / Wilayah | Keadaan di Disk Saat Ini |
| --- | --- |
| `code/ace_operational/abc_v3_scorer.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/cognitive_memory.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/evo0007_run.py` | `NOT_ON_MAIN_PROTECTED_RESERVED` |
| `code/ace_operational/g1_instrument.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/g3_instrument.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/g4_instrument.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/g5_instrument.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/memory_bridge.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/memory_writeback.py` | `PRESENT_ON_DISK` |
| `code/ace_operational/round2_instrument.py` | `PRESENT_ON_DISK` |
| `tools/abc_v3_run.py` | `PRESENT_ON_DISK` |
| `tools/memory_writeback.py` | `PRESENT_ON_DISK` |
| `tools/round2_gate_run.py` | `PRESENT_ON_DISK` |

### Modul `code/ace_evaluator/` Terlindung

- `code/ace_evaluator/__init__.py`
- `code/ace_evaluator/cheat_detection.py`
- `code/ace_evaluator/sealed_generator.py`
- `code/ace_evaluator/task_families.py`

### Corpus Beku `handover/*.jsonl` (Read-Only)

- `handover/EVO_0003_CORPUS_TAIL_V1.jsonl`
- `handover/EVO_0005_CORPUS_V1.jsonl`
- `handover/EVO_0006_CORPUS_CANDIDATES_V1.jsonl`

## 4. Resep Verifikasi Sebelum Buka Draft PR

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest <modul_uji_terkait> -v
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_sources.py
git status --short  # pastikan tidak ada perubahan di wilayah terlarang / sisa tmp
```
