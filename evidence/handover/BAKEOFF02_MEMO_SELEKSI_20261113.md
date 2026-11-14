# MEMO SELEKSI BAKE-OFF 02 — PAKET KEPUTUSAN (bukan keputusan)

Disusun Ian, 2026-11-13, atas umpan meja hub. Memo ini
menyiapkan butir tunggu OVERNIGHT_PENDING nomor 2 agar bisa
ditutup pemilik dengan SATU jawaban. Tidak ada unduhan,
tidak ada yang terkunci oleh memo ini. Kriteria kandidat
mengikuti desain PR #152 (C-1…C-6): identitas berbeda +
klaim suksesi satu kalimat yang bisa gugur; terukur dengan
instrumen yang sama; muat amplop terukur (GGUF termuat jalur
attested terpin, ukuran ≤ incumbent 5.027.783.488 byte);
bisa dikustodi dari identitas terharap (HF LFS oid +
ukuran); Rp0/local-first.

## A. Kandidat yang benar-benar tersedia hari ini

| Kandidat | Status terukur | Nasib menurut kriteria |
|---|---|---|
| Qwen3-8B-Q4_K_M (incumbent, 5.027.783.488 B, sha256 d98cdcbd…) | Bertahan di bake-off 01; direktur bertugas | Bukan penantang |
| Qwen3-4B-Q4_K_M (di disk, 2.497.280.256 B) | **GAGAL bake-off 01**: instrumen B 0/4 — sitasi fabrikasi `nimbus-gate` (tidak ada di 25 id paket); audit CLEAN | **TERKELUAR oleh C-1** — tidak boleh di-run apa adanya |
| Qwen2.5-Coder-3B-Instruct-Q4_K_M (di disk, 2.104.932.800 B) | Belum pernah diukur pada instrumen bake-off; selama ini hanya baseline pembanding | Layak secara bentuk (identitas beda, muat amplop, tanpa unduhan) — tetapi klaim suksesinya lemah: model coder 3B melawan direktur generalis 8B; kegagalan yang sangat terharap memberi informasi baru yang sedikit sesudah pelajaran 4B |
| Qwen3-14B-Q3_K_M (unduhan parsial 1,52/7,32 GB) | Berkas **KORUP** (parsial) dan ukurannya memang di atas cap incumbent | **TERKELUAR dua kali** — oleh identitas (disebut eksplisit di desain) dan oleh ukuran |
| **Meta-Llama-3.1-8B-Instruct Q4_K_M** (unduhan baru) | Belum diukur. Ukuran berkas **4,92 GB** (tabel repo HF second-state/Meta-Llama-3.1-8B-Instruct-GGUF; rekaman seed pihak ketiga: 4.920.739.232 byte untuk repo bartowski/Meta-Llama-3.1-8B-Instruct-GGUF) — **di bawah cap** 5.027.783.488 byte | Satu-satunya penantang dengan klaim nyata: keluarga model BERBEDA pada skala sama. **LFS oid belum diambil** — gerbang kustodi pada dry-intake wajib mengonfirmasi oid + ukuran langsung dari HF sebelum praregistrasi terkunci. Lisensi: Llama community license (bukan Apache) — pemakaian riset lokal Rp0 tetap di dalam cakupannya |

Klaim suksesi draf untuk Llama (satu kalimat, bisa gugur,
bunyi final terkunci di praregistrasi): "Llama-3.1-8B-
Instruct Q4_K_M, keluarga model berbeda pada skala yang
sama, lulus ketiga instrumen bake-off (A siklus direktur,
B dosier B2A-02 4/4 tanpa pelanggaran sitasi, C perbaikan
tersegel 6/6) dengan succession_margin ≥ 0 terhadap angka
bake-off 01 incumbent."

Aturan lulus (desain PR #152, satu komposit):
succession_margin = min(margin A ±1, margin B =
decision_score − 4, margin C = kasus − 6, margin kecepatan
= (535,6 − wall_B)/535,6), kernel gte 0; PLUS dry-intake
check wajib sebelum kunci.

## B. Dua keputusan yang menunggu pemilik (satu ketukan)

**KEPUTUSAN 1 — kandidat penantang:**
- (a) Unduh Llama-3.1-8B-Instruct Q4_K_M (~4,92 GB)
  sebagai penantang bake-off 02.
- (b) Tanpa unduhan: jalankan Qwen2.5-Coder-3B yang sudah
  di disk (Rp0 mutlak, langsung jalan, klaim lemah).
- (c) Tunda bake-off 02; butir tunggu tetap terbuka.

**KEPUTUSAN 2 — semantik validator sitasi PR #162.**
Desain PR #152 menetapkan penolakan SELURUH balasan
sebagai semantik operatif (penguatan validator hanya
mencatat); build PR #162 mengimplementasikan kelolosan
PER-PROPOSAL sebagai semantik operatif (proposal bersitasi
valid selamat; yang fabrikasi ditolak per butir dengan
objek penolakan terstruktur `ace.citation_rejection.v1`),
sambil tetap membawa penanda `legacy_whole_reply_rejected`
di setiap laporan agar kedua bacaan tetap bisa diperiksa.
Praregistrasi harus memilih satu secara eksplisit sebelum
build dipin:
- (a) Per-proposal (build PR #162 apa adanya).
- (b) Whole-reply (build disesuaikan sebelum dipin).

## C. REKOMENDASI TEKNIS IAN (ditandai: rekomendasi, BUKAN keputusan)

- Keputusan 1 → **(a) Llama-3.1-8B**. Alasan: satu-satunya
  kandidat yang klaim suksesinya sungguh bisa gugur secara
  informatif — keluarga berbeda, skala sama, ukuran muat
  dengan sisa ~107 MB di bawah cap. Opsi (b) hampir pasti
  mengulang pelajaran bake-off 01 (model lebih kecil gagal
  di B) tanpa menguji hipotesis baru apa pun.
- Keputusan 2 → **(a) per-proposal**. Alasan: whole-reply
  mencampur satu sitasi buruk dengan kegagalan direktur
  total — pengukuran kehilangan resolusi persis di tempat
  kegagalan 4B dulu terjadi; ledger penolakan terstruktur
  PR #162 menyimpan bukti fabrikasinya apa pun semantiknya,
  dan penanda legacy membuat bacaan whole-reply tetap
  dapat direkonstruksi dari data yang sama.

## D. Sesudah jawaban pemilik (mekanis, tanpa keputusan baru)

Memo seleksi final → gerbang kustodi (unduh, verifikasi
oid+ukuran HF) → kunci praregistrasi (termasuk pilihan
semantik validator + identitas validator terpin) →
dry-intake check → run. Validator PR #162 sudah terbangun
dan terverifikasi (16/16 tes); satu tindak lanjut kecil
tercatat: append penolakan ke kustodian kernel saat run
(V-5 build kini rantai hash mandiri).
