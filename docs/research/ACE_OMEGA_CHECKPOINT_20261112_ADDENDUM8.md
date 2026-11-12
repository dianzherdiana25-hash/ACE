# ACE Ω — Addendum 8, 2026-11-12: OMEGA-06 Kernel Protokol & Bukti (cakupan dokumen penuh)

Addendum 6 mengeksekusi inti OMEGA-06 yang diarahkan pemilik
(reproduksi independen). Addendum ini melengkapinya dengan pembangunan
kernel sesuai definisi dokumen program Ω. OMEGA-06 kini terpenuhi dari
dua sisi: **kernel terbangun + klaim Fase 1 terverifikasi ulang**.

## Yang dibangun (PR #109, draft, bertumpuk di atas #108)

Modul baru `code/ace_operational/experiment_kernel.py`:

- **Preregistrasi sebelum hasil**: hipotesis, protokol (wajib
  `pass_rule`), evaluator, anggaran, himpunan kandidat dengan baseline
  wajib dan kontrol negatif opsional — ter-hash isi (`protocol_hash`),
  tidak bisa diubah sesudahnya. Hasil untuk eksperimen tak terdaftar
  ditolak.
- **Split custody**: kustodian kandidat menandatangani digest artefak
  kandidat; kustodian evaluator menandatangani digest evaluator +
  fixture (HMAC; kunci tidak disimpan). Penukaran evaluator, fixture,
  atau artefak kandidat sesudah registrasi terdeteksi saat audit.
- **Vonis diturunkan, bukan diklaim**: pass/fail dihitung ulang dari
  metrik + pass_rule; bendera sukses (atau gagal) palsu ditolak.
  `abstain` adalah vonis kelas satu dan butuh alasan bila metrik
  sebenarnya menentukan.
- **Penjaga kontaminasi**: token canary protokol tidak boleh muncul di
  artefak kandidat maupun telemetri; kandidat yang artefaknya ADALAH
  evaluator atau fixture ditolak.
- **Ledger hasil append-only** berantai hash dengan telemetri mentah;
  audit atas ledger yang diubah/dipotong melaporkan **INCOMPLETE**
  dengan prefiks terverifikasi — tidak pernah CLEAN. Kontrol negatif
  yang lulus adalah pelanggaran kontrol.

## Pengujian adversarial (daftar uji dokumen OMEGA-06)

19 test di `test_experiment_kernel.py`, semua lulus: kebocoran canary
(artefak + telemetri), vonis palsu dua arah, mutasi fixture, evaluator
berubah, kandidat = evaluator (mengedit tesnya sendiri), kontaminasi
train/test (kandidat = fixture), penukaran artefak pasca-custody,
replay parsial, kunci custody salah, disiplin preregistrasi.
Tumpukan Ω penuh sekarang: **94 test OK (10 skip)** — tanpa regresi.

## Pemisahan rekayasa vs ilmiah

Kernel menyimpan dan mengaudit bukti; ia tidak menjalankan eksperimen
dan tidak menaikkan vonis apa pun melampaui metriknya. Gerbang ilmiah
tidak berubah: **G1 NOT_ASSESSED, OAIE belum terbukti**.

## Antrean Fase 1 berikutnya

OMEGA-07 (memori kognitif persisten; bergantung 04+06 — keduanya kini
terpenuhi), lalu OMEGA-09 (bergantung 08 ✓), OMEGA-10 (06+08 ✓),
OMEGA-11 (03+06+09). Dilanjutkan di bawah mandat pada tahap berikutnya.
