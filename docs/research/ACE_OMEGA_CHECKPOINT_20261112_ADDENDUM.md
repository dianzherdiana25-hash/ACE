# ACE Ω — Addendum Checkpoint 2026-11-12 (Fase 1, lanjutan sesi yang sama)

Addendum untuk `ACE_OMEGA_CHECKPOINT_20261112_MUSE.md`. Urutan kerja sesuai
keputusan pemilik: Fase 1 dikerjakan langsung oleh Muse; model lokal bukan
gerbang. Otomatisasi Research Director adalah Fase 2, belum dimulai.

## 1. Perbaikan OMEGA-01 — draft PR #107

Ditemukan saat verifikasi live, diperbaiki sebagai kode + test
(branch `research/ace-omega-router-provenance-20261112`, bertumpuk di atas #104):

1. **GGUF terpotong lolos sebagai model valid.** `discover_local_gguf` hanya
   memeriksa magic 4 byte, sehingga unduhan parsial 1.520.062.464 byte dari
   model 7.321.313.312 byte terdaftar sebagai kandidat inferensi sah.
   Discovery kini mem-parse header GGUF, menghitung ukuran total yang
   dideklarasikan tata letak tensor, dan menolak ketidakcocokan ukuran ke
   `corrupted_models`. Field receipt/discovery baru: `size_verified`,
   `expected_size_bytes`.
2. **Budget thinking habis di dalam reasoning** (finish_reason `length`,
   konten kosong) kini dilaporkan sebagai `THINKING_BUDGET_EXHAUSTED`,
   bukan `SERVER_INFERENCE_FAILED` generik. Tetap kegagalan; tidak ada
   keluaran yang dikarang.

Bukti: 5 test baru (`test_gguf_integrity.py`) lulus; suite fokus lama 51 test
tetap lulus (10 skipped). Discovery live terhadap cache model nyata:
Qwen3-8B Q4_K_M dan Qwen2.5-Coder-3B `size_verified=true`; parsial
Qwen3-14B Q3_K_M ditolak — `gguf_size_mismatch expected=7321313312
actual=1520062464` (nilai expected dihitung dari header file dan cocok
dengan content-length penerbit).

## 2. Evaluasi OMEGA-02 — retriever repo ACE

Subjek: `ace_code_agent.repo_retrieval.BoundedRepositoryRetriever` (dari #99)
di repo ini, di VM operator. Evidence mentah:
`evidence/omega02_retrieval_eval.json`.

- Indeks: 402 file, 4.026 simbol, terbangun dalam 3,69 detik.
- Query known-item (jawaban benar ditetapkan independen via grep):
  **hit@1 = 4/5, hit@5 = 5/5**.
- Satu-satunya miss di rank-1 (`CONFIRMED_SEALED`): retriever menempatkan
  `ace_evaluator/test_sealed_evaluator.py` di atas file ground-truth grep
  (`ace_core_repair/doctor.py`, tetap masuk top-5) — secara semantik hasil
  retriever dapat dipertahankan; dicatat apa adanya, tidak diskor ulang.
- Probe bahasa natural Bahasa Indonesia (tidak diskor): hasil teratas
  `ace_operational/coding_loop.py`. Retrieval simbol/token bekerja baik;
  retrieval semantik bahasa natural lemah — tidak ada lapisan semantik.
  Klaim "hybrid" pada paket ini harus dibaca dengan batas tersebut.

## 3. Agenda Research Director — evidence apa adanya

Dua percobaan panggilan agenda ke Qwen3-8B Q4_K_M:

- Percobaan 1 hilang: server dibunuh OOM setelah ±53 menit (exit 137) —
  tercatat sebagai batas host; pola operasi server lokal di VM ini harus
  on-demand, bukan daemon permanen.
- Percobaan 2 selesai (500 token, 2,45 tok/s) tetapi JSON keluarannya rusak
  pada karakter ±197 (kemungkinan terpotong di tengah string karena mode
  thinking menghabiskan budget token). Respons mentah disimpan di
  `evidence/director_agenda_raw.json`. Tidak ada agenda yang dipakai sebagai
  arahan kerja dari keluaran yang tidak valid ini.

Status gerbang tidak berubah dari checkpoint utama: G0 PASS (bersyarat
sesi), G1–G5 NOT_ASSESSED. Fase 2 (loop director otomatis) belum dimulai
dan menunggu Fase 1 selesai sesuai keputusan pemilik.
