# PENAPISAN PRODUK DIREKTUR PERTAMA — Ian

*Penapisan atas `handover/PRODUK_DIREKTUR_PERTAMA.md`
(brain-of-origin: groq/openai/gpt-oss-120b; generasi hub 18 Nov 2026,
2.367 token penyelesaian dalam 4,88 dtk ≈ 485 t/s). Setiap aset
bernama di kolom "aset rumah dipakai ulang" kucek terhadap repo
(origin/main). Hasilnya menentukan vonis; produknya sendiri mendarat
di register apa pun vonis usulannya — penapisan adalah gerbang
agenda, bukan gerbang kustodi.*

## Hasil cek aset (semua nama kucek satu per satu)

| Nama yang diklaim produk | Di repo? | Padanan nyata |
|---|---|---|
| `agenda_log` (tabel) | **TIDAK ADA** | agenda hidup di store engine; register peluang di `opportunity_register.py` |
| skrip audit G1–G5 | **TIDAK ADA** | penilaian G5 = dokumen dossier + PR #249 |
| modul `judge_stats` | **TIDAK ADA** | data skor = berkas wave jsonl + `screen_census` (#257) |
| `judge_log` | **TIDAK ADA** | log runner `evo0006p.log` + jsonl per fase |
| flag `--knowledge-mode` di #276 | **TIDAK ADA** | `pattern_distill.py` nyata (#276); CLI-nya tanpa flag itu |
| modul `mem_profile` di engine | **TIDAK ADA** | — |
| skrip `socket_keepalive` | **TIDAK ADA** | — |
| modul `gate_lift` + patch `lift_fix_v1` | **TIDAK ADA** | — |
| skrip `royalty_audit` | **TIDAK ADA** | `royalty_track.py` nyata (#284) |
| flag konfigurasi `serial4_closed` | **TIDAK ADA** | toggle "Selesai" = keadaan UI platform KBM |

Sepuluh dari sepuluh nama aset spesifik adalah **karangan yang
terdengar masuk akal** — persis risiko yang ditandai hub di header
produk. Tidak satu pun usulan boleh dieksekusi dalam bentuk
tulisannya.

## Vonis per usulan

**Usulan 1 (metrik sumber-agenda) — DITERIMA DENGAN KOREKSI.**
Metriknya ternyata **sudah ada**: `opportunity_register.py`
mengimplementasikan `origin_share` — "the doctrine's long-run
measure" — dengan atribusi brain-of-origin per entri. Yang berdiri
bukan kolom baru di tabel karangan, melainkan: laporkan origin_share
secara berkala dari register yang ada dan jadikan kenaikannya
ukuran siklus direktur berikutnya. Garis falsifikasi usulan aslinya
tidak koheren (usulan pengukuran tidak bisa dipalsukan oleh
bacaannya sendiri) — kriteria berdiri: origin_share terlaporkan per
siklus.

**Usulan 2 (variansi judge) — DITERIMA DENGAN KOREKSI.**
Kebutuhannya nyata (celah 2 bahan siklus), asetnya karangan.
Bentuk berdirinya: praregistrasi kalibrasi berikutnya wajib memuat
aturan variansi eksplisit — pita pada rerata dengan sebaran A/B
terlaporkan, episode bersebaran besar ditandai tidak stabil —
dirancang bersama vonis penerus 0006, bukan modul "normalisasi"
yang menekan deviasi dengan fiat.

**Usulan 3 (transformasi pengetahuan 0007) — DITOLAK sebagaimana
tertulis.** Ia salah membaca rancangannya sendiri: record pola
(task_shape/approach/pitfalls) MEMANG bentuk pengetahuannya; enam
slot adalah parameter praregistrasi, bukan slot recall yang
"mengembalikan knowledge-type ≥ 80". Inti sahnya sudah berdiri
sebagai pekerjaan bernama: mengisi enam slot dari vonis penerus.

**Usulan 4 (batch-sizing front-OOM) — DITOLAK mekanismenya.**
`mem_profile` karangan, dan mekanismenya keliru: kematian front
adalah pertumbuhan KV pada generasi tunggal panjang di pagu 6 GiB,
bukan ukuran batch. Keputusan pemilik (tanpa penggantian) berdiri;
celahnya tetap tercatat sebagai catatan desain dan jendela ukur
dikelola secara operasional.

**Usulan 5 (keep-alive ping) — DITOLAK sebagaimana tertulis.**
Spesies timeout-nya sudah ditutup Amandemen 3 (PR #306, timeout
klien scored 2400 dtk); perbaikan akarnya — chat streaming, Opsi D —
sudah berdiri sebagai utang teknis bernama untuk siklus bangunnya
sendiri. Usulan ini tidak menambah apa pun di atas keduanya.

**Usulan 6 (patch lift G2) — DITOLAK tegas.** `gate_lift` dan
`lift_fix_v1` karangan, dan kerangkanya salah: tiga nol G2 adalah
hasil ukur dari eksperimen terpraregistrasi, bukan bug satu baris.
Menambal lalu menjalankan ulang melanggar disiplin praregistrasi
dan aturan tanpa-rerun-tanpa-delta. Kewajiban F → I tetap berdiri:
item berikutnya harus lahir sebagai mekanisme BARU dalam bentuk
rancangan — bukan tambalan.

**Usulan 7 (finalisasi serial 4 + royalti) — DITOLAK
mekanismenya.** Toggle "Selesai" adalah tindakan UI platform (item
terbuka bernama, tangan pemilik/Ian lewat aplikasi), bukan flag
konfigurasi. Verifikasi tiga-bukti mensyaratkan catatan penarikan
yang benar-benar ada — belum ada; ambang arbitrer Rp1.000 juga
keliru terhadap minimum transfer platform Rp15.000. Urutannya
sudah diatur rancangan EVO 0008 + prasyarat tes tebal royalty_track
(antrean Codex).

## Ringkasan

7 usulan → **0 diterima sebagaimana tertulis, 2 diterima dengan
koreksi (1, 2), 5 ditolak dengan inti sahnya terawetkan** di tempat
yang sudah berdiri. Nilai siklus ini terukur pada dua hal: kecepatan
direktur (485 t/s melawan 0,45–0,79 t/s lokal) dan pelajaran
penapisannya — organ kuat fasih pada celah bernama tetapi mengarang
aset rumah; setiap produk direktur berikutnya wajib melewati cek
aset yang sama sebelum usulannya dikutip.
