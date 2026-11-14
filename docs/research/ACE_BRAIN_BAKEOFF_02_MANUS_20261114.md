# Evaluasi Otak Lokal CPU-Only & Manus Bake-Off 02 Probes (2026-11-14)

**Lingkungan terukur:** Manus Sandbox (`2887726280f4`, 8 vCPU Intel Cascade Lake dengan AVX-512/VNNI, ~23.6 GiB / 24,207 MiB RAM, tanpa GPU, tanpa swap), `llama.cpp b12316` (`build 5d4c8eeb2`), `-t 4` (`-c 8192 -fa on -ctk q8_0 -ctv q8_0 --reasoning off`), diukur dalam kondisi **RAM bersih (nol model lain residen)**.

> **Batas Kustodi & Pemisahan Protokol (Penting):**
> Evaluasi ini dijalankan di **Manus Sandbox** (`-t 4`) untuk menjawab pemilihan otak CPU+RAM tercepat dan paling reliabel bagi ACE, **bukan** penutupan resmi run VM-path pada `bakeoff02-kernel` ([`ACE_BAKEOFF_02_PREREGISTRATION_20261113.md`](ACE_BAKEOFF_02_PREREGISTRATION_20261113.md) §3 mengecualikan angka Sandbox dari kernel VM-path).
> Selain itu, **Instrumen C (`Keamanan-01`)** berstatus **`BLOCKED_MISSING_SEALED_EVALUATOR`** karena artefak evaluator tersegel (`security-test/evaluator`, `sha256 6b0610f0...`) tidak ada di Manus Sandbox pasca-rollback — dihilangkan secara jujur tanpa substitusi mock.

---

## 1. Identitas Artefak Terukur (SHA-256)

| Kandidat GGUF | Ukuran File | Params | SHA-256 Terukur di Manus |
|---|---:|---:|---|
| `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | `2.32 GiB` | `4.02 B` | `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` |
| `Qwen3.5-4B-Q4_K_M.gguf` | `2.54 GiB` | `4.21 B` | `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4` |
| `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | `4.58 GiB` | `8.03 B` | `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c` |

Referensi baseline historis di repo:
- `Qwen3-30B-A3B Q4_K_M` (`~16.3 GiB` RSS, `-t 1` baseline resmi Wave 1 di [`SERVING_INTEGRATION_REVIEW_20261114.md`](../../handover/SERVING_INTEGRATION_REVIEW_20261114.md)): `pp512 = 7.96 ± 0.35 t/s`, `tg128 = 2.46 ± 0.10 t/s` (dan pada jendela penuh tertekan: `tg128 = 0.91 ± 0.09 t/s`).
- `Qwen3-8B Q4_K_M` (petahana Bake-off 01 VM-path di [`ACE_BRAIN_BAKEOFF_01_20261113.md`](ACE_BRAIN_BAKEOFF_01_20261113.md)): `B wall = 535.6 s`, `4/4`.
- `Qwen3-4B Q4_K_M` (`7485fe6f...`, ditolak di Bake-off 01 [`bakeoff_result.json`](../../evidence/bakeoff_result.json)): `B = 0/4` (`341.4 s`, memalsukan fact-ID `'nimbus-gate'`).

---

## 2. Benchmark Kecepatan Mentah (`llama-bench -p 256 -n 128 -t 4 -r 3`)

Artefak mentah: [`evidence/bakeoff02_manus/bench_t4.log`](../../evidence/bakeoff02_manus/bench_t4.log).

| Model | Threads | `pp256` (t/s) | `tg128` (t/s) | Rasio `tg128` vs A3B (`2.46 t/s`) |
|---|---:|---:|---:|---:|
| **`Qwen3-4B-Instruct-2507-Q4_K_M`** | `4` | **`34.91 ± 2.08`** | **`7.67 ± 0.14`** | **`3.12x`** |
| `Qwen3.5-4B-Q4_K_M` | `4` | `33.72 ± 3.13` | `5.00 ± 0.35` | `2.03x` |
| `Meta-Llama-3.1-8B-Instruct-Q4_K_M` | `4` | `19.62 ± 0.59` | `3.38 ± 0.22` | `1.37x` |

Temuan hardware CPU+RAM:
- Dengan ukuran `2.32 GiB` (sekitar 12.5% footprint A3B `18.56 GiB`), `Qwen3-4B-Instruct-2507-Q4_K_M` menyisakan `>19 GiB` RAM bebas di Manus dan menggandakan throughput token generasi hingga **7.67 t/s** (**2.27x** lebih cepat daripada `Meta-Llama-3.1-8B-Instruct` dan **1.53x** lebih cepat daripada `Qwen3.5-4B`).

---

## 3. Evaluasi Instrumen Fungsional ACE (A + B Vanilla + B Whitelist Schema)

Menggunakan modul persis dari repo (`DirectorLoop`, `validate_reply`, `b2a_market.validate_decision`, `b2a_market.score_decision`, `CognitiveMemory`) pada konfigurasi router `temperature=0.3`, `max_tokens=700`, `timeout=900s`:

### Ringkasan Hasil

| Model | Instrumen A (`DirectorLoop`) | Instrumen B Vanilla (`B2A-02`) | Instrumen B Whitelist Schema (`#146 §5(a)`) | Instrumen C (`Keamanan-01`) |
|---|---|---|---|---|
| **`Qwen3-4B-Instruct-2507-Q4_K_M`** | **ACCEPTED** (`5/5` usul, `0` ditolak, `176.12s`, `700` tok @ `5.02 t/s`) | **`4.0 / 4.0`** (`semantic_correct_4_of_4 = True`, `0` pelanggaran sitasi, `190.00s`, `355` tok) | **`4.0 / 4.0`** (`semantic_correct_4_of_4 = True`, `0` pelanggaran sitasi, `78.32s`, `cache_n=1679`) | `BLOCKED_MISSING_SEALED_EVALUATOR` |
| `Qwen3.5-4B-Q4_K_M` | **ACCEPTED** (`5/5` usul, `0` ditolak, `96.38s`, `449` tok @ `4.77 t/s`) | **`0.0 / 4.0`** (ditolak fail-closed: menyitir `["[criteria-gate]", "[criteria-bounds]", "[criteria-score]"]` dengan tanda kurung siku; meski disposisi semantik 4/4, `29.95s`) | **`3.0 / 4.0`** (`semantic_correct_4_of_4 = False`: `spektra` dilabeli `eligible_not_selected`, `marketing_rejected = 0.0`, `53.59s`) | `BLOCKED_MISSING_SEALED_EVALUATOR` |
| `Meta-Llama-3.1-8B-Instruct-Q4_K_M` | **ACCEPTED** (`5/5` usul, `0` ditolak, `238.64s`, `537` tok @ `3.13 t/s`) | **`2.0 / 4.0`** (`semantic_correct_4_of_4 = False`, `gate_caught = 0.0`, `marketing_rejected = 0.0`: salah klasifikasi `stabilo`, `spektra`, dan `murah`; `221.92s`) | **`4.0 / 4.0`** mekanik namun **`semantic_correct_4_of_4 = False`** (`stabilo` tetap dilabeli `ineligible_bounds`, `58.74s`) | `BLOCKED_MISSING_SEALED_EVALUATOR` |

Artefak bukti lengkap:
- [`evidence/bakeoff02_manus/bo02_q3_4b.json`](../../evidence/bakeoff02_manus/bo02_q3_4b.json)
- [`evidence/bakeoff02_manus/bo02_q35.json`](../../evidence/bakeoff02_manus/bo02_q35.json)
- [`evidence/bakeoff02_manus/bo02_llama8b.json`](../../evidence/bakeoff02_manus/bo02_llama8b.json)

### Analisis Kausal Per Kandidat

1. **`Qwen3-4B-Instruct-2507-Q4_K_M` (Pemenang Jelas Otak Cepat CPU):**
   - Berbeda dari `Qwen3-4B` generasi awal (yang memalsukan `nimbus-gate` di Bake-off 01) maupun `Qwen3.5-4B` / `Meta-Llama-3.1-8B-Instruct`, versi `2507` ini menyitir fact-ID persis dari paket (`need`, `criteria-bounds`, `criteria-score`, `criteria-gate`, `<vendor>-claim`, `<vendor>-attested`, `<vendor>-digest`, `<vendor>-price-per-ram`, `computed-ranking`) dan mengklasifikasikan seluruh 4 vendor secara benar baik dengan maupun tanpa `response_format` JSON schema (`4.0/4.0` dan `semantic_correct_4_of_4 = True`).
   - Waktu B vanilla (`190.00s`) **2.82x** lebih cepat daripada catatan petahana `Qwen3-8B` (`535.6s`) dan **1.80x** lebih cepat daripada `Qwen3-4B` lama (`341.4s`), dengan jejak memori hanya ~2.3 GiB.
2. **`Meta-Llama-3.1-8B-Instruct-Q4_K_M` (Tersingkir di B2A-02):**
   - Sekalipun ukurannya hampir dua kali lipat (`4.58 GiB`) dan kecepatannya kurang dari setengah `2507` (`3.38 t/s` `tg128`), `Meta-Llama-3.1-8B-Instruct` **gagal pada B2A-02 vanilla (`2.0/4.0`)** karena menukar pelanggaran identitas (`murah`) dengan pelanggaran batas (`spektra` & `stabilo`). Bahkan saat dipandu `whitelist_schema`, ia tetap salah menilai `stabilo` sebagai `ineligible_bounds` (`semantic_correct_4_of_4 = False`). Di bawah standar Bake-off 02 (`B = 4/4`), klaim suksesinya gugur secara empiris pada Instrumen B.
3. **`Qwen3.5-4B-Q4_K_M` (Spesialis Grammar-Constrained Proposer, Bukan Direktur Bebas):**
   - Pada prompt B2A-02 vanilla, ia membaca `[criteria-gate]` secara literal lengkap dengan tanda kurung sikunya sehingga validator gagal-tutup menolak seluruh balasan (`0.0/4.0`). Pada whitelist schema, ia malah kehilangan ketajaman batas `spektra` (`3.0/4.0`).
   - Sebaliknya, pada [`PROPOSER_STAGE1_V2_EXIT_GATE_VERDICT_20261114.md`](../../handover/PROPOSER_STAGE1_V2_EXIT_GATE_VERDICT_20261114.md), model ini terukur **6/6 lulus validator** (`mean_diff = +7.50`, `95% CI lower = +0.83`, `201.83s/ep`) di bawah skema JSON Stage 1 v2 (`096bef9b...`).

---

## 4. Rekomendasi Arsitektur Otak Lokal CPU+RAM untuk VM ACE

1. **Otak Kerja / Direktur Utama (`:8000` selalu aktif saat jendela kerja biasa):** **`Qwen3-4B-Instruct-2507-Q4_K_M`** (`-t 4 -c 8192 -fa on -ctk q8_0 -ctv q8_0 --reasoning off`). Terukur tercepat (`7.67 t/s`), stabil di A+B (`4/4` tanpa celah semantik), dan cukup ringan (~2.3 GiB) agar VM/Sandbox tetap punya ruang lega untuk kernel/validator/test lain.
2. **Otak Spesialis Proposer Stage 1/2 (`json_schema` ketat):** **`Qwen3.5-4B-Q4_K_M`** ketika menjalankan siklus sintesis paket praregistrasi terstruktur (`6/6`, Quality PASS).
3. **Catatan Suksesi Resmi Direktur (`Qwen3-8B` -> `Qwen3-4B-Instruct-2507`):**
   Pergantian status resmi di `bakeoff02-kernel` tetap membutuhkan satu eksekusi tersegel Instrumen C (`Keamanan-01`) begitu artefak `security-test/evaluator` (`sha256 6b0610f0...`) tersedia kembali atau dikustodi ulang sesuai konstitusi ACE.
