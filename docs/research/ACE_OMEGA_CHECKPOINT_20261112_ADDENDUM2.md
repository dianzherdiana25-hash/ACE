# ACE Ω — Addendum 2, 2026-11-12: OMEGA-03 uji coding (varian G1)

Lanjutan Fase 1 (Muse sebagai pelaksana; model lokal bukan gerbang).
Format mengikuti Bagian XXI Master Prompt, diringkas untuk satu paket.

## A. Implementasi nyata

Tidak ada perubahan source ACE pada addendum ini; yang dihasilkan adalah
evidence eksperimen OMEGA-03 atas komponen yang sudah ada
(`LocalRepoWorkflow` dari #104, `ModelRouter` + perbaikan #107,
`BoundedRepositoryRetriever` dari #99). Fixture uji adalah repo baru yang
belum pernah dilihat ACE: modul harga `harga.py` dengan dua cacat nyata
di satu fungsi (syarat batas diskon besar `>` seharusnya `>=`; basis PPN
memakai subtotal awal, seharusnya nilai setelah diskon), aturan tertulis
di README fixture, test pengembang di dalam repo, dan test evaluator
terpisah di luar repo (6 test) yang tidak dapat diubah kandidat.

## B. Model lokal

Qwen3-8B Q4_K_M (SHA-256 `d98cdcbd…45785`) via llama.cpp b12316.
Temuan operasional: jalur CLI router mensyaratkan model lolos estimasi
`fits_ram` (1,25× ukuran file); di host ini `MemAvailable` ±3,5 GiB
(cache halaman tertahan file model, `/proc` read-only) sehingga 8B tidak
pernah terpilih lewat CLI dan router memilih baseline 3B. Jalur server
tidak mempunyai syarat itu dan 8B berjalan nyata (RSS ±4,2–5,3 GB).

## C. Coding autonomy — tiga percobaan, semua tercatat

1. **Workflow resmi `LocalRepoWorkflow`**: `BLOCKED_ENVIRONMENT` pada
   baseline — sandbox mewajibkan bubblewrap+seccomp dan `bwrap` tidak
   tersedia di host (receipt lengkap: `evidence/omega03_workflow_result.json`).
   Ini verdict OMEGA-05 untuk host ini, terukur, bukan asumsi.
2. **Varian degradasi-isolasi, percobaan 1 (CLI, Qwen2.5-Coder-3B)**:
   `PROPOSAL_INVALID` — keluaran tidak lolos parser JSON ACE; simbol masih
   placeholder `function_name`; konten dibungkus string literal.
3. **Percobaan 2 (server, Qwen3-8B, `/no_think`, digest diattestasi operator)**:
   patch valid, memperbaiki basis PPN (`subtotal` → `total`), tetapi cacat
   batas lolos. Evaluator 4 gagal → 2 gagal; dev 2 gagal → 1 gagal.
4. **Percobaan 3 (umpan balik test yang gagal diberikan ke model)**:
   patch satu baris `>` → `>=`. **Semua test lulus**: evaluator 6/6,
   pengembang 3/3. Verdict varian: `LOCALLY_VERIFIED (degraded isolation)`.

Penyimpangan varian dari workflow resmi, dinyatakan terbuka: (i) isolasi
namespace absen — test berjalan sebagai subprocess biasa pada salinan
sekali-pakai; (ii) digest model diattestasi operator yang menjalankan
server dari file GGUF tercatat, bukan digest in-band jalur CLI;
(iii) saklar `/no_think` ditambahkan agar JSON muat dalam budget token.

## D. Scientific evidence

Hipotesis: model lokal 8B dapat memperbaiki bug repo tak-dikenal dari
instruksi bahasa alami bila diberi konteks retrieval + loop umpan balik
test. Hasil: didukung sebagian pada fixture ini — perbaikan penuh butuh
3 percobaan dan umpan balik test yang spesifik; one-shot 8B hanya
memperbaiki 1 dari 2 cacat; one-shot 3B gagal pada level kontrak keluaran.
Baseline one-shot tanpa loop tercatat pada percobaan 2. Hasil negatif
percobaan 1–2 dipertahankan di evidence, tidak dihapus.

## E. Evolution evidence

Tidak ada kandidat populasi yang dihasilkan pada paket ini. Lineage
percobaan (1→2→3) disimpan sebagai evidence mentah JSON di `evidence/`.

## F. Belum terselesaikan

- OMEGA-05 di host ini: `BLOCKED_ENVIRONMENT` selama bubblewrap tidak
  tersedia; workflow resmi tidak dapat memberi verdict coding di VM ini.
- G1 tetap **NOT_ASSESSED**: satu fixture buatan operator dengan isolasi
  terdegradasi adalah evidence menuju G1, bukan PASS gerbang.
- Estimasi `fits_ram` router (1,25×) tidak pernah meloloskan 8B di host
  ini untuk jalur CLI — kandidat perbaikan OMEGA-01 lanjutan (kalibrasi
  estimasi terhadap RSS terukur), belum dikerjakan.

## G. Aksi berikutnya

1. Kalibrasi estimasi RAM router terhadap pengukuran RSS nyata + test
   (OMEGA-01, tidak terhalang dependensi).
2. OMEGA-04 (durable task workflow) — paket Fase 1 berikutnya yang
   prasyaratnya terpenuhi.
3. Ulangi uji OMEGA-03 pada host berkemampuan namespace bila tersedia,
   agar verdict workflow resmi dapat diperoleh tanpa degradasi.
