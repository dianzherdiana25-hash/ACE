# ACE Ω — Addendum 13, 2026-11-12: Fase 2 Dibuka — Siklus Pertama Direktur Riset Lokal

Fase 1 dinyatakan tuntas oleh direktur program berdasarkan Addendum
12; syarat pemilik untuk Fase 2 terpenuhi dan Fase 2 resmi dibuka.
Dokumen ini mencatat tahap 1 Fase 2: loop Direktur Riset lokal
terkecil yang terverifikasi ujung-ke-ujung.

## Yang dibangun (PR #115, draft, bertumpuk di atas #114)

`code/ace_operational/director_loop.py` — loop observe → prioritise →
assign dengan Qwen3-8B Q4_K_M sebagai direktur *penasihat*:

- **Observasi**: ObservationPacket disusun hanya dari artefak nyata
  (status gerbang, gap terbuka, hasil terukur, recall memori).
- **Prioritisasi fail-closed**: balasan model wajib satu objek JSON
  sesuai skema + kosakata kategori tetap; pelanggaran apa pun —
  struktur, kategori liar, nilai di luar rentang, atau kutipan fakta
  yang tidak ada di observasi — menolak SELURUH balasan dan mencatat
  penolakannya. Peringkat akhir dihitung ulang harness secara
  deterministik (value, effort, judul), bukan urutan model.
- **Assign = mencatat, tidak mengeksekusi**: proposal yang diterima
  ditulis ke memori kognitif OMEGA-07 sebagai record episodik
  bersumber-model (tebakan menurut konstruksi; tidak dapat menggeser
  fakta berbasis bukti) dan ke berkas agenda append-only. Duplikat
  lintas siklus dibuang.
- **Pelajaran THINKING_BUDGET diterapkan**: prompt memakai mode ringkas
  `/no_think` dengan batas token keluaran eksplisit.
- Server lokal on-demand saja (start → siklus → stop); kegagalan
  direktur tidak menghentikan jalur utama.

## Siklus live pertama (evidence: director_cycle1.json, director_agenda.json)

Masukan: status Fase 1 yang sebenarnya (16 fakta: 7 gerbang, 5 gap,
4 hasil). Server sehat, satu panggilan, **438,6 detik** generasi di VM
ini, server dimatikan sesudahnya (terverifikasi tidak ada proses
tersisa). Hasil: **ACCEPTED — 5 proposal valid**, semua mengutip id gap
nyata dari observasi; 5 record memori tertulis sebagai tebakan model.

Agenda hasil peringkat harness:
1. Melakukan Pilot A/B/C PRD untuk Evaluasi G1 (experiment, 5/4)
2. Mengatasi Blokir Lingkungan untuk OMEGA-05 (engineering, 5/4)
3. Memverifikasi Kinerja Keluarga Tugas Shipping (measurement, 4/3)
4. Menggabungkan Tumpukan PR yang Tersisa (engineering, 4/3)
5. Menyelesaikan Keputusan Unduhan Parsial Model 14B (engineering, 4/3)

Catatan jujur atas isi: prioritasnya masuk akal dan berpijak pada
fakta, tetapi rationale model sebagian besar memparafrasekan teks gap
— agenda penasihat yang berguna, bukan analisis mendalam. Dua dari
lima proposal (merge tumpukan, keputusan 14B) adalah kategori
*reserved pemilik*: loop benar mengusulkannya sebagai agenda, dan
loop juga benar tidak mengeksekusinya.

Sapuan paket penuh di branch Fase 2: **193 test OK (10 skip)**.

## Langkah berikutnya dalam Fase 2

Item agenda yang berada dalam mandat dan lolos gerbang bukti akan
diambil sebagai tahap kerja berikutnya oleh pelaksana, dimulai dari
yang dapat dikerjakan tanpa keputusan reserved: pengukuran keluarga
shipping (mengapa lemah) dan desain pilot A/B/C kustodi penuh.
