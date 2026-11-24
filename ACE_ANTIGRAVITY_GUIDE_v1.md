# ACE Mengatur Antigravity — Panduan v1

ACE adalah agentic AI-nya: ia memegang antrean tugas, memori jangka
panjang, aturan routing, dan verifikasi. Antigravity adalah salah satu
agen pekerjanya — otak eksternal yang mengambil tugas dari ACE,
mengerjakannya, dan mengembalikan hasil lewat ACE. ACE memang sudah
mengantisipasi pola ini: MissionBus ACE memakai worker bawaan bernama
`worker_antigravity_local`, dan kanal evolusinya
(`evolution_mission_loop.py`) menerbitkan work order tersegel yang
secara eksplisit ditujukan ke "Antigravity, Claude, Codex, Gemini".

Dokumen ini adalah jalur yang sudah terverifikasi dari sisi ACE
(server MCP diuji langsung: 149 tool tersaji lewat stdio).

## 1. Topologi v1 (satu mesin)

Antigravity berjalan di komputer pemilik. Karena itu untuk v1, clone
repo ACE dan workspace ACE juga berada di komputer yang sama:

- Clone repo ini, misalnya ke `~/ACE`.
- Buat direktori workspace agen di luar repo, misalnya `~/ace-workspace`
  (di sinilah ACE menyimpan store tugas, memori kognitif, dan receipt).
- Antigravity membuka clone ACE sebagai workspace proyeknya.

Lintas mesin (Antigravity di satu komputer, runtime ACE di komputer
lain) belum diaktifkan — itu keputusan penundaan pemilik; server ACE
sebenarnya sudah punya transport HTTP, tetapi panduan ini tidak
mengandalkannya.

## 2. Daftarkan ACE sebagai MCP server di Antigravity

Antigravity mendukung MCP. Buat berkas `.agents/mcp_config.json` di
dalam clone ACE (berlaku untuk workspace ini), atau tambahkan entri
yang sama ke konfigurasi global `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "ace": {
      "command": "python3",
      "args": [
        "-m", "ace_mcp.server",
        "--workspace", "/PATH/ABSOLUT/KE/ace-workspace",
        "--read-write"
      ],
      "env": {
        "PYTHONPATH": "/PATH/ABSOLUT/KE/ACE/code"
      },
      "cwd": "/PATH/ABSOLUT/KE/ACE"
    }
  }
}
```

Catatan:

- Ganti ketiga path absolut dengan lokasi nyata di komputer pemilik.
- `--read-write` adalah opt-in operator ACE sendiri: tanpa flag ini
  server hanya menyajikan tool baca. Dengan flag ini Antigravity bisa
  membuat tugas, mengambil work order, menulis memori, dan mengirim
  hasil — semua tercatat sebagai event store atas nama agennya.
- Setelah konfigurasi disimpan, mulai ulang Antigravity; tool ACE
  muncul sebagai `ace_op_*` (149 tool: 21 operasional + 122 toolbox +
  6 riset, per batch 21).

## 3. Protokol kerja agen (tempel ke instruksi agen Antigravity)

```text
Kamu bekerja UNTUK ACE lewat tool MCP ace_op_*. Identitas agenmu
selalu "antigravity" pada setiap pemanggilan tool tulis.

Putaran kerjamu:
1. ace_op_task_list — lihat antrean. Ambil tugas QUEUED yang memiliki
   work order (itu tugas yang didelegasikan ACE kepadamu). Tugas tanpa
   work order bukan milikmu kecuali pemilik memintanya langsung.
2. ace_op_work_order_create (bila belum ada) dengan idempotency_key
   unik, lalu kerjakan tujuan tugasnya di repo/workspace.
3. Simpan fakta awet ke ace_op_memory_remember (kind episodic,
   agent "antigravity") — ACE yang mengingat lintas agen dan sesi.
4. ace_op_work_order_submit dengan hasil + bukti (path berkas, commit,
   keluaran tes). Status verifikasi hasilmu mulai UNVERIFIED; jangan
   pernah menyatakan pekerjaanmu sendiri terverifikasi — ACE yang
   memverifikasi.
5. Mentok atau menemukan kekurangan tool/skill: ace_op_gap_report.
   Gap-mu menjadi antrean perbaikan ACE, bukan catatan hilang.
6. Selesai: ace_op_task_update_status hanya setelah submit diterima.
```

## 4. Bagaimana ACE "mengatur" Antigravity

- **Antrean milik ACE.** Tugas hidup di OperationalStore ACE, bukan di
  sesi Antigravity. Sesi boleh mati; tugas, memori, dan receipt tetap.
- **Aturan routing (commit 880ee4ff).** Engine otonom ACE TIDAK
  mengeksekusi tugas yang memiliki work order — tugas itu milik agen
  eksternal. Engine mencatat keputusannya sebagai event
  `task_routed_to_agent`. Ini mencegah ACE mensertifikasi pekerjaan
  template sebagai pengganti tujuan tugas yang sebenarnya.
- **Verifikasi fail-closed.** Hasil work order mulai UNVERIFIED.
  Receipt hanya lahir dari jalur eksekutor ACE yang receipted; agen
  tidak bisa mencetak receipt lewat tool.
- **Memori lintas agen dengan provenans.** Tulisan Antigravity tercatat
  sebagai provenans external/"antigravity", terpisah dari tulisan
  Claude atau agen lain; agen berikutnya membaca memori yang sama.
- **Gap menjadi pekerjaan.** Kekurangan yang dilaporkan agen masuk
  store ACE sebagai gap ter-fingerprint (dedupe otomatis) dan menjadi
  bahan antrean perbaikan berikutnya.

## 5. Pintu kedua: work order berkas (tanpa MCP)

Untuk tugas evolusi repo, ACE juga menerbitkan
`EVOLUTION_WORK_ORDER.json` + `.md` yang tersegel hash oleh
PassiveEvolutionPlanner; Antigravity mengerjakan patch-nya di repo,
dan EvolutionPatchVerifier memverifikasi secara fail-closed sebelum
hasilnya diterima sebagai proof pheromone + writeback memori. Jalur ini
cocok bila MCP belum dikonfigurasi.

## 6. Batas yang jujur

- Arah ACE → Antigravity bersifat **tarik (pull)**: Antigravity bukan
  server, jadi ACE tidak bisa membangunkannya; Antigravity mengambil
  tugas saat ia aktif. (Arah dorong ACE → agen saat ini hanya berjalan
  ke agen yang terhubung ke brain bridge ACE.)
- Panduan ini tidak mengubah status ilmiah ACE (NOT_ASSESSED /
  BLOCK_RELEASE). Yang berubah adalah siapa yang mengerjakan tugas:
  agen eksternal, di bawah pengaturan ACE.
- Agen lain (Claude, ChatGPT, Gemini, Codex) memakai pintu yang sama:
  satu inti layanan, banyak agen. Mengganti agen tidak mengganti ACE.
