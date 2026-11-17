# RANCANGAN EVO 0007 — Recall Pola Terdistilasi ala Katalog
## Dokumen desain (Ian, 2026-11-17 pagi) — BUKAN praregistrasi

Status: rancangan saja, atas arahan hub. Praregistrasi
0007 menunggu vonis penerus 0006 — karena mesin probe
set 0007 mewarisi kalibrasi apa pun yang divalidasi
penerus 0006 (margin judge), dan tidak ada gunanya
membekukan 0007 di atas instrumen yang belum terbukti
bisa mengisi pita.

## 1. Hipotesis

Konteks yang dibangun dari POLA TERDISTILASI — bukan
receipt ratifikasi — mengangkat accept-rate proposer
pada probe set terkalibrasi margin. Dasar keberadaan:
Blok D (EVO 0004) membuktikan artefak ber-isi (katalog
operator) berpindah lintas konteks dengan efek terukur;
diagnosis 0005 (PR #250) membuktikan receipt metadata
gagal ganda: tidak terkirim (recall 0/8 pada 7 episode)
dan tidak berguna sekalipun terkirim.

## 2. Record pola — skema

Satu record pola per episode ratified, ditulis pada
saat write-back oleh organ validator (yang sudah
membaca output + menulis reasons), berisi:
- `task_shape`: jenis + ciri struktural tugas DALAM
  kosakata tugasnya sendiri (agar recall menemukan
  relevansi — pelajaran pengantaran 0005);
- `approach`: langkah/ceklist yang menghasilkan output
  yang diterima (distilasi dari output yang lolos);
- `pitfalls`: titik kritis penerimaan dari reasons
  judge — apa yang diperiksa judge, apa yang hampir
  menggagalkan, jebakan yang harus dihindari;
- `source_episode`: id episode asal (provenance).
Disimpan lewat record_verified_event sebagai kelas
event baru `pattern_distilled` (kind semantic) —
penambahan EVENT_CLASSES = catatan bangun, pola PR #244.

## 3. Jalur recall

Sama dengan yang sudah ada: recall_context atas record
pola; konteks yang disisipkan ke proposer adalah
approach + pitfalls dari pola-pola ter-recall (bukan
metadata episode). Gerbang pengantaran ≥ 75% berlaku;
konteks per episode tercatat kelas-satu.

## 4. Sketsa lengan (untuk praregistrasi kelak)

Empat kondisi pada probe set terkalibrasi margin yang
sama: (a) konteks pola terdistilasi; (b) konteks receipt
(bentuk 0005, sebagai pembanding langsung); (c) sham
sepadan bentuk dari episode tak-ratified; (d) tanpa
konteks. Vonis pada accept-rate dengan gerbang
pengantaran per lengan-konteks. Pertanyaan yang dijawab
desain ini: apakah ISI (pola) yang mengangkat, atau
sekadar KEHADIRAN konteks — pemisahan yang tidak bisa
dilakukan 0005 karena treatment-nya tidak sampai.

## 5. Yang belum diputuskan (sengaja)

Ukuran distilasi (panjang pola maksimum), organ
pendistilasi final (validator vs coder), ambang
kemiripan recall, dan N probe — semuanya menunggu
bentuk kalibrasi final dari penerus 0006.
