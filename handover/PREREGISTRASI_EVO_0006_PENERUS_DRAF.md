# PREREGISTRASI PENERUS EVO 0006 — DRAF (Ian, 2026-11-17 pagi)
## Uji inheritance yang sama, instrumen kalibrasi margin judge

## §0 Kenapa paket baru, bukan tambalan

EVO 0006 berakhir INSTRUMEN_TIDAK_CUKUP (PR #252):
kalibrasi berburu belah biner stokastik tidak bisa
mengisi probe set karena pasangan organ nyaris
deterministik per episode (vonis A/B sepakat 23/24).
Klaim inheritance-nya tidak teruji. Paket ini menguji
klaim yang SAMA dengan instrumen kalibrasi yang diganti
total: pita sensitivitas diukur dari MARGIN judge
(skor), bukan dari belah biner.

Temuan pendukung dari artefak 0006: judge saat ini hanya
mengembalikan {accept, reasons}; jumlah reasons BUKAN
margin yang bersih (accept code membawa 4–6 reasons,
accept language hampir selalu 1) — karena itu margin
harus DIMINTA secara eksplisit dari judge (§2), bukan
diturunkan dari reasons.

## §1 Klaim (identik dengan 0006)

Instans segar di-seed store penuh program (definisi
gabungan 0006: live ∪ store akumulasi, snapshot + pin
sha pada staging lari, komposisi tercatat apa adanya
saat lari) mengungguli instans segar dari nol pada probe
set terkalibrasi, lewat jalur recall_context yang sama.

## §2 Perubahan instrumen (dinyatakan; prasyarat bangun)

Prompt judge v3: selain accept + reasons, judge WAJIB
mengembalikan `score` integer 0–100 dengan rubrik
berjangkar di dalam prompt:
0–39 gagal substansi · 40–59 sebagian benar, cacat
nyata · 60–79 benar dengan cacat kecil · 80–100 benar
dan rapi. `accept` tetap mata uang vonis di lengan;
`score` hanya untuk pita kalibrasi + readout sekunder.
Baris tanpa score yang bisa di-parse = baris error
(fail-closed; aturan berhenti-saat-error berlaku).
Bangunannya: varian scoring di ratification_loop + tes,
sebagai draft PR tersendiri, ter-ratifikasi hub SEBELUM
lari. Lari menunggu dua ratifikasi: paket ini + bangun.

## §3 Pita margin + kalibrasi bergelombang (aturan beku)

Episode DI DALAM PITA iff rata-rata score dua lari
kalibrasi (kondisi kosong) berada di [45, 75].

- **Gelombang 1:** 24 kandidat korpus 0006 yang sama
  (sha 1d09d590…; hasil binernya sudah dikenal, score-nya
  pengukuran baru) × 2 lari. Probe set = yang di pita.
- **Gelombang 2** (hanya bila probe < 8 sesudah
  gelombang 1): sampai 24 kandidat BARU ditulis dengan
  menarget bukti gelombang 1 (jenis/topik yang score-nya
  mengelompok terdekat ke tepi pita; kesulitan dinaikkan
  untuk penembus-plafon, diturunkan untuk yang lantai),
  dibekukan sebagai korpus v2 dengan sha-nya sendiri
  SEBELUM disaring, × 2 lari.
- **Cap keras:** kalibrasi berhenti sesudah gelombang 2
  apa pun hasilnya; probe < 8 → INSTRUMEN_TIDAK_CUKUP
  (pendaratan sah, tanpa gelombang tambahan).
- Perkiraan biaya jujur pada laju terukur 0006 (code
  ±800 dtk, language ±200 dtk per lari): gelombang 1
  ±6–7 jam; gelombang 2 sebanding. Jendela pecah
  per-jenis seperti 0006; bentuk jendela keputusan hub
  saat ratifikasi.

## §4 Lengan (persis 0006)

SEEDED (konteks = recall atas snapshot store penuh)
vs KOSONG (recall atas store kosong), tanpa write-back
selama probe, konteks per episode tercatat kelas-satu.
Gerbang pengantaran ≥ 75% pada lengan SEEDED — di
bawahnya vonis TIDAK_TERANTAR. TERDUKUNG iff gerbang
lolos DAN accept-rate SEEDED > KOSONG pada probe set;
NOL iff gerbang lolos DAN tidak lebih besar. Readout
sekunder (tidak mengubah vonis): rata-rata score judge
per lengan.

## §5 Ikatan tetap

Aturan instrumen tetap berlaku penuh: fase berhenti
pada baris error pertama; baris outage dipertahankan
sebagai berkas invalid + pasangan hilang diukur ulang;
korpus tidak ditambal di tengah gelombang (korpus
gelombang 2 ditulis DI ANTARA gelombang di bawah aturan
§3, bukan selama gelombang berjalan); engine dijeda
selama jendela ukur; store live tidak diubah; tidak ada
merge; tidak ada model/front/venue baru.
