# ACE Ω — Hasil Semesta Generalisasi Grid (Tahap F, 2026-11-12)

**Pertanyaan resmi** (keputusan direktur, Addendum 26): apakah
substrat struktural grid (PR #125, 58/58 pada katalognya)
menggeneralisasi, atau hanya menghafal katalog operatornya?

**Jawaban terukur: hafalan katalog.** Pada instrumen yang valid,
tidak satu pun lengan menyelesaikan satu pun tugas kelas-baru.

## Tiga putaran — dua invalidasi yang jujur, satu pengukuran sah

Pagar validitas yang dipra-registrasi bekerja dua kali sebelum
pengukuran yang sah tercapai; keduanya dicatat, bukan dihapus:

- **v1** (`pilot-grid-gen-v1`, protocol hash
  `fe984a8bc904c485…`): set shown terkecil yang identifiable →
  kontrol katalog 47% < garis 80% → **invalid** (kelaparan sinyal;
  diagnosis: 13/18 kegagalan kontrol adalah pencarian yang bahkan
  tak mencapai shown-sempurna).
- **v2**: set shown terbesar → holdout kehabisan kasus gagal →
  kontrol nol "menyelesaikan" 64/114 → **invalid** (holdout tak
  diskriminatif).
- **v3** (`pilot-grid-gen-v3`, protocol hash
  `65358f589514889363fb9128065b207ec59837026c8b8f8ac73dc8c4089e179e`,
  audit kernel **CLEAN**): pool 20 kasus, shown dibatasi
  failing−3 sehingga setiap holdout menyimpan ≥3 kasus gagal.
  Semesta aktual: train 36, new_only 47, mixed 32, kontrol 34
  (satu tugas bounds_off_by_one tak terbangun — tercatat sebagai
  kegagalan generasi).

## Hasil v3 (semua lengan identik)

| subset | A | B | C | kredit parsial (rerata fraksi holdout) |
|---|---|---|---|---|
| new_only (47) | **0** | **0** | **0** | 0,3702 |
| mixed (32) | 2 | 2 | 2 | 0,4833 |
| catalog_control (34) | 33 | 33 | 33 | 0,9804 |
| kontrol nol (113) | — | — | — | 0 terselesaikan |

Kondisi validitas: kontrol katalog 97% ≥ 80% ✓; kontrol nol
0/113 ✓; audit CLEAN ✓.

## Interpretasi

1. Kompetensi substrat v1 berhenti persis di batas katalognya.
   Empat kelas defek baru (dist_step_2, bounds_off_by_one,
   returns_start_distance, wall_char_x) tidak tersentuh oleh satu
   pun operator — termasuk wall_char_x yang gejalanya sama dengan
   walls_passable tetapi mekanismenya berbeda: substrat mencocokkan
   *mekanisme yang dikenal*, bukan gejala.
2. Kredit parsial 0,37 pada new_only adalah kasus yang memang
   tidak terpengaruh defek — bukan perbaikan parsial atas defek
   baru.
3. A = B = C identik di semua subset: dengan 3 operator dan
   ekspansi greedy best-first, pembelajaran urutan/subset tidak
   punya ruang untuk berbeda. Perbedaan lengan membutuhkan ruang
   operator yang lebih kaya — pelajaran desain untuk pilot
   berikutnya, sejajar dengan saturasi v1/v2 di G2.
4. Konsekuensi program: pertumbuhan kemampuan ACE berikutnya
   bukan penyetelan lengan, melainkan **pertumbuhan katalog itu
   sendiri** — operator baru harus *ditemukan/diusulkan* (oleh
   direktur riset lokal atau proses sintesis operator), bukan
   ditulis tangan per kelas. Itu kandidat tahap terukur berikutnya
   yang sesungguhnya.

Status gerbang tidak berubah: G2 tetap MEASURED-nol pada semesta
ekspresi; pengukuran ini menambah satu fakta terukur tentang
substrat grid, bukan gerbang baru.
