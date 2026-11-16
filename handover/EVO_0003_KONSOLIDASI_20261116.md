# KONSOLIDASI EVO 0003 — Ledakan, Ekor, dan Insiden

Status: catatan konsolidasi program (Ian, 2026-11-16). Praregistrasi:
PR #239 (docs/ace-evo0003-prereg-20261116). Basis semua larian:
`main @ f6d7546213449f8fc65b825fc87b5b87a69eec0e`. Rumah ledakan dan
ekor: sandbox ACE. Semua vonis di bawah ini TER-RATIFIKASI hub pada
hari yang sama. Artefak bukti menyertai di `evidence/evo0003/`
(manifes beku, registri, laporan ledakan, hasil saringan, snapshot
hasil ekor + vonis potong, log bench T3).

## 0. Pembekuan panggung

- Manifes ledakan beku: `blast_manifest.json` **sha256
  809b962e2cb9a4017f5614ae95d8710b3c728ec1f8585ac98f0f1318c18d0c92**
  (10 artefak, preflight pelari = []).
- Registri baterai beku: 1 entri (berdiri saja), sha256
  88faa2c73b0604b66576292f1889c45efcb8c2a5a1f4c06286fb0bb5364b42bb.
- Saringan varian (Amendemen 3, seragam di sandbox, instrumen v2):
  **24/24 kandidat NO_WITNESS, 0 evidenced**, dinding 4.486,9 dtk;
  lengan bersih jangkar 32/34 dalam 120 dtk. Efek kausal terkunci
  pada permutasi persis (5,2,3,0,1,4).
- Instrumen v3 (memoisasi persiapan invarian) **gagal gerbang
  validasi** (3/128 ketidakcocokan bit, satu arah, di bawah beban
  16-proses) dan dibatalkan tanpa negosiasi; status presisnya
  "gagal validasi di bawah kontensi", bukan tertolak sebagai
  desain. Registri adalah produk satu instrumen: v2.
- Snapshot B4: memory.jsonl sha256
  80556222f455ea6d4cbeb838be00d71f3b50cb5cd4d7af958f6d00b3cdf06f62.
- Korpus ekor beku: sha256
  60177c51e095ea685fee84d474fbd204568b3d10db1361a68244aba1dba0637e
  (16 baris: 8 dialog + 8 episode).

## 1. Ledakan (B1–B5) — BLAST_DONE, dinding total 1.874,0 dtk

Tanda hub RUMAH KOSONG SEMUA PINTU; cek pintu detik peluncuran:
MemAvailable ±18,67 GB, penyewa llama tunggal organ depan, engine
dijeda selama jendela. Target rancangan ±10 menit tidak tercapai;
angkanya berdiri sebagai fakta (komponen mencatat TIMEOUT pada
batas future beku 660 dtk, tanpa perpanjangan diam-diam).

### B1 — sel solver, band 20261901–20261906

- 20261901: **TIMEOUT**. 20261902: **TIMEOUT**.
- 20261903: bersih 33/34 · terinfeksi stok **30/34** · terinfeksi
  guarded **33/34**.
- 20261904: bersih 34/34 · stok **31/34** · guarded **34/34**.
- 20261905: bersih 34/34 · stok **32/34** · guarded **34/34**.
- 20261906: bersih 34/34 · stok **33/34** · guarded **34/34**.

Pola konsisten di empat band tuntas: kunci kausal memangkas stok,
guard memulihkan persis ke tingkat bersih — temuan Stage 3/Q1
tereplikasi di semesta baru.

### B2 — baterai distraktor (registri 1 entri): TIDAK LOLOS, 0/1

Entri berdiri name-swap-523014-nc-band20261501: stok
**NOT_SUSCEPTIBLE**, guarded NOT_SUSCEPTIBLE. Anatomi prasyarat-nol:
di rumah+instrumen ini stok tidak rentan pada semesta jangkar,
jadi tidak ada flip saksi yang bisa dilindungi. Bukan kegagalan
guard; bukan pula lolos. Tercatat apa adanya.

### B3 — suite penuh: all_green FALSE (berdiri sebagai catatan kondisi-lari)

168 modul, 8 shard: shard 0 = 155 tes, 1 failure; shard 4 = 203
tes, 2 failure; 6 shard lain hijau. Identifikasi lanjutan (kerja
meja, TER-RATIFIKASI): shard 0 bersih 155/155 di rumah sepi basis
pristine; shard 4 kedua failure-nya di `ace_runtime.test_engine`
(tes siklus-proses) dan bersih 15/15 sebagai penyewa tunggal di
venv sandbox. **Ketiga failure adalah tes sensitif-waktu di bawah
kontensi; tidak ada regresi basis f6d75462 yang terbukti dari
komponen ini.** Dua fakta berdampingan, tidak saling menghapus.

### B4 — audit ingatan: ERROR (cacat probe pelari, atribusi Ian)

Probe pelari memanggil `record_verified_event` dengan kelas
`evo0003_blast_b4_probe` yang tidak terdaftar di EVENT_CLASSES;
modul menolak dengan ValueError persis sesuai desainnya (kelas tak
dikenal = kesalahan pemrograman). Pertanyaan audit B4 tetap BELUM
TERJAWAB; pendaftaran kelas probe yang benar adalah amendemen
praregistrasi masa depan, bukan perbaikan diam-diam.

### B5 — live-fire fail-closed: PASS

chat organ mati → RAISED; embed organ mati → RAISED; sovereign
tanpa executor → QUARANTINED_NO_PROOF. 100% fail-closed.

## 2. Penyalaan engine (konteks ekor)

Engine otonom dihidupkan ulang 09:32:58 hanya dengan mengganti
env `ACE_LLAMA_SERVER_URL` dari :8000 (mati) ke :8001 (organ
depan slate) — nol edit kode. TER-RATIFIKASI hub di tingkat
router; bukti lahir-siklus menyusul: cycle_count 1503, peristiwa
store seq 3251 @03:26:52Z + seq 3257 @03:42:32Z COMPLETED backend
local-gguf-server (actor ace_controller). Klasifikasi CAP-36.01
hub: generasi lahir-siklus naik dari unknown menjadi
evidence-demonstrated. Engine dijeda selama jendela ledakan dan
selama jendela ukur ekor; hidup lagi di luar keduanya (siklus
1505 saat ledakan tutup).

## 3. Ekor

### Insiden T1 (delta bernama, TER-RATIFIKASI)

Larian pertama: dlg-001 lolos gerbang. Pada dlg-002 **organ depan
OOM-kill pukul 11:42:50** (systemd: ace-front MemoryMax 4 GiB,
proses utama status 9/KILL; restart otomatis 11:42:55) di bawah
konsumen konkuren engine + ekor; dlg-003…008 tercatat error
ketersediaan oleh pelari. Oom-kill identik juga tercatat pukul
10:07:00 (era saringan, restart otomatis). Hasil larian pertama
tersimpan utuh (`tail-out/incident_pass1.jsonl`); remediasi:
engine dijeda, item error diukur ulang pada larian remediasi,
dlg-001 yang sah dipertahankan. Keputusan hub atas temuan topi:
**MemoryMax ace-front naik 4 → 6 GiB** (total topi slate 13,5 GiB
< plafon kerja rumah), terap SESUDAH vonis blok T1/T2.

### T1 — kampanye dialog (larian remediasi): 8/8 LOLOS GERBANG

dlg-001 dari larian pertama (sah, sebelum insiden) + dlg-002…008
dari larian remediasi: semua `gate_pass = true`; validator coder
menilai kedelapan jawaban `acceptable: true, grammar_ok: true,
issues: []` — tanpa satu pun catatan. Panjang jawaban 125–416
karakter. TER-RATIFIKASI hub dengan catatan insiden OOM melekat
permanen pada blok ini.

### T2 — episode heterogen (klaim §1): VONIS BERCAKUPAN TEREDUKSI — TERDUKUNG

Blok penuh 8 episode DIGANTIKAN oleh perintah potong pemilik
(kotak waktu 10 menit, via hub 12:53): jalur mulai ±12:54,
panen berhenti 13:04. Vonis ini BUKAN vonis blok praregistrasi.

Instrumen v2 (delta bernama): judge() memakai chat_structured
untuk semua validator — pass-1 gugur karena kanal juri mentah
ke organ depan mengembalikan konten kosong (ep-code-001) dan
timeout 900 dtk (ep-code-002); catatan pass-1 tersimpan di
`tail-out/t2_pass1.jsonl`.

Panen unik: **2/8 episode terukur, keduanya kode.**
- ep-code-002: TER-RATIFIKASI 2/2 larian (gerbang struktural
  lolos; validator depan menerima, JSON bersih, alasan berbahasa
  Indonesia; pasangan heterogen coder→depan).
- ep-code-001: 0/2 larian — satu penolakan substantif
  (accept=false: docstring tidak menyebut penanganan ValueError
  yang diminta instruksi), satu vonis juri tak ter-parse.
- NOT_MEASURED (bukan gagal, bukan lolos): ep-code-003,
  ep-code-004, ep-lang-001…004.

**Klaim §1 pada cakupan tereduksi: TERDUKUNG** (laju ratifikasi
di antara yang terukur > 0 — ep-code-002, 2/2 larian).

Dua cacat pelaksanaan (terbuka, milik pelari):
1. Filter jalur bahasa `EVO_LANE=lang` tidak cocok dengan
   korpus (task_kind dieja "language") — jalur bahasa keluar
   dengan nol item; separuh bahasa tidak terukur karenanya.
2. Pelari sekuensial v2 selamat dari kill pra-peluncuran dan
   balapan dengan jalur kode, mengukur ep-code-001/002 dua
   kali secara konkuren; arah vonis duplikat konsisten
   (001 ditolak 2×, 002 diterima 2×).

Artefak: `tail-out/tail_cut_verdict.json` +
`tail_results_box_snapshot.jsonl`. Engine hidup lagi sesudah
kotak tertutup (siklus 1505, running).

### T3 — bench Sahabat-AI-9B + ik_llama

Intake Sahabat TERVERIFIKASI: repo
`gmonsoon/gemma2-9b-cpt-sahabatai-v1-instruct-GGUF`, berkas
Q4_K_M, 5.761.058.208 B, **sha256
d66772251598d63ff1c715e4fd7dbe4adc55cc69d8c5950146a5b5fe98a1d772**
== pin sumber.

Bench dijalankan 2026-11-16 di rumah bekerja (engine belajar
+ organ slate residen; BUKAN jendela rumah-kosong — angka apa
adanya), llama-bench -p 512 -n 128 -r 3, berkas yang sama:

| Mesin | Utas | pp512 (t/s) | tg128 (t/s) |
|---|---|---|---|
| llama.cpp b12316 | 1 | 6,03 ± 0,18 | 0,99 ± 0,09 |
| llama.cpp b12316 | 8 | 31,79 ± 0,97 | 0,70 ± 0,07 |
| ik_llama | 1 | 10,19 ± 0,39 | 0,90 ± 0,02 |

Pola rumah berulang: utas menolong pemrosesan prompt dan
merugikan generasi. Pada -t 1, ik_llama menang di pp
(+69% atas stok) dan kurang-lebih seri di tg (−9%).
Biner ik ditemukan terbangun di
`/workspace/tools/ik-llama/src/build/bin/` (probe kedalaman
awal meleset — tercatat). Log penuh: `evidence/evo0003/t3_bench.log`.

## 4. Yang berubah sesudah EVO 0003

- MemoryMax ace-front 4 → 6 GiB (keputusan hub; TERAP live
  2026-11-16 via set-property, terverifikasi 6.442.450.944 B,
  health ok; total topi slate 13,5 GiB).
- Pertanyaan audit B4 (kelas probe terdaftar) = amendemen
  praregistrasi masa depan.
- B2: prasyarat kerentanan stok bergantung rumah/instrumen —
  baterai masa depan menyatakan keadaan bersih tugas saksi
  sebagai prasyarat terukur sebelum vonis.
