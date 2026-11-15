# Misi 9 — Inventarisasi 08bd836..7541782 (draf kerja, 2026-11-15)

## HEAD terverifikasi
- ls-remote + fetch: origin/main = 754178246ad0852f58a41125ad6762e3e96b61c4
  ("feat(mission-0001b)..."; parent 055dd64). Sama dengan cek terakhir hub.
- Rentang 08bd836..7541782: 788 file ADDED, 17 MODIFIED, 0 deleted.
  Bukan hanya lini mission-0001/OAIE: merge #200-#208 ikut masuk
  (Batch 2/3/4, proposer v2, Stage 2 staging, bakeoff02 Manus,
  lineage-guard confirm, R5, suplemen baterai).

## File MODIFIED (17) — yang menyentuh jalur sealed-run
- code/ace_operational/operator_discovery.py (+561/-63): ekspansi Stage L2
  (4 skema baru: bool_constant, name_swap, unary_not, subscript_index;
  pair discovery; FamilyAdapter decoupling) + wiring guard (9b88475,
  guard=False default, docstring: bit-for-bit identical bila OFF).
- code/ace_operational/curriculum_lab.py: _pricing_family ranges widened
  (B-3 freeze 2026-11-13, coordinator-ratified; 36 -> 480 kombinasi).
  HANYA family pricing; grid tidak berubah.
- Lainnya (language, store, autonomous_engine, self_evolution_engine,
  story_projector, pilot_abc, web_server, component_synthesizer,
  visual_bridge/cli+contract, .gitignore, checkpoints state): TIDAK ada
  import dari jalur solver (abc_v3_run/grid_adapter/grid_generalization/
  operator_discovery/grid_substrate). Terverifikasi via grep.

## Baseline yang dicek vs head PR masing-masing (git diff PR-head vs origin/main)
- PR #192 Stage 3 record+state+runner+harness_ext: BYTE-IDENTICAL.
  (Satu-satunya diff: ctrlreg_stage3_intervention_harness.py +545 —
  file itu tidak ada di head PR #192; masuk lewat konsolidasi Batch 3
  dari cabang PR #184. Bukan perubahan isi.)
  Record: P1_REPRODUCED, P2/P3 long-form; digest 20261601 e5c7875d...,
  20261602 561d272b..., 20261603 465508ef...; infected 32/33/33. COCOK.
- PR #193 harness+gate+tests lineage-guard: BYTE-IDENTICAL di main.
- PR #189 preaudit_validator.py: BYTE-IDENTICAL di main.
- PR #196 R5 evidence + manifest + requirements: BYTE-IDENTICAL di main.
- PR #195 supplement manifest: BYTE-IDENTICAL di main.
- G5 (Misi 8): draft d3f2bb25... EXACT, instrumen 82eba4d1... EXACT di tip.
- discovery_20261501.json di main: sha 9d398f63... = file custody. EXACT.
- tools/abc_v3_run.py di main: sha e426249a... = entri manifest custody. EXACT.
- evidence/ctrlreg_stage3_official_harness_ext.py: sha 99831ca5... = manifest. EXACT.

## Confirmation run 20261701-03 (commit 5f2daf0, 16:26 WIB 14 Nov)
- Verdict doc: GUARD_ADOPTED; act operator "Antigravity autonomous
  execution (Manus Sandbox 2887726280f4 under owner mandate 2026-11-14)";
  window "clean-RAM R3 custody window post Bake-off 02 (zero model
  processes resident)", 21.609 MiB bebas.
- Verifikasi internal (tangan Ian, dari main):
  * 3 digest band dihitung ulang dari discovery_*.json -> MATCH semua
    (50050728... / 465508ef... / 8113acba...).
    20261702 == 20261603 digest karena admission identik (6 keys, 0 chain)
    — digest murni fungsi (keys, chains); bukan anomali.
  * 12 cell files: solved counts + total 34 + wall cocok tabel vonis semua.
  * 4 witness stock-infected: 7 calls, never_generated — persis W.
  * Anchor round_log: witness 021 (20261701/02) guard_event round-1
    triggered=True, occupant BASE, displaced 6577e3ee... (hash gagal B);
    round-2 true_path generated+scored rank 1, frontier_out 6504b23b...
    (hash menang A). L5 violations [] di worksheet; death_rounds stock
    {2:4}, guarded {None:102}; cost ratio median 1.0.
  * Admitted keys ketiga band: 6 keys skema LAMA semua (binop_swap,
    binop_unwrap, int_constant x2, return_indices, string_literal);
    tanpa kunci skema-baru L2.
  * CATATAN: act file TIDAK menyebut penutupan butir clean-logout
    (gerbang keras langkah 3 urutan aktivasi). Statusnya TIDAK
    TERVERIFIKASI dari record — butuh konfirmasi sisi operator/hub.
  * Gates di run record hanya string "PASS" (L4/L1_L2/step4) tanpa
    detail JSON; bukti rinci pra-run tidak ada di paket ini.

## Proposer (papan gerbang)
- Stage 1 v2: prereg 52e5fe9 terkunci 13:36 WIB -> generasi freeze
  14:07 WIB -> verdict 14:08 WIB (urutan prosedural BENAR; amendemen
  v2.1 13:45 sebelum outcomes dibaca). Vonis PARTIAL (Quality PASS:
  mean_diff +7.50, CI lower +0.83; 6/6 grammar_only, 0 repair).
  Model BARU Qwen3.5-4B-Q4_K_M, -t 4, json_schema. v1 NOT_PASSED
  dipertahankan tanpa modifikasi.
  NUANCE "exactly one" (PR #199 §3): prereg v2 mengunci KEDUA
  pertanyaan desain (grammar-constrained DAN 1-shot repair); vonis
  bersandar pada arm grammar_only (0 repair terpanggil) — substansi
  satu pertanyaan, huruf prereg dua pertanyaan. Butuh penilaian hub.
- Stage 2: constitution verdict 7/7 battery PASS offline (staging-only,
  tanpa dispatch live). Mengklaim pembukaan staging terisolasi di bawah
  addendum §5 PETA_ARAH. Bukan vonis Stage 2 penuh.
- Bake-off 02 Manus (f209726, 14:36 WIB): evaluasi Sandbox -t 4, BUKAN
  penutupan resmi VM-path (prereg §3 mengecualikan angka Sandbox dari
  kernel). Qwen3-4B-Instruct-2507 tercepat (tg 7.67) + A/B 4/4;
  Llama-8B gagal B (2.0/4.0); Qwen3.5-4B gagal B vanilla (0.0/4.0).
  Instrumen C BLOCKED_MISSING_SEALED_EVALUATOR. Suksesi resmi tetap
  butuh Instrumen C tersegel. B/C VM-path tetap tertunda per perintah
  pemilik. Bake-off 02 tetap TERBUKA.

## Re-gate di worktree segar (berjalan, /tmp/m9gate)
- Import assert: control=34 keys=60 chains=1 digest OK, 'nc' posisi 31
  (digest katalog dev a6768563... reproduksi di bawah kode main baru).
- Gate 4/4: identical=True anchor=True semua (020 A/B, 021 A/B).
  -> Gate verdict menunggu gate.json (checkpoint tertulis).
- Sel uncapped (control/rounds_only/frontier_only) berjalan; hasil
  410/159 menyusul.
