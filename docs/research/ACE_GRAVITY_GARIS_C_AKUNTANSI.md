# Akuntansi Garis C · Memori & Lapis 3

Serahan Garis C disusun oleh Antigravity di atas `origin/main` (`478848d`) sebagai PR draf terpisah per butir, seluruhnya berstatus **strictly read-only** terhadap memory store maupun engine hidup (jalur sambungan ke engine tetap di meja Ian). Akuntansi garis sebelumnya tersedia di [PR #345](https://github.com/dianzherdiana25-hash/ACE/pull/345) (Garis B).

| Butir | Status | PR & Commit | Modul & Ringkasan |
| --- | --- | --- | --- |
| C1 · Model-diri naratif | Selesai | [PR #346](https://github.com/dianzherdiana25-hash/ACE/pull/346) (`gravity/c1-narrative-self-model`, `56820e8`) | `tools/narrative_self_model.py`: membaca ledger, snapshot memori baca-saja (`memory.jsonl`, `ace_seed_snapshot.json`), dan papan gerbang/status → narasi `identity`/`proven`/`unproven`. Gerbang provenans keras menolak klaim tanpa sumber dan memisahkan tebakan `model`. 5 tes lulus. |
| C2 · Probe kontinuitas | Selesai | [PR #347](https://github.com/dianzherdiana25-hash/ACE/pull/347) (`gravity/c2-continuity-probe`, `d1c79aa`, base `gravity/c1-narrative-self-model`) | `tools/self_model_continuity_probe.py`: menjalankan generator C1 di atas sumber identik lintas 3 konfigurasi label organ & variasi gaya teks, membandingkan fakta terekstrak (bukan redaksi), serta mendeteksi mutasi nilai/hilang/tambahan, klaim tanpa sumber, dan kebocoran token organ. 5 tes C2 (+ 5 tes C1 = 10) lulus; probe nyata `CONTINUITY_INTACT` atas 20 fakta. |
| C3 · Konsolidasi memori metakognitif | Selesai | [PR #348](https://github.com/dianzherdiana25-hash/ACE/pull/348) (`gravity/c3-metacog-consolidation`, `6e9c13e`) | `tools/metacog_memory_consolidate.py`: mengelompokkan kegagalan/keberhasilan berulang dari `memory.jsonl` (`0444/0555` verified), log episode JSONL, dan `checkpoints/self_dev/metacognitive_memory.json` tanpa menulis ke store; melaporkan peringatan negative transfer, MAE kalibrasi, overconfident failures, temuan HIGH terbuka, dan utang `superseded`. 2 tes lulus. |
| C4 · CLI recall & introspeksi | Selesai | [PR #349](https://github.com/dianzherdiana25-hash/ACE/pull/349) (`gravity/c4-introspect-recall`, `ee5e1cb`) | `tools/introspect_recall.py`: tanya-jawab CLI di atas snapshot memori dan `handover/` + ledger; memprioritaskan `evidence`/`operator` di atas tebakan `model`, menandai `GUESS_ONLY_UNVERIFIED`, menyertakan SHA-256 setiap sitasi, dan abstain jujur (`NO_VERIFIED_EVIDENCE`) bila bukti tidak memadai. 3 tes lulus. |
| C5 · Laporan-diri berkala | Selesai | [PR #350](https://github.com/dianzherdiana25-hash/ACE/pull/350) (`gravity/c5-periodic-self-report`, `60ef41c`) | `tools/periodic_self_report.py`: menghasilkan laporan berkala pemilik berisi papan gerbang (`G1`–`G5`, `round2-gate-01`), vonis terbaru, antrean aktif (`SOURCE_NOT_PRESENT` bila berkas belum ada), dan utang bukti bernama, kompatibel dengan JSON C1. 3 tes lulus. |
| C6 · Agenda dari kegagalan | Selesai | [PR #351](https://github.com/dianzherdiana25-hash/ACE/pull/351) (`gravity/c6-failure-to-agenda`, `7bdff82`) | `tools/failure_to_agenda.py`: memindai dokumen vonis/ledger dan keluaran konsolidasi C3 / `memory.jsonl` menjadi kandidat agenda berformat register (`brain_of_origin: gravity-proposal`, `decision_owner: Ian`, `decision_status: PROPOSED_AWAITING_IAN`) berdeduplikasi kanonik. 3 tes lulus. |

## Hasil Suite Gabungan & End-to-End Garis C

Pada overlay sementara seluruh modul C1–C6 di atas `main` (`478848d`):

- **Suite gabungan C1–C6 + memori eksisting** (`tools.test_narrative_self_model`, `tools.test_self_model_continuity_probe`, `tools.test_metacog_memory_consolidate`, `tools.test_introspect_recall`, `tools.test_periodic_self_report`, `tools.test_failure_to_agenda`, `ace_operational.test_cognitive_memory`, `ace_operational.test_memory_writeback`, `ace_selfmodel.test_selfmodel`): **Ran 49 tests in 3.278s — OK** (21 tes baru C1–C6 + 28 tes regresi `cognitive_memory`/`memory_writeback`/`selfmodel`).
- **Uji alir end-to-end lintas modul (overlay)**:
  - `narrative_self_model.py` → `periodic_self_report.py --narrative-json`: `8` gerbang, `5` utang bukti bernama.
  - `metacog_memory_consolidate.py` → `failure_to_agenda.py --consolidation`: `16` kandidat agenda dengan `brain_of_origin = gravity-proposal`.
- **`python3 tools/verify_sources.py`**: `PASS: 25 imported files match their recorded Git blob IDs (offline)`.

## Batas yang Dijaga
- Tidak satu pun modul C1–C6 memanggil konstruktor tulis `CognitiveMemory(...)` atau menyentuh `tools/memory_writeback.py`, `code/ace_operational/memory_writeback.py`, instrumen EVO 0007, korpus beku, ataupun direktori stage Ian.
- C2 disusun di atas C1 (`--base gravity/c1-narrative-self-model`) agar menguji generator C1 nyata tanpa duplikasi kode.

## Usulan Tranche 2 untuk Garis C (bernomor)

1. **C-T1 · Probe kontinuitas lintas-bahasa + snapshot historis ter-tombstone**: perluas C2 untuk memverifikasi bahwa tombstoned records (`tombstones`) menghasilkan `deleted_fact` deterministik tanpa memunculkan isi konten yang sudah dihapus.
2. **C-T2 · Audit rantai lintas sesi pada konsolidasi metakognitif**: tambahkan deteksi konflik semantic antar beberapa berkas snapshot `memory.jsonl` (misalnya workspace utama vs arsip portabel) pada `metacog_memory_consolidate.py`.
3. **C-T3 · Bench regresi tanya-jawab introspeksi beranotasi (`introspect_recall.py`)**: siapkan himpunan 30 pasangan pertanyaan–pointer wajib (termasuk pertanyaan jebakan tanpa jawaban sah untuk menguji tingkat abstention 100%).
4. **C-T4 · Integrasi sambungan non-instrumen antara C1/C5/C6 dan dashboard/register pembacaan (Garis F)**: setelah PR Garis A/C diratifikasi Ian, sambungkan keluaran `periodic_self_report` dan `failure_to_agenda` ke permukaan bacaan pemilik serta siklus pra-review Ian.

**SELESAI** — Garis C (C1–C6, PR #346–#351) dan dokumen akuntansi Garis C selesai; suite gabungan 49 tes lulus penuh.  
**TERSISA** — penyaringan PR oleh Ian; kelanjutan langsung antrean ke **Garis A Tranche 2 (5 butir diratifikasi Ian)**.  
**PENGHAMBAT** — nihil.
