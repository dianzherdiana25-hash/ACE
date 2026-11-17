# PREREGISTRASI EVO 0005 — DRAF (Ian, 2026-11-16; untuk ratifikasi hub)

## §1 Klaim

Akumulasi write-back ratifikasi adalah ASET yang terukur:
sesudah N episode famili latih melewati loop ratifikasi
(Tahap 2) dan yang ratified tertulis-balik sebagai record
verdict_sealed, laju ratified pada famili HELD-OUT yang
belum pernah dilihat NAIK dibanding baseline (before) —
ketika record akumulasi disediakan sebagai konteks proposer.

Mekanisme yang diuji persis: generasi terkondisi-memori.
Bukan "engine menjadi lebih pintar" secara umum.

## §2 Famili & korpus (dibekukan sebelum lari)

- Famili LATIH: 8 episode baru (4 code + 4 language),
  disjoint dari korpus 0003/0004.
- Famili HELD-OUT: 8 episode baru (4 code + 4 language),
  disjoint dari keduanya dan dari famili latih.
- Keduanya dibekukan sebagai JSONL + sha256 di paket ini
  sebelum pengukuran apa pun.

## §3 Lengan (semua instrumen v2, pasangan PR #238)

1. **BEFORE:** held-out diukur dengan loop polos (proposer
   tanpa konteks memori) → R_before per jenis + gabungan.
2. **AKUMULASI:** famili latih dijalankan lewat loop
   ter-wire (Tahap 2) ke store SALINAN (bukan store live);
   record verdict_sealed yang tertulis dihitung (n_acc).
3. **AFTER-AKUMULASI:** held-out diukur lagi; prompt
   proposer ditambah ringkasan record verdict_sealed
   akumulasi sebagai konteks → R_after_acc.
4. **AFTER-SHAM (kontrol):** held-out diukur dengan konteks
   sama panjang dari record TAK-teratifikasi / famili lain
   → R_after_sham. Lengan ini memisahkan "konteks apa pun
   membantu" dari "akumulasi ratified membantu".

## §4 Vonis

- TERDUKUNG iff R_after_acc > R_before DAN
  R_after_acc > R_after_sham (gabungan; per-jenis dicatat).
- NOL bila salah satu gagal. Bila n_acc = 0, akumulasi
  tidak terjadi dan misi berhenti di gerbang itu sebagai
  TIDAK_BERJALAN_AKUMULASI_KOSONG.

## §5 Urutan malam ini (DIAMENDEMEN pemilik 2026-11-16 16:42)

Amendemen pemilik (via hub): aturan jendela G5 dibebaskan;
target malam ini = gerbang kecerdasan OAIE ujung-ke-ujung.
Konsekuensinya bagi misi ini: pengukuran 0005 berjalan
PENUH malam ini — BEFORE → AKUMULASI → AFTER-AKUMULASI →
AFTER-SHAM dalam satu rangkaian sesudah Tahap 2
ter-ratifikasi. N (jumlah episode latih yang benar-benar
melewati loop) adalah yang muat malam ini dari famili
latih yang beku (maksimum 8); N dan cakupan aktual dicatat
apa adanya di laporan hasil, bukan diandaikan penuh.

## §6 Binding

Store salinan untuk akumulasi; store live tidak disentuh.
Engine dijeda selama jendela ukur (pola 0004). Tanpa model
baru, tanpa front baru, tanpa merge.
