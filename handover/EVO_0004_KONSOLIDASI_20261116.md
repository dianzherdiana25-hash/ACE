# EVO 0004 — Konsolidasi

Basis: main @ f6d75462 + PR #242 (konsolidasi EVO 0003).
Praregistrasi: PR #243 (ter-ratifikasi). Urutan eksekusi
B → A → D → C. Prinsip pemilik: masif di inti, tidak ada
yang aneh; tanpa model baru, tanpa front baru.

## Blok B — audit jalur tulis (PASS, ter-ratifikasi)

Utang B4 EVO 0003 terjawab. Kelas event khusus
`writepath_audit_probe` terdaftar di EVENT_CLASSES lewat
PR #244 (draft, head 5e71eff5; tes 10/10 termasuk kelas tak
terdaftar 'evo0003_blast_b4_probe' tetap ditolak).

Audit di atas salinan snapshot B4 (sha pin 80556222…):
record mem_6f68e996487f8dbc298f tertulis, terbaca kembali
cocok (kelas + ringkasan + provenance == sha256 bukti blast
report), replay mengembalikan id yang sama tanpa duplikat,
kelas tak terdaftar ditolak → **PASS**.
Bukti: evidence/evo0004/blokb_audit.json.

B2 (retest baterai di semesta bersaksi hidup, band
20261903 — flips 020/021/024 dari blast ter-ratifikasi):
stok SUSCEPTIBLE 3/3, guarded NOT_SUSCEPTIBLE 3/3 →
**PASS**. Ambiguitas B2 0003 (0/1 tanpa saksi) tertutup:
guard bekerja persis seperti dirancang.
Bukti: evidence/evo0004/blokb2_result.json.

## Blok A — §1 cakupan penuh (TERDUKUNG, ter-ratifikasi)

Kedelapan episode korpus beku (sha 60177c51…) di bawah
instrumen v2 (judge via chat_structured), pelari TUNGGAL
sekuensial, preflight di dalam runner (sha + set episode
persis per jenis — dua cacat 0003 dirancang keluar),
engine dijeda selama jendela:

- language: **4/4 ratified (rate 1.0)**, dinding
  388/82/90/113 dtk.
- code: **3/4 ratified (rate 0.75)** — ep-code-001 tidak
  ratified (konsisten dengan dua pengukuran 0003 atas
  episode itu; sifat episode, bukan noise).
- errors 0. Kriteria ketat praregistrasi (kedua jenis > 0)
  TERPENUHI — vonis cakupan-terpotong 2/8 dari kotak 10
  menit pemilik (EVO 0003) gugur oleh pengukuran penuh.

Satu cacat kosmetik diakui: baris HEALTH_ERROR di log awal
(snapshot diagnostik memanggil health() tanpa argumen
organ); panggilan episode tidak terpengaruh.
Bukti: evidence/evo0004/bloka_summary.json +
bloka_results.jsonl.

## Blok D — transfer katalog (VONIS: TERDUKUNG)

Definisi operasional ter-ratifikasi hub sebelum lari
(deviasi diungkap): kedua lengan dibandingkan pada semesta
yang sama (20262001) untuk membunuh confound seed;
20262002 = referensi cold lintas-band. Donor: katalog
20261904 (digest 50050728…). Biaya = panggilan _safe_score
(penghitung murni-mengamati) + wall; cakupan = solved
evaluation/control dengan katalog akhir.

| lengan | panggilan skor | wall | katalog akhir | eval | control |
|---|---|---|---|---|---|
| cold 20262001 | 23.507 | 1.569 dtk | 6 keys/2 chains | 29/29 | 34/34 |
| seeded 20262001 | **14.748** (donor 42 + discovery 14.706) | 46 + 327 dtk | 6 keys/1 chain (= donor) | 29/29 | 34/34 |
| cold 20262002 (referensi) | 37.231 | 2.942 dtk | 60 keys/1 chain (digest == katalog anchor a6768563…) | 30/30 | 34/34 |

Anatomi: katalog donor dari band LAIN memecahkan SELURUH
pool band baru (12/12 tugas, hanya 42 panggilan) — transfer
lintas-band nyata dan kuat pada famili tugas ini. Sisa
biaya seeded adalah overhead tetap run_discovery (fase
pair/chain + sapuan ukur internal) atas pool kosong.
Penghematan total 8.759 panggilan (−37%) pada cakupan
solved yang identik di kedua split → kriteria praregistrasi
terpenuhi: **TERDUKUNG**.

Bukti: evidence/evo0004/blokd_verdict.json (+ per-lengan).

## Blok C — peran Sahabat (keputusan tercatat)

Sahabat-AI-9B = organ on-demand untuk tugas batch Bahasa
Indonesia; bukan always-on, bukan hakim loop (tg ±0.9–1.0
t/s, bench T3). Smoke generation Bahasa Indonesia:
**SMOKE_OK** — paragraf pembuka surat resmi kepala desa
tentang gotong royong, koheren dan sopan, wall 131.9 dtk
pada llama-cli b12316 -t 1 (footer sesi mencatat
Generation 1.0 t/s, konsisten dengan T3).
Naskah penuh: handover/EVO_0004_BLOKC_KEPUTUSAN.md;
bukti: evidence/evo0004/blokc_smoke.json.

## Penutup

Engine hidup kembali belajar sesudah jendela ukur tutup.
Tanpa penggabungan (merge) dalam misi ini — semua PR
draft, sesuai kewenangan pemilik.
