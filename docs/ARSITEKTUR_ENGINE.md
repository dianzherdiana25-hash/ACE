# Arsitektur engine ACE

Dokumen ini memetakan implementasi `main` pada `1af87a6` setelah
PR #393 dan #394. Gerbang transport, receipt verifikasi, dan penyimpanan
menjelaskan di mana setiap hasil siklus berasal dan kapan hasil itu dapat
masuk ke cognitive memory.

## Urutan satu siklus

| Urutan | Perilaku pada kode | Rujukan |
| --- | --- | --- |
| Mulai | Tambah penghitung siklus, simpan cursor, lalu tulis status `cycle_started`. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._persist_cursors` |
| Cek GGUF | Tulis status `discovering_models`. Periksa frontier `cap_local_gguf` dan, bila perlu, coba verifikasi inferensi lokal. Langkah ini mendahului agenda juga dalam mode bridge. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.verify_and_promote_local_gguf` |
| Agenda | Ambil agenda berstatus `QUEUED` atau `PAUSED`. Lanjutkan dengan batas dua langkah dan catat jumlah yang dieksekusi. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.check_and_advance_agenda` |
| Belajar campuran | Saat agenda tidak maju, cek keterampilan berbicara bertahap, lalu dahulukan teknis pada siklus ganjil atau bahasa pada siklus genap. Coba trek lain bila yang pertama tidak menghasilkan kerja. Setiap trek memilih item kurikulum pertama yang belum tercatat sebagai skill sebelum masuk latihan dinamis. Siklus dengan trek bahasa dan cursor bahasa ganjil juga dapat mengeksplorasi kosakata. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_continuous_mixed_learning`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_continuous_language_learning`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_continuous_technical_learning` |
| Kata terdengar | Coba memberi makna pada kata terdengar, baik setelah agenda maju maupun setelah belajar campuran. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._auto_teach_heard_words` |
| Ratification | Jalankan satu episode bila `ACE_RATIFICATION_LOOP` persis `1`. Sumbernya `projects/ratification/episodes.jsonl` di workspace. Sumber absen atau cursor habis menghasilkan status tersendiri. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_ratification_step` |
| Self-audit | Jalankan audit integritas AST setiap kelipatan sepuluh siklus. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._run_periodic_self_evolution_audit` |
| Akhir | Simpan cursor kembali, tulis status `idle_waiting_next_cycle`, dan kembalikan ringkasan berisi siklus, trek, kemajuan agenda, hasil belajar, hitungan kosakata, ratification, dan self-audit. Daemon melaporkan `cycle_error` bila siklus melempar exception. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_cycle`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.run_forever` |

## Mode otak dan latihan generatif

- **Local slate.** Jika `bridge_url()` menghasilkan `None`,
  klien memilih endpoint lokal per organ. Gerbang latihan generatif engine
  memeriksa `local_gguf.server_healthy` dari `ModelRouter.health_check()`.
  Setelah gerbang terbuka, engine mendelegasikan generasi lokal ke
  `ModelRouter.generate_text()`.
  `code/ace_operational/brain_endpoints.py:bridge_url`,
  `code/ace_operational/brain_endpoints.py:organ_url`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._practice_backend_ready`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._gen_text`,
  `code/ace_operational/models_backend.py:ModelRouter.health_check`,
  `code/ace_operational/models_backend.py:ModelRouter.generate_text`.
- **Bridge.** Mode bridge aktif saat `ACE_BRAIN_BRIDGE_URL` masih berisi
  URL setelah spasi tepi dan slash akhir dibuang. Engine memeriksa `/health`
  pada bridge dan mengirim chat ke `/v1/chat/completions` dengan organ sebagai
  `role`. Latihan teknis memilih `coder`. Dialog dan latihan kosakata
  memilih `front`. Hasil generasi meneruskan label
  `bridge:<brain_of_origin>`, dengan nama peran sebagai cadangan bila
  provenance kosong.
  `code/ace_operational/brain_endpoints.py:bridge_mode`,
  `code/ace_operational/brain_endpoints.py:health`,
  `code/ace_operational/brain_endpoints.py:chat`,
  `code/ace_operational/brain_endpoints.py:parse_chat_response`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._gen_text`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_technical_practice`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_language_dialogue_practice`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._explore_vocabulary_batch`.
- **Saat transport gagal.** Klien membungkus kegagalan HTTP, I/O, atau JSON
  sebagai `BrainUnavailable`. Pada batas generasi engine, exception itu
  menghasilkan `None`. Jalur teknis kembali sebelum membuat task dan receipt
  praktik. Dialog dapat memakai pertanyaan tetap jika generasi pertanyaan
  gagal, tetapi memerlukan jawaban untuk mencatat latihan. Eksplorasi
  kosakata kembali dengan daftar kosong saat jawaban kosong. Ini adalah
  idle pada jalur yang tidak mendapat hasil, sementara siklus masih dapat
  mencoba trek lain. Cursor dan status siklus dapat tetap berubah.
  `code/ace_operational/brain_endpoints.py:_request`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._gen_text`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_technical_practice`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_language_dialogue_practice`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._explore_vocabulary_batch`,
  `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.execute_continuous_mixed_learning`.

## Write-back ke cognitive memory

Item kurikulum disimpan sebagai skrip dalam workspace, dikompilasi, lalu
dijalankan. Syarat lulusnya adalah kompilasi dan eksekusi berstatus nol serta
`verification_str` ditemukan di stdout. Engine mencatat receipt dan, saat
lulus, mencatat skill dan frontier lalu memanggil
`_writeback_skill_verified()`. Latihan teknis dinamis punya verifier skrip
sendiri dan memanggil helper write-back yang sama setelah receipt lulus.
`code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._run_verified_curriculum_item`,
`code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._writeback_skill_verified`,
`code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._verify_python_script`,
`code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_technical_practice`,
`code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._writeback_verified_event`.

Jalur penulisan terverifikasi memakai `record_verified_event()` dengan
daftar kelas tertutup. Engine menyerialkan receipt ke byte bukti. Helper
menyimpan hash bukti sebagai anchor, menghubungkan record berjenis sumber
`evidence` ke hash itu melalui `source_ref`, dan memakai kembali ID jika
konten serta hash bukti identik. Record memuat ringkasan dan rujukan receipt.
Kegagalan write-back menghasilkan log serta `None` sebagai ID memori,
sementara verdict receipt tetap berdiri.
`code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._writeback_verified_event`,
`code/ace_operational/memory_writeback.py:record_verified_event`,
`code/ace_operational/cognitive_memory.py:CognitiveMemory.anchor_evidence`,
`code/ace_operational/cognitive_memory.py:CognitiveMemory.remember`.

| Kind cognitive memory | Kelas pada write-set terverifikasi |
| --- | --- |
| Procedural | `skill_verified` |
| Semantic | `verdict_sealed`, `pattern_distilled` |
| Episodic | `mission_ratified`, `finding_high_opened`, `finding_high_closed`, `writepath_audit_probe` |

Daftar kelas, kind, dan confidence bawaan berada dalam
`code/ace_operational/memory_writeback.py:EVENT_CLASSES`.

## Peran dan budget bridge

Bridge memetakan `front`, `coder`, `validator`, `embedding` dan `judge`
ke organ penyedia. Budget bawaan per hari lokal adalah 200 untuk `front`,
`coder` dan `embedding`, 100 untuk `validator`, serta 20 untuk `judge`.
Governor menyimpan tanggal dan pemakaian per peran di
`bridge_state.json` di sisi bridge. Tanggal baru memulai penghitung baru.
Permintaan POST menagih satu pemakaian sebelum inferensi dan mendapat HTTP
429 saat budget habis. `GET /health` melaporkan peran dan batas budget.
`code/ace_operational/brain_bridge.py:ROLE_MAP`,
`code/ace_operational/brain_bridge.py:BUDGETS`,
`code/ace_operational/brain_bridge.py:STATE`,
`code/ace_operational/brain_bridge.py:_today`,
`code/ace_operational/brain_bridge.py:_budget_check`,
`code/ace_operational/brain_bridge.py:Handler.do_POST`,
`code/ace_operational/brain_bridge.py:Handler.do_GET`.

`serve_chat()` mencoba fallback yang terdaftar satu kali bila organ utama
gagal. Respons bridge menandai organ yang benar-benar melayani melalui
`brain_of_origin`. Untuk jalur relai store-and-forward, relai membuat
permintaan spool dan pump memakai fungsi governor dan fungsi chat yang sama.
`code/ace_operational/brain_bridge.py:serve_chat`,
`code/ace_operational/brain_bridge.py:Handler.do_POST`,
`code/ace_operational/brain_bridge_relay.py:Handler.do_POST`,
`code/ace_operational/brain_bridge_pump.py:execute`.

## Letak state

| Lokasi | Isi | Rujukan |
| --- | --- | --- |
| Workspace | Argumen `--workspace`, workspace store yang diberikan, `ACE_WORKSPACE`, lalu `~/.local/share/ace/workspace` menurut urutan resolusi. | `code/ace_operational/autonomous_engine.py:main`, `code/ace_operational/autonomous_engine.py:_resolve_workspace_path` |
| `ace_operational.sqlite3` | Store SQLite dalam mode WAL untuk meta, task, receipt, agenda, skill, dan frontier. Engine menyimpan hitungan siklus serta cursor bahasa dan teknis di meta. | `code/ace_operational/store.py:OperationalStore.__init__`, `code/ace_operational/store.py:OperationalStore._init_schema`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._persist_cursors` |
| `autonomous_engine.status.json` | Snapshot status daemon dengan schema, running, penghitung dan cursor, aksi berjalan, PID, waktu pembaruan, dan details. Penulisan memakai berkas sementara lalu replace. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.__init__`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.update_status_file` |
| `cognitive_memory/memory.jsonl` | Log append-only berantai hash. Replay mengembalikan state memori. Audit melaporkan integritas rantai dan hitungan anchor. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._writeback_verified_event`, `code/ace_operational/cognitive_memory.py:CognitiveMemory.__init__`, `code/ace_operational/cognitive_memory.py:CognitiveMemory._append`, `code/ace_operational/cognitive_memory.py:CognitiveMemory._replay`, `code/ace_operational/cognitive_memory.py:CognitiveMemory.audit` |
| `projects/bahasa/dialog_corpus.jsonl` dan `projects/teknis/technical_corpus.jsonl` | Catatan latihan dinamis bahasa dan teknis. | `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine.__init__`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_language_dialogue_practice`, `code/ace_operational/autonomous_engine.py:ContinuousAutonomousEngine._generate_dynamic_technical_practice` |

## Memeriksa jalur dengan fixture

Jalankan dari akar repo. Tes membangun workspace sementara dan mengganti
transport bridge dengan fixture.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest -q \
  ace_operational.test_engine_writeback_seam \
  ace_operational.test_engine_bridge_practice \
  ace_operational.test_brain_bridge_mode
```
