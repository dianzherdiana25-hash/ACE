# ACE Fase 2 — Pengukuran Kelemahan Keluarga Shipping (2026-11-12)

Item agenda Direktur Riset lokal #3 (Addendum 13). Evidence mentah:
`shipping_diagnostic.json` (30 tugas shipping, level 1–3, seed 1–10;
anggaran 200; solver grammar & token-search dari OMEGA-11).

## Metode

Tiga instrumen: (1) tingkat penyelesaian per set defek di bawah sinyal
kasus-shown yang sebenarnya; (2) ablasi *sinyal oracle* — fitness
dihitung atas SEMUA kasus (hanya diagnostik, bukan kondisi eksperimen
yang sah): bila solver pulih di bawah oracle, hambatannya adalah
kelangkaan sinyal, bukan pencarian/operator; (3) statistik eksposur
shown: setiap tugas punya ≥1 kasus shown yang mengekspos defek (10
tugas tepat 1, 20 tugas tepat 2) — jadi "defek tak terlihat" bukan
penjelasannya.

## Hasil

| Set defek | n | grammar shown | grammar oracle | token shown | token oracle |
|---|---|---|---|---|---|
| free_boundary | 10 | **10/10** | 10/10 | 0/10 | **10/10** |
| multiplier_dropped | 10 | 0/10 | 0/10 | 2/10 | 2/10 |
| keduanya | 10 | 0/10 | 0/10 | 0/10 | 2/10 |

## Diagnosis (tiga penyebab berbeda, terpisah secara kausal)

1. **Celah operator pada grammar (terbukti, bebas-sinyal).**
   `multiplier_dropped` tidak terpecahkan grammar bahkan di bawah
   oracle (0/10): grammar yang diauthor memang tidak punya operator
   pemulih pengali — geser konstanta hanya menyentuh konstanta yang
   disebut spec, sedangkan `*= 1` bukan salah satunya. Ini kekurangan
   kemampuan, bukan kekurangan informasi.
2. **Gradien fitness terlalu lemah untuk token-search.** Pada
   `free_boundary`, token-search 0/10 dengan sinyal shown tetapi
   10/10 dengan oracle: perbaikan yang benar ada di ruang
   substitusinya, tetapi fitness 2-kasus tidak memberi gradien cukup
   untuk memeringkat varian yang benar dalam anggaran.
3. **Tugas komposisi mewarisi kedua masalah** (0/10 shown untuk semua;
   oracle hanya menolong token-search sebagian, 2/10).

## Konsekuensi terukur untuk tahap berikutnya

- Menambah operator pemulih-pengali ke grammar akan mengubah kontras
  OMEGA-11 — itu eksperimen baru, bukan tambalan diam-diam.
- Untuk keluarga seperti shipping, kasus shown per-defek (satu kasus
  mengekspos per defek) atau jumlah shown lebih besar adalah perbaikan
  kurikulum yang terukur manfaatnya (OMEGA-10).
- Desain pilot A/B/C wajib memperlakukan celah operator ini sebagai
  confound yang dipra-registrasi: bekukan substrat solver yang sama
  untuk semua lengan sebelum pra-registrasi, atau stratifikasi hasil
  per set defek. Mengukur pilot di atas bug yang sudah diketahui hanya
  akan mengukur bug itu.
