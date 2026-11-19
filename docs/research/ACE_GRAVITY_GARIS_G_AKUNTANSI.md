# Akuntansi Penutup Garis G — Permukaan Pemilik & Operasi (Gravity)

> **Status:** Draft PR penutup Garis G (`G1–G4`). Seluruh pekerjaan berdiri di atas `origin/main` (`478848d`), pada branch `gravity/*`, tanpa menyentuh `evo0007_run.py`, instrumen judge/scorer, jalur tulis memory store, maupun direktori staging aktif EVO 0007.

## 1. Daftar Serahan & Status PR

| Butir | Branch | Commit | Draft PR | Ringkasan Serahan |
| --- | --- | --- | --- | --- |
| **G1** | `gravity/g1-status-dashboard-v3` | `7748962` | [#375](https://github.com/dianzherdiana25-hash/ACE/pull/375) | `tools/repo_status_dashboard_v3.py` (`ace.repo-status-dashboard.v3`) + `tools/test_repo_status_dashboard_v3.py`: generator 1 berkas HTML + vanilla JS luring interaktif (0 URL eksternal, 0 angka hardcoded, tab panel + filter pencarian, `SOURCE_NOT_PRESENT`, organ slate, XSS escaping). |
| **G2** | `gravity/g2-handover-index` | `c1b2c17` | [#376](https://github.com/dianzherdiana25-hash/ACE/pull/376) | `tools/handover_index.py` (`ace.handover-index.v1`) + `docs/HANDOVER_INDEX.md` + `tools/test_handover_index.py`: indeks deterministik `handover/` & `docs/` (`355 berkas`, skip symlink, verifier `--check` exit 0/1). |
| **G3** | `gravity/g3-repo-cartography` | `dc5c3f8` | [#377](https://github.com/dianzherdiana25-hash/ACE/pull/377) | `tools/repo_cartography.py` (`ace.repo-cartography.v1`) + `docs/REPO_CARTOGRAPHY.md` + `tools/test_repo_cartography.py`: pemindai AST statis murni 68 subsistem, diagram Mermaid `flowchart LR`, deteksi siklus SCC Tarjan, batas zona aman vs terlindung, & `--check`. |
| **G4** | `gravity/g4-run-evidence-packer-verify` | `4f2ff44` | [#378](https://github.com/dianzherdiana25-hash/ACE/pull/378) | `tools/run_evidence_pack.py` (`ace.run-evidence-pack.v1`) + `tools/test_run_evidence_pack.py`: perakit/verifikator bukti run/stage berparameter wajib `--run-dir` (fail-closed scan rahasia, `gzip mtime=0` tar.gz deterministik, verifikasi isi & penolakan tar traversal/symlink). |

## 2. Catatan Integrasi Penting (Pasca-Merge `G2` + `G3`)

Saat menguji overlay gabungan `G1..G4` di `/tmp/garis_g_combo`, ditemukan interaksi urutan pembangkitan dokumen antara `G2` dan `G3`:
- `docs/HANDOVER_INDEX.md` (G2) mencatat SHA-256 seluruh berkas di `docs/`, termasuk `docs/REPO_CARTOGRAPHY.md` (G3), sementara mengecualikan berkas indeks dirinya sendiri (`docs/HANDOVER_INDEX.md`).
- Karena itu, setelah `G2` dan `G3` sama-sama masuk `main`, jalankan refresh berurutan:
  1. `python3 tools/repo_cartography.py --output docs/REPO_CARTOGRAPHY.md`
  2. `python3 tools/handover_index.py --output docs/HANDOVER_INDEX.md`
- Sesudah urutan tersebut, kedua pemeriksa `--check` lulus persis serentak (`FRESH`).

## 3. Hasil Uji Gabungan Worktree Overlay (`/tmp/garis_g_combo`)

Worktree sementara `/tmp/garis_g_combo` dibuat dari `origin/main` dengan cherry-pick `--no-commit 7748962 c1b2c17 dc5c3f8 4f2ff44`, diuji penuh pada `Cwd="/tmp/garis_g_combo"`, lalu segera dihapus bersih (`git worktree list` bersih):

```text
python3 tools/repo_cartography.py --output docs/REPO_CARTOGRAPHY.md
python3 tools/handover_index.py --output docs/HANDOVER_INDEX.md
python3 tools/repo_cartography.py --check docs/REPO_CARTOGRAPHY.md
  -> FRESH: /tmp/garis_g_combo/docs/REPO_CARTOGRAPHY.md mutakhir dan cocok persis (23636 karakter).
python3 tools/handover_index.py --check docs/HANDOVER_INDEX.md
  -> FRESH: /tmp/garis_g_combo/docs/HANDOVER_INDEX.md mutakhir dan cocok persis (62343 karakter).

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/garis_g_combo/code:/tmp/garis_g_combo \
  python3 -m unittest \
  tools.test_repo_status_dashboard_v3 tools.test_handover_index \
  tools.test_repo_cartography tools.test_run_evidence_pack \
  tools.test_repo_status_dashboard tools.test_repo_index \
  tools.test_repo_index_doc tools.test_storage_debt \
  tools.test_stage_verify tools.test_pack_evidence --buffer
----------------------------------------------------------------------
Ran 35 tests in 6.535s

OK
```

- `PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_sources.py`: `PASS: 25 imported files match their recorded Git blob IDs (offline)`.
- Live smoke HTML G1 (`tools/repo_status_dashboard_v3.py`): `106.731 byte`, `http://: False`, `https://: False`, zero jaringan live.

## 4. Batas Wilayah Terlarang & Modul Menunggu Engineer Utama

- Tidak satu berkas pun pada `code/ace_operational/evo0007_run.py`, `code/ace_evaluator/*`, instrumen/scorer (`abc_v3_scorer.py`, `g*_instrument.py`, `round2_instrument.py`), jalur tulis `memory_writeback.py` / `cognitive_memory.py`, maupun direktori staging aktif EVO 0007 dibaca/ditulis/dieksekusi.
- Kartografi AST G3 mendokumentasikan 4 subsistem berstatus non-`SAFE_WORKSPACE` (`code/ace_evaluator` = `PROTECTED_INSTRUMENT`, `code/ace_operational` & `tools` = `MIXED_PROTECTED`, `handover` = `FROZEN_CORPUS_SPEC`) tanpa melakukan impor runtime.

## 5. Usulan Tranche Berikutnya (Bernomor)

1. **Garis H (`H1–H4` + Akuntansi):** Perkakas rel pendapatan offline sesuai spesifikasi WS-2 (`kbm_seabank`, `fastwork_bank`, `gopay_qris`), rekonsiler buku kas `projects/`, KBM tooling v2 (`Decimal` + pacing + cover check), dan ringkasan syarat platform dari dokumen repo — tetap 0 eksekusi pembayaran nyata.
2. **Garis I (`I1–I3` + Akuntansi Induk Final):** Ekstraktor keputusan handover ber-sitasi baris, glosarium program berbasis AST/heading, paket onboarding kontributor, serta akuntansi penutup lintas seluruh garis (`B..I` + `A-T2`) dengan daftar `SELESAI / TERSISA / PENGHAMBAT`.
3. **Penyegaran pasca-merge `G2+G3`:** Setelah `#376` dan `#377` diratifikasi ke `main`, jalankan `repo_cartography.py` lalu `handover_index.py` sekali di `main` agar `docs/REPO_CARTOGRAPHY.md` & `docs/HANDOVER_INDEX.md` sinkron di `HEAD`.
