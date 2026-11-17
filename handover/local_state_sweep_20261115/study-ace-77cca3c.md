# Studi Mendalam Repo ACE @ `77cca3c` (origin/main)

- **Objek:** worktree `~/workspace/ace-study`, detached HEAD `77cca3c6ec2a1f0f46647bff275ee796c1661e2b` ("feat(engine): add mixed tech+language autonomy, loopback auth, and ace engine CLI"), repo `dianzherdiana25-hash/ACE`.
- **Metode:** read-only penuh. Tidak ada berkas diubah, tidak ada tes dijalankan. Setiap klaim disertai path berkas.
- **Konvensi baca:** di seluruh laporan dibedakan tegas — **[BERKAS]** = apa yang dokumen/record *katakan*; **[KODE]** = apa yang kode *benar-benar lakukan* saat dibaca.
- **Skala repo:** 1.550 berkas (di luar `.git`), ±33 MB, 725 commit, rentang 2026-11-04 → 2026-11-15 (`git log`).

---

## 1. PETA POHON PENUH

### 1.1 Area tingkat atas

| Area | Berkas | Isi dominan | Sifat |
|---|---|---|---|
| `code/` | 518 (509 `.py`, 135.494 baris Python) | 54 subpaket Python | Kode (campuran: inti terukur + mesin besar + riset) |
| `evidence/` | 614 (±736.937 baris JSON, 17.273 baris md, 6.345 baris py) | 48 subdirektori + 133 berkas lepas | Artefak bukti/run-state mesin |
| `docs/` | 217 (±28.822 baris md) | architecture, evaluation, evolution, research (+agenda/capability/f12/f13/f14/generations/hypgen/self_dev), security, validation | Dokumen manusia |
| `handover/` | 32 (+ 3 subdir: `lm-eval-screening/`, `serving-lane/`, `sqlite-vec-trial/`) | Vonis, manifes kustodi, review integrasi | Dokumen keputusan |
| `checkpoints/` | 13 (semua JSON, ±32.071 baris) | `checkpoints/self_dev/` | State mesin self-dev |
| `.ace_evolution/` | 44 (±32.346 baris JSON) | state evolusi, misi pengguna, skill sintesis | State + artefak mesin |
| `data/` | 1 | `data/ace_seed_snapshot.json` (5.293 baris) | Snapshot data |
| `tests/` | 19 (4.789 baris py) | 18 berkas tes (13 di `tests/e2e/`) | Tes |
| `tools/` | 37 (6.724 baris py) | harness, verifier, benchmark, driver larian | Kode pendukung/harness |
| `examples/` | 5 | manifest + contoh JSON terminal | Contoh |
| `projects/` | 12 | 2 aplikasi: `projects/pengelola_keuangan/` (app.py + tes), `projects/sistem_manajemen_usaha/` (server.py + db.py + tes) | Produk sampingan (aplikasi usaha Indonesia) |
| `chat_tasks/` | 1 | `chat_tasks/current.json` | Pemicu runner CI |
| `.github/` | 18 | semua di `.github/workflows/` | CI (lihat §7) |
| Root | 20 berkas | dokumen inti + 4 skrip Python + `install.sh` (227 baris) + `LICENSE` + `pyproject.toml` | Campuran |

### 1.2 Anatomi `code/` — satu paket mendominasi

- `code/ace_operational/`: **160 berkas `.py`, 59.566 baris — 44% seluruh Python repo.** Dari 160 itu, **83 modul non-tes dan 77 berkas `test_*.py`** — hampir separuh "inti" adalah kode tes.
- Paket menengah: `code/ace_self_dev/` 34 py/9.461 baris; `code/ace_host_controller/` 18/4.547; `code/ace_code_agent/` 18/3.039; `code/ace_autonomy/` 15/3.544; `code/ace_research_repair/` 12/5.203; `code/ace_research_discovery/` 10/4.144; `code/ace_research_generations/` 12/2.672; `code/ace_indo_nlp/` 9/2.280; `code/ace_neurosymbolic/` 9/2.936.
- ±40 paket kecil (kebanyakan pola seragam 3 berkas, 100–1.500 baris): `ace_egraph`, `ace_smt`, `ace_mcts` (185 baris), `ace_game_theory`, `ace_conformal`, `ace_pac_bayes`, `ace_causal`, `ace_ilp`, `ace_gnn`, `ace_automata`, dll. — perpustakaan teknik-teknik riset, sebagian besar tidak terhubung ke jalur terukur (§3).
- Duplikasi struktural: ada **dua pohon checkpoints** — `checkpoints/self_dev/` dan `code/checkpoints/self_dev/`; di `tools/` ada dua keluarga bakeoff (`tools/bakeoff_a.py`, `bakeoff_b.py`, `bakeoff_c.py` dan `tools/bakeoff02_a.py`, `bakeoff02_b.py`, `bakeoff02_c.py`, `bakeoff02_finalize.py`).

### 1.3 Klasifikasi isi

- **Kode tangan (manusia/mesin campuran):** `code/` + `tools/` + root scripts — tidak ada penanda provenance per berkas; commit history menunjukkan dua penulis efektif: lini hub/Ian (gerbang terukur) dan lini Antigravity (mesin), keduanya di bawah akun pemilik.
- **Artefak bukti mesin:** `evidence/` (614 berkas, didominasi JSON run-state ±737 ribu baris), `checkpoints/`, `.ace_evolution/` (mayoritas JSON snapshot hash misi ±32 ribu baris), `data/`.
- **Dokumen manusia:** `docs/` (217), `handover/` (32), root docs (±20).

---

## 2. TATA KELOLA & KLAIM — APA KATA REPO TENTANG DIRINYA

### 2.1 Identitas yang diklaim

- **[BERKAS]** ACE = *Autonomous Capability Evolution*; meneliti kecerdasan yang "develop, test, transfer and inherit capabilities across generations"; visi jangka panjang OAIE. `main` hanyalah "runnable public research toolkit" / integrasi terpilih, **bukan** codebase historis lengkap; "choosing its own research agenda, inventing new learning/representation classes, robust open-world transfer and OAIE remain open" (`README.md`).
- **[BERKAS]** Versi hati-hati konsisten di dokumen inti: OAIE adalah "aspirasi penelitian, bukan kapabilitas terdemonstrasi" (`ACE_RESEARCH_MASTER_RECORD_v1.0.md` §1); "Bukti OAIE, penemuan primitive fundamental, dan AGI/ASI masih terbuka" (`PROJECT_CHARTER.md`); PRD asli: "belum diimplementasikan atau divalidasi secara empiris… ACE v0.1 bukan AGI, ASI, maupun bukti recursive self-improvement" (`docs/PRD_ACE_v0.1.md` §15).

### 2.2 Field governance — konsisten hampir di semua tempat

- **[BERKAS]** `release_gate=BLOCK_RELEASE`, `scientific_status=NOT_ASSESSED`, `oaie_established=False` — verbatim sama di `STATUS.md` §5, `README.md`, `TEST_READY.md` §5, `docs/ACE_VISION_ALIGNMENT_CURRENT.md`, dan blok `governance` di `checkpoints/self_dev/v03_researcher_state.json`. Tanpa `ACE_SEALED_SEED`, klaim ilmiah fail-closed `NOT_ASSESSED` (`QUICKSTART.md`).
- **Pengecualian yang bertabrakan:** header `STATUS.md` sendiri mengklaim "Status Ilmiah Repositori: `CONFIRMED_SEALED` (diotorisasi pemilik)" — bertentangan dengan §5 berkas yang sama (lihat §8).

### 2.3 Papan gerbang Ω menurut repo sendiri (Addendum 59/60 — tertinggi, tidak ada ≥61)

- **[BERKAS]** "G0 PASS (session-scoped); G1 DEMONSTRATED; **G2 MEASURED — NOT_DEMONSTRATED**; **G3 MEASURED — SPECIALIZATION**; **G4 MEASURED — INHERITANCE_DEMONSTRATED**; **G5 NOT_ASSESSED** (period locked 12 Nov → 30 Nov 2026). OAIE unproven." (`docs/research/ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md`, `docs/research/ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM60.md` §3; sama di `handover/PETA_ARAH_SERIBU_TAHUN.md`).
- **Addendum 58** (`docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md`): G3 naik MEASURED—SPECIALIZATION, G4 MEASURED—INHERITANCE_DEMONSTRATED atas verifikasi dua-checker; antrean decider diluncurkan.
- **Addendum 59**: A/B/C v3 selesai, DI pooled **−1,98pp → G2 MEASURED NOT_DEMONSTRATED** (null terukur ketiga); lahir agenda regresi-kontrol.
- **Addendum 60**: round-2 gate `LIFT_DEMONSTRATED` (round2_index tepat 0,0) — hasil mekanisme, **eksplisit bukan gerak papan G1–G5**, bertumpu pada 1 motion key/1 bentuk defect.
- Addendum 55 & 56 **tidak ada sebagai berkas tersendiri**; isinya hanya diringkas ulang di Addendum 57 (`docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM57.md`).
- Ada **tiga sistem "G" bertabrakan nama**: gerbang PRD G1–G5 (`docs/PRD_ACE_v0.1.md` §3), papan Ω G0–G5 (Addendum 59/60), dan generasi rekursif G0→G1→G2 (`docs/ACE_G0_G2_RESULTS_V1.md`). Dokumen tidak selalu membedakannya.

### 2.4 Klaim dokumen yang tidak ditopang berkas lain

1. Blok angka `STATUS.md` §2/§4: 368/368 tes, 808+ mission submissions "VALID (verified)", 15 mesin terverifikasi, swarm 7 agen, BALD "87,12% query reduction", Neural A* "6,69x–34,88x", sketching "28,57x", W4 BFS 100% vs 85,8% — hanya diulang di `docs/LAPORAN_HASIL_RISET_HP.md`, tanpa berkas hasil penopang. Audit internal repo sendiri memperingatkan `CONFIRMED_SEALED` bisa muncul hanya karena seed env terisi dan W4 100% adalah solver pasokan peneliti, bukan discovery (`docs/validation/ACE_OAIE_AUDIT_20261110.md` §4, `docs/validation/ACE_OAIE_REVIEW_20261110.md` §8).
2. `CHANGELOG.md`: "Lolos verifikasi independen 100% (ALL CHECKS PASSED)" dan "Armada AI aktif (PowerBrain, Pollinations, G4F, AI Horde)" — tanpa berkas verifikasi yang dirujuk; bertabrakan dengan invarian Rp0/offline di `README.md`/`STATUS.md` §5.
3. `PROJECT.md`: "Complete 808-test pass verification, zero mock bypass", M1 DONE/M2 IN PROGRESS — angka 808 bertabrakan dengan 82 (`TEST_READY.md`), 368 (`STATUS.md`), 784 discovered tests (`docs/research/ACE_OMEGA_PR_AUDIT_20261111.md`); hitungan studi ini: **189 berkas tes** di seluruh tree (§7).
4. `docs/architecture/ACE_OAIE_UNLIMITED_DOCTRINE.md`: status `OPERATIONAL_SUBSTRATE_V2`, klaim mengendalikan AI manapun, "100% Brain-Agnostic", waterfall utang 50/30/20 (Rp4.208.328) — file kodenya ada (`code/ace_operational/oaie_unlimited.py`), tetapi tidak ada evidence pendapatan penopang; `handover/PETA_ARAH_SERIBU_TAHUN.md` sendiri mencatat "penghasilan terverifikasi Rp0".
5. `STATUS.md` bertanggal **8 Nov 2026** dan menunjuk commit `de1f644`, padahal tree berada di `77cca3c` (15 Nov) — sementara `CURRENT_STATE.md` dan `NEXT_ACTION.md` hanya mengalihkan pembaca ke `STATUS.md` basi itu sebagai sumber kebenaran.

---

## 3. INTI TERUKUR — `code/ace_operational/`

### 3.1 Jalur solve: utuh, tetapi entry point di luar paket dan tidak portabel

- **[KODE]** Tidak ada `abc_v3_run.py` di `code/ace_operational/`. Entry point sebenarnya **`tools/abc_v3_run.py`**, yang menyatakan dirinya `HARNESS, not repo code`.
- **[KODE]** Alurnya nyata dan tersambung: `tools/abc_v3_run.py: run_band()` → `build_universe(seed)` (`code/ace_operational/grid_generalization.py:209`) → `run_discovery(...)` sekali (`code/ace_operational/operator_discovery.py`, 851 baris) → freeze keys/chains + `catalog_digest` → arm A/B/C via `solve_task(..., max_score_calls=4000)` → `assess_abc_v3` (`code/ace_operational/abc_v3_scorer.py`, 247 baris). `main()` menjalankan band 20261501–03.
- **[KODE]** Kopling longgar yang sehat: `operator_discovery.py` tidak mengimpor family secara statis; inti di-decouple via `FamilyAdapter(Protocol)`, adapter default lazy dari `code/ace_operational/grid_adapter.py` (43 baris) → `grid_generalization.py` (382) → `grid_substrate.py` (238) + `curriculum_lab.py` (660) + `reasoning_lab.py` (350). Cek statis: **tidak ada import hilang** di modul non-tes paket ini.
- **[KODE] Rapuh:** `tools/abc_v3_run.py:40,51,53` meng-hardcode `sys.path` dan path evidence absolut ke `/home/hatch/workspace/ace-omega/wt-abcv3/...` — pipeline terukur **tidak bisa dijalankan dari clone segar repo ini** tanpa menyunting path.

### 3.2 Modul-modul inti (peran per [KODE])

- Solver/discovery: `operator_discovery.py` (satu-satunya solver terukur), `grid_generalization.py`, `grid_substrate.py`, `grid_adapter.py`, `abc_v3_scorer.py`; family kedua `pricing_adapter.py`/`pricing_substrate.py` (tidak dipakai driver grid v3); `lexical_ops.py` (810, solver leksikal sendiri), `statement_ops.py` (527, diimpor lazy oleh discovery), `curriculum_lab.py`, `catalog_gap.py`, `catalog_artifact.py`, `curriculum_generator.py`, `admission_hygiene.py`.
- Instrumen gerbang (standalone, membaca berkas evidence JSON, fail-closed; tidak dipanggil solver): `g1_instrument.py` (184), `g3_instrument.py` (297), `g4_instrument.py` (394), `g5_instrument.py` (440), `round2_instrument.py` (330).
- Pendukung ukur: `profiling_observer.py` (1.076), `parse_once_bench.py`, `gen_context_bench.py`, `pilot_abc.py` (pilot lama substrat v2, bukan driver v3).

### 3.3 Empat komponen yang dicari

- **Lineage guard — [KODE] ADA di solver pada commit ini, tetapi opt-in dan tidak dipakai driver terukur.** Bukan berkas terpisah: menyatu di `operator_discovery.py: solve_task(..., guard=False, guard_stats=None)` — label first-generation-wins BASE vs ENRICHED + hook satu slot (frontier tanpa BASE diganti anggota terendahnya dengan kandidat BASE teratas). Default **OFF** (diklaim bit-identik ke stok). Ter-wire selektif di `admission_hygiene.py`, `lexical_ops.py`, `oaie_engine.py`, `coevolution_arena.py` (guard=True) — tetapi `tools/abc_v3_run.py` memanggil `solve_task` **tanpa** guard. Harness/gate tetap di luar inti: `evidence/lineage_guard_harness.py` (991 baris), `evidence/lineage_guard_gate.py`, `evidence/test_lineage_guard_harness.py`.
- **Proposer — substansial, mandiri dari solve.** Rantai nyata: `proposer_schema.py` (98, skema `ace.proposal.v1` fail-closed) → `proposer_validator.py` (186) → `proposer_episodes.py`/`proposer_rubric.py`/`proposer_simulation.py` (Stage-1) → `proposer_stage1_v2.py` (298, grammar-constrained + maks 1 repair) → `proposer_stage2.py` (2.111, staging konstitusi) → `proposer_stage2_battery.py` (433). Bukan stub; tetapi docstring-nya sendiri: Stage-1 `simulation-only, no dispatch/no execution path`; tidak diimpor jalur solve.
- **Validator — substansial, mandiri.** `preaudit_validator.py` (1.260, validator mekanik offline read-only C1–C4), `preaudit_oracle.py` (179, docstring eksplisit `TEST SUPPORT ONLY`), `citation_validator.py` (346).
- **Distractor battery — kecil, lengkap, dan tipis.** `code/ace_operational/distractor_inoculation.py` (134 baris): `load_registry()` fail-closed, `inject()`, `run_battery()` — hanya melapor `SUSCEPTIBLE`/tidak, tidak mengubah solver. Registry-nya (`code/ace_operational/distractor_registry.json`, 1.553 B) berisi **tepat 1 distractor terdaftar**: `name-swap-523014-nc-band20261501`, key `('name_swap',(5,2,3,0,1,4),'nc')`, witness `catalog_control-020/021`. Seluruh bangunan Stage-3/lineage-guard bertumpu pada satu witness terdaftar ini.
- **Kebersihan kode:** `TODO/FIXME` di paket ini = 3 hit, semuanya string status tugas `'TODO'` di `store.py`, bukan komentar; `NotImplementedError` = 0; fungsi pass-only hanya method `Protocol` (disengaja) + satu `log_message` di `web_server.py`. Kode mati berbentuk stub kosong praktis tidak ada; yang ada adalah **modul utuh yang tidak terhubung** (lihat §3.4).

### 3.4 Mesin besar di luar jalur terukur (masih di `ace_operational/`)

[KODE] Modul-modul besar berikut nyata sebagai kode, tetapi **tidak terhubung ke `abc_v3_run`/jalur terukur** dan klaimnya hanya sekuat docstring-nya: `autonomous_engine.py` (1.575), `autonomy_loop.py` (1.394), `compositional_oaie.py` (1.646), `oaie_engine.py` (895), `oaie_unlimited.py` (1.373), `coding_loop.py` (1.647), `evolution_mission_loop.py` (1.839), `coevolution_arena.py` (500), `causal_repo_evolution.py` (806), `ontological_godel_engine.py` (492), `sovereign_runtime.py` (613), `language.py` (1.142), `speech_acquisition.py` (1.843), `store.py` (1.854, store SQLite ber-fencing), `web_server.py` (2.005, §4.4), `models_backend.py` (813), `experiment_kernel.py` (360). `open_world_cli.py` sendiri menyatakan "never executes".

---

## 4. LINI MESIN (Antigravity) — APA YANG BENAR-BENAR BEKERJA

### 4.1 Launcher root: shim tipis

- **[KODE]** `ace.py` = **12 baris**, `autonomy.py` = **13 baris**: keduanya hanya `sys.path.insert(0, .../code)` lalu delegasi — `ace.py` → `ace_runtime.cli:main`, `autonomy.py` → `ace_autonomy.cli:main` (paket di `code/ace_runtime/`, `code/ace_autonomy/`). Tidak ada logika di berkas root ini.
- **[KODE]** `auto_curriculum.py` (160 baris): fungsional — kurikulum 8 level **hardcoded** (seed tetap) → `ace_capability_evolution.compositional:bank()` → `ace_runtime.engine.Runtime` → hasil dibaca dari outcome runtime (`REUSE_VALIDATED/LEARNED_STAGED/NO_VALIDATED_MODEL`); ada cacat kosmetik laporan (penyebut train tercetak sebagai nama tugas).
- **[KODE]** `ace_self_evolver.py` (342 baris): **sebagian fungsional.** Riil: `MissionBus` SQLite (`code/ace_mission/`), admission via `bus.submit_mission()`, solver reasoning sungguhan (`ace_cognition.reasoning`), gate commit = subprocess tes + branch isolasi `ace-evolution/<id>` + rollback. Canned: (a) "diagnostics" penerbit misi = 4 string templat hardcoded (`INFORMATION_SHORTAGE/METHOD_SHORTAGE/TOOL_SHORTAGE/BUDGET_EXHAUSTION`); (b) angka **"52 tests"** di pesan sukses/commit adalah **string hardcoded**, bukan hitungan hasil gate; (c) jalur non-reasoning eksplisit `UNVERIFIED_PROPOSAL, benchmark_score 0.0` — jujur, tidak fabrikasi skor.

### 4.2 `code/ace_indo_nlp/` — rule-based murni, tanpa model

9 berkas, 2.280 baris; terhubung keluar hanya lewat `code/ace_operational/speech_acquisition.py` dan `autonomous_engine.py`.

- `phonotactics.py` (170): tokenisasi digraf, silabifikasi maximal-onset dengan set klaster hardcoded, pola CV; `synthesize_babble` deterministik (aritmetika seed), bukan belajar. **Fungsional (aturan).**
- `morphology.py` (353): stemmer "Nazief-Adriani-inspired" — ekspansi prefiks (termasuk nasalisasi) × sufiks, strip klitik, reduplikasi; akar dipilih dari `known_roots` bila diberi, selain itu kandidat pertama tanpa validasi kamus; `COLLOQUIAL_SLANG_MAP` ±150 entri hardcoded. **Fungsional (heuristik).**
- `lexicon_kb.py` (450): KB statis tulis-tangan — `CORE_INDONESIAN_LEXICON` (docstring klaim "280+"), stopwords, pola telegrafik; relasi semantik dibangun dari tuple yang sama. **Fungsional sebagai data, bukan hasil akuisisi.**
- `discourse.py` (893): parser regex nyata (pengajaran langsung, anafora, koreksi, guard reported-speech) + ekstraksi Q&A yang grounded ke leksikon dan jujur bila kata tak dikenal. **Tetapi** `realize_indonesian_turn` — bagian "dialog alami" — adalah **kaskade templat canned**: semua balasan string tulis-tangan (termasuk 3 cerita tetap, jawaban warna tetap "biru langit dan ungu", tebak-kata tetap "langit"), dipilih deterministik via `sum(ord)+turn_index`. **[BERKAS] misi "dialog alami" teratifikasi VERIFIED; [KODE] realisasinya templat + slot echo, bukan generasi.**
- Tes pendamping: 10 tes perilaku terarah (`test_discourse.py` 3, `test_lexicon_kb.py` 2, `test_morphology.py` 2, `test_phonotactics.py` 3).

### 4.3 Sistem misi & ratifikasi — self-attested

- `.ace_evolution/user_missions/CURRENT_USER_MISSION.json` **byte-identik** dengan misi 0002; isinya order `ace.user_mission_order.v1` (`mission_seq 3`) yang mayoritasnya (±4.600 baris) adalah snapshot `before_hashes`/AST counts.
- Tiga misi, semua `status: VERIFIED_AND_RATIFIED, accepted: true, dag_chain_valid: true`: `mission-0001-skill-berbicara.ratified.json`, `mission-0001b-dialog-alami.ratified.json`, `mission-0002-memori-jangka-panjang.ratified.json` (`.ace_evolution/user_missions/`).
- **[KODE/BERKAS]** Setiap ratified menyimpan `check_results` (perintah unittest + `output_tail` + `returncode 0`) dan `post_hashes` — ini **bukti yang dicatat sistem itu sendiri** (self-attested), bukan verifikasi pihak luar.

### 4.4 Mission-0002: memori kognitif — komponen terkuat lini mesin

- **[KODE]** `code/ace_operational/cognitive_memory.py` (349): genuinely functional — log JSONL append-only hash-chained (`GENESIS→prev/hash`, diverifikasi saat replay), 3 kind (episodic/semantic/procedural), provenance struktural (record wajib `source_ref` ∈ digest yang sudah di-anchor), resolusi konflik semantik by rank sumber → confidence → recency (yang kalah `superseded`, tidak dihapus), `forget()` menulis tombstone, `recall()` dengan skor overlap token + token budget + flag stale, canary-token → `ContaminationError`. Tes: 14 di `test_cognitive_memory.py`.
- **[KODE]** `code/ace_operational/memory_bridge.py` (818): fungsional di atasnya — intent percakapan via **regex berurutan sempit** (`ingat bahwa…/lupakan…/apa yang kamu ingat tentang…`), ekstraksi triple hanya dari pola tetap (nama, domisili, pekerjaan, hobi, dst.), fallback episodic = teks mentah. Terhubung riil ke `language.py` (`ConversationalEngine`). Catatan: `steps` prosedural di `record_task_episode` **hardcoded sama untuk semua domain**, dan `verify_and_promote_frontier()` menaikkan kapabilitas menjadi `KNOWN_AND_TESTED` hanya dari `audit.chain_ok` — promosi-diri, bukan uji perilaku. Tes: 6 di `test_memory_bridge.py`.

### 4.5 Web Studio — fungsional, tanpa autentikasi sama sekali

- **[KODE]** `code/ace_operational/web_server.py` (2.005 baris): ±1.530 baris pertama adalah satu string HTML/CSS/JS inline (`ANIME_WEB_HTML`, avatar SVG 5 state); sisanya `ACEWebCore` + handler + `ACEWebServer`. Menyajikan data riil dari `OperationalStore` (SQLite yang sama dengan CLI), `ConversationalEngine`, `ModelRouter`, `CodingAgentLoop`, `AutonomyOrchestrator`: GET `/api/status|conversations|events|story|tasks|artifacts|gaps|skills|deliverables|experiments|speech|memory`, POST `/api/chat`, `/api/tasks/<id>/control` (pause/stop/**resume mengeksekusi ulang coding loop**), `/api/memory` (store), `/api/memory/recall`, `/api/memory/forget`. SSE bukan streaming hidup (event dirangkai sekali lalu koneksi ditutup).
- **[KODE] Auth: tidak ada token/cookie/session/Authorization sama sekali** di jalur server. Satu-satunya pengaman = binding: konstruktor menolak host non-loopback kecuali `allow_lan=True` eksplisit. Konsekuensi: proses lokal mana pun dapat memanggil semua API termasuk `POST /api/memory/forget` dan kontrol tugas; record privat terekspos via `GET /api/memory?include_private=1`; bila `allow_lan` menyala, seluruh API terbuka ke LAN tanpa kredensial. (Klaim commit `77cca3c` menyebut "loopback auth" — yang ada adalah *loopback binding*, bukan autentikasi.)

---

## 5. ARTEFAK STATUS

### 5.1 Self-dev researcher v03 — `checkpoints/self_dev/v03_researcher_state.json`

- **[BERKAS]** `completed_cycles=122`, `history` 122 entri, `tested_patches` 122; keputusan: **ACCEPTED 96, INCONCLUSIVE 26**; `active_problems=[]`.
- Siklus terakhir: `cycle=122`, `2026-11-15T03:40:21Z`, `INCONCLUSIVE`, alasan verbatim: `STAGED_ONLY_NOT_EXECUTED: UNSUPPORTED_OR_INCOMPLETE_CANDIDATE; public synthetic scores are not independent evidence, and candidate is not wired into active ACE behavior.` — mesinnya sendiri menyatakan kandidat terakhir tidak terhubung ke perilaku aktif ACE.
- Governance verbatim: `{"release_gate": "BLOCK_RELEASE", "scientific_status": "NOT_ASSESSED", "oaie_established": false}`.
- PR buatan engine: **tepat 1** — PR #90 (`pr_meta_hyp_expand_dispatch_3`, 2026-11-08); 121 siklus lain `pr_created=false`.

### 5.2 Evolusi — `.ace_evolution/evolution_state.json`

- **[BERKAS]** `generation_seq=1`, `ratified_count=5`, `rejected_count=0`, `user_mission_seq=3`.
- **[BERKAS vs hitungan]** `ratified_history` berisi 5 entri tetapi hanya **3 misi unik** — `mission-0001-skill-berbicara` tercatat **3×**, 0001b 1×, 0002 1×; semua `resolution_note="user_mission_verified"`. Jadi "5 teratifikasi" = 3 misi, satu dihitung tiga kali.
- `generation_seq=1` sementara skill sintesis berlabel g1–g4 (generasi hidup di runtime `compositional_oaie`, berkas state ini tertinggal).
- Work order aktif mencatat temuan `unguarded_verified_true` di `code/ace_operational/sovereign_runtime.py:517` (`.ace_evolution/EVOLUTION_WORK_ORDER.json`).

### 5.3 Synthesized skills — 14 berkas, aritmetika trivial berkomposisi

`.ace_evolution/compositional_oaie/synthesized_skills/`: `g1_abs_diff.py`, `g1_bounded_margin.py`, `g1_is_framed.py`, `g1_positive_delta.py`, `g2_band_breach.py`, `g2_quota_overage_fee.py`, `g2_safe_framed_len.py`, `g2_sla_excess.py`, `g3_framed_band_breach.py`, `g3_framed_margin.py`, `g3_framed_square.py`, `g3_net_settled_after_gap.py`, `g4_framed_overage_charge.py`, `g4_safe_settled_after_gap.py`.
**[KODE]** Semuanya komposisi tiga primitif — `bounded_margin(a,b)=a-b if a>b else 0`, `is_framed(tok)=startswith('[') and endswith(']')`, `abs_diff` — tanpa I/O/efek samping. Generasi 3–4 hanya membungkus generasi sebelumnya dengan cek `is_framed` yang sama (pola `... if is_framed else 1`). Nyata sebagai bukti komposisi/pewarisan mekanis; dangkal sebagai "keterampilan".

### 5.4 Seed snapshot — `data/ace_seed_snapshot.json`

- **[BERKAS, terverifikasi hitung]** `vocab_count=864` = persis 864 entri `lexicon`; `dialog_corpus_count=133` = 133 entri; **`memories_count=2`** — hanya 2 memori. Diekspor `2026-11-15T08:09:05Z`, `schema="ace.seed_snapshot.v1"`.
- Leksikon: entri `{word, meaning_id, role}` (mis. `ajar/alat/ambil` — ketiganya ber-`role: "aksi"`, termasuk "alat" yang benda).
- Korpus dialog: pasangan prompt/response nyata bertanda `backend: "local-gguf-server"` (respons model lokal via server GGUF), mis. cycle 94–95 tanggal 2026-11-15T07:01Z — jadi korpus adalah log interaksi dengan model lokal, bukan keluaran `discourse.py`.

---

## 6. EVIDENCE/ — INVENTARIS & VONIS KUNCI

614 berkas: 481 di 48 subdirektori + 133 berkas lepas. Keluarga besar: `evidence/handover/` **203** (keluarga terbesar — termasuk memo G5, exhibit ecosystem/serving), `ctrlreg_stage3_official/` 30, `lineage_guard_state/` 21, `proposer_stage1_v2/` 18, `abc-v3-run-state/` 16, `g3-run/` 16, `ctrlreg_stage1_state/` 12, `mission_admission/` 12, `proposer_stage1/` 12, `w3_admission/` 12, `g4-run/` 11, `autonomous_missions/` 9, `preaudit_pilot_v1/` 9, `r5_custody/` 9, `round2-gate-run/` 8, `ctrlreg_stage0_state/` 6, `ctrlreg_stage2_state/` 6, `preaudit_pilot_v2/` 6, `real_world/` 6, `audit_20261110/` 5, `ctrlreg_stage3_state/` 4, `bakeoff02_manus/` 4, sisanya ≤3 (kernel, audit legacy PR, discovery, preaudit, runtime, repair, f12/f13/f14, generations, agenda, autonomy, composition, host_foundation, hypgen, integration, phase2, research, self_dev, selfmodel, reptransfer, internal_reasoning, omega_g0_20261112, proposer_stage2 1 berkas).

Vonis kunci (verbatim dari berkas):

- **Stage 3 resmi:** `{"P1": "P1_REPRODUCED", "P2": "HELD — neither R nor F recovered any infected failure", "P3": "HELD — never_generated on every infected S failure"}` (`evidence/ctrlreg_stage3_official_record.json`); sel: 20261601 clean 34/34, infected 32/34 (gagal 020, 022); 20261602 infected 33/34 (021); 20261603 infected 33/34 (020); semua `never_generated`, `recovered_by_R/F=[]`.
- **Konfirmasi lineage-guard (record commit `5f2daf0`):** `verdict="GUARD_ADOPTED"`, `experiment="lineage-guard confirmation run (PR #188)"`, `gates={"L4":"PASS","L1_L2":"PASS","step4_battery":"PASS"}`, band 20261701/20261702/20261703 (`evidence/lineage_guard_run.json`); dokumen pasangannya `handover/LINEAGE_GUARD_CONFIRMATION_VERDICT_20261114.md` (recovery 4/4 witness, clean 102/102, guarded infected 102/102) **dengan batas tertulisnya sendiri: hanya harness solver, belum wiring produksi**. Artefak pendukung: `evidence/lineage_guard_state/` (12 berkas sel 2026170{1,2,3} × {stock,guarded} × {clean,infected}, 3 discovery, `act_confirm_20261701.json`, battery guarded/stock, `gate.json` PASS).
- **Proposer Stage-1 v1:** `EXIT GATE VERDICT: NOT_PASSED` — kualitas FAIL (mean diff −91,67 vs margin −10; CI95 lower −98,33 vs floor −20), waktu `NOT_ASSESSABLE`, proposer 0/6 episode (`evidence/proposer_stage1/SIMULATION_REPORT.md`, `simulation_report.json`; dokumen `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md`).
- **Proposer Stage-1 v2:** kedua arm `Quality PASS`, `Time NOT_ASSESSABLE`, `Exit Gate Verdict PARTIAL`, diterima 6/6, mean diff +7,50 (`evidence/proposer_stage1_v2/SIMULATION_REPORT.md`). **Stage-2:** baterai konstitusi `all_passed=true`, 7/7 (`evidence/proposer_stage2/constitution_battery_report.json`) — baterai offline staging, bukan pembukaan Stage 2.
- **G5:** **tidak ada** berkas panen G5 di `evidence/`. Yang ada hanya memo kesiapan yang menyatakan verbatim: "Status: MEMO KESIAPAN — bukan panen, bukan praregistrasi, bukan penilaian. G5 tetap NOT_ASSESSED." (`evidence/handover/G5_HARVEST_READINESS_MEMO.md`, `evidence/handover/G5_INDEKS_BUKTI_PANEN_20261113.md`).
- **Speed/ecosystem/serving:** tidak berbentuk direktori evidence tersendiri; jejaknya di `handover/` (`ECOSYSTEM_INTAKE_01_20261113.md`, `ECOSYSTEM_LMEVAL_EXHIBIT_01_20261113.md`, `ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_20261114.md`, `SERVING_INTEGRATION_REVIEW_20261114.md`, subdir `handover/lm-eval-screening/`, `handover/serving-lane/`, `handover/sqlite-vec-trial/`) dan `evidence/handover/` (203 berkas).

---

## 7. TES & CI

### 7.1 Tes — 189 berkas, tidak pernah dijalankan dalam studi ini

- Total: **189 berkas tes** (`test_*.py`/`*_test.py`) — `code/` 166, `tests/` 18, `projects/` 2, `tools/` 2, `evidence/` 1 (`evidence/test_lineage_guard_harness.py`).
- Konsentrasi: `code/ace_operational/` **77** (hampir separuh berkas paketnya), `tests/` 18 (13 e2e), `code/ace_self_dev/` 8, `code/ace_indo_nlp/` 4, `code/ace_code_agent/` 4, `code/ace_host_controller/` 4, `code/ace_neurosymbolic/` 4, `code/ace_cognition/` 4; ±45 paket lain masing-masing 1–3.
- Bandingkan klaim dokumen: 82 (`TEST_READY.md`) / 368 (`STATUS.md`) / 784 discovered (`docs/research/ACE_OMEGA_PR_AUDIT_20261111.md`) / 808 (`PROJECT.md`) — keempatnya tidak cocok dengan hitungan berkas maupun satu sama lain (angka "tes" vs "berkas tes" memang beda satuan, tetapi tidak ada dokumen yang menjelaskan satuannya).

### 7.2 CI — 18 workflow, hanya 2 terjadwal

`.github/workflows/`: `ace-full-system-ci.yml` (CI utama), `ace-autonomous-dev-v03.yml`, `ace-autonomous-scheduler.yml`, `ace-autonomy-prototype.yml`, `ace-ava-contract.yml`, `ace-chat-task-runner.yml`, `ace-fr01-benchmark.yml`, `ace-fr01-retrieval.yml`, `ace-gemini-r9.yml`, `ace-internal-reasoning.yml`, `ace-m1-fenced-store.yml`, `ace-mcp-bridge.yml`, `ace-mission-admission.yml`, `ace-open-world-pilot.yml`, `ace-repair-v2-receipt.yml`, `ace-research.yml`, `ace-runtime-v2-receipt.yml`, `ace-w3-admission.yml`.

- **CI utama** (`ace-full-system-ci.yml`, "ACE full-system verification"): trigger push ke `main` + 3 branch verifikasi, PR terbatas path (`code/**, tools/**, evidence/**, docs/validation/**`, dll.), `workflow_dispatch`. Tiga job (25/20/10 menit), matriks Python 3.12/3.13, `PYTHONPATH=code`: `tools/verify_sources.py`, `pip install numpy==2.1.3`, menjalankan **semua modul tes yang ditemukan** via `pathlib.Path('code').rglob('test_*.py')` → `python -m unittest`, replay komposisi deterministik (`cmp`), kustodi demo runtime, `tools/verify_full_system.py --group evidence`.
- **Scheduler otonom (2):** `ace-autonomous-dev-v03.yml` — cron `0 3 * * *` harian (+PR/dispatch) — inilah mesin di balik siklus self-dev GitHub Actions; `ace-autonomous-scheduler.yml` — cron `0 0 * * *`. Sisanya 16 adalah CI/verifikasi gerbang per-area berbasis push/PR path-spesifik. `ace-chat-task-runner.yml` dipicu push ke `chat_tasks/current.json`, bukan cron.

---

## 8. DISKREPANSI & RISIKO

### 8.1 Terhadap papan gerbang hub — sebagian besar SEJALAN

Papan Ω repo sendiri (Addendum 59/60, §2.3) **identik** dengan papan hub: G2 NOT_DEMONSTRATED, G3 SPECIALIZATION, G4 INHERITANCE_DEMONSTRATED, round-2 LIFT_DEMONSTRATED, G5 NOT_ASSESSED. Proposer stage-1 v1 NOT_PASSED dan v2 PARTIAL juga sama-sama tercatat. G5: repo tidak memiliki evidence panen apa pun — konsisten dengan NOT_ASSESSED. **Satu-satunya konflik papan:** lineage guard (8.2 butir 1).

### 8.2 Daftar diskrepansi

1. **Lineage guard — record `GUARD_ADOPTED` ada di main; hub tidak meratifikasinya; kode mendukung posisi hati-hati.** `evidence/lineage_guard_run.json` + `handover/LINEAGE_GUARD_CONFIRMATION_VERDICT_20261114.md` menyatakan GUARD_ADOPTED atas band 20261701–03. Namun: (a) dokumen vonisnya sendiri membatasi "hanya harness solver, belum wiring produksi"; (b) [KODE] guard di solver ber-default `guard=False` dan driver terukur `tools/abc_v3_run.py` tidak memakainya; (c) record itu lahir di luar urutan aktivasi terkunci hub (gerbang clean-logout belum tertutup). Kesimpulan studi: di dalam repo, "GUARD_ADOPTED" adalah klaim satu record, **bukan** keadaan kode.
2. **`STATUS.md` kontradiksi diri + basi.** Header `CONFIRMED_SEALED (diotorisasi pemilik)` vs §5-nya sendiri `NOT_ASSESSED/BLOCK_RELEASE`; bertanggal 8 Nov/commit `de1f644` sementara tree 15 Nov; `CURRENT_STATE.md`/`NEXT_ACTION.md` mengarahkan pembaca ke berkas basi ini. Otorisasi pemilik bukan bukti tersegel.
3. **Angka tes empat versi** (82/368/784/808) vs 189 berkas tes terhitung; tak satu pun dokumen menjelaskan satuan hitungnya.
4. **`CHANGELOG.md` vs invarian repo.** Klaim armada AI eksternal aktif (PowerBrain, Pollinations, G4F, AI Horde) + "verifikasi independen 100%" tanpa berkas rujukan — bertabrakan dengan invarian Rp0/offline-first `README.md`/`STATUS.md` §5.
5. **"Loopback auth" (pesan commit `77cca3c`) vs kode.** Web Studio tidak memiliki autentikasi apa pun (§4.5): yang ada hanya penolakan binding non-loopback. Endpoint sensitif (`/api/memory/forget`, `include_private=1`, kontrol tugas yang mengeksekusi ulang coding loop) terbuka bagi proses lokal mana pun, dan ke LAN bila `allow_lan=True`. Ini risiko keamanan nyata, bukan sekadar istilah.
6. **"Dialog alami" teratifikasi vs realisasi templat.** Misi 0001b `VERIFIED_AND_RATIFIED`, tetapi generator giliran dialognya kaskade templat canned dengan cerita/jawaban tetap (§4.2). Yang fungsional adalah parser dan Q&A leksikonnya.
7. **Ratifikasi = self-attested.** Ketiga `.ratified.json` menyimpan hasil cek yang dicatat sistem yang sama (`output_tail`, `returncode`); `ratified_count=5` menghitung misi 0001 tiga kali (3 misi unik); `verify_and_promote_frontier()` di `memory_bridge.py` mempromosikan kapabilitas dari pemeriksaan rantainya sendiri.
8. **Angka hardcoded menyamar hasil ukur.** `ace_self_evolver.py` mencetak "52 tests" sebagai string tetap di pesan sukses/commit — bukan keluaran gate. Pola sama di blok angka `STATUS.md` §2/§4 (performa BALD/Neural A*/swarm tanpa berkas hasil; audit internal repo sudah memperingatkan sebagian adalah solver pasokan peneliti).
9. **Pipeline terukur tidak portabel.** `tools/abc_v3_run.py` meng-hardcode path absolut mesin lama (`/home/hatch/workspace/ace-omega/wt-abcv3`) dan menyatakan diri "HARNESS, not repo code" — reproduksi A/B/C v3 dari clone segar repo ini tidak bisa jalan apa adanya.
10. **Satu distractor menanggung seluruh bangunan.** Registry battery berisi tepat 1 distractor (`distractor_registry.json`); Stage-3, lineage-guard, dan record konfirmasinya semua bertumpu pada witness tunggal `name_swap … 'nc'` atas band 20261501. Generalitas klaim "inokulasi" terbatas pada satu kunci itu.
11. **Snapshot memori: `memories_count=2`.** Misi "memori jangka panjang" teratifikasi, dan `cognitive_memory.py` memang fungsional penuh — tetapi snapshot handoff-nya hanya membawa 2 memori (substansi snapshot adalah leksikon 864 + korpus dialog 133 dari backend GGUF lokal, bukan dari mesin dialog repo).
12. **Doktrin ekonomi vs ledger.** `ACE_OAIE_UNLIMITED_DOCTRINE.md` menyajikan waterfall utang Rp4.208.328 sebagai substrat operasional; `handover/PETA_ARAH_SERIBU_TAHUN.md` mencatat penghasilan terverifikasi Rp0. Tidak ada evidence pendapatan di tree.
13. **Addendum hilang & ledger tertinggal.** Addendum 55/56 tidak ada sebagai berkas (hanya ringkasan di 57); `RESEARCH_LEDGER.md` berhenti di fase E1.4t tanpa satu pun hasil Ω — dokumen yang menamakan diri ledger tidak memuat papan terbaru.
14. **Duplikasi & kebersihan pohon.** Dua pohon `checkpoints/self_dev` (`checkpoints/` dan `code/checkpoints/`), dua keluarga skrip bakeoff di `tools/`, ±40 subpaket riset kecil yang tidak terhubung ke jalur terukur — luas permukaan besar dengan rasio pakai rendah; `generation_seq=1` di state evolusi tertinggal dari label generasi g1–g4 pada skill.

### 8.3 Penilaian akhir studi

- **[KODE] yang benar-benar bekerja:** jalur terukur grid/discovery/scorer (tersambung, tanpa import hilang, tanpa stub); instrumen gerbang fail-closed; proposer/validator/battery sebagai subsistem mandiri yang utuh; `cognitive_memory.py` + `memory_bridge.py`; Web Studio sebagai server lokal; self-dev researcher sebagai mesin siklus GitHub Actions (122 siklus tercatat dengan governance jujur `NOT_ASSESSED`).
- **[BERKAS] yang hanya kata:** klaim `CONFIRMED_SEALED`, angka performa/tes di dokumen status lama, "dialog alami" sebagai generasi, "loopback auth" sebagai autentikasi, `GUARD_ADOPTED` sebagai keadaan aktif, dan seluruh doktrin ekonomi OAIE-Unlimited.
- Repo ini secara tidak biasa **memuat koreksinya sendiri**: dokumen audit internal (`docs/validation/ACE_OAIE_AUDIT_20261110.md`, `docs/research/ACE_OMEGA_CAPABILITY_AUDIT_20261111.md`), field governance `BLOCK_RELEASE/NOT_ASSESSED` yang konsisten, dan batas-batas jujur di dalam dokumen vonisnya. Risiko utamanya bukan fabrikasi di inti terukur, melainkan **dokumen status yang basi dan klaim permukaan (commit message, changelog, doctrine) yang berlari lebih jauh daripada kode dan evidence-nya**.
