# PEMBEKUAN PAKET EVO 0007 — CATATAN PEMBEKUAN

*Status: DRAF untuk ratifikasi hub atas head PR ini. Paket BEKU
pada saat hub meratifikasi head ini; tidak ada episode — termasuk
gelombang kalibrasi — yang berjalan sebelum itu. Dokumen ini
mengunci teks, instrumen, kolam, dan mesin paket; yang sengaja
tidak dikunci di sini dicatat sebagai perbuatan di dalam paket
yang tercatat di aneks pembekuan polanya.*

## 1. Teks dan fondasi yang dikunci

- Praregistrasi: PR #311, head teratifikasi **b3868b3f**
  (`handover/PRAREGISTRASI_EVO_0007_FINAL_DRAF.md`).
- Fondasi: PR #310, head **e4de068b**.
- Prasyarat bangun §9, head remote terverifikasi dari respons
  push: kelas event pattern_distilled PR #312 head **a68dde7b**;
  runner paket PR #313 head **9bab252d** (termasuk amandemen
  adapter korpus beku; 16/16 tes); kandidat pabrik siaga PR #314
  head **4ab955f8**.

## 2. Kolam kalibrasi (sha256 terverifikasi di sandbox, 18 Nov)

Tahap: `/workspace/evo0003-stage/evo0006p-stage/` (rumah ACE).

| Berkas | Baris | sha256 |
|---|---|---|
| corpus_candidates.jsonl (gelombang-1) | 24 (12 kode + 12 bahasa, catatan penerus) | 1d09d590fc370cebbdbe55718daf34a79568a1ffa3f32f642903ce029ed3c800 |
| corpus_candidates_v2.jsonl (gelombang-2) | 24 | 22b939611488011b0bb8e729adc468a2ba2b8e7ebeb9d998a0026fe9ec280212 |
| corpus_reserve_v3.jsonl (cadangan) | 12 bahasa | 740e8a29a1ee5b9146034a811dbb76d38de1c4b2548fa83ab1307a34b8620ad0 |

Format baris terverifikasi: `{id, instruction, kind="episode",
task_kind}`. Adapter ke bentuk kandidat paket adalah
`adapt_candidate` pada runner terkunci (prompt := instruction;
judge_prompt := templat judge paket). Urutan saring: cadangan
bahasa lebih dulu (aturan komposisi §3 praregistrasi), lalu
gelombang-2, lalu gelombang-1, sampai set probe cukup atau kolam
habis; gelombang pabrik (#314) hanya sesudah itu, sesuai anggaran
saring §3.

## 3. Yang dilakukan di dalam paket, tercatat di aneks

- **Material pola:** sumber = episode ratified gelombang penerus
  (berkas wave1/wave2 sandbox) + episode ratified gelombang
  kalibrasi paket ini + korpus beku rumah. Pendistilasi
  (gemini/gemini-2.5-pro) menulis record pattern_distilled lewat
  kelas event #312.
- **task_shape episode probe:** BUKAN field korpus. Ia ditetapkan
  pada pembekuan pola oleh lintasan pendistilasi, dari kosakata
  pola terdistilasi; episode tanpa padanan adalah data
  POLA-tidak-terantar, bukan error (semantik runner terkunci).
- **Teks receipt/sham per episode probe:** diproduksi pada
  pembekuan pola dari catatan ratifikasi episode itu (receipt =
  bentuk 0005; sham = teks sepadan bentuk dari episode
  tak-ratified sejenis), tercatat di aneks.
- **Cap dan snapshot:** cap persentil-95 dari panjang record
  nyata; snapshot store pola + sha256-nya dicatat di aneks
  SEBELUM lengan pertama. Tidak ada write-back selama probing.

## 4. Instrumen dan anggaran (mengunci §2/§8 praregistrasi)

Pasangan organ persis tabel §2 praregistrasi; judge
gonka/deepseek-ai/DeepSeek-V4-Flash-0731 dengan aturan parse
objek-pertama; saldo Gonka adalah kendala pengikat (±50 rb dari
100 rb token/bulan terencana) dan kemajuannya dilaporkan per
fase; habis = jeda + amandemen, bukan pergantian. Rumah eksekusi:
VM Ian (organ API; helper konektor lokal), direktori tahap
`~/workspace/evo0007-stage/`; hasil tiap fase didorong sebagai
draft PR.

## 5. Dua tafsir runner yang dibekukan bersama catatan ini

Ratifikasi head ini menetapkan dua tafsir yang kunamai di PR #313
sebagai berlaku untuk paket ini: (1) penolakan validator menutup
episode sebagai tidak-diterima tanpa panggilan judge (tercatat
judge_skipped); (2) flag band_rederived mencatat pemicu fraksi
§3 menyala, bukan pitanya bergerak. Bila hub menghendaki lain,
perubahan adalah amandemen atas catatan ini sebelum episode
pertama — bukan penyesuaian di tengah lari.

## 6. Yang tidak dibekukan

Snapshot pola (perbuatan di dalam paket, §3); gelombang pabrik
(tetap siaga); LLMTR (tetap dikecualikan — tergerbang dan tak
teregistrasi); garis klaim warisan lokal (tetap TIDAK TERUJI,
di luar paket ini sepenuhnya).
