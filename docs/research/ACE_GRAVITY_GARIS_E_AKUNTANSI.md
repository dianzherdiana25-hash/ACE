# Akuntansi Garis E · Perkakas Organ & Multi-Brain EVO 0009 (Strictly Offline)

Seluruh serahan Garis E dibangun oleh Antigravity di atas `origin/main` (`478848d`) sebagai **draft PR** terpisah per butir, dengan kepatuhan mutlak: **0 panggilan HTTP/socket live** serta tanpa memodifikasi `brain_endpoints.py`, kredensial/vault, instrumen EVO 0007, ataupun direktori stage Ian. Akuntansi garis sebelumnya tersedia di [PR #345](https://github.com/dianzherdiana25-hash/ACE/pull/345) (Garis B), [PR #352](https://github.com/dianzherdiana25-hash/ACE/pull/352) (Garis C), [PR #358](https://github.com/dianzherdiana25-hash/ACE/pull/358) (Garis A Tranche 2), dan [PR #365](https://github.com/dianzherdiana25-hash/ACE/pull/365) (Garis D).

| Butir | Status | PR Draf & Commit | Branch | Ringkasan Serahan & Hasil Uji |
| --- | --- | --- | --- | --- |
| E1 · Validator Registry & Slate Organ | Selesai | [PR #366](https://github.com/dianzherdiana25-hash/ACE/pull/366) (`2c30569`) | `gravity/e1-organ-registry-validator` | `tools/organ_registry_validate.py` (`ace.organ-slate.v1` + `ace.brain_registry.v1`): pemeriksaan 5 peran EVO 0009, heterogenitas proposer≠validator, pemindai kebocoran token/API key, urutan kontingensi pemilik, dan pencegahan wildcard `descriptor=""`. 10 tes baru + 5 `test_brain_registry` = 15 tes OK. |
| E2 · Buku Kuota & Rotasi Multi-Rute | Selesai | [PR #367](https://github.com/dianzherdiana25-hash/ACE/pull/367) (`806cb3d`) | `gravity/e2-quota-ledger-rotation` | `tools/organ_quota_ledger.py` (`ace.organ-quota-ledger.v1`): akuntansi harian Groq/Gemini multi-bucket, saldo token bulanan Gonka, kebijakan rotasi/lekat (`coder` sticky di Groq, `judge` hold+amend pada paket ukur), aktivasi berurut kontingensi `nvidia -> cloudflare -> zai -> cometapi`, dan rekonsiliasi `bridge_calls.jsonl`. 10 tes OK. |
| E3 · Protokol Smoke Harness Offline | Selesai | [PR #368](https://github.com/dianzherdiana25-hash/ACE/pull/368) (`e782e57`) | `gravity/e3-organ-smoke-harness` | `tools/organ_smoke_harness.py` (`DryRunOrganAdapter` + injeksi handler mock, menolak URL live via `LiveNetworkDisallowedError`) + `docs/research/ACE_ORGAN_SMOKE_PROTOCOL.md`: cek `/health`, `/v1/models`, chat terbatas reasoning, embedding finit, penolakan `a3b` di bridge, serta 5 latihan injeksi fail-closed. 8 tes OK (`network_calls=0`). |
| E4 · Bench Kesepakatan Silang Multi-Organ | Selesai | [PR #369](https://github.com/dianzherdiana25-hash/ACE/pull/369) (`9a0b4ec`) | `gravity/e4-cross-organ-agreement` | `tools/cross_organ_agreement.py` (`ace.cross-organ-agreement.v1`): kanonikalisasi jawaban (JSON terurut/angka/teks), pemisahan abstensi/error, perhitungan `raw_agreement` dan Cohen's kappa berpasangan bertanda `cross_provider`, serta toleransi baris JSONL korup/duplikat. 8 tes OK. |

## Uji Gabungan Lintas E1–E4 + `brain_registry` & `brain_endpoints` (Overlay `/tmp/garis_e_combo`)

Seluruh commit E1–E4 digabungkan ke worktree sementara `/tmp/garis_e_combo` (dibersihkan setelah uji) dan dijalankan terhadap 7 modul tes (`E1`–`E4` = 36 tes baru + `ace_operational.test_brain_registry`, `test_brain_endpoints`, `test_brain_endpoints_edge` = 57 tes eksisting):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/garis_e_combo/code:/tmp/garis_e_combo python3 -m unittest \
  tools.test_organ_registry_validate \
  tools.test_organ_quota_ledger \
  tools.test_organ_smoke_harness \
  tools.test_cross_organ_agreement \
  ace_operational.test_brain_registry \
  ace_operational.test_brain_endpoints \
  ace_operational.test_brain_endpoints_edge -v
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/garis_e_combo/tools/verify_sources.py
```

- **Suite gabungan:** **Ran 93 tests in 2.163s — OK**
- **Integritas sumber:** **PASS: 25 imported files match their recorded Git blob IDs (offline)**

## Batas yang Dijaga

- **0 panggilan jaringan/HTTP live** pada seluruh kode maupun unit tes Garis E; penolakan URL live ditegakkan secara eksplisit (`LiveNetworkDisallowedError`).
- Tidak ada modifikasi ke `code/ace_operational/brain_endpoints.py`, `code/ace_operational/brain_registry.py`, runner EVO 0007, instrumen ukur, jalur tulis memory store, ataupun direktori stage Ian.

## Usulan Tranche 2 untuk Garis E (Bernomor)

1. **E-T2-1 · Adaptor pembaca `bridge_state.json` & `bridge_calls.jsonl` terpadu ke E1/E2:** Setelah cabang `feat/ace-evo0009-bridge-20261118` mendarat ke `main`, sambungkan pembangkitan peringatan otomatis bila kuota harian mendekati 85% pada `organ_quota_ledger.py`.
2. **E-T2-2 · Kalibrator ambang abstensi multi-organ pada E4:** Tambahkan agregasi histogram `disagreement_cases` per domain tugas (`code` vs `language` vs `judge`) ke `cross_organ_agreement.py` untuk evaluasi kalibrasi proposer≠validator.
3. **E-T2-3 · Smoke praterbang otomatis sebelum `SIGCONT`:** Integrasikan keluaran validator E1 dan protokol E3 ke daftar periksa pra-penyalaan operator VM.

**SELESAI** — Seluruh butir Garis E (`E1`–`E4`, PR #366–#369) dan akuntansi penutup selesai; suite gabungan 93 tes lulus tanpa kesalahan.  
**TERSISA** — Antrean berikutnya pada **Garis F s.d. I**.  
**PENGHAMBAT** — Nihil.
