# STAGING NOTE EVO 0004 (Ian, 2026-11-16)

Paket praregistrasi mengikuti pola PR #239. Rancangan:
`handover/PREREGISTRASI_EVO_0004_DRAF.md` (ditulis hub;
status DRAFT menunggu ratifikasi hub).

## Basis dan pin

- Basis kode: main @ f6d7546213449f8fc65b825fc87b5b87a69eec0e.
- Korpus Blok A = korpus ekor beku EVO 0003, dibawa utuh ke
  paket ini: `handover/EVO_0003_CORPUS_TAIL_V1.jsonl`,
  sha256 60177c51e095ea685fee84d474fbd204568b3d10db1361a68244aba1dba0637e
  (16 baris: dlg-001..008 + ep-code-001..004 + ep-lang-001..004;
  nilai task_kind korpus: "code" dan "language" — filter jalur
  WAJIB diuji ke nilai persis ini saat preflight Blok A).
- Instrumen Blok A: evo_tail v2 (judge via chat_structured),
  pasangan organ PR #238 (kode: coder→front; bahasa:
  front→coder). Topi ace-front 6 GiB sudah terap live.

## Alokasi seed Blok D

- 20262001 — band ter-seed (prior katalog band donor dari
  burst 20261903–20261906; donor persisnya ditetapkan di
  catatan lari Blok D sebelum eksekusi, dari katalog yang
  sudah ter-ratifikasi di PR #242).
- 20262002 — band cold start.
- Cadangan 20262003–20262004 (hanya atas akta hub).
- Terverifikasi disjoint dari semua seed terpakai/ternama:
  20261501–03, 20261601–03, 20261701–03 (ternama, tak
  terpakai), 20261801–05, 20261901–06 (+cadangan 07–10).

## Urutan eksekusi (sesudah ratifikasi)

Blok B (kelas probe audit BARU didaftarkan di EVENT_CLASSES
+ audit tulis-baca + Blok B2 baterai bergerbang prasyarat
pada band burst bersaksi) → Blok A (§1 full scope 8 episode;
preflight filter wajib cocok ≥1 item per jalur; kill proses
terverifikasi; engine dijeda; anggaran dinding dari laju
terukur: kode ±12 mnt/episode, bahasa diproyeksikan tertulis
dari 2 episode pertama) → Blok D → Blok C (keputusan peran
Sahabat + satu smoke generation Bahasa Indonesia).

Konsolidasi EVO 0004 = satu draft PR di akhir, pola PR #242.
