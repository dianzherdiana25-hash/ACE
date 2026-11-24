# ACE Orchestrator v3 — Panduan Operasional Multi-Agen, Auto-GitHub, Reels 9:16, & KBM Apps

> Dokumen ini melengkapi [ACE_TOOL_LAYER_GUIDE_v1.md](./ACE_TOOL_LAYER_GUIDE_v1.md) dan [ACE_AGENT_MASTER_PROMPT_v1.md](./ACE_AGENT_MASTER_PROMPT_v1.md) dengan kapabilitas penuh **ACE Orchestrator v3** (`Rp0` tanpa API LLM berbayar, tanpa perlu HTTP tunnel publik).

---

## 1. Prinsip Kerja Utama ACE v3

1. **AI di Mana Pun Adalah Otak & Pekerja ACE — ACE Memegang Memori, Antrean, & Mutu:**
   - ACE mengatur agen lewat **4 pintu zero-API**:
     - **Pintu A — MCP Lokal (`stdio` / loopback HTTP) & Thin CLI** (`antigravity`, `gemini`, `claude`, `codex`, dll. di mesin lokal).
     - **Pintu B — Git Portable Dispatch (`handover/dispatch` ↔ `handover/returns`)** untuk agen AI di cloud sandbox terpisah (seperti Antigravity Cloud VM atau Codex Cloud).
     - **Pintu C — Browser Copy-Paste Relay** untuk AI Web (`ChatGPT Web`, `Gemini Web`, `Muse.ai Web`, `Claude Web`) lengkap dengan **Tool-Request Loop (`type="tool_requests"`)**.
     - **Pintu D — Local Subscribed CLI Bridge** untuk CLI yang sudah login di mesin pemilik (`gemini`, `claude`, `codex`).
2. **Hanya Kualitas Tinggi (`>= 8500 bp` / `85%`) yang Boleh Auto-Merge / Auto-Publish:**
   - Hasil dengan klaim riset tanpa `source_ref` otomatis ditolak (`UNGROUNDED_CLAIMS`).
   - Video Reels di bawah ambang retensi / tanpa MP4 9:16 ber-audio / fakta belum disetujui ditolak (`REJECTED_BELOW_BAR`) dengan detail adegan terlemah (`lowest_proxy_scene`) untuk direvisi.
   - Naskah KBM di bawah `arc_rubric >= 0.85` atau gagal `kbm_qc` ditolak (`REJECTED_BELOW_BAR`).
   - Perubahan kode tanpa tes hijau / melanggar [`docs/UPSTREAM_SOURCES.json`](./docs/UPSTREAM_SOURCES.json) / membocorkan pola secret otomatis ditolak.
3. **Vault Kredensial Terpisah & Anti-CAPTCHA:**
   - Sesi browser Facebook & KBM Apps disimpan lokal di `<workspace>/vault/browser_profiles/` dan kredensial di `<workspace>/vault/credentials.json` (`0600`), **tidak pernah** dikirim ke prompt AI, memori, event log, maupun commit Git.
   - Jika Facebook / KBM menampilkan form login ulang, 2FA, atau CAPTCHA, eksekutor berhenti aman (`WAITING_FOR_OWNER_AUTH`) dengan bukti screenshot.

---

## 2. Menghasilkan Konfigurasi Untuk Semua Agen (`setup`)

```bash
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace setup --vendor all
```

Gunakan `--tool-profile core` pada MCP server atau CLI apabila agen hanya memiliki jendela konteks ringkas (agen dapat mencari semua tool melalui `ace_op_tool_search` dan memanggilnya lewat `ace_op_tool_invoke`):

```bash
PYTHONPATH=code python3 -m ace_mcp.server \
  --workspace ~/.local/share/ace/workspace \
  --transport stdio --read-write --tool-profile core
```

---

## 3. Kebijakan Otonomi Host (`.ace_policy.json`)

Buat berkas `.ace_policy.json` di root repo atau `<workspace>/.ace_policy.json` untuk menyalakan otonomi opt-in (default selalu `false` / `off`):

```json
{
  "git_auto_pr": true,
  "git_auto_merge": true,
  "allow_live_facebook_publish": true,
  "allow_live_kbm_actions": true,
  "publish_mode": "auto",
  "min_quality_score_bp": 8500
}
```

Atau setel cepat via variabel lingkungan untuk Git: `export ACE_GIT_AUTONOMY=merge` (`off | pr | merge`).

---

## 4. Menyiapkan Sesi Login Facebook & KBM Sekali Saja (Live Browser Vault)

Sesuai pilihan pemilik untuk memakai sesi login Facebook langsung via browser nyata:

```bash
# 1. Buka jendela Chromium persisten untuk login akun Facebook pemilik:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace \
  --read-write vault browser-login --venue facebook

# 2. (Opsional) Jika suatu saat juga ingin memakai Meta Graph Page API:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace \
  --read-write vault set-facebook --page-id <PAGE_ID> --page-token <TOKEN>

# 3. Buka jendela Chromium persisten untuk login akun KBM Apps pemilik:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace \
  --read-write vault browser-login --venue kbm

# 4. Cek kesiapan vault (hanya status boolean, tanpa menampilkan rahasia):
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace vault status
```

---

## 5. Menjalankan Alur Kerja End-to-End

### A. Membuat & Menggerakkan Goal DAG
```bash
# Video Reels 9:16 + Upload Facebook Reels:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace --read-write \
  goal create --domain video_reels --title "Reels Tips Produktif" \
  --request "Riset tren topik X, buat video 9:16 skor >=85%, render MP4, dan publish ke Facebook Reels"

# KBM Apps:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace --read-write \
  goal create --domain kbm_apps --title "Update Serial Y" \
  --request "Audit serial Y, tulis bab ber-arc_rubric >= 0.85, cek QC, dan simpan/publish di KBM"

# Otonomi Kode & GitHub Auto-PR/Auto-Merge:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace --read-write \
  goal create --domain code_evolution --title "Perbaikan Parser" \
  --request "Perbaiki modul X dengan tes hijau, cross-review, PR, dan merge saat >=85%"

# Jalankan 1 tick atau nyalakan daemon orkestrator:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace --read-write goal tick <goal_id>
python3 tools/ace_autonomous_daemon.py --mode orchestrator --workspace ~/.local/share/ace/workspace
```

### B. Web Relay Untuk ChatGPT Web / Gemini Web / Muse.ai Web
```bash
# Ekspor prompt siap salin:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace \
  relay export --vendor muse.ai --work-order-id <wo_id>

# Tempel balasan JSON dari AI web ke reply.txt lalu proses:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace --read-write \
  relay ingest --vendor muse.ai --work-order-id <wo_id> --reply-file reply.txt
```
Atau jalankan Web Command Center melalui `python3 code/ace_operational/web_server.py` dan buka drawer **Orchestrator v3** memakai token dari `<workspace>/.ace-web-auth.json`.

### C. Cloud Sandbox VM Dispatch (Git Handover)
```bash
# Ekspor ke handover/dispatch/<wo_id>.json + .md:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace \
  dispatch export <wo_id> --agent-id antigravity-cloud --vendor antigravity

# Ingest & verifikasi otomatis hasil dari handover/returns/<wo_id>.json:
PYTHONPATH=code python3 -m ace_mcp.cli --workspace ~/.local/share/ace/workspace --read-write \
  dispatch ingest handover/returns/<wo_id>.json
```

---

## 6. Menjalankan Seluruh Suite Pengujian ACE v3

```bash
PYTHONPATH=code python3 -m unittest \
  ace_mcp.test_multi_agent_orchestration \
  ace_mcp.test_relay \
  ace_operational.test_quality_gate_engine \
  ace_operational.test_git_ops \
  ace_media_studio.test_reels_pipeline \
  ace_operational.test_connectors \
  ace_operational.test_portable_dispatch_and_verifier \
  ace_operational.test_v3_web_and_cli -v

python3 tools/verify_sources.py
python3 tools/wiring_audit.py --format json
```
