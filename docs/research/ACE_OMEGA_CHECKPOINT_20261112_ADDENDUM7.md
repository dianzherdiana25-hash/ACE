# ACE Ω — Addendum 7, 2026-11-12: OMEGA-08 Population & Lineage Archive

Dilanjutkan langsung sesudah OMEGA-06 sesuai instruksi tetap pemilik
(progres tahap tidak menunggu pemilik) dan dependensi dokumen program
(OMEGA-08 bergantung pada OMEGA-06).

## Yang dibangun (PR #108, draft, bertumpuk di atas #107)

Modul baru `code/ace_operational/population_archive.py` — arsip populasi
& silsilah yang append-only dan content-addressed:

- **Identitas diturunkan dari isi** (SHA-256 atas record kanonis):
  registrasi duplikat bersifat idempoten (ID sama, satu record); record
  yang diubah tidak lagi cocok dengan ID-nya sendiri → terdeteksi korup.
- **Write-once + ledger berantai hash**: seluruh keadaan populasi bisa
  di-replay dari ledger saja dan hash-nya dibandingkan dengan keadaan
  hidup.
- **Silsilah eksplisit**: induk wajib sudah terdaftar; penelusuran
  dijaga siklus. Siklus hasil pemalsuan di disk tertandai korup — siklus
  sungguhan tidak dapat memenuhi content addressing (butuh fixed point
  SHA-256), dan itu dicatat apa adanya di pengujian.
- **Perbandingan hanya di dalam satu grup (evaluator, protokol,
  anggaran)**: mencampur evaluator/anggaran adalah error, bukan
  dirata-rata diam-diam. Seleksi Pareto dengan penanganan tie yang
  deterministik; metrik hilang → kandidat tersisih dengan alasan.
- **Hasil negatif adalah arsip kelas satu** — tidak ada API hapus.

## Pengujian adversarial (daftar uji dokumen OMEGA-08)

17 test di `test_population_archive.py`, semua lulus di VM ini:
identitas duplikat, siklus silsilah (penjaga traversal + pemalsuan
disk), bukti/induk hilang, tabrakan evaluator campuran, Pareto & tie,
bukti korup (terdeteksi dan tersisih dari seleksi), rantai ledger rusak,
replay = hash keadaan. Tumpukan Ω penuh: **75 test OK (10 skip)** —
58 sebelumnya + 17 baru, tanpa regresi.

## Demonstrasi gerbang ilmiah (artefak nyata, satu evaluator, satu anggaran)

Populasi = empat keadaan nyata modul `harga.py` OMEGA-03, dievaluasi
evaluator held-out yang sama (6 test) + dev test (3), satu kali jalan
per kandidat — `evidence/omega08_gate_demo.json`:

| Kandidat | Evaluator | Dev | Hasil |
|---|---|---|---|
| original (buggy) | 2/6 | 1/3 | fail — terarsip sebagai negatif |
| model one-shot (attempt 2) | 4/6 | 2/3 | fail — terarsip sebagai negatif |
| model feedback-loop (attempt 3) | 6/6 | 3/3 | pass |
| baseline skrip deterministik | 6/6 | 3/3 | pass |

Front Pareto: **{model feedback-loop, baseline deterministik} — tie
yang jujur.** Pada fixture sekecil ini, skrip dua substitusi menyamai
patch terbaik model; dicatat apa adanya, tanpa dibesar-besarkan.
Silsilah attempt-3 terverifikasi: `original → one-shot → feedback`.
Verifikasi arsip demo: 4 kandidat, 4 evaluasi, 0 korup, rantai OK,
replay cocok.

## Pemisahan rekayasa vs ilmiah

Ini memenuhi *mekanika* gerbang OMEGA-08 (≥2 kandidat berbeda nyata +
baseline anggaran-sama di bawah satu evaluator) pada satu fixture kecil.
Ia **bukan** bukti kemampuan ilmiah baru: G1 tetap NOT_ASSESSED dan
OAIE tetap belum terbukti (`oaie_proven=false`).

## Sisa Fase 1 menurut dokumen program

OMEGA-07 bergantung pada OMEGA-04+06; OMEGA-09 pada 08; OMEGA-10 pada
06+08; OMEGA-11 pada 03+06+09. Kernel protokol OMEGA-06 versi dokumen
lengkap (preregistrasi, split custody, uji canary/pemalsuan) juga masih
terbuka. Antrean dilanjutkan di bawah mandat pada tahap berikutnya.
