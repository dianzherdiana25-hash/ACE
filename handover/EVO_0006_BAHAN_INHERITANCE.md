# EVO 0006 — Bahan Desain: Uji Inheritance Memory-Store
## (Ian, 2026-11-16 — bahan saja, bukan praregistrasi)

## Pertanyaan

Apakah instans ACE yang SEGAR (proses + workspace baru)
yang di-seed dengan memory store yang sudah terakumulasi
berperilaku berbeda — terukur lebih baik — daripada
instans segar dari nol, pada tugas yang sama? Ini uji
G4-style pada level store kognitif: yang diwarisi bukan
katalog solver (sudah terdemonstrasi di EVO 0004 Blok D
untuk katalog operator), melainkan record memori hasil
ratifikasi (verdict_sealed dkk).

## Bentuk uji (draf)

- Dua workspace salinan: SEEDED (cognitive_memory = salinan
  store akumulasi 0005 + store live bila diizinkan) vs
  KOSONG (cognitive_memory baru, hanya seed bawaan).
- Keduanya menjalankan himpunan episode probe yang sama
  lewat ratification_loop DENGAN konteks recall aktif
  (recall_context atas store masing-masing): yang kosong
  me-recall hampir-nol record; yang seeded me-recall
  record akumulasi.
- Metrik: rate ratified probe + jumlah record yang
  ter-recall dan benar-benar masuk konteks proposer
  (jejak recall dicatat per episode).
- Kontrol: episode probe disjoint dari famili latih DAN
  held-out 0005; urutan sama; organ sama.

## Yang harus diputuskan sebelum praregistrasi

1. Sumber seed: store akumulasi 0005 (kecil, murni) vs
   store live engine (besar, campuran kelas) — atau dua
   lengan seeded terpisah.
2. Apakah "instans segar" berarti workspace saja, atau
   juga proses engine baru dengan status file baru
   (definisi G4 yang lama memakai kelahiran ulang penuh).
3. Ambang vonis: selisih rate minimum yang dianggap
   inheritance nyata vs derau pada N kecil.

## Status

Bahan desain untuk EVO 0006; belum praregistrasi, belum
diukur. Menunggu giliran sesudah vonis 0005 (mekanisme
recall yang sama adalah prasyaratnya).
