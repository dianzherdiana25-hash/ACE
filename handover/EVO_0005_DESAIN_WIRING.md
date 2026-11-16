# TAHAP 2 — Desain wiring loop ratifikasi ke cycle engine
## (catatan desain Ian, ditulis 2026-11-16 selama Blok D mengukur;
##  eksekusi sesudah EVO 0004 tutup, sebagai draft PR terpisah)

## Mesin yang ada (main @ f6d75462)

- `ContinuousAutonomousEngine.execute_cycle()` (autonomous_engine.py):
  Step 1 health/GGUF, Step 2 agenda, Step 3 mixed learning
  (hanya bila agenda kosong), Step 4 audit AST tiap 10 cycle,
  Step 5 ringkasan. Cursor persisten via store meta
  (autonomous_cycle_count / lang / tech).
- Loop ratifikasi terukur (EVO 0004 Blok A, instrumen v2):
  pasangan heterogen brain_endpoints.proposer_validator_pair
  → proposer chat_structured → gerbang struktural → judge
  validator chat_structured → ratified.
- Write-back: memory_writeback.record_verified_event(
  memory_root, event="verdict_sealed", ...) — replay-safe,
  kelas terdaftar PR #235.

## Perubahan (kecil di engine, besar di modul baru)

1. **Modul baru `code/ace_operational/ratification_loop.py`:**
   `run_ratification_episode(episode, *, memory_root,
   chat_fn=..., pair_fn=...)` — semantik IDENTIK Blok A
   (prompt, gerbang struktural, token budget, pasangan per
   task_kind). Bila ratified: tulis-balik SATU record
   verdict_sealed (evidence = transkrip episode JSON;
   content_extra = id episode + provenance pasangan).
   Tidak ratified / BrainUnavailable: TIDAK ada write-back,
   hasil terstruktur dikembalikan (fail-closed selaras
   PR #233). Fungsi chat/pair ter-inject agar teruji tanpa
   organ sungguhan.
2. **Engine:** metode `execute_ratification_step()` —
   membaca episode berikutnya dari sumber JSONL
   (workspace/projects/ratification/episodes.jsonl),
   cursor persisten `autonomous_ratification_cursor` via
   store meta (pola cursor yang ada), emit event store,
   kembalikan ringkasan. Di `execute_cycle()`: Step 3b —
   dijalankan HANYA bila env `ACE_RATIFICATION_LOOP=1`
   (default mati: merge perubahan ini tidak mengubah
   perilaku engine live; jendela ukur EVO 0005 yang
   menyalakannya / menggerakkannya langsung).
3. **Tes `test_ratification_loop.py`:** chat_fn palsu —
   jalur ratified menulis tepat satu record kelas benar +
   provenance; jalur validator-menolak tidak menulis;
   BrainUnavailable tidak menulis + error tercatat; gerbang
   struktural gagal tidak menulis. Tes langkah engine:
   workspace tmp + loop palsu → cursor maju, event store
   terbit, sumber habis → langkah no-op bersih.

## Yang TIDAK dilakukan perubahan ini

Tidak menyentuh slate, tidak menyentuh jalur solve solver,
tidak mengaktifkan loop di engine live (gerbang env),
tidak menulis ke store produksi dari tes.
