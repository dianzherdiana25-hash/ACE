# ACE Ω — Addendum 10, 2026-11-12: OMEGA-09 Mesin Mutasi + Perbaikan Parser GGUF

## OMEGA-09 (PR #111, draft, bertumpuk di atas #110)

Modul baru `code/ace_operational/mutation_engine.py`. Kandidat adalah
genotipe terstruktur (planner, algorithm, representation, learning,
architecture, prompt_template, tool_set, parameter numerik):

- **Tujuh kelas mutasi** sesuai dokumen + rekombinasi uniform, dengan
  provenans lengkap (digest induk + diff field persis) di setiap usulan.
- **Admisi sebelum eksistensi**: validasi skema (enum, universe tool,
  batas numerik); usulan invalid ditolak dengan alasan dan dikembalikan
  sebagai hasil negatif — tidak pernah dibuang diam-diam.
- **Preservasi regresi**: tiap kelas hanya boleh menyentuh grup
  field-nya sendiri, terbukti oleh diff; untuk rekombinasi, setiap field
  wajib berasal dari salah satu induk.
- **Kebaruan struktural, klaim dibatasi**: jarak dengan dead-zone epsilon
  (jitter kosmetik bukan kebaruan), kelas duplicate/variant/novel — dan
  **tidak ada jalur kode yang mensertifikasi "primitif baru"**; klaim
  semacam itu dicatat sebagai belum terverifikasi, sesuai gerbang
  OMEGA-09.
- Pencarian terbatas dan deterministik per seed; duplikat terhadap
  populasi arsip (OMEGA-08) ditolak.

13 test dokumen lulus: isolasi field per kelas (multi-seed), parentage
rekombinasi, determinisme, false-positive kebaruan, duplikat arsip,
mutasi invalid, hasil negatif terarsip.

## Perbaikan tumpukan (PR #112, draft, bertumpuk di atas #111)

Sapuan **seluruh paket** `ace_operational` saat tahap ini (158 test,
bukan hanya daftar suite Ω) menemukan cacat lama yang lolos dari
verifikasi PR #107:

1. **Parser GGUF tidak total**: file dengan hitungan tensor/KV absurd di
   header melempar `struct.error`/`OverflowError` yang tidak tertangkap
   keluar dari discovery — seharusnya tercatat sebagai model korup.
   Diperbaiki: semua kegagalan parse menjadi `ValueError`; hitungan tak
   masuk akal ditolak eksplisit; tipe tensor eksotik yang well-formed
   tetap `None` (tak terverifikasi, tak pernah diasumsikan).
2. **Fixture edition4 bukan GGUF asli**: test era PR #104 memakai stub
   header-saja sebagai "model valid", yang memang benar ditolak admisi
   struktural. Fixture kini GGUF minimal yang genuine (pembangun yang
   sama dengan `test_gguf_integrity`), sehingga satu-satunya cacatnya
   adalah yang dinamai test-nya.
3. Test regresi baru: header sampah masuk `corrupted_models`, tidak
   pernah mengcrash discovery.

Hasil: **seluruh paket ace_operational 158 test OK (10 skip), 0 error**
— termasuk suite pra-Ω yang tidak masuk daftar verifikasi sebelumnya.
Pelajaran proses yang dicatat: mulai sekarang verifikasi tumpukan Ω
memakai sapuan paket penuh, bukan daftar suite pilihan.

## Pemisahan rekayasa vs ilmiah

Tidak ada gerbang yang berubah: **G1 NOT_ASSESSED, OAIE belum terbukti**.

## Antrean berikutnya

OMEGA-10 (ko-evolusi lingkungan & kurikulum; 06+08 ✓) dan OMEGA-11
(lab penalaran; 03+06+09 ✓). Dilanjutkan di bawah mandat.
