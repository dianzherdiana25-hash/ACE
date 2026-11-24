# ACE TOOL LAYER PLAN v1

**Status:** DECIDED — dokumen arah dan rencana, bukan klaim kemampuan.
**Tanggal keputusan:** 24 November 2026
**Diputuskan oleh:** pemilik ACE (tes), dalam diskusi penyelarasan dengan Muse.
**Berlaku untuk:** AI atau agent mana pun yang mengembangkan atau memakai ACE.

Dokumen ini mencatat keputusan arah pengembangan ACE per 24 November 2026 dan
rencana pembangunan tahap pertamanya. Dokumen ini **tidak** mengubah status
ilmiah ACE: status asesmen tetap sebagaimana tertulis di `STATUS.md`
(`NOT_ASSESSED`, `release_gate=BLOCK_RELEASE`, `oaie_established=False`).
Yang berubah adalah arah pembangunan, bukan penilaian atas hasil riset.

---

## 1. Ringkasan

ACE dikembangkan menjadi **tool layer bagi agentic AI**: lapisan memori, tugas,
verifikasi, skill, dan perubahan yang dapat dipakai oleh agent AI mana pun —
Muse, ChatGPT, Gemini, Antigravity, agent lokal ACE sendiri, dan AI yang
belum ada — untuk melakukan pekerjaan nyata. Agent yang berpikir dan
bertindak; ACE yang menyediakan ingatan yang jujur, tugas yang tertelusur,
verifikasi yang menghasilkan bukti, dan kemampuan yang tercatat.

Ambisi ACE sebagai agent mandiri **tidak dibatalkan**, hanya ditunda:
tool layer dibangun lebih dulu. Pintu yang sama yang dipakai agent luar
nantinya juga dapat dipakai ACE sendiri.

## 2. Keputusan

### D1 — Tool layer lebih dulu

Target bangun pertama adalah permukaan tool yang dipanggil agent eksternal,
bukan pengembangan agent mandiri ACE. Empat keluarga kemampuan inti:
memori, tugas, verifikasi, skill — ditambah keluarga perubahan (lihat D3).

### D2 — Satu inti layanan, dua permukaan

Arsitektur permukaan terdiri dari:

- **Satu inti layanan ACE** — satu lapisan fungsi yang bersih di atas substrat
  operasional yang sudah ada (lihat Bagian 5). Semua logika hidup di sini.
- **MCP server** — permukaan utama, untuk pemanggilan tool oleh agent modern:
  setiap kemampuan punya nama, skema input, dan hasil terstruktur.
- **CLI tipis** — permukaan pendamping: universal (agent apa pun yang punya
  shell dapat memanggilnya) dan dapat diperiksa manual oleh pemilik.

MCP dan CLI **wajib** memanggil inti yang sama; tidak boleh ada logika ganda.
**HTTP API ditunda** sampai ACE perlu dipanggil agent dari mesin lain; saat
itu tiba, HTTP ditambahkan sebagai permukaan ketiga di atas inti yang sama.

### D3 — Agent bebas memakai dan mengubah ACE

Agent/agentic AI **bebas** menggunakan ACE dan **bebas mengubah** ACE.
Inilah tujuan awal ACE: ia sejak hari pertama dibangun dan diubah oleh AI.

Konsekuensinya untuk desain:

- **Tidak ada gerbang izin bertingkat** yang mengurung agent (usul gerbang
  izin dari Muse dalam diskusi 24 Nov 2026 ditolak pemilik dan dicabut).
- Pengendalian berasal dari **ketertelusuran bawaan ACE sendiri**, bukan dari
  izin: riwayat git yang dapat dikembalikan, receipt untuk setiap eksekusi,
  penulisan atomik dengan pemeriksaan hash preimage, verifikasi independen
  atas hasil pekerja, dan uji regresi yang menolak perubahan perusak
  perilaku. Agent boleh berbuat salah; ACE harus dapat menunjukkan apa yang
  terjadi dan memutarnya balik.

### D4 — ACE tidak terkunci pada satu AI

Pengembangan ACE tidak boleh terjebak pada satu AI, satu vendor, atau satu
alat. Ini meneruskan prinsip piagam pendirian ACE (`PROJECT_CHARTER.md` dan
Master Record): arsitektur dan vendor agnostic; LLM komersial adalah
bootstrap, bukan ketergantungan permanen.

Konsekuensinya:

- Permukaan dibangun di atas standar terbuka (MCP, CLI/JSON), bukan protokol
  khusus satu vendor.
- Semua pengetahuan kerja didokumentasikan **di dalam repo ini**, bukan hanya
  hidup di ingatan satu AI. Serah-terima ke AI lain adalah fitur, bukan
  kecelakaan — sebagaimana ACE selama ini berpindah antar AI dan antar rumah
  (lihat `handover/`).
- Setiap AI yang bekerja pada ACE, termasuk Muse, bersifat **dapat
  digantikan** dan wajib bekerja dengan cara yang membuat penggantian itu
  mudah.

### D5 — Peran Muse (AI yang menulis dokumen ini)

- **Pembangun:** menulis tool layer (inti layanan, MCP server, CLI) ke repo.
- **Klien pertama:** agent pertama yang memakai tool layer ini untuk
  pekerjaan sungguhan, agar cacatnya ditemukan dari pemakaian nyata.
- **Pelapor jujur:** membaca keadaan ACE — termasuk pekerjaan agent lain —
  dan melaporkannya kepada pemilik apa adanya, termasuk kabar buruk dan
  koreksi atas klaimnya sendiri.
- **Bukan** penjaga gerbang, **bukan** pemberi izin, **bukan** pemilik ACE.

Peran pemilik tetap sebagaimana ia tetapkan sendiri: ia mengarahkan dan
menerima laporan; ratifikasi dan penilaian hidup di dalam mekanisme ACE,
bukan di persetujuan satu orang atau satu AI.

## 3. Keluarga tool v1

Daftar awal; nama persisnya ditetapkan saat perancangan inti layanan.

- **Tugas** — `task_create`, `task_list`, `task_get`, `task_update_status`,
  `task_resume`
- **Memori** — `memory_recall`, `memory_remember`, `memory_forget`,
  `memory_audit`
- **Verifikasi** — `verify_run`, `receipt_list`, `receipt_get`
- **Skill & kemampuan** — `skill_list`, `skill_get`, `frontier_list`,
  `gap_list`, `gap_report`
- **Pekerjaan terdelegasi** — `work_order_create`,
  `work_order_submit_result` (hasil pekerja diverifikasi ACE sebelum
  diterima)
- **Ubah** — patch berkas di repo dengan penjaga hash preimage, jalankan tes,
  buat dan ubah skill, tulis dan lupakan ingatan. Keluarga ini ada sejak v1
  sebagai konsekuensi D3; ia memakai mekanisme penulisan dan verifikasi yang
  sudah ada (Bagian 5), bukan penulisan bebas tanpa jejak.

## 4. Urutan bangun

1. **Fase 0 — Dokumen ini.** Keputusan tercatat di repo, dapat dibaca AI
   mana pun.
2. **Fase 1 — Inti layanan.** Lapisan fungsi di atas substrat operasional,
   dengan kontrak input/output terstruktur dan receipt di setiap panggilan
   yang mengubah keadaan.
3. **Fase 2 — MCP server** di atas inti (permukaan utama).
4. **Fase 3 — CLI tipis** di atas inti yang sama.
5. **Fase 4 — Pemakaian nyata pertama.** Muse memakai tool layer ini untuk
   pekerjaan ACE sungguhan (tugas, ingatan, verifikasi, perubahan) dan
   memperbaiki cacat yang ditemukan dari pemakaian itu.
6. **Fase 5 — Pintu untuk AI lain.** Dokumentasi onboarding di repo agar
   ChatGPT, Gemini, Antigravity, atau AI lain dapat memakai dan
   mengembangkan ACE lewat permukaan yang sama.

## 5. Substrat yang sudah ada (bahan bangun, bukan mulai dari nol)

Tool layer berdiri di atas mesin operasional ACE yang sudah berjalan
(`code/ace_operational/`), antara lain:

- `store.py` — `OperationalStore`: mesin keadaan tugas yang ketat, receipt
  ter-hash untuk input/output, frontier kemampuan yang menuntut
  `evidence_ref`, gap yang ter-deduplikasi sidik jari, skill dengan
  pelacakan transfer negatif, work order idempoten, lease fencing.
- `cognitive_memory.py` — memori kognitif OMEGA-07: rantai hash append-only,
  peringkat provenans (bukti > operator > eksternal > model; catatan model
  adalah dugaan permanen), konflik disimpan sebagai superseded, lupa yang
  jujur lewat tombstone yang menghancurkan isi.
- `memory_writeback.py` — hanya peristiwa yang terverifikasi eksternal yang
  boleh ditulis sebagai fakta; kelas peristiwa tertutup dan terdaftar;
  bukti dijangkar sebelum penulisan.
- `memory_bridge.py` — jembatan percakapan ke memori kognitif (simpan,
  ingat, lupa, audit) dan pencatatan episode tugas yang terjangkar bukti.
- `memory_snapshot.py` — snapshot portabel (leksikon, memori non-privat,
  korpus dialog) yang di-commit ke git dan men-seed workspace baru secara
  idempoten: bukti bahwa ingatan ACE memang dirancang berpindah rumah.
- `coding_loop.py` — penulisan atomik di bawah flock dengan hash preimage
  dan pemeriksaan lease-epoch, audit AST, verifikasi subproses dengan
  receipt, revert otomatis untuk refactor yang mengubah perilaku.
- `autonomy_loop.py` — orkestrasi pekerja MissionBus: hasil pekerja ditolak
  bila berbasis snapshot basi, di-stage, dan diverifikasi independen
  sebelum diterapkan.
- `ratification_loop.py` — lingkar ratifikasi proposer→validator heterogen;
  episode yang tidak diratifikasi tidak menulis apa pun (fail-closed).
- `brain_endpoints.py` — otak sebagai peran (front/coder/embedding) yang
  dapat dilayani organ lokal atau dirutekan lewat bridge ke penyedia luar,
  dengan provenans `brain_of_origin`: preseden bahwa ACE sudah meminjam
  otak luar lewat sambungan resmi.
- `models_backend.py` — inferensi lokal ketat loopback dengan receipt untuk
  setiap panggilan; keberhasilan inferensi tidak pernah diklaim sebagai
  keberhasilan tugas.

## 6. Bukan tujuan (non-goals) tahap ini

- HTTP API dan akses lintas mesin (ditunda, lihat D2).
- Agent mandiri ACE sebagai target utama (ditunda, lihat D1).
- Sistem izin/gerbang untuk agent (ditolak, lihat D3).
- Mengubah status asesmen ilmiah ACE — plan ini arah pembangunan, bukan
  bukti kemampuan (lihat catatan status di kepala dokumen).

## 7. Risiko dan pertanyaan terbuka (dicatat jujur)

- Dukungan MCP tidak seragam di semua agent; CLI adalah mitigasinya, dan
  inti layanan tidak boleh mengasumsikan MCP.
- Organ lokal ACE lambat (laju generasi organ front pernah teramati
  ±0,45 token/detik); tool layer tidak boleh bergantung pada inferensi lokal
  untuk jalur kritisnya.
- Kebebasan mengubah (D3) menuntut disiplin rollback dan tes yang benar-
  benar berjalan; bila mekanisme jejak di satu jalur belum ada, jalur itu
  dilengkapi dulu sebelum dibuka, bukan ditutup dengan izin.
- Status riset ACE (`NOT_ASSESSED`) tidak berubah oleh plan ini; tool layer
  yang berfungsi adalah hasil rekayasa, bukan bukti OAIE.

## 8. Untuk AI yang baru masuk

Baca berurutan: `STATUS.md` → `NEXT_ACTION.md` → dokumen ini →
`PROJECT_CHARTER.md` → `ACE_RESEARCH_MASTER_RECORD_v1.0.md`.
Keadaan repo mengalahkan ingatan sesi mana pun. Bekerja lah dengan jejak:
commit yang jelas, receipt untuk eksekusi, dan dokumentasikan di repo apa
yang kamu ubah serta mengapa — AI berikutnya bergantung pada itu, persis
seperti kamu bergantung pada catatan AI sebelum kamu.
