# EVO 0006 — Staging Note (Ian, 2026-11-16 malam)

- Bahan asal: handover/EVO_0006_BAHAN_INHERITANCE.md
  (PR #249) + diagnosis PR #250 (syarat instrumen §4
  praregistrasi ini menurunkannya menjadi gerbang
  pengantaran + layar kalibrasi).
- Mesin: ratification_loop (PR #246) apa adanya; tidak
  ada perubahan kode untuk misi ini. Jalur recall:
  memory_writeback.recall_context.
- Snapshot store penuh (§2 praregistrasi): dibangun di
  staging lari dari dua sumber baca-saja — store live
  /workspace/ace-workspace/cognitive_memory (2 record,
  dibaca via sudo) + store akumulasi 0005
  (evo0005-stage/out/accum_ws/cognitive_memory,
  10 record) — dedup per id → 10 record unik; berkas
  snapshot + sha256 masuk bukti lari.
- Korpus kandidat: EVO_0006_CORPUS_CANDIDATES_V1.jsonl
  (24 baris, sha256 1d09d590fc370cebbdbe55718daf34a
  79568a1ffa3f32f642903ce029ed3c800).
- Urutan lari: snapshot → layar kalibrasi (24 kandidat
  × 2, kondisi kosong) → bekukan probe set → SEEDED →
  KOSONG (urutan lengan dicatat; KOSONG sesudah SEEDED
  aman karena probe tanpa write-back).
- Perkiraan wall dari laju 0005 terukur: kalibrasi
  48 episode ±3–5 jam terlalu panjang untuk satu
  jendela malam — layar boleh dipecah per-jenis dan
  dilanjutkan dari checkpoint; angka ini dicatat agar
  hub memutuskan bentuk jendelanya saat ratifikasi.
