# ACE TOOL LAYER GUIDE v1

**Untuk:** AI / agent mana pun yang akan memakai atau mengembangkan tool layer ACE.
**Keputusan di baliknya:** `ACE_TOOL_LAYER_PLAN_v1.md` (D1–D5, pemilik, 24 Nov 2026).
**Status implementasi:** Fase 1–5 selesai untuk v1 (24 Nov 2026); bukti uji di Bagian 7.

---

## 1. Apa ini

Tool layer adalah permukaan resmi bagi agent untuk memakai ACE: memori
jangka panjang, tugas, receipt/verifikasi, skill, frontier, gap, work
order, dan penulisan berkas terjaga — di atas substrat operasional ACE
yang sudah ada (`code/ace_operational/`).

Tool layer **tidak** ditulis dari nol. Repo ini sudah memiliki server
MCP (`code/ace_mcp/`) untuk runtime riset; v1 memperluasnya dengan inti
operasional. Satu inti, dua permukaan:

- **Inti:** `ace_mcp.bridge.ACEBridge` (tool riset) +
  `ace_mcp.op_bridge.OperationalBridge` (tool operasional, awalan
  `ace_op_*`). Semua logika hidup di sini.
- **Permukaan 1 — MCP server:** `ace_mcp.server` (stdio, atau HTTP
  loopback bertoken yang sudah ada sejak sebelumnya).
- **Permukaan 2 — CLI tipis:** `ace_mcp.cli`, memanggil inti yang sama
  persis. Tidak ada logika ganda.

## 2. Konsep workspace

Semua keadaan hidup di satu direktori **workspace** ACE: basis data
tugas (SQLite), memori kognitif (`<workspace>/cognitive_memory/`), dan
berkas yang ditulis lewat tool. Server dan CLI harus menunjuk workspace
yang sama untuk berbagi keadaan. Contoh workspace kerja Muse saat
dogfooding: `~/workspace/ace-agent-workspace` (di luar repo).

## 3. Menjalankan

Dari akar repo (Python ≥ 3.9, hanya stdlib):

```bash
export PYTHONPATH=code

# MCP lewat stdio (permukaan utama) - operasional aktif, tulis aktif:
python3 -m ace_mcp.server --workspace <workspace> --read-write

# MCP lewat HTTP loopback (token wajib, min 32 karakter):
ACE_MCP_HTTP_TOKEN=<token-panjang> python3 -m ace_mcp.server \
  --workspace <workspace> --read-write --transport http --port 8735

# CLI tipis:
python3 -m ace_mcp.cli --workspace <workspace> --read-write list
python3 -m ace_mcp.cli --workspace <workspace> --read-write \
  call ace_op_task_create '{"agent": "<namamu>", "title": "...", "goal": "..."}'
python3 -m ace_mcp.cli --workspace <workspace> \
  call ace_op_memory_recall '{"query": "nama"}'
```

`--research-only` mematikan tool operasional bila hanya runtime riset
yang dibutuhkan.

## 4. Soal izin tulis (`--read-write`)

Tool baca selalu aktif. Tool tulis aktif hanya bila operator menjalankan
server/CLI dengan `--read-write`. Ini mekanisme bawaan ACE sendiri
(sekelas penanda self-send), **bukan** gerbang izin bertingkat: sesuai
keputusan pemilik (D3), agent bebas memakai dan mengubah ACE, dan
operator ACE menjalankannya dengan tulis aktif. Pengendalian berasal
dari ketertelusuran (Bagian 6), bukan dari izin per-tool.

## 5. Katalog tool v1

Tool riset (sudah ada sebelumnya, atas `ace_runtime`): `ace_status`,
`ace_submit_task`, `ace_run_tasks`, `ace_get_report`, `ace_predict`,
`ace_evaluate` (+ diagnostik opt-in).

Tool operasional (`ace_op_*`, baru di v1):

| Tool | Jenis | Fungsi |
|---|---|---|
| `ace_op_status` | baca | Ringkasan tugas/gap/skill/frontier/memori |
| `ace_op_task_create` | tulis | Buat tugas di store |
| `ace_op_task_list` | baca | Daftar tugas |
| `ace_op_task_get` | baca | Tugas + receipt + work order |
| `ace_op_task_update_status` | tulis | Pindah status (mesin keadaan store menegakkan transisi legal) |
| `ace_op_memory_remember` | tulis | Simpan pernyataan ke memori kognitif |
| `ace_op_memory_recall` | baca | Recall terbatas, bertanda provenans |
| `ace_op_memory_forget` | tulis | Lupakan per ID/kueri; isi dihancurkan, tombstone teraudit |
| `ace_op_memory_audit` | baca | Audit rantai hash memori |
| `ace_op_receipt_list` | baca | Daftar receipt eksekusi |
| `ace_op_verify_task` | baca | Vonis verifikasi dari receipt + rantai memori |
| `ace_op_skill_list` / `ace_op_skill_get` | baca | Daftar/ambil skill |
| `ace_op_skill_create` | tulis | Buat/perbarui skill |
| `ace_op_frontier_list` | baca | Frontier kemampuan |
| `ace_op_gap_list` | baca | Daftar gap |
| `ace_op_gap_report` | tulis | Laporkan gap (deduplikasi sidik jari) |
| `ace_op_work_order_create` | tulis | Work order terdelegasi (idempoten) |
| `ace_op_work_order_list` | baca | Daftar work order |
| `ace_op_work_order_submit` | tulis | Kirim hasil pekerja — **tidak** memverifikasi diri |
| `ace_op_file_write` | tulis | Tulis berkas di workspace, dijaga hash preimage, atomik |

## 6. Provenans dan ketertelusuran (wajib dipahami agent)

- Sertakan `"agent": "<namamu>"` di setiap panggilan tulis. Nama itu
  tercatat di log peristiwa store (`kind=tool_call`) dan menjadi
  `source_ref` ingatanmu.
- Ingatan yang kamu simpan berprovenans **`external`** — pernyataan agent
  tidak pernah menyamar sebagai fakta operator, apalagi bukti
  (`evidence`). Peringkat provenans ACE: bukti > operator > eksternal >
  model.
- `ace_op_file_write` menolak menulis bila `expected_sha256` tidak sama
  dengan hash berkas saat ini (`""` berarti berkas harus belum ada).
  Baca dulu, tulis dengan hash yang kamu lihat.
- Kamu **tidak bisa** membuat receipt lewat tool layer. Receipt hanya
  lahir dari mesin eksekusi ACE. Karena itu `ace_op_verify_task` akan
  menjawab `NOT_VERIFIED` untuk tugas tanpa receipt — itu kejujuran
  sistem, bukan kerusakan.
- Hasil work order yang kamu kirim berstatus `UNVERIFIED` sampai ACE
  memverifikasinya. Jangan mengklaim sebaliknya.

## 7. Bukti uji v1 (24 Nov 2026)

- `python3 -m unittest ace_mcp.test_op_bridge ace_mcp.test_bridge
  ace_mcp.test_transport ace_mcp.test_code_diagnostic` → **30 tes OK**
  (22 lama tanpa regresi + 8 baru).
- Uji asap MCP stdio langsung: `initialize`, `tools/list`,
  `ace_op_task_create`, `ace_op_memory_remember`, `ace_op_memory_recall`,
  `ace_op_status` — semua menjawab benar pada workspace uji.
- Uji asap CLI pada workspace yang sama: tugas hasil MCP terlihat lewat
  CLI (inti yang sama), audit memori `chain_ok: true`.
- Dogfooding (Fase 4): Muse memakai tool layer untuk pekerjaan nyata di
  workspace persisten — membuat dan menjalankan tugas pembangunan ini,
  menyimpan ingatan, menulis catatan terjaga hash, dan menerima vonis
  `NOT_VERIFIED` yang jujur untuk tugas tanpa receipt.

## 8. Catatan pemakaian memori

Parser memori percakapan ACE berbahasa Indonesia: pernyataan berbentuk
fakta sederhana ("namaku adalah …", "X adalah Y") tersimpan sebagai
memori **semantik**; kalimat naratif tersimpan sebagai memori
**episodik** (peristiwa). Keduanya sah — pilih bentuk sesuai maksudmu,
dan periksa `kind` pada hasil `ace_op_memory_remember`.

## 9. Batas v1 yang diketahui

- Vonis verifikasi bergantung pada receipt dari mesin eksekusi; tool
  layer sendiri tidak mengeksekusi tugas operasional (eksekusi tetap
  milik loop ACE yang sudah ada).
- Transport HTTP hanya loopback + token (desain lama yang dipertahankan);
  akses lintas mesin yang aman adalah pekerjaan lanjutan, sesuai plan.
- Status ilmiah ACE tidak berubah oleh tool layer ini (`STATUS.md`
  tetap otoritatif).

## 10. Untuk AI yang baru masuk

1. Baca `STATUS.md` → `NEXT_ACTION.md` → `ACE_TOOL_LAYER_PLAN_v1.md` →
   dokumen ini.
2. Jalankan server atau CLI menunjuk workspace kerja, sertakan namamu
   di setiap panggilan tulis.
3. Bekerja dengan jejak: tugas untuk pekerjaanmu, ingatan untuk fakta
   yang layak disimpan, gap untuk kemampuan yang hilang.
4. Apa pun yang kamu ubah di repo: commit yang jelas dan dokumentasikan
   di repo. AI berikutnya bergantung pada catatanmu, seperti kamu
   bergantung pada catatan ini.

## 11. Toolbox: perkakas repo ACE untuk agennya (batch 1-2, 24 Nov 2026)

Atas arahan pemilik ("tools/skill ACE banyak sekali — dari jaman sebelum
EVO sampai EVO 0060"), tool layer diperluas bertahap dari 21 tool
operasional ke perkakas ACE sendiri di paket `tools/` (205 modul).
Prinsipnya sama dengan v1: registri eksplisit per fungsi yang sudah
terverifikasi tanda tangannya dari sumber asli — bukan pintu impor
bebas. Semua argumen berkas bersifat relatif terhadap workspace dan
dijaga seperti `ace_op_file_write`.

Batch 1 (`ace_op_tool_*`, baca-saja, 12 tool): mastery_board,
metacog_memory_consolidate, occurrence_outlier_scan, candidate_census,
receipt_chain_verify, custody_manifest_check, director_prose_audit,
practice_task_lint, curriculum_ab_report, director_cap_simulator,
gap_pattern_report, memory_chain_compare — fungsi audit/laporan yang
sudah dipakai runtime ACE sendiri lewat leap_wiring.

Batch 2 (10 tool): memory_hygiene_audit, memory_decay (rencana saja,
tidak menghapus), gap_root_cause_report, director_challenger,
director_fold, director_queue_router, director_grounding_check,
failure_taskgen (baca-saja), plus candidate_factory_v2 dan
discriminating_candidate_factory (menulis di dalam workspace, jadi
tunduk pada opt-in tulis operator yang sama).

Total permukaan agen saat ini: 49 tool (21 operasional + 22 toolbox +
6 riset). Bukti: suite `ace_mcp` 41 tes lulus, termasuk 11 tes toolbox.
Batch berikutnya: keluarga organ/observasi dan paket-paket `code/`
per era, mengikuti peta inventarisasi di workspace agen.

Batch 3 (9 tool, semua baca-saja): organ_quality_board,
recall_delivery_probe, recall_precision_probe, saturation_scan,
engine_idle_report, verdict_board, transfer_probe, incident_book,
memory_anchor_audit. Total permukaan agen: 58 tool; suite ace_mcp
44 tes lulus. Dua perkakas ditunda dengan alasan tercatat di
op_bridge.py: organ_smoke (butuh transport suntikan) dan perkakas
baca-repo (di luar kotak pasir workspace).

Batch 4 (8 tool, semua baca-saja): curiosity_questions,
capability_report, self_assessment verify, corpus_novelty,
evo_results, periodic_self_report, agenda prioritize +
failure scan. Total permukaan agen: 66 tool; suite ace_mcp
46 tes lulus. repo_status_dashboard_v3 menyusul keputusan
adapter baca-repo yang sama dengan daily_digest.

Batch 5 (8 tool, semua baca-saja): execution_invariants,
introspect_recall, bridge_self_check, story_consistency_gate,
behavior_fingerprint diff, organ_registry_validate,
recall_ablation, cross_organ_agreement. Total permukaan
agen: 74 tool; suite ace_mcp 48 tes lulus.

Batch 6 (7 tool, semua baca-saja): arc_rubric,
experiment_designer, cycle_planner_sim, quota_failover_sim,
specialization_delta, writeback_diagnose, constitution
dilemma validate. Total permukaan agen: 81 tool; suite
ace_mcp 50 tes lulus.

Batch 7 (6 tool, semua baca-saja, dari kelas A triase):
bundle_manifest_check, organ_forensics, autobiography
suite + grade, cover_check, pattern_catalog. Total
permukaan agen: 87 tool; suite ace_mcp 52 tes lulus.

Batch 8 (6 tool, semua baca-saja): curriculum_lab (terakhir
kelas A triase) + paket code/ pertama — ace_conformal
(kuantil), ace_pac_bayes (tiga batas), ace_game_theory
(nash gap), ace_indo_nlp (kueri arti + parse pengajaran).
Total permukaan agen: 93 tool; suite ace_mcp 55 tes lulus.
Pola _pkg_tool membuka 63 paket code/ lain untuk batch
berikutnya per era.

Batch 9 (4 tool, semua baca-saja, paket code/): ace_causal
d-separation, ace_epistemic entropi, ace_selfmodel metrik
kalibrasi, ace_report laporan mobile Bahasa Indonesia.
Total permukaan agen: 97 tool; suite ace_mcp 58 tes lulus.

Batch 10 (3 tool, paket ace_evaluator): integritas kandidat
(deteksi pola curang pada kode), seed evaluasi tersegel,
pembangkit instans keluarga tugas. Total permukaan agen:
100 tool; suite ace_mcp 60 tes lulus.

Batch 11 (4 tool, semua baca-saja): validasi skema misi
(ace_mission), verifikasi receipt patch (ace_code_agent),
skor Brier + ECE (ace_self_dev). Total permukaan agen:
104 tool; suite ace_mcp 62 tes lulus.

Batch 12 (3 tool, semua baca-saja): status penyegelan OS +
audit AST kandidat (ace_host_controller), partisi awalan
beranggaran node (ace_research_discovery). Total
permukaan agen: 107 tool; suite ace_mcp 64 tes lulus.

Batch 13 (5 tool, semua baca-saja): evaluator ter-anchor
ace_software_factory — hakim acceptance (setiap kriteria
perlu tepat satu aturan + satu observasi cocok), tren mutu
bench lintas run, simulator lifecycle pembayaran fiktif
(konservasi saldo terverifikasi), evaluasi feature flag
(bucketing hash stabil, fail-closed), dan evaluasi uptime
(slot tanpa bukti menurunkan batas bawah). Catatan desain:
fungsi-fungsi ini menerima pasangan (plan, expected) dengan
expected = sha256 JSON kanonis plan; bridge menghitung
anchor dari plan yang dipasok pemanggil, jadi yang
divalidasi adalah konsistensi internal + logika paket —
bukan kustodi eksternal atas plan (pada CLI paket, operator
memberi --expect-sha256 dari saluran terpisah). Total
permukaan agen: 112 tool; suite ace_mcp 67 tes lulus.
