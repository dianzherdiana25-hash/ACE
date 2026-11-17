# RANCANGAN — Jalur Tulis Engine → Ingatan Kognitif
## (Audit penyerapan PR #231, butir #8 — rancangan dulu, hub menilai)

Status: RANCANGAN, belum dibangun. Ditulis Ian 2026-11-15.

## 0. Penutupan item PROVISIONAL audit (keluaran lab/practice)

Lokasi DITEMUKAN: `/workspace/ace-workspace/projects/
learning_lab/` di sandbox (70 berkas, 392 KB) — sapuan
pertama melewatkannya karena direktori itu milik ubuntu
dengan izin 700 dan daftar `ls` terpotong. Isi: kurikulum
bahasa (6 target: analisis_sentimen, ekstraksi_waktu,
slang_normalizer, morfologi_imbuhan, ringkas_teks,
evaluasi_dialog) + teknis (target kurikulum + berkas
practice_cycle_NNN.py per siklus). Klasifikasi FINAL:
**(c) sebagai kode** — berkas-berkas itu tidak diimpor
kode produksi mana pun; nilai belajarnya mengalir lewat
alur lab → verifikasi + receipt → registri skill di DB
operasional (ace_operational.sqlite3), bukan lewat berkas
kodenya. Register inventarisnya ada di PR #231.

## 1. Masalah

Isi ingatan kognitif ACE (mission 0002) berhenti di 2
entri seed operator. Sementara itu ACE menghasilkan
keluaran terverifikasi setiap hari — skill terverifikasi
dengan receipt, vonis tersegel, misi ter-ratifikasi,
perbaikan temuan HIGH — dan TIDAK SATU PUN ditulis ke
ingatan itu. Mesinnya ada dan terbaca (ConversationalEngine
+ Web Studio lewat memory_bridge); yang hilang hanya
jalur tulis dari sisi engine.

## 2. Mesin yang sudah ada (tidak perlu store baru)

`code/ace_operational/cognitive_memory.py` —
`CognitiveMemory`:
- `remember(kind, content, source_kind, source_ref,
  confidence, sensitivity, ...)` → id turunan-konten;
  menulis ulang konten yang sama mengembalikan id yang
  sama (idempoten by construction — aman dari replay).
- KINDS = episodic | semantic | procedural;
  SOURCE_KINDS = evidence | operator | external | model.
- source_kind="evidence" WAJIB jangkar:
  `anchor_evidence(bytes)` harus dipanggil dulu dan
  source_ref harus digest yang terjangkar (fail-closed
  ProvenanceError). Ada penjaga kontaminasi (canary) dan
  resolusi konflik semantik (supersede).
- `record_outcome(record_id, context, success)` untuk
  umpan-balik hasil; `recall(query, kinds)` untuk baca;
  `audit()` untuk integritas rantai hash.

## 3. Yang layak ditulis (write set — hanya yang terverifikasi)

| Peristiwa | kind | Bukti wajib | confidence |
|---|---|---|---|
| Skill terverifikasi di lab/engine | procedural | receipt id + digest artefak | 0.90 |
| Vonis tersegel / ratifikasi (mis. GUARD_ADOPTED) | semantic | sha akta/PR + digest paket bukti | 0.95 |
| Misi selesai ter-ratifikasi | episodic | spore/order sha | 0.95 |
| Temuan backlog HIGH dibuka / ditutup | episodic | finding_key + PR perbaikan | 0.90 |

BUKAN untuk ditulis: tick siklus, keluaran practice,
generasi tak terverifikasi, skor di bawah gerbang,
payload mentah apa pun. Isi record = ringkasan satu-dua
baris + id/digest bukti — bukan artefaknya sendiri.

## 4. Penempatan penulis

Satu helper tipis `memory_writeback` di ace_operational,
dipanggil di titik peristiwa itu terjadi (penerbitan
receipt verifikasi skill; penutupan ratifikasi di
evolution_mission_loop; pencatatan vonis) — tulis pada
waktu peristiwa, BUKAN daemon pengais berkala. Urutan
per tulis: baca artefak → `anchor_evidence(bytes)` →
`remember(source_kind="evidence", source_ref=digest)`.
Store yang dibuka = root yang sama dengan yang dibaca
bridge (`ace-workspace/cognitive_memory`); satu proses
penulis pada satu waktu (engine live adalah penulisnya;
perkakas Ian tetap read-only terhadap store itu).
Kegagalan tulis (Provenance/Contamination/MemoryError)
WAJIB tercatat di log — tidak boleh except-pass
(rujuk PR #234).

## 5. Sisi baca (agar menulis bukan menimbun)

Satu penggunaan baca konkret sebagai syarat penerimaan:
sebelum siklus perbaikan dimulai, engine memanggil
`recall()` atas konteks kegagalan saat ini (error_type /
domain) dan mencatat record mana yang dipakai; hasil
perbaikan ditutup dengan `record_outcome()` pada record
itu. Tanpa loop ini, jalur tulis ditunda.

## 6. Tes penerimaan untuk build-nya nanti

1. Peristiwa skill-terverifikasi menulis tepat 1 record
   procedural dengan source_ref = digest terjangkar.
2. Replay peristiwa yang sama → 0 record baru (id sama).
3. Vonis semantik baru men-supersede vonis lama yang
   bertentangan (status lama tergantikan, rantai utuh).
4. Tulis tanpa jangkar bukti → ProvenanceError, store
   tidak berubah.
5. Dua entri seed operator tetap utuh; `audit()` lolos
   sesudah semua tulis di atas.

## 7. Pertanyaan terbuka untuk hub

1. Penulis di dalam engine lini Antigravity, atau mulai
   dari titik ratifikasi/vonis yang dikendalikan Ian+hub
   dulu (lebih aman; receipt-skill menyusul)? Usul Ian:
   mulai dari titik ratifikasi — 3 dari 4 kelas peristiwa
   di tabel §3 memang lahir di sana.
2. Retensi: record episodic diberi expires_after_events
   atau dibiarkan permanen sampai ada kebijakan lupa?
   Usul: permanen untuk semantic/procedural; episodic
   ditinjau sesudah 30 hari berjalan.
