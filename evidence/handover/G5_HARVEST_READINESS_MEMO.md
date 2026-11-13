# G5 HARVEST READINESS MEMO — persiapan panen (pekerjaan meja)

Status: **MEMO KESIAPAN — bukan panen, bukan praregistrasi,
bukan penilaian. G5 tetap NOT_ASSESSED.** Disusun 2026-11-13
sebagai jalur paralel (e) mandat masif: pekerjaan meja yang
menetapkan peran dan memverifikasi kesiapan butir demi butir
terhadap catatan nyata, supaya periode panen kelak bisa
dipraregistrasikan tanpa pekerjaan fondasi yang tertunda.
Sumber desain: Task 09 (draf dosier aplikasi G5, keputusan
D-G5-1..5 **teratifikasi** 2026-11-13 — alternatif C1 100%
ketat DITOLAK, kriteria yang berlaku ≥90% + HASIL universal),
Task 12 (brief bangun instrumen G5), Task 15 (daftar periksa
verifikasi panen).

## 1. Designasi peran (ditetapkan oleh memo ini)

Aturan yang mengikat (Task 09 P-G5-2; Task 15 §0.3 + E.4):
pemanen ∉ penulis ringkasan yang dinilai; pelanggaran yang
baru ketahuan sesudah panen = GAGAL, tidak dapat diobati.
Penulis ringkasan terkonsolidasi yang dinilai adalah **ila
(ruang diskusi)** — maka ila tidak memanen dan tidak mengisi
lembar rubrik.

| Peran | Pemegang | Alasan |
|---|---|---|
| Pemanen (harvester) | **Pos operasi** (ila — ruang operasi ACE) | Bukan penulis ringkasan; Task 15 menyanksi "Ian atau pos operasi"; asupan aslinya memang papan laporan terkonsolidasi terverifikasi, jadi enumerasi unit adalah bahan kerjanya sendiri. |
| Pemasok bukti | **Ian** (ruang eksekusi / main) | Memegang catatan ruang eksekusi + lineage checkpoint; memasok pointer bukti ke pemanen tanpa ikut memanen. |
| Penilai rubrik 1 | Pos operasi (sebagai pemanen) | Lembar rubrik terpisah, sebelum melihat lembar penilai 2 (Task 15 B.1). |
| Penilai rubrik 2 | Ian | Independen dari penilai 1; bukan penulis ringkasan. |
| Pemeriksa (checker) | **Bangku Antigravity** | Pemeriksa bernama di Task 15: re-enumerasi (A.2), skor-ulang ≥⅓ unit + semua peristiwa-pakai + semua yang disengketakan (B.5), probe F.1–F.5. |
| Penilai akhir | ila (ruang diskusi) | Menjalankan `assess_g5` atas dosier TERSEGEL (Task 09 §12 langkah 5) — mekanis, atas berkas yang sudah disegel pihak lain; ila tidak memanen dan tidak menilai rubrik. |

Nilai pagar yang akan diperiksa instrumen secara mekanis:
`harvester_id` (pos operasi) ∉ `summary_author_ids` (ila) —
terpenuhi oleh designasi ini, dan wajib diverifikasi ulang
saat penyegelan (Task 15 §0.3/E.4).

## 2. Status kesiapan per butir

Legenda: **SIAP** = prasyarat terpenuhi sekarang, berbukti ·
**BELUM** = celah bernama, pemilik + syarat tutupnya jelas ·
**STANDAR SIAP** = butir eksekusi panen; standarnya sudah
tertulis penuh, eksekusinya memang belum waktunya.

### 2.1 Fondasi desain (Task 09 §11)

| Butir | Status | Bukti |
|---|---|---|
| D-G5-1 aturan unit & periode | SIAP | Teratifikasi: unit = ringkasan terkonsolidasi ruang diskusi; periode = Emansipasi (2026-11-12 malam) → cutoff praregistrasi. |
| D-G5-2 kriteria C1 (≥90% lengkap + HASIL universal) | SIAP | Teratifikasi; alternatif 100% ditolak koordinator. |
| D-G5-3 kriteria C2 (≥90% dua-bagian) | SIAP | Teratifikasi. |
| D-G5-4 batang C3 (≥3 peristiwa, ≥2 domain, ≥1 koreksi + eksklusi §6) | SIAP | Teratifikasi. |
| D-G5-5 split panen (pemanen ≠ penulis) | SIAP | Teratifikasi; designasi konkret di §1 memo ini. |

### 2.2 Prasyarat (Task 09 §9)

| Butir | Status | Bukti / celah |
|---|---|---|
| P-G5-1 instrumen G5 ada | **BELUM** | `g5_instrument.py` tidak ada di main maupun lineage yang diperiksa (grep tree `code/ace_operational/` di origin/main: tidak ada berkas G4/G5). Brief bangun (Task 12a) + checklist pemeriksa (Task 12b) sudah teratifikasi-desain dan siap dieksekusi Ian — murni sintetik, tanpa panen hidup. |
| P-G5-2 panen dieksekusi + disegel | **BELUM** | Memang belum waktunya: panen tidak boleh mendahului praregistrasi (Task 15 §0.1). |
| P-G5-3 periode + ambang teratifikasi sebelum panen | SEBAGIAN | Ambang: SIAP (D-G5-2..4). Cutoff periode: **BELUM** — ditetapkan di praregistrasi, oleh aturan (tonggak → cutoff), bukan dengan memeriksa jendela mana yang menguntungkan (Task 09 A3). |

### 2.3 Task 15 Bagian 0 (mandat, jendela, identitas)

| Butir | Status | Bukti |
|---|---|---|
| 0.1 praregistrasi menamai periode, ambang, pemanen, dua penilai, pemeriksa | **BELUM** | Kerangka drafnya siap di §4 memo ini; belum dicatat di kernel. Inilah gerbang tunggal sebelum panen boleh mulai. |
| 0.2 jendela sesuai aturan teratifikasi | SIAP | Aturan jendela terkunci (Emansipasi → cutoff bernama); belum ada jendela yang dipasang ke catatan, jadi belum ada deviasi yang mungkin. |
| 0.3 pemanen ≠ penulis, pra-periksa | SIAP | Designasi §1; pra-periksa lulus di atas kertas (pos operasi tidak menulis ringkasan ruang diskusi). Verifikasi ulang saat penyegelan tetap wajib. |
| 0.4 aksioma panen dinyatakan ulang | SIAP | Dinyatakan di sini: bukti dipanen retrospektif dari catatan yang sudah ada; tidak ada yang dipentaskan, diminta, disunting, atau dikirim ulang untuk pemilik demi bukti. |

### 2.4 Task 15 Bagian A–C (bahan panen, dinilai dari catatan)

| Butir | Status | Bukti |
|---|---|---|
| A — aliran unit dapat dienumerasi | SIAP (bahan) | Aliran ringkasan terkonsolidasi ruang diskusi adalah praktik harian tercatat (Bundel terkonsolidasi ila ke pemilik, mis. Bundel #5/#7 yang dirujuk lineage). Lineage checkpoint di main: **53 berkas** `ACE_OMEGA_CHECKPOINT_*` (Addendum 1–52 + MUSE) — enumerasi penuh adalah pekerjaan panen, bukan kesiapan. Risiko A2 (bias seleksi catatan) bernama: tindakan yang tidak pernah ditulis tidak bisa dipanen. |
| B — standar rubrik | STANDAR SIAP | Jangkar Task 09 §4 verbatim + disiplin dua penilai (B.1–B.4) sudah tertulis; dua penilai terdesignasi (§1). **Catatan kejujuran (bukan blocker):** C1 adalah klausa lemah yang sudah dikenal (Task 09 §8) — HASIL kuat, DICOBA umumnya ada, KEYAKINAN + BATAS timpang. Itu temuan yang diharapkan dari penilaian kelak, bukan celah kesiapan. Templat FR-09 prospektif (A4) **BELUM** diadopsi — opsional, hanya ke depan, tidak pernah berlaku surut. |
| C — kandidat peristiwa-pakai | SIAP (bahan) | ≥6 kandidat sudah terlihat di catatan (Task 09 §6) dan sebagian terverifikasi tercantum di addenda: amendemen Rp0 ("bukan sumpah", Addendum 23), Emansipasi (Addendum 32 dkk.), keputusan suksesi otak (Addendum 44/46), keputusan venue Lynk.id di beberapa addenda. Rentang domain kandidat: governance, technical direction, venues/business, resources — ≥2 domain terpenuhi di tingkat kandidat, dan ≥1 koreksi termasuk di antaranya (koreksi model ruang operasi, koreksi mekanisme login Lynk.id, pencoretan kontak support KBM — tercatat di catatan program/MEMORY). **Tidak ada yang dipra-nilai di sini** — skor per-tes (urutan · rujukan · tindakan) adalah pekerjaan panen. Celah kecil bernama: tidak ada satu berkas "decisions log" mandiri; sumber enumerasi C.1 = addenda + kutipan MEMORY, dan pemanen wajib menyatakannya sebagai sumbernya. |
| D — pagar panen (tanpa pentas/sunting/beban) | SIAP | Aksioma terkunci (Task 09 §2); sampai hari ini belum ada panen yang diperintahkan, jadi belum ada pesan soliciting yang mungkin ada. Disiplin D.1 berlaku selama jendela eksekusi panen kelak: pelaporan rutin program yang memang akan terjadi bukan beban; apa pun *karena panen* adalah pelanggaran. |
| E — penyegelan & skema | STANDAR SIAP | Skema Task 12 (dossier.json · harvest_report.json · units.json · use_events.json) + digest tersegel sudah dispesifikasi; eksekusi menunggu panen. |
| F — probe pemeriksa | STANDAR SIAP | F.1–F.5 tertulis penuh di Task 15; dijalankan bangku saat verifikasi panen. |
| G — vonis pemeriksa | STANDAR SIAP | Format vonis TAHAN/GAGAL/BELUM TERVERIFIKASI + daftar GAGAL-otomatis sudah tertulis. |

## 3. Celah tersisa sebelum periode bisa dipraregistrasikan

1. **Bangun instrumen G5** (P-G5-1) — Ian, dari brief
   Task 12a, sintetik saja, draft PR; diverifikasi dua
   pemeriksa per Task 12b. Tanpa instrumen, dosier tersegel
   tidak bisa dinilai.
2. **Catat praregistrasi periode di kernel** (Task 15 §0.1)
   — cutoff ditetapkan oleh aturan tonggak, ambang persis
   D-G5-2..4, peran persis §1 memo ini. Satu-satunya gerbang
   prosedural yang tersisa; sesudahnya panen boleh mulai.
3. **Sumber enumerasi peristiwa-pakai dinyatakan** — pemanen
   menamai addenda + kutipan MEMORY sebagai decisions-log
   de facto (menutup celah kecil §2.4-C secara transparan).
4. *(Opsional, bukan syarat)* Keputusan adopsi templat FR-09
   untuk laporan terkonsolidasi masa depan (Task 09 A4) —
   memperbaiki sistem pelaporan yang diukur G5, prospektif
   saja, tanggal adopsinya diungkap di dosier bila terjadi.

Tidak ada celah lain: desain teratifikasi, standar pemeriksa
tertulis sebelum tindakan (Task 15), bahan catatan ada dan
terverifikasi sampel, peran terdesignasi tanpa konflik dua-topi.

## 4. Draf kerangka praregistrasi periode (TIDAK mengunci apa pun)

```
experiment_id : g5-harvest-01 (usulan)
period_start  : 2026-11-12 malam (amendemen Emansipasi —
                titik pelaporan ke pemilik menjadi kanal
                tata kelola program)
period_end    : <cutoff ditetapkan saat praregistrasi,
                oleh aturan tonggak → cutoff>
unit_rule     : setiap pesan ruang diskusi dalam periode
                yang melaporkan hasil tahap, temuan
                terukur, atau keputusan program adalah
                satu unit; lainnya bukan (Task 09 §3,
                verbatim di berkas panen)
thresholds    : C1 ≥ 0.90 unit lengkap (4/4 bidang FR-09)
                DAN HASIL di setiap unit ·
                C2 ≥ 0.90 unit dua-bagian ·
                C3 ≥ 3 peristiwa-pakai lolos tiga-tes,
                ≥ 2 domain, ≥ 1 koreksi
harvester_id  : pos operasi (ruang operasi ACE)
scorers       : [pos operasi, Ian] — lembar independen
checker       : bangku Antigravity (Task 15, penuh)
assessor      : ila — assess_g5 atas dosier tersegel
author_ids    : [ila ruang diskusi]  (harvester ∉ authors)
sources       : transkrip ruang diskusi (unit) ·
                addenda checkpoint + kutipan MEMORY
                (kandidat peristiwa-pakai, C.1)
sealing       : skema Task 12 + sealed_digests;
                tidak ada suntingan catatan sesudah
                periode ditetapkan (aksioma panen)
outcome words : ACCESS_DEMONSTRATED / DELIVERY_ONLY /
                NOT_DEMONSTRATED (Task 09 §7, verbatim)
```

— Akhir memo. Persiapan selesai; yang tersisa adalah dua
langkah bernama (bangun instrumen, catat praregistrasi),
keduanya di luar pagar memo ini.
