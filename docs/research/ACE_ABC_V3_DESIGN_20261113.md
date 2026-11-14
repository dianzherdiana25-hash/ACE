# ACE Pilot A/B/C v3 — Desain: lengan dibedakan oleh STRATEGI (2026-11-13)

Dokumen DESAIN untuk dipra-registrasi di kernel OMEGA-06
sebelum pilot dijalankan. Ditulis Ian (Muse) dari bukti
terukur program, bukan dari kerangka v1.

## 0. Mengapa v3 ada: dua null terukur dan satu putusan

- **Pilot v1** (keluarga pricing/shipping): A=B=C=190/200
  pada held-out — saturasi langit-langit; hipotesis TIDAK
  DIDUKUNG. Residu terukur: perangkap identifiabilitas
  shown-set, bukan ketiadaan efek.
- **Pilot v2**: A=B=C=220/220 — saturasi lagi, pada
  semesta yang sama.
- **Putusan item agenda siklus #4** (Addendum 36):
  membedakan A/B/C lewat ruang operator yang lebih kaya
  TIDAK DIDUKUNG sebagaimana dirumuskan; **v3 membedakan
  lengan oleh STRATEGI**. Sejak putusan itu, strategi
  ketiga menjadi konkret terukur: penemuan komposisi v2
  (PR #140) — rantai dengan enumerasi-ulang per langkah
  memecahkan 3/6 tugas pasangan yang 0/6 untuk pasangan
  statis, dan transfer tunggal naik 11 → 15.
- **Pagar G2 (PRD)**: perbandingan adil A/B/C atas tugas
  yang TIDAK dipakai selama evolusi. G2 tetap
  MEASURED — null ×2 sampai v3 berjalan.

Dua kegagalan v1/v2 adalah kegagalan SEMESTA (jenuh) dan
kegagalan LENGAN (tidak terbedakan). Desain ini menyerang
keduanya secara eksplisit.

## 1. Lengan = strategi, di atas substrat dan anggaran yang sama

Substrat bersama: keluarga grid (generator + scorer yang
sama dengan penemuan operator), solver greedy yang sama,
verifier yang sama. Yang berbeda HANYA strategi pencarian
solusi pada saat evaluasi:

- **A — Katalog.** Hanya katalog operator dasar beku
  (`enumerate_variants` atas program tugas). Tanpa
  penemuan, tanpa pembelajaran antar tugas. Ini lengan
  garis-dasar: ACE tanpa mekanisme evolusinya.
- **B — Penemuan tunggal.** Katalog dasar + operator
  TUNGGAL hasil penemuan yang diterima (admission ≥2 dari
  pool latih; `discover_for_task` / `apply_operator`).
  Penyelesaian tetap satu langkah per defek.
- **C — Komposisi.** Seluruh perangkat B + RANTAI yang
  diterima (admission ≥2 menurut tanda-tangan rantai;
  `discover_chain_for_task` dengan enumerasi-ulang pada
  program antara; `apply_chain` saat penyelesaian).

Mesin penemuan TIDAK dibangun ulang: `run_discovery`
yang terukur di v4 (bukti `operator_discovery_v4.json`)
menghasilkan katalog tunggal + rantai yang diterima;
desain ini mensyaratkan fungsi penyelesaian di dalamnya
(`solve_with`) diangkat menjadi pemecah per-lengan yang
dapat dipakai ulang dengan penghitung anggaran — satu
refaktor kecil, diuji terhadap replikasi angka v4
(gerbang yang sama dengan prasyarat P1 tahap aplikasi
G3: perilaku lama harus tereplikasi persis sebelum
dipakai mengukur hal baru).

Di dalam pilot tidak ada LLM dan tidak ada direktur:
strategi adalah mekanisme ACE sendiri (aturan dua topi).

## 2. Semesta: tak-jenuh oleh konstruksi, berstrata oleh daya beda

Semua tugas evaluasi HELD-OUT terhadap evolusi: identitas
program (digest) tidak muncul di pool mana pun (pool,
pair_pool, chain_pool, kontrol). Tiga strata, masing-masing
dipilih karena daya bedanya yang TERUKUR:

- **S1 — terpecahkan-oleh-penemuan** (target ≥30 tugas):
  kelas defek di mana katalog dasar gagal tetapi operator
  tunggal temuan terukur berpindah >0 (zona Stage I /
  komposisi v2: bounds, returns_start, dan kawanannya).
  Membedakan B,C > A.
- **S2 — butuh komposisi** (target ≥30 tugas): tugas
  multi-defek bermasking berbentuk pool rantai, di mana
  tunggal terukur berhenti (rantai 3/6 vs pasangan 0/6).
  Membedakan C > B.
- **S3 — kontrol** (target ≥15 tugas): tugas katalog
  dasar (kontrol 34/34 pada semua run penemuan). Semua
  lengan wajib tetap di langit-langit; regresi di sini
  membatalkan klaim mana pun.

**Gerbang anti-saturasi (dipra-registrasi, pola P4 sensus
harga)**: sebelum run resmi, lintasan kalibrasi atas set
kalibrasi yang TERPISAH dari set evaluasi mengukur lengan
A. Run resmi hanya sah bila tingkat penyelesaian A pada
kalibrasi berada ketat di antara 10% dan 90% keseluruhan
dan S3 di langit-langit. Gagal → semesta digenerasi ulang
lebih keras/lebih mudah (pita seed baru) dan kalibrasi
diulang; set evaluasi tidak disentuh sebelum gerbang
lulus. Hasil SATURATED_BY_DESIGN dicatat sebagai
INCONCLUSIVE, bukan sebagai null — membedakan "semesta
rusak" dari "strategi setara" adalah pelajaran v1/v2.

Pengulangan (menjawab syarat PRD ≥3): semesta evaluasi
dibangun dari TIGA pita seed yang saling lepas; hasil
dilaporkan per pita dan tergabung. Mesinnya deterministik
— pengulangan di sini menguji kepekaan terhadap semesta,
bukan terhadap kebisingan sampling solver.

## 3. Kontrol adil

- **Anggaran dalam panggilan-skor.** Setiap lengan per
  tugas mendapat plafon panggilan `_safe_score` yang
  IDENTIK (langkah rantai memakan anggaran yang sama
  dengan langkah tunggal — di sinilah komposisi membayar
  biayanya secara adil), plus plafon dinding per tugas.
  Pelanggaran anggaran = tugas itu tak-terpecahkan bagi
  lengan tersebut, tercatat, bukan ABSTAIN diam-diam.
- Penemuan (untuk B dan C) berjalan SATU KALI atas pool
  latih yang sama, sebelum evaluasi; katalog + rantai
  yang diterima dibekukan dan didigest. Lengan A tidak
  menerima artefak penemuan apa pun.
- Kustodi kernel penuh: pra-registrasi (hash protokol +
  aturan lulus + garis dasar A dari kalibrasi) sebelum
  hasil evaluasi ada; digest kandidat per lengan dan
  evaluator terpisah; semua kegagalan disimpan.

## 4. Aturan keputusan (dipra-registrasi; pelajaran bake-off 01 diterapkan)

Metrik per lengan: tingkat penyelesaian held-out per
strata dan keseluruhan. Klaim yang diuji: **urutan
strategi C > B > A adalah nyata, bukan artefak semesta.**

Indeks diferensiasi (SATU metrik komposit — kernel
menurunkan verdict dari satu metrik, jadi konjungsi
dikodekan di dalamnya, bukan ditulis sebagai prosa):

```
DI = min( (C - A) - 15 , (B - A) - 5 , kontrol_margin )
kontrol_margin = tingkat S3 terendah antar lengan - 100% + toleransi 0
                 (0 bila tak ada regresi; negatif bila ada)
DI >= 0  ->  DIFFERENTIATION_DEMONSTRATED (pass)
DI <  0  ->  NOT_DEMONSTRATED (fail)
```

Ambang diturunkan dari efek terukur, bukan dibulatkan
dari udara: rantai 3/6 vs 0/6 pada tugas berbentuk-S2
adalah +50pp pada strata itu; agregat keseluruhan yang
jujur jauh lebih kecil, maka C−A ≥ +15pp keseluruhan
adalah klaim yang berarti tetapi terjangkau. B−A ≥ +5pp:
transfer tunggal terukur naik +4 kelas dari 15 pada
komposisi v2 — efek tunggal nyata tetapi lebih kecil,
maka ambangnya lebih rendah. Kontrol tanpa toleransi:
regresi apa pun pada tugas yang sudah bisa dipecahkan
katalog membatalkan narasi peningkatan.

Kosakata hasil yang mungkin, semuanya dicatat apa
adanya: DIFFERENTIATION_DEMONSTRATED / NOT_DEMONSTRATED /
SATURATED_BY_DESIGN (gerbang kalibrasi gagal) /
INCONCLUSIVE (anggaran waktu habis sebelum evaluasi
lengkap — dilaporkan parsial, tidak dilengkapi).

Pemetaan gerbang: hasil v3 memberi makan penilaian G2.
DI ≥ 0 dengan audit CLEAN = bukti diferensiasi strategi
pertama yang terukur; DI < 0 = null KETIGA yang terukur,
dan konsekuensinya bukan "coba lagi" melainkan item
agenda baru tentang mengapa strategi tidak berpindah —
sesuai doktrin bahwa setiap null melahirkan item
mekanisme berikutnya.

## 5. Bentuk implementasi dan biaya

Satu driver baru (`abc_v3_run.py`) di atas
`operator_discovery` yang ada + satu kernel baru
(`abc-v3-kernel`). Urutan tahap pembangunan nanti:
(1) angkat `solve_with` menjadi pemecah per-lengan
beranggaran + gerbang replikasi v4; (2) sensus semesta
grid untuk strata S1/S2/S3 (pola sensus Task 07:
enumerasi kejenuhan generator per kelas defek);
(3) kalibrasi; (4) pra-registrasi dengan DI sebagai
aturan metrik tunggal; (5) run. Biaya terukur dari run
v4: penemuan ~1.337 dtk; evaluasi adalah detik-solver
per tugas — total diperkirakan < 1 jam dinding. Rp0,
tanpa LLM, deterministik.

## 6. Keputusan desain yang dinyatakan terbuka

1. **Keluarga grid saja.** v3 tidak menunggu prasyarat
   P1 (decouple dari grid) milik aplikasi G3; lintas-
   keluarga adalah v4 bila v3 menunjukkan diferensiasi.
   Alasan: mesin yang terukur hari ini adalah grid, dan
   pertanyaan v3 adalah tentang strategi, bukan keluarga.
2. **A sebagai garis dasar, bukan B.** Putusan siklus #4
   membingkai ulang lengan sebagai strategi; A=Katalog
   adalah satu-satunya garis dasar yang membuat B dan C
   dapat diatribusikan ke mekanismenya masing-masing.
3. **Ambang 15/5 pp bersifat dapat digugat.** Keduanya
   diturunkan dari angka terukur di §4; siapa pun yang
   meratifikasi desain ini boleh menantang turunannya —
   tetapi ambang terkunci di pra-registrasi, sebelum
   hasil, atau pilotnya tidak berarti.

Status gerbang sesudah dokumen ini: tidak berubah.
**G2 tetap MEASURED — null ×2.** Desain bukan hasil.
