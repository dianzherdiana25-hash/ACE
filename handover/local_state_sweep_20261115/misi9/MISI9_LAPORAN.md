# MISI 9 — Re-verifikasi papan gerbang & baseline sealed-run terhadap origin/main yang baru

Tanggal: 2026-11-15 ~06:07 WIB. Pelaksana: Ian (main chat), atas penugasan hub via ace-queue-watchdog.
Batas dipatuhi: tanpa merge; TANPA push apa pun; tanpa retry push G5; tanpa uang/publikasi;
urutan aktivasi lineage-guard tidak disentuh.

## 0. HEAD terverifikasi

- `git ls-remote` + `fetch`: origin/main = **754178246ad0852f58a41125ad6762e3e96b61c4**
  ("feat(mission-0001b)...", parent 055dd64). Sama dengan cek terakhir hub.
- Rentang 08bd836..7541782: **788 file ADDED, 17 MODIFIED, 0 deleted.**
  Bukan hanya lini mission-0001/OAIE: merge #200–#208 ikut masuk (Batch 2/3/4,
  proposer v2, Stage 2 staging, bakeoff02 Manus, lineage-guard confirm, R5,
  suplemen baterai). Worktree segar: `~/workspace/ace-omega/ACE/wt-m9main`.

## 1. Verdict per baseline

### 1.1 Stage 3 official record (PR #192) — MASIH BERLAKU
- Record + state + runner + harness_ext di main **byte-identical** vs head PR #192
  (0cfc1199). (Satu-satunya diff: `ctrlreg_stage3_intervention_harness.py` +545 —
  file itu tidak ada di head PR #192; masuk lewat konsolidasi Batch 3 dari cabang
  PR #184. Bukan perubahan isi.)
- Isi cocok dengan vonis beku: P1_REPRODUCED, P2/P3 long-form; digest 20261601
  e5c7875d…, 20261602 561d272b…, 20261603 465508ef…; infected 32/33/33.

### 1.2 R5 custody (PR #196) — MASIH BERLAKU
- Evidence R5 + manifest + requirements di main **byte-identical** vs head PR #196
  (945cd0c4). Manifest populasi 80 file / tree digest c02221775c… tetap acuan.
- `tools/abc_v3_run.py` di main sha e426249a… = entri manifest. `harness_ext.py`
  sha 99831ca5… = entri manifest. `discovery_20261501.json` sha 9d398f63… = file custody.

### 1.3 Harness + gate lineage-guard (PR #193) — MASIH BERLAKU
- `lineage_guard_harness.py` + `lineage_guard_gate.py` + tests di main
  **byte-identical** vs head PR #193 (73a902ec).

### 1.4 Rantai validator (PR #189) — MASIH BERLAKU
- `preaudit_validator.py` di main **byte-identical** vs head PR #189 (25bd8be3).

### 1.5 Suplemen baterai (PR #195) — MASIH BERLAKU
- Manifest suplemen di main **byte-identical** vs head PR #195 (cb3c597d).

### 1.6 G5 lock (Misi 8) — MASIH BERLAKU (konten)
- Draft praregistrasi d3f2bb25… EXACT, instrumen 82eba4d1… EXACT di tip 7541782.
  (Soal push yang ditolak pemilik tetap terpisah; misi ini tidak menyentuhnya.)

### 1.7 Katalog dev band 20261501 — MASIH BERLAKU (reproduksi di bawah kode baru)
- Re-gate di worktree segar (scratch /tmp/m9gate, kode main baru, data beku):
  import assert lolos — control=34, keys=60, chains=1, digest a6768563… OK,
  'nc' posisi 31.
- **Gate 4/4 PASS**: stock == param_nolog == param_log identik; anchor Stage-0
  exact (A-win 6504b23b… kedua task; B-fail dcfb155f… 410 calls,
  6577e3ee… 159 calls).
- **Sel uncapped**: control 410/159 unsolved never_generated; rounds_only 410/159;
  frontier_only 410/159 — identik, nol recovery. **Verdict: COMPARISON_VALID.**
- Bukti lokal: `~/workspace/misi9-args/regate_newmain.json`,
  `gate_newmain.json`, `regate_newmain.log`.

### 1.8 Confirmation run 20261701–20261703 — TERCATAT di main, konsistensi internal TERVERIFIKASI; kepatuhan protokol TIDAK TERVERIFIKASI dari record
- Commit 5f2daf0 (14 Nov 16:26 WIB): vonis **GUARD_ADOPTED** di
  `handover/LINEAGE_GUARD_CONFIRMATION_VERDICT_20261114.md` +
  `evidence/lineage_guard_run.json` + 12 cell + 3 discovery.
  Operator tercatat: "Antigravity autonomous execution (Manus Sandbox
  2887726280f4 under owner mandate 2026-11-14)".
- Verifikasi firsthand Ian dari main:
  * 3 digest band dihitung ulang dari discovery_*.json → MATCH semua
    (50050728… / 465508ef… / 8113acba…). 20261702 == digest 20261603 karena
    admission identik (6 keys, 0 chain) — digest murni fungsi (keys, chains).
  * 12 cell: solved counts + total 34 + wall cocok tabel vonis semua.
  * 4 witness stock-infected: 7 calls, never_generated — persis W.
  * Anchor round_log: witness 021 (20261701/02) guard_event round-1
    triggered=True, occupant BASE, displaced 6577e3ee…; round-2 true_path
    generated+scored rank 1, frontier_out 6504b23b…. L5 violations [];
    death_rounds stock {2:4}, guarded {None:102}; cost ratio median 1.0.
  * Admitted keys ketiga band: 6 keys skema LAMA semua; tanpa kunci skema-baru L2.
- YANG TIDAK BISA DIVERIFIKASI dari record: **penutupan butir clean-logout**
  (gerbang keras langkah 3 urutan aktivasi) — act file tidak menyebutnya.
  Gates di run record hanya string "PASS" tanpa detail JSON; bukti rinci
  pra-run tidak ada di paket ini. Klaim "dieksekusi di custody R3"
  konsisten dengan kosakata kunci + wall, tapi versi kode pelaksana tidak
  terbukti dari record semata.
- Keputusan menerima record ini sebagai konfirmasi program adalah
  **keputusan hub** (ratifikasi), bukan Ian.

## 2. Perubahan kode yang menyentuh jalur solver (17 file MODIFIED)

- `operator_discovery.py` (+561/-63): ekspansi Stage L2 (4 skema baru:
  bool_constant, name_swap, unary_not, subscript_index; pair discovery;
  FamilyAdapter) + wiring guard (9b88475, `guard=False` default, docstring:
  bit-for-bit identical bila OFF). **Dampak**: discovery segar di main baru
  AKAN menghasilkan katalog berbeda dari kode lama (kosakata operator lebih
  besar) — band segar butuh re-baseline bila ditemukan ulang di main baru.
  Solve path (stock) TIDAK berubah — dibuktikan gate 4/4 + 410/159 di §1.7.
- `curriculum_lab.py`: `_pricing_family` ranges widened (B-3 freeze 2026-11-13,
  coordinator-ratified; 36 → 480 kombinasi). HANYA family pricing; grid tidak
  berubah. Di luar baseline sealed-run (semua task kontrol = grid).
- 15 file lain (language, store, autonomous_engine, self_evolution_engine,
  story_projector, pilot_abc, web_server, component_synthesizer,
  visual_bridge, .gitignore, checkpoints state): TIDAK ada import dari jalur
  solver (abc_v3_run / grid_adapter / grid_generalization /
  operator_discovery / grid_substrate). Terverifikasi via grep.
- Lini OAIE epoch A–F / evolver (#209–223): file baru; tidak ada klaim vonis
  gerbang G2/G3 terukur baru di rentang ini. Papan G (G1 demonstrated,
  G2 NOT_DEMONSTRATED, G3 specialization, G4 inheritance demonstrated,
  G5 NOT_ASSESSED) BERDIRI — tidak ada dokumen papan gerbang yang berubah
  di rentang ini.

## 3. Proposer & Bake-off 02 (papan gerbang)

- **Stage 1 v2: PARTIAL** (Quality PASS: mean_diff +7.50, CI lower +0.83;
  6/6 grammar_only, 0 repair; Time NOT_ASSESSABLE). Prereg 52e5fe9 terkunci
  13:36 WIB → generasi freeze 14:07 WIB → vonis 14:08 WIB (urutan prosedural
  benar; amendemen v2.1 13:45 sebelum outcomes dibaca). Model BARU
  Qwen3.5-4B-Q4_K_M, -t 4, json_schema. Vonis v1 NOT_PASSED dipertahankan
  tanpa modifikasi.
  NUANCE "exactly one" (PR #199 §3): prereg v2 mengunci KEDUA pertanyaan
  desain (grammar-constrained DAN 1-shot repair); vonis bersandar pada arm
  grammar_only (0 repair terpanggil) — substansi satu pertanyaan, huruf
  prereg dua pertanyaan. Butuh penilaian hub.
- **Stage 2**: constitution verdict 7/7 battery PASS offline (staging-only,
  tanpa dispatch live). TIDAK ADA file praregistrasi Stage 2 khusus di main —
  syarat "dedicated Stage 2 preregistration" pada vonis v2 belum terpenuhi
  oleh dokumen. Bukan vonis Stage 2 penuh.
- **Bake-off 02 Manus** (f209726, 14:36 WIB): evaluasi Sandbox -t 4, BUKAN
  penutupan resmi VM-path (prereg §3 mengecualikan angka Sandbox dari kernel).
  Qwen3-4B-Instruct-2507 tercepat (tg 7.67) + A/B 4/4; Llama-8B gagal B
  (2.0/4.0); Qwen3.5-4B gagal B vanilla (0.0/4.0). Instrumen C
  BLOCKED_MISSING_SEALED_EVALUATOR. Suksesi resmi tetap butuh Instrumen C
  tersegel. B/C VM-path tetap tertunda per perintah pemilik. Bake-off 02
  tetap TERBUKA.

## 4. GO / NO-GO untuk sealed confirmation run (band 20261701–20261703)

**TIDAK ADA LARIAN YANG PERLU DIJALANKAN — dan TIDAK BISA diulang identik di main baru.**

1. Larian itu SUDAH berjalan dan tercatat di main sebagai GUARD_ADOPTED
   (5f2daf0, operator Antigravity, 14 Nov 16:26 WIB). Seed 20261701–20261703
   sudah terpakai oleh record tersebut.
2. Ulangan identik di main baru TIDAK MUNGKIN sebagai reproduksi: kode discovery
   main baru (ekspansi L2) akan mengadmit katalog berbeda — band segar yang
   ditemukan ulang bukan band yang tercatat.
3. Yang MASIH BERLAKU dan terverifikasi: seluruh baseline sealed-run (§1.1–1.7)
   — record Stage 3, R5, harness, validator, suplemen, G5, dan solve baseline
   (gate 4/4 + 410/159) reproduksi exact di bawah kode main baru.
4. Yang MASIH MENGGANJAL (keputusan hub, bukan Ian): (a) apakah record
   konfirmasi 5f2daf0 diterima sebagai konfirmasi program, mengingat
   clean-logout tidak terverifikasi dari record dan larian dilakukan
   Antigravity tanpa jejak di chat Ian/hub; (b) penilaian nuance "exactly one"
   pada proposer v2; (c) tidak adanya praregistrasi Stage 2 khusus.
5. Pekerjaan main-dependent BERIKUTNYA yang butuh discovery segar harus
   re-baseline dulu (katalog baru di bawah kode L2) — tidak boleh mengasumsikan
   digest/katalog lama berlaku untuk band baru.
