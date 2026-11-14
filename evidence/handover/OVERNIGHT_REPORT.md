# OVERNIGHT REPORT — mode swakelola (2026-11-13 malam)

Laporan konsolidasi malam; diperbarui per tahap selesai.
Tidak ada delta potongan ke hub malam ini kecuali
ancaman integritas run G3 / kegagalan pagar keras.

## Sudah selesai sebelum paket malam
- Jalur (e) kesiapan panen G5 — memo
  handover/G5_HARVEST_READINESS_MEMO.md (designasi
  pemanen = pos operasi; dua celah bernama).
- Jalur (f) desain Bake-off 02 — draft PR #152.

## Sedang berjalan saat paket diterima
- Run aplikasi G3: rantai fase satu tarikan (sets →
  discovery grid → … → finalize), anggaran dinding
  bersih 45 menit.
- Sensus strata A/B/C v3 band 1 (seed 20261201).
- Subagen jalur (b) instrumen G4 + materialisasi
  katalog; jalur (d) discovery v-next desain +
  prototipe.

## Antrean malam (urutan kerja Ian)
(b) siklus direktur pertama atas register peluang —
sesudah rantai G3 selesai (melindungi dinding run);
(c) bangun instrumen G5 (Task 12, sintetik);
(d) lanjutan v3 sesudah sensus (kalibrasi);
(e) draf teks praregistrasi Bake-off 02 (desain
PR #152); (f) addendum berkala + higiene PR berbasis
bukti + indeks bukti.

## Selesai malam ini
- (e) Draf teks praregistrasi Bake-off 02 — draft
  PR #153 (docs/research/ACE_BAKEOFF_02_PREREGISTRATION_DRAFT_20261113.md):
  mengikuti desain PR #152; gerbang hulu (ratifikasi
  desain, pin validator, memo seleksi, persetujuan
  unduhan pemilik) sebagai field ⟨TBD-GATE⟩; metrik
  komposit succession_margin + dry-intake check.
  Tidak mengunci apa pun.

- (d) Discovery v-next: desain + prototipe + pengukuran
  sandbox SELESAI — draft PR #154 (commit a55d001,
  sha256 remote terverifikasi; uji prototipe 10/10,
  sweep branch 261 OK). Pengukuran (band sandbox
  70000–70099, di luar semua band terlarang; pool 10 /
  evaluasi 30): substrat beku 8/30 (26,7%, konsisten
  dengan kalibrasi Addendum 49); +semua gerak legal
  13/30; +kunci ter-admisi saja 13/30 — SATU kunci
  gerak ter-admisi menangkap seluruh gain. Dekomposisi
  jujur: hanya 13/30 tugas yang shown-discriminating;
  pada mereka A 8/13 → B 13/13 (100% plafon tercapai).
  Kontrol tanpa regresi. Bukan pengukuran gerbang;
  G3 tidak terpengaruh.

- (b) Instrumen G4 + materialisasi katalog SELESAI —
  draft PR #155 (commit 5648b7e; sha256 remote 7/7
  MATCH). g4_instrument.py: scorer murni C1/C2/C3,
  threshold dibaca dari laporan (tak pernah
  hardcode), pagar digest keras dua-pelajaran-G3;
  20 uji sintetis hijau. Katalog v4 kini artefak
  mandiri (operator_catalog_v4.json), digest kanonik
  e7925aa7…a808, reproduksi byte-for-byte
  terverifikasi — celah G-1 Task 08 TERTUTUP; 7 uji
  loader hijau. Sweep lineage 270 → 297 OK.
  Prasyarat aplikasi tersisa: P-G4-3/4/5 +
  praregistrasi. G4 tetap NOT_ASSESSED.

## Daftar tunggu
Lihat OVERNIGHT_PENDING.md (3 butir saat file ini
dibuat).
- (a) RUN APLIKASI G3 SELESAI — dosier dinilai
  instrumen: **SPECIALIZATION** (kriteria v1).
  Angka: grid baseline 0% → extended 75% pada
  tunggal evaluasi murni (Δ +75pp, net-new 9/12,
  katalog 0e4ac118…); pricing katalog 100% → 100%
  (Δ0, jenuh sesuai kalibrasi); pricing terkonstruksi
  35% → 35% (Δ0 — prediksi batas ruang skema dari
  catatan interpretasi TERKONFIRMASI: baseline
  membuktikan tugas terpecahkan, discovery tak
  menambah apa pun di strata ini); pooled pricing Δ0;
  regresi kontrol 0; sham OK. Metrik komposit
  −10,0 → vonis kernel FAIL atas H1 (konjungsi
  transfer gugur di pricing); audit kernel CLEAN;
  tepat 1 baris ledger; dinding total fase
  2.126,5 dtk dari anggaran 2.700. C1 PASS, C2 PASS
  (satu warning tercatat: laporan grid merangkap
  sumber + evaluasi — interpretasi terdeklarasi
  instrumen), C3 FAIL bernama ("efek positif di 1
  keluarga; 2 disyaratkan"). Dua kegagalan harness
  finalize (jalur /tmp terhapus restart; tanda tangan
  panggilan instrumen) terungkap penuh di
  g3-run/run_notes.json + run_summary.json; tidak ada
  penulisan kernel ganda. PAPAN GERBANG TIDAK BERUBAH
  malam ini — penilaian dua pemeriksa menunggu hub.
- Sensus v3 band 1 SELESAI (bukti
  evidence/v3_census_band1.json; seed 20261201):
  S1 = 30 (lantai pas), S2 = 0 (lantai ≥30 GAGAL —
  tak ada tugas yang membutuhkan chain di luar
  singles pada band ini; singles rantai di waktu
  solve menelan seluruh gain komposisi), S3 = 33
  (32 terpecahkan A), baseline-eval 0, unsolved 0.
  Konsekuensi desain untuk tahap kalibrasi/praregistrasi
  v3 dicatat di evidence/v3_calibration_note.md.
- (c) Instrumen G5 SELESAI — draft PR #156 (commit
  1860c8d, basis dde75ef): tepat 2 berkas
  (g5_instrument.py + test_g5_instrument.py); 22 uji
  hijau mencakup ke-20 kasus wajib brief Task 12a
  (probe lantai HASIL, probe tamper bernama tepat
  sekali, harvester-is-author); sweep lineage
  270 → 292 OK. Semua bar dibaca dari
  harvest_report.json (tak ada literal di logika
  klausul). Celah kesiapan G5 #1 TERTUTUP. G5 tetap
  NOT_ASSESSED; praregistrasi periode tetap menunggu.
- (f) Addendum 54 ditulis (run aplikasi G3:
  SPECIALIZATION) tetapi push ke main TERBLOKIR:
  persetujuan egress kedaluwarsa berulang kali
  (pemilik tidur; satu upaya terputus restart
  layanan). Berkas ter-stage utuh di
  ~/workspace/ace-omega/staging/add54/ — dorong
  begitu persetujuan mengalir. Tercatat juga di
  OVERNIGHT_PENDING.md.
- (b) Siklus direktur PERTAMA atas register peluang
  SELESAI — origin share ACE-side bergerak dari
  baseline 0,0 menjadi **0,833** (5 dari 6 entri).
  Tiga percobaan, semuanya tercatat: percobaan 1 mati
  di jendela kesehatan server (cache dingin);
  percobaan 2 membalas KOSONG pada timeout 900 dtk —
  prefill paket 37 kandidat melampaui amplop inferensi
  host pada konfigurasi router yang teruji; percobaan
  3 (paket dipecah 4 tranche ≤10 fakta, satu sesi
  server) keempat tranche-nya ACCEPTED (dinding
  153–246 dtk). Lima entri ter-append, semua origin
  brain_local_qwen3_8b, status design, rantai hash
  register terverifikasi valid sesudahnya: KBM ×
  Facebook; kapabilitas evaluasi tersegel × Facebook;
  Facebook × Threads; Qwen3-8B × KBM; Qwen3-8B ×
  Lynk.id. Ini sintesis sisi-ACE sebagaimana doktrin
  mendefinisikannya (pilihan direktur atas scan
  deterministik, sitasi terverifikasi) — proposal
  tercatat, bukan klaim nilai terbukti; eksekusi
  adalah pekerjaan terpisah. Bukti:
  evidence/opportunity_cycle1.json (+ attempt2
  terarsip terpisah).
- (d) Kalibrasi anti-saturasi v3 SELESAI (band 2,
  seed 20261301; evidence/v3_calibration_band2.json):
  lengan A memecahkan evaluasi 0/30 (0,0%), kontrol
  34/34 (100%), pooled 53,12%. Konsisten dua band:
  gerbang 10–90 LULUS pada denominator pooled dan
  GAGAL pada denominator evaluation-only di kedua
  band — draf praregistrasi wajib menetapkan
  denominator secara eksplisit beserta alasannya
  (dicatat di evidence/v3_calibration_note.md).
  Tugas kontrol yang gagal di band 1 tidak muncul di
  band 2 (band-spesifik, bukan sistematis); S2 tetap
  kosong secara mekanisme. Pengungkapan: run pertama
  malam ini sempat melaporkan 100% semu (bug wrapper
  di skrip kalibrasi — string kode diperlakukan
  sebagai boolean); run itu BATAL, terkoreksi dengan
  catatan tertanggal di berkas bukti.
- (f) Pekerjaan meja penutup: indeks bukti
  DIBANGUN (evidence/INDEX.md — 84 artefak, 18 area;
  pembangun: build_evidence_index.py, aman dijalankan
  ulang). Addendum berkala: Addendum 54 tertulis dan
  ter-stage (push terblokir persetujuan — lihat daftar
  tunggu butir 4). Higiene branch/PR: inventaris
  tercatat (draft tahap aktif #135–#156; 61 PR triase
  beku; spesial #65/#66/#90/#92/#102); TINDAKAN
  penutupan apa pun menunggu persetujuan egress dan
  masuk daftar tunggu butir 5 — tidak ada PR yang
  ditutup malam ini, tidak ada merge.

## Penutup paket malam
Antrian paket malam HABIS dikerjakan: keenam jalur
Massive Mandate selesai ((a) run G3 — SPECIALIZATION,
menunggu dua pemeriksa; (b) instrumen G4 + katalog —
PR #155; (c) instrumen G5 — PR #156; (d) v-next —
PR #154; (e) draf praregistrasi Bake-off 02 —
PR #153; (f) meja penutup), ditambah siklus direktur
register peluang pertama (origin share 0,0 → 0,833)
dan kalibrasi v3 band 2. Yang tersisa hanya butir
daftar tunggu (OVERNIGHT_PENDING.md butir 1–5):
praregistrasi periode G5, unduhan kandidat Bake-off
02, penilaian dosier G3 oleh dua pemeriksa, push
Addendum 54, dan tindakan higiene PR — semuanya
menunggu hub/pemilik, bukan menunggu pekerjaan.
Papan gerbang tidak berubah malam ini: G3, G4, G5
tetap NOT_ASSESSED; OAIE tetap belum terbukti.
