# Garis D1 — Pengerasan Fuzz Parser & Pembaca Berkas Non-Verdict (`gravity/d1-fuzz-hardening`)

Dokumen ini mencatat perluasan harness fuzz [`tools/fuzz_parsers.py`](file:///home/antigravity/dianzherdiana25-hash/ACE/tools/fuzz_parsers.py), matriks pengujian `3 seed × 300 iterasi` (`20261117`, `20261118`, `20261119`), serta 10 perbaikan crash nyata yang ditemukan selama audit Garis D1.

## Cakupan Target (33 Target — 900 Eksekusi per Target)

1. **Target inti `tools/` (3 target):** `ace_mobile_dashboard.parse_logs_to_stories`, `ace_ai_diagnostic.audit_consultations`, `dashboard_state_build.rp_to_int`.
2. **Target `code/` non-verdict aman (6 target):**
   - `code.ace_visual_bridge.cli.process`
   - `code.ace_host_exchange.contracts.verify`
   - `code.ace_autonomy.policy.BudgetCeiling`
   - `code.ace_code_agent.read_failure_history`
   - `code.ace_code_agent.verify_receipt`
   - `code.ace_indo_nlp.syllabify_and_morphology`
3. **Target `tools/` opsional (24 target):**
   - `corpus_lint.lint_file`, `screen_census.compute_census`, `corpus_registry`, `stage_verify.verify_stage`, `bench_table.summarize_bench`, `pack_evidence.verify_evidence`
   - `pattern_distill.distill_evidence`, `four_arm_report.analyze_four_arms`, `corpus_tag.tag_corpus`
   - `cover_check.check_cover`, `royalty_track.summarize_royalties`, `kbm_schedule.build_schedule`
   - `kbm_split.split_manuscript`, `kbm_pack_check.check_package`, `kbm_pipeline.run_pipeline`
   - `curriculum_gen.generate_curricula`, `portability_pack.verify_bundle`, `instance_kit.validate_isolation`
   - `ruleset_readiness.check_repo_readiness`, `opportunity_register.generate_proposals`, `repo_status_dashboard.collect_and_render`
   - `self_send_audit_view.inspect_audit_files`, `repo_index.build_and_render`, `daily_digest.build_daily_digest`

**Status wilayah terlarang:** Tidak ada instrumen verdict (`evo0007_run.py`, judge/scorer, runner preregistrasi) maupun jalur tulis memory store (`memory_writeback.py`, jalur tulis `cognitive_memory.py`) yang disentuh atau dijadikan target fuzz.

## 10 Bug Crash Nyata & Perbaikannya

1. **`tools/pattern_distill.py`**: `_as_optional_float` gagal dengan `OverflowError` pada integer raksasa (`10**400`), dan `distill_evidence(append=True)` gagal `AttributeError` bila `provenance` berjenis non-dict. Diperbaiki dengan menangkap `OverflowError` dan menjaga tipe `dict`.
2. **`tools/four_arm_report.py`**: `_load_rows` memeriksa `any(k in parsed_single ...)` lalu memanggil `next(...)` yang memicu `StopIteration` saat kunci bernilai non-list (`{"episodes": "bad"}`). Diperbaiki dengan memeriksa `isinstance(parsed_single.get(k), list)`.
3. **`tools/curriculum_gen.py`**: `_load_staging_coverage` gagal `TypeError` atau memecah karakter string ketika `task_shape.keywords` bukan list. Diperbaiki dengan guard `isinstance(raw_kws, list)`.
4. **`tools/repo_index.py`**: `_parse_python_module` fallback untuk berkas Python rusak (`SyntaxError`/`UnicodeDecodeError`) tidak menyertakan `"from_imports": []`, memicu `KeyError: 'from_imports'` di `build_repo_index`.
5. **`tools/portability_pack.py`**: Arsip `.tar.gz` terpotong/korup memicu `EOFError`/`zlib.error` tak tertangani; nilai `path=None` ikut ter-stringifikasi `"None"`; nilai `bool` diterima sebagai `int` bytes. Diperbaiki menjadi `PortabilityPackError` dan pelanggaran manifest eksplisit.
6. **`tools/instance_kit.py`**: NUL byte (`\x00`) pada `allowed_root` atau direktori memicu `ValueError: embedded null byte` mentah di `os.path.abspath`/path check. Kini dilaporkan sebagai pelanggaran terstruktur `invalid_path_nul_byte`.
7. **`tools/ruleset_readiness.py`**: Nilai non-numerik/overflow pada `required_approving_review_count` memicu `ValueError`/`TypeError`/`OverflowError` di `int(...)`. Diperbaiki via helper `_safe_nonneg_int`.
8. **`tools/repo_status_dashboard.py`**: Bagian renderer kartu/tabel panel memanggil `int(...)` mentah tanpa pengaman atas JSON panel korup. Diperbaiki memakai `_safe_int` dan validasi tipe koleksi bersarang.
9. **`tools/kbm_pack_check.py`**: NUL byte pada `cover_name` membocorkan `ValueError` mentah, bukan `KbmPackCheckError`. Diperbaiki lewat validasi eksplisit di awal `check_package`.
10. **`tools/opportunity_register.py`**: Nilai `origin_attribution` tak ter-hash (list/dict) pada proposal memicu `TypeError: unhashable type` saat `attr in proposal_by_origin`. Diperbaiki dengan memeriksa `isinstance(attr, str)`.
