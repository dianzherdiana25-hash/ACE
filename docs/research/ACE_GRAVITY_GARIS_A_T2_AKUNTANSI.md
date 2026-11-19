# Akuntansi Garis A · Tranche 2 (Lanjutan Ian dari PR #339)

Seluruh serahan berupa **draft PR** bertumpuk langsung pada branch Garis A terkait (`codex/line-a1-pattern-catalog` s.d. `codex/line-a5-self-dev`) di atas basis `origin/main` (`478848d`), tanpa menyentuh instrumen ukur, jalur tulis memory store, atau direktori stage EVO 0007.

| Butir | PR Draf | Branch | Basis | Ringkasan serahan & bukti |
| --- | --- | --- | --- | --- |
| A-T2-1 | [#353](https://github.com/dianzherdiana25-hash/ACE/pull/353) | `gravity/a1-t2-catalog-compat` | `codex/line-a1-pattern-catalog` | Kompatibilitas lintas versi `v1 <-> v2` pada `tools/pattern_catalog.py`, normalisasi ekspor `ace.pattern-distilled.v1` untuk pengusul kurikulum (`curriculum_propose.py`), `trace_conflict_changes` + subperintah `trace-conflicts` (16 tes OK). |
| A-T2-2 | [#354](https://github.com/dianzherdiana25-hash/ACE/pull/354) | `gravity/a2-t2-agenda-closure` | `codex/line-a2-agenda` | `build_closure_report` (`ace.agenda-closure.v1`) & CLI `closure` pada `tools/agenda_candidates.py` untuk pembuktian status penutupan berbasis ID kandidat + `decision_pointer` terverifikasi SHA-256/baris serta penolakan fail-closed atas pointer rusak/konflik/orphan (14 tes OK). |
| A-T2-3 | [#355](https://github.com/dianzherdiana25-hash/ACE/pull/355) | `gravity/a3-t2-director-historical` | `codex/line-a3-director` | Audit lima dokumen validasi/handover historis nyata: perbaikan tautan Markdown relatif (`../`) dan pemisahan konstanta/SHA pada `tools/director_asset_check.py`, pemindai bentuk prosa disetujui (`tools/director_prose_audit.py`), serta fixture per bentuk & batas negatif `unrecognized_prose` (25 tes OK). |
| A-T2-4 | [#356](https://github.com/dianzherdiana25-hash/ACE/pull/356) | `gravity/a4-t2-bundle-metric-scope` | `codex/line-a4-experiment-support` | Matriks audit bundel lintas paket terpin (`audit_bundle_matrix` / `audit-matrix` pada `tools/seal_run.py`) melawan 4 mode salinan rusak, ditambah `scope_notes` per pasangan paket + pengaman fail-closed `unit_mismatch` / `population_or_scope_mismatch` (`compare_package_matrix` / `compare-matrix` pada `tools/evo_results.py`) (21 tes OK). |
| A-T2-5 | [#357](https://github.com/dianzherdiana25-hash/ACE/pull/357) | `gravity/a5-t2-git-history-audit` | `codex/line-a5-self-dev` | `pre_review_report` (`ace.self-dev-branch-prereview.v1`) dan subperintah `prereview` pada `tools/self_dev_git_audit.py` dari daftar commit terpin operator, deteksi ekuivalensi `git patch-id --stable` atas cherry-pick, pelacakan multi-induk merge commit, dan diff checkpoint terlampir (15 tes OK). |

## Uji gabungan lintas Garis A Tranche 2 + pengusul kurikulum (`ws4-curriculum-propose`)

Seluruh branch A-T2-1 s.d. A-T2-5 dan `origin/codex/ws4-curriculum-propose` di-overlay bersama `origin/main` di direktori uji terisolasi (`/tmp/a_t2_combo`, dibersihkan setelah eksekusi) dan dijalankan dalam satu proses `unittest`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -c '
import sys, unittest
sys.path[:0] = ["/tmp/a_t2_combo", "/tmp/a_t2_combo/code"]
mods = [
    "tools.test_pattern_catalog",
    "tools.test_pattern_catalog_compat",
    "tools.test_pattern_distill",
    "tools.test_curriculum_propose",
    "tools.test_agenda_candidates",
    "tools.test_agenda_closure",
    "tools.test_opportunity_register",
    "tools.test_director_audit",
    "tools.test_director_historical_shapes",
    "tools.test_evo_experiment_support",
    "tools.test_evo_tranche2_audit",
    "tools.test_pack_evidence",
    "tools.test_evo_scaffold",
    "tools.test_self_dev_git_audit",
    "tools.test_self_dev_prereview",
    "ace_operational.test_director_loop",
]
res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(mods))
sys.exit(0 if res.wasSuccessful() else 1)
'
python3 tools/verify_sources.py
```

- **Suite gabungan**: **Ran 98 tests in 4.154s — OK** (termasuk verifikasi langsung ekspor katalog `v1` dan `v2` terhadap `tools.curriculum_propose.propose_curriculum`).
- **Verifikasi sumber**: **PASS: 25 imported files match their recorded Git blob IDs (offline)**.

## Batasan yang dicatat

- Penetapan keputusan akhir agenda (Garis A2) dan ratifikasi praregistrasi (Garis A4) tetap menjadi kewenangan engineer utama (Ian) dan hub.
- Perluasan parser prosa historis (Garis A3) sengaja dibatasi pada 6 bentuk terstruktur yang disetujui; klaim bebas bernomor di luar bentuk tersebut dibiarkan berstatus `unrecognized_prose` agar tidak terjadi tebakan diam-diam.

## Usulan tranche berikutnya bernomor (Garis A Tranche 3)

1. **A-T3-1**: Sambungkan `export_snapshot_jsonl` (`pattern_catalog.py`) dan `propose_curriculum` (`curriculum_propose.py`) ke subperintah terpadu `curriculum-from-catalog` lengkap dengan manifest asal pola dan pelacakan konflik.
2. **A-T3-2**: Ekspor keluaran `build_closure_report` (`agenda_candidates.py`) ke ringkasan Markdown/HTML yang memuat tabel tautan `proof_sha256` + status penutupan untuk penyaringan cepat Ian.
3. **A-T3-3**: Tambahkan jembatan opsional `director_prose_audit.py` -> JSONL `numeric_claims` berbantu sumber agar klaim rasio historis yang terverifikasi bisa dipasangkan dengan JSON Pointer artefak bukti.
4. **A-T3-4**: Tambahkan pemeriksaan matriks tanda tangan/commit `prereview` otomatis atas seluruh PR tumpuk multi-branch (`--stack-manifest`) dalam satu panggilan laporan gabungan.

**SELESAI** — Seluruh 5 butir Garis A Tranche 2 (#353–#357) siap review, suite gabungan 98 tes lulus.

**TERSISA** — Antrean berikutnya pada Garis D s.d. I.

**PENGHAMBAT** — Nihil.
