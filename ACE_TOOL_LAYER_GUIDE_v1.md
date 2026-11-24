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
