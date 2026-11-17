# BLOK D — catatan operasional (DRAF, ditulis sebelum lari; diungkap ke hub sebelum eksekusi)

## Temuan mesin (dari kode, main @ f6d75462)

- `run_discovery` (operator_discovery) TIDAK punya parameter
  prior/katalog-awal. Kandidat lahir per kelas defek dari
  `discover_for_task` atas tugas pool; sebuah key diakui bila
  fix_count ≥ 2 (mengukur perbaikan nyata per tugas).
- Katalog hasil discovery dipakai di waktu SOLVE (lengan
  B/C run_band). Jadi "seed katalog sebagai prior" harus
  didefinisikan pada ekonomi discovery-nya, bukan ditempel
  sebagai daftar key.

## Definisi operasional yang diusulkan

Donor: katalog band 20261904 (6 keys/1 chain, digest
50050728…) — katalog berbeda dari katalog modal 465508ef,
diambil dari checkpoint ter-ratifikasi PR #242.

- **Lengan SEEDED (band 20262001):** (1) solve seluruh pool
  dengan katalog donor; tugas pool yang sudah terpecahkan
  donor KELUAR dari pool discovery (prior sudah menutupnya);
  (2) run_discovery atas pool tersisa; (3) katalog akhir =
  donor ∪ hasil discovery. Biaya total = panggilan fase-donor
  + panggilan discovery, dihitung jujur keduanya.
- **Lengan COLD (band 20262001):** run_discovery atas pool
  penuh; katalog akhir = hasil discovery.
- **Referensi lintas-band:** lengan COLD juga dijalankan di
  20262002 (band segar kedua sesuai praregistrasi).
- **Biaya** diukur sebagai jumlah panggilan `_safe_score`
  (pembungkus penghitung yang murni mengamati — tidak
  mengubah perilaku solver sama sekali) + wall time.
- **Cakupan** diukur pada katalog akhir masing-masing lengan:
  ukuran katalog + solved evaluation/control memakai katalog
  akhir itu (gerbang yang sama).
- **Vonis:** hipotesis transfer TERDUKUNG iff biaya seeded <
  biaya cold secara terukur DAN cakupan seeded ≥ cold DAN
  tidak ada mismatch vonis (solved control/eval seeded tidak
  di bawah cold). Selain itu hipotesis ditutup apa adanya.

## Deviasi dari huruf praregistrasi (diungkap, bukan diam-diam)

Praregistrasi menulis dua band: satu seeded, satu cold.
Perbandingan lintas-band tercemar confound seed (semesta
berbeda → biaya/cakupan tak sebanding langsung). Karena itu
kedua lengan dibandingkan pada SEMESTA YANG SAMA (20262001),
dan band kedua (20262002) menjadi referensi cold lintas-band.
Makna yang diuji tidak berubah: apakah katalog prior
menurunkan biaya discovery menuju cakupan yang sama.

## Eksekusi

Sandbox, detached, per-lengan checkpoint JSON (pintu bisa
jatuh). Engine dijeda selama lari (instrumen sensitif-dinding
60 dtk di solved() abc_v3 + alarm 5 dtk di run_discovery).
Perkiraan: discovery penuh ±55–70 mnt/lengan di era katalog;
tiga lengan ≈ 2–3 jam dinding sandbox.
