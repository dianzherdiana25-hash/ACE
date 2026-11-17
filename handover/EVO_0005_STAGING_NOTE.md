# EVO 0005 — Staging Note (Ian, 2026-11-16)

- Basis: main @ d66aba6 (origin/main terkini; garis
  self-dev engine menekan commit risetnya sendiri ke main
  pada 16 Nov — tercatat apa adanya) + mesin Tahap 2 di
  PR #246 (draft, branch feat/ace-ratification-loop-20261116,
  head 9eb25156): modul ratification_loop + langkah engine
  bergate env ACE_RATIFICATION_LOOP=1.
- Korpus: handover/EVO_0005_CORPUS_V1.jsonl — 16 episode
  (latih tr-code-001..004 + tr-lang-001..004; held-out
  ho-code-001..004 + ho-lang-001..004), task_kind persis
  "code"/"language", disjoint dari korpus 0003/0004.
  sha256: 3cbbf5fc0412de0c444d8eae2d150ff03b658164ab37a5ccb3c32a3c9c3b68eb
- Instrumen: ratification_loop (semantik identik instrumen
  v2 yang terukur di 0003/0004). Konteks AFTER diambil dari
  memory_writeback.recall_context atas store SALINAN
  akumulasi (bukan store live); konteks SHAM = ringkasan
  record dari famili latih yang TIDAK teratifikasi /
  teks netral sama panjang (dibangun dari hasil akumulasi
  aktual, dicatat di hasil).
- N: episode latih yang muat malam ini (maks 8), dicatat
  apa adanya; gerbang TIDAK_BERJALAN_AKUMULASI_KOSONG bila
  n_acc = 0.
- Rumah ukur: sandbox; engine live dijeda selama jendela
  ukur 0005 (pola 0004), hidup lagi sesudahnya.
- Urutan lengan: BEFORE (held-out, tanpa konteks) →
  AKUMULASI (latih via loop ter-wire ke store salinan) →
  AFTER-AKUMULASI → AFTER-SHAM.
