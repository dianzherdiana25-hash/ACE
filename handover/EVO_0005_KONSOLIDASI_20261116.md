# EVO 0005 — Konsolidasi (2026-11-16 malam)

Praregistrasi: PR #247 (ter-ratifikasi hub malam ini).
Mesin: PR #246 (ratification_loop + langkah engine
bergate env). Basis kode lari: verify-main2 + berkas
PR #246 (sha modul tercatat di log lari: 4b8226916dfa).
Jendela: sandbox, engine live dijeda, pola EVO 0004.
Amendemen pemilik 16:42: pengukuran PENUH malam ini.

## Vonis: NOL

Klaim §1 — akumulasi record verdict_sealed menaikkan
rate ratified held-out saat ringkasannya diberikan
sebagai konteks proposer — TIDAK TERDUKUNG pada N=8
di famili ini. Ketiga lengan sahih mendarat di angka
yang sama persis:

| lengan | code | language | total |
|---|---|---|---|
| BEFORE (terkoreksi) | 3/4 | 4/4 | 7/8 = 0.875 |
| AFTER-akumulasi | 3/4 | 4/4 | 7/8 = 0.875 |
| AFTER-sham | 3/4 | 4/4 | 7/8 = 0.875 |

Kedua klausa praregistrasi gugur oleh kesetaraan:
R_after_acc > R_before tidak terpenuhi (sama), dan
R_after_acc > R_after_sham tidak terpenuhi (sama).
Pola per-episode identik lintas lengan: ho-code-001
gagal di semua lengan (sifat episode itu, konsisten
dengan ep-code-001 di 0003/0004); sisanya lolos di
semua lengan. Konteks akumulasi dan konteks sham
tidak menghasilkan perbedaan yang terukur.

## Mesinnya sendiri bekerja penuh

Lengan AKUMULASI berjalan lewat langkah engine yang
ter-wire (execute_ratification_step, store SALINAN):
8/8 episode latih ratified, 8 record verdict_sealed
tertulis ke memory store salinan, cursor + event store
per episode. Yang NOL adalah klaim efek konteksnya,
bukan fungsi loop-nya.

## Insiden outage + koreksi (keputusan hub ±20:00)

ace-front OOM-killed 19:32:18 di tengah lengan BEFORE
(jurnal systemd; restart otomatis, counter 5; sehat
sesudahnya, MemoryCurrent ±3,6 GB dari cap 6 GiB).
Empat baris bahasa BEFORE adalah baris outage (satu
mati di tengah 900 dtk, satu koneksi putus, dua
BrainUnavailable wall 0) — DIPERTAHANKAN di
before.jsonl dan ditandai invalid_by_outage di vonis
terkoreksi; set bahasa BEFORE diukur ulang dengan
front sehat (before_lang_remeasure.jsonl: 4/4) dan
R_before sahih lahir dari gabungan code BEFORE +
pengukuran ulang itu. Vonis tidak berubah oleh
koreksi (NOL oleh klausa sham sekalipun R_before
mentah yang tercemar dipakai). Pola OOM front pada
generasi panjang di cap 6 GiB tercatat sebagai
catatan desain; bukan perbaikan malam ini.

## Konteks sham

n_acc = 8 (maksimum; tidak ada episode latih yang
gagal), jadi konteks sham dibangun dari 5 id
non-ratified lengan BEFORE (termasuk id outage —
string sham bersifat sintetis bentuk-sama, tercatat
apa adanya di sham_context.json).

## Bukti

evidence/evo0005/: before.jsonl, after_acc.jsonl,
after_sham.jsonl, before_lang_remeasure.jsonl,
accumulation.json, sham_context.json,
evo0005_verdict.json (vonis runner, R_before
tercemar outage), evo0005_verdict_corrected.json
(vonis final), evo0005.log.
