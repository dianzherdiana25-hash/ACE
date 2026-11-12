# ACE Ω — Addendum 9, 2026-11-12: OMEGA-07 Memori Kognitif Persisten

Bergantung pada OMEGA-04 (durabilitas checkpoint — terverifikasi) dan
OMEGA-06 (kernel bukti — terbangun), sesuai antrean dokumen program.

## Yang dibangun (PR #110, draft, bertumpuk di atas #109)

Modul baru `code/ace_operational/cognitive_memory.py`:

- **Tiga jenis record** — episodik, semantik, prosedural — dalam log
  JSONL append-only berantai hash; keadaan dibangun ulang lewat replay
  saat dibuka (bertahan dari kematian proses, pelajaran OMEGA-04).
- **Provenans struktural**: record bersumber "evidence" wajib menunjuk
  digest bukti yang sudah di-anchor lebih dulu; record bersumber
  "model" selamanya berlabel tebakan — tidak bisa menaikkan dirinya,
  tidak pernah menggeser fakta berbasis bukti dalam konflik maupun
  peringkat recall.
- **Konflik disimpan, bukan disembunyikan**: fakta semantik yang kalah
  berstatus superseded dan tetap bisa diambil dengan penanda jelas.
- **Recall terbatas dan jujur**: limit jumlah + anggaran token dengan
  laporan pemotongan; record privat butuh flag eksplisit; record basi
  (lewat `valid_until_seq`) tertandai, yang kedaluwarsa tersisih.
- **Melupakan itu nyata**: `forget()` menjalankan redaction pass —
  event record diganti tombstone (ID + alasan + hash isi) dan rantai
  dibangun ulang. Isi yang dilupakan benar-benar hilang dari disk;
  tindakannya sendiri tetap teraudit. (Desain awal append-only murni
  ditolak justru karena isi "yang dilupakan" akan tetap ada di log.)
- **Transfer negatif disurfaced**: outcome prosedural dicatat per
  konteks; recall ke konteks tempat prosedur itu gagal (atau belum
  pernah berhasil) memberi flag `negative_transfer_risk`.

## Pengujian (daftar uji dokumen OMEGA-07)

14 test, semua lulus: recall lintas-restart, recall per jenis, batas
retrieval, provenans (anchor wajib; tebakan di bawah bukti), injeksi
memori palsu (tebakan percaya diri 1.0 tetap tidak menggeser bukti),
supersesi oleh bukti lebih baru, pengetahuan basi, kedaluwarsa,
pelupaan + tombstone, privasi, canary, rantai rusak tertandai, transfer
negatif. Tumpukan Ω penuh: **108 test OK (10 skip)**.

Dua cacat ditemukan dan diperbaiki selama pengujian, dicatat jujur:
(1) tokenizer whitespace gagal atas JSON kanonis kompak sehingga recall
kosong — diganti ekstraktor kata regex; (2) satu test kedaluwarsa
ternyata mencocokkan record kontrolnya sendiri — test diperbaiki.

## Pemisahan rekayasa vs ilmiah

Ini infrastruktur memori dengan jaminan integritas yang teruji — bukan
bukti kemampuan kognitif. Gerbang tidak berubah: **G1 NOT_ASSESSED,
OAIE belum terbukti**.

## Antrean berikutnya

OMEGA-09 (mutasi & keanekaragaman; bergantung 08 ✓), OMEGA-10
(ko-evolusi lingkungan/kurikulum; 06+08 ✓), OMEGA-11 (lab penalaran;
03+06+09). Dilanjutkan di bawah mandat.
