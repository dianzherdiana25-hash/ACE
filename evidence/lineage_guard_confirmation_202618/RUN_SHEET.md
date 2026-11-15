# LEMBAR LARIAN — Konfirmasi Lineage-Guard Tersegel (PR #188, A.6)

## Rumah, pintu, perkiraan

- Rumah eksekusi: sandbox ACE (host 2887726280f4), pohon custody
  `/workspace/ace-custody-lineage-guard`. Pintu: SSH baru sshremote:443
  (sudo di sesi baru). Proses detached via nohup + log; BUKAN pintu MCP
  (cgroup ~1 CPU).
- Perkiraan durasi total: ~1,5–2 jam (persiapan kustodi ~15 mnt;
  gerbang dev langkah 2–3 ~10 mnt; baterai langkah 4 ~5 mnt; sel
  langkah 6: 12 sel × ~3–5 mnt ≈ 40–60 mnt; cadangan kejutan).
  Estimasi berbasis waktu Stage 3 (VM ~0,55 core) dan probe R5 —
  bukan janji.
- Instrumen: PR #193, harness commit
  73a902ec8b43518b95e69680d6d863eb1bd7f200
  (evidence/lineage_guard_harness.py + lineage_guard_gate.py),
  masuk kustodi sebagai suplemen #2 (manifes
  handover/CUSTODY_SUPPLEMENT_MANIFEST_INSTRUMENT_20261115.json,
  tree digest 29d7d71a826399dc25101f1046a33bd966e0543d33bae7c5db432d20619f314a).

## Band (field 2, diamendemen ke triple berurutan)

Harness MENEGAKKAN A.5 secara mekanis (seeds harus berurutan persis;
{20261801, 20261803, 20261804} ditolak kode). Triple yang dipakai:
[20261803, 20261804, 20261805] — digest 03/04 terverifikasi di paket
re-baseline; 05 menunggu discovery + verifikasi digest + cek kunci
kausal (aturan berhenti Misi 10 berlaku). Amendemen field 2 akta §9
menunggu ratifikasi hub.

## Persiapan (sekali, di kustodi, sebelum larian)

- P1. Verifikasi populasi di tempat: 80 berkas, 1.049.673 B, tree
  digest c02221775c2b81117effb93b204cccd0aaaa930e166e4a9c3883cf1d233fc6c2
  (pola pemeriksa R5).
- P2. Transfer suplemen #2 → `<custody>/evidence/lineage_guard_harness.py`
  + `lineage_guard_gate.py`; verifikasi sha256 per berkas + tree digest
  manifes DI kustodi.
- P3. Tempatkan discovery_20261803.json, discovery_20261804.json,
  discovery_20261805.json dari paket re-baseline ke
  `<custody>/abc-v3-run-state/`; hitung ulang digest tiap berkas —
  harus sama dengan field 2 akta (langkah 5 harness membaca berkas
  ini; band TIDAK di-discovery ulang oleh harness).
- P4. Snapshot registry: sha256 berkas
  `<custody>/wt-battery/code/ace_operational/distractor_registry.json`
  harus f9d8982a1314cc5807f815dc700affd0c3dd9cf42ff2b35855a7704dc0911680,
  ids ["name-swap-523014-nc-band20261501"] (langkah 0 harness
  memverifikasi mekanis terhadap akta; mismatch = berhenti).
- P5. Tulis akta final (dari ACT_CONFIRM_DRAFT.json, window diisi nama
  jendela dari hub) →
  `<custody>/evidence/lineage_guard_state/act_confirm_202618.json`.
- P6. Asap lingkungan (BUKAN tersegel): `python3 evidence/lineage_guard_harness.py gate --base /workspace/ace-custody-lineage-guard`
  harus L4 PASS + L1/L2 PASS; sekaligus verifikasi layout --battery-dir
  yang diharapkan adapter gerbang (baterai di `<custody>/wt-battery`).

## Larian (satu perintah, detached)

Gerbang pra-mulai (JENDELA KONFIRMASI): dari dalam sandbox, baca
MemAvailable (`grep MemAvailable /proc/meminfo`) dan laporkan ke hub —
mulai hanya bila ≥ 4 GB. Delta ke hub sebelum perintah run dijalankan.

```
cd /workspace/ace-custody-lineage-guard && nohup python3 evidence/lineage_guard_harness.py run --act evidence/lineage_guard_state/act_confirm_202618.json --base /workspace/ace-custody-lineage-guard --battery-dir /workspace/ace-custody-lineage-guard/wt-battery/code/ace_operational > evidence/lineage_guard_state/run_confirm_202618.log 2>&1 &

> ERRATA (15 Nov 21:28 WIB, dicatat operator): perintah versi awal
> memakai --battery-dir …/wt-battery — SALAH satu tingkat: adapter
> gerbang mencari distractor_inoculation.py LANGSUNG di dalam dir
> yang diberikan. Percobaan larian pertama berhenti VOID di langkah
> 4 karena ini (langkah 2–3 PASS; langkah 5–8 tak pernah jalan).
> Jalur terkoreksi = …/wt-battery/code/ace_operational (di situlah
> berkas suplemen baterai tinggal, sha cbc5e7df… terverifikasi).
```

- Berhenti mekanis (A.6): langkah 2/3 FAIL → instrumen VOID, berhenti;
  langkah 4 guarded SUSCEPTIBLE → GUARD_REFUTED, berhenti; snapshot
  mismatch → berhenti sebelum apa pun berjalan.
- Hasil: `<custody>/evidence/lineage_guard_run.json` (record puncak) +
  state per sel di `evidence/lineage_guard_state/`; vonis worksheet
  mekanis A.7 (GUARD_ADOPTED iff R=W ∧ H=∅ ∧ median rasio biaya ≤ 3;
  L5 diperiksa di setiap larian guarded).
- Sesudah: paket evidence via draft PR (push menunggu kata pemilik);
  delta ke hub; papan gerbang hanya bergerak oleh ratifikasi hub.

## Prasyarat terbuka

(a) Kredensial SSH — PULIH (uji satu kali 15 Nov ~21:47: BISA MASUK,
    hostname terverifikasi).
(b) Jendela SUDAH dinamai hub: **JENDELA KONFIRMASI** — tanda KHUSUS
    pengganti tanda baku RUMAH KOSONG untuk larian ini (keputusan hub
    15 Nov): larian BOLEH berdampingan dengan tenant llama-server
    Qwen3-8B lini Antigravity (JANGAN disentuh), dengan syarat:
    (1) sebelum mulai, cek + laporkan MemAvailable dari dalam sandbox
    — mulai hanya bila bebas ≥ 4 GB; (2) selama jendela, tidak ada
    muatan model baru dari sisi kita; (3) deviasi dicatat eksplisit
    di akta run: rumah tidak kosong (tenant statis 8B ±15,3 GB),
    larian CPU-only tanpa muatan model — risiko yang dijaga tanda
    asal (tabrakan earlyoom antar-muatan model) tidak terjadi di
    sini.
(c) Ratifikasi amendemen field 2: BERSYARAT dari hub (15 Nov) — sah
    bila 20261805 terverifikasi LAYAK. Bila TIDAK LAYAK: berhenti,
    jangan bakar seed lanjutan, lapor ke hub.
(d) Discovery 20261805 selesai dan LAYAK (berjalan di VM, PID 26868).
