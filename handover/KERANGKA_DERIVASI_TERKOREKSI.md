# KERANGKA DERIVASI SLOT 0007 — TERKOREKSI (Ian, 18 Nov 2026)

*Bentuk terkoreksi dari produk direktur `PRODUK_DIREKTUR_DERIVASI_
0007.md` (brain-of-origin groq/openai/gpt-oss-120b) sesudah
penapisan terhadap kerangka praregistrasi dan rancangan #254.
Slot tetap KOSONG sampai vonis penerus 0006 tersegel; pada hari
vonis, finalisasi berjalan mekanis dari dokumen ini. Penapisan
penuh: handover/PENAPISAN_SIKLUS_PELUANG_DAN_DERIVASI_0007.md.*

## Arsitektur (diterima dari produk)

- Vonis SUPPORTED atau NULL → nilai diturunkan per aturan slot.
- Vonis NOT_DELIVERED (gerbang antar < 75%) atau
  INSTRUMEN_TIDAK_CUKUP (probe < N) → slot TIDAK diturunkan.
  Tidak ada probe susulan/top-up pada paket tersegel; hasil itu
  melahirkan paket kalibrasi baru terpraregistrasi (F → I).

## Aturan per slot (terkoreksi)

1. **Sumber final material pola** (§4 kerangka; slot yang hilang
   dari produk — dipulihkan): bentuk vonis memutuskan sumbernya —
   episode ratified dari lari kalibrasi/lengan penerus (hanya ada
   bila memang dihasilkan) dan/atau korpus beku rumah. Diputuskan
   saat pembekuan material, dicatat dengan sha snapshot.
2. **Organ pendistilasi** (validator vs coder): diturunkan dari
   perilaku per-organ pada kalibrasi penerus — organ mana yang
   penilaiannya stabil/in-band. Vonis NULL = tanpa bukti organ:
   pilihan jatuh ke konvensi tercatat (organ lebih murah) dan
   dinyatakan sebagai konvensi di praregistrasi.
3. **Panjang maksimum pola:** tidak diturunkan dari vonis —
   diturunkan saat pembekuan dari distribusi panjang record
   terdistilasi nyata (cap persentil tinggi), tercatat bersama
   sha snapshot store pola.
4. **Pita margin:** sifat instrumen judge, bukan sifat vonis —
   diturunkan dari data kalibrasi penerus (distribusi in-band
   gelombang-gelombangnya), dinyatakan eksplisit dengan sumbernya
   (bukan warisan diam-diam). NULL tidak mengubahnya; kalibrasi
   gagal membuatnya tak terderivasi.
5. **N probe minimum:** lantai penerus (8) dipertahankan; naik
   hanya bila data variansi vonis menuntut presisi lebih (aturan
   variansi eksplisit — hasil terkoreksi siklus direktur pertama),
   keputusan + basis tercatat.
6. **Sumber kandidat probe + sha:** tindakan pembekuan dari
   korpus beku nyata — gelombang-2 (sha 22b93961…), cadangan
   gelombang-3 (sha 740e8a29…), korpus rumah. Sha dicatat saat
   pembekuan; tidak pernah diturunkan dari vonis.

## Yang dibuang dari produk asli

Slot karangan "ambang kemiripan recall" (recall #254 = pencocokan
kosakata task_shape, tanpa ambang); semua nilai contoh karangan
(label organ v2.1/c3.0, baseline 0005 yang tidak ada, cap 1024/768,
pita 50–70, N=6, corpus_home_v2 + sha contoh, ambang 0,78/0,75/
0,70); dan seluruh cabang "pengukuran tambahan termurah" sebagai
prosedur pasca-vonis.
