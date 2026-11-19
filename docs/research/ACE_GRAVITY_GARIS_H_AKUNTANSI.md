# Akuntansi Penutup Garis H — Produksi & Rel Pendapatan Luring (Gravity)

> **Status:** Draft PR penutup Garis H (`H1–H4`). Seluruh pekerjaan berdiri di atas `origin/main` (`478848d`), pada branch `gravity/*`, **hanya membangun perkakas offline (eksekusi payout nyata diparkir)**. Zero panggilan HTTP/jaringan live, zero penyimpanan nomor rekening penuh, dan tidak menyentuh wilayah terlarang (`evo0007_run.py`, instrumen judge/scorer, jalur tulis memory store, atau direktori staging EVO 0007).

## 1. Daftar Serahan & Status PR

| Butir | Branch | Commit | Draft PR | Ringkasan Serahan |
| --- | --- | --- | --- | --- |
| **H1** | `gravity/h1-ws2-multi-rail-fixtures` | `0bc65d2` | [#380](https://github.com/dianzherdiana25-hash/ACE/pull/380) | `tools/ws2_fixture_harness.py` (`ace.ws2-fixture-harness.v1`) + `tools/test_ws2_multi_rail_integration.py`: harness 8 fixture wajib `SPESIFIKASI_WS2_REL_DAN_BUKTI.md` (3 rel sah `kbm_seabank`, `fastwork_bank` berbiaya eksplisit, `gopay_qris`, blokir `facebook`/`REL TAK TERDAFTAR`, `HILANG`, `SEBAGIAN` lag > 14 hari, `TIDAK COCOK` KBM < Rp15.000, blokir kebocoran rekening, adaptor CSV royalti KBM, serta terverifikasi cocok byte-per-byte `r1 == r2` dengan `origin/codex/ws2-revenue-verification:tools/revenue_verify.py`). |
| **H2** | `gravity/h2-ledger-reconciler` | `55222b2` | [#381](https://github.com/dianzherdiana25-hash/ACE/pull/381) | `tools/revenue_reconcile.py` (`ace.revenue-reconcile.v1`) + `tools/test_revenue_reconcile.py`: rekonsiler buku kas JSON (`projects/pengelola_keuangan/data_keuangan.json` / skema `entries`) terhadap `ace.revenue-verification.v1` memakai integer rupiah berbasis `Decimal` (menangkap `DUPLICATE_CLAIM`, `AMOUNT_MISMATCH`, `RAIL_MISMATCH`, `UNVERIFIED_PARTIAL_OR_MISSING`, `UNLINKED_LEDGER_INCOME`, peristiwa terverifikasi yang belum dibukukan (bidang laporan `unbooked_verified_events`), dan memblokir nomor rekening mentah). |
| **H3** | `gravity/h3-kbm-tools-v2` | `1fb8bb5` | [#382](https://github.com/dianzherdiana25-hash/ACE/pull/382) | `tools/kbm_suite_v2.py` (`ace.kbm-suite.v2`) + `tools/test_kbm_suite_v2.py`: subkomando `qa` (`kbm_pack_check` + `cover_check` + pacing kata min/maks/stddev + deteksi bab kosong/duplikat SHA-256) dan `project` (proyeksi royalti `Decimal` rollover ambang cair Rp15.000 + histori CSV `royalty_track` + ekspor CSV/JSON). |
| **H4** | `gravity/h4-platform-requirements-summary` | `58c9611` | [#383](https://github.com/dianzherdiana25-hash/ACE/pull/383) | `tools/platform_requirements_summary.py` (`ace.platform-requirements-summary.v1`, `brain_of_origin: gravity-proposal`) + `docs/research/ACE_PLATFORM_REQUIREMENTS_SUMMARY.md` + `tools/test_platform_requirements_summary.py`: ringkasan ber-sitasi `file:line` (`408 berkas`, `112 kutipan`) atas aturan pembayaran, biaya, eksklusivitas KBM, AI/kualitas, & pagar privasi dengan pemeriksa `--check`. |

## 2. Hasil Uji Gabungan Worktree Overlay (`/tmp/garis_h_combo`)

Worktree sementara `/tmp/garis_h_combo` dibuat dari `origin/main` dengan cherry-pick `--no-commit 0bc65d2 55222b2 1fb8bb5 58c9611`, diuji penuh pada `Cwd="/tmp/garis_h_combo"`, lalu segera dihapus bersih (`git worktree list` bersih):

```text
python3 tools/platform_requirements_summary.py --check docs/research/ACE_PLATFORM_REQUIREMENTS_SUMMARY.md
  -> FRESH: /tmp/garis_h_combo/docs/research/ACE_PLATFORM_REQUIREMENTS_SUMMARY.md mutakhir dan cocok persis (32162 karakter).

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/garis_h_combo/code:/tmp/garis_h_combo \
  python3 -m unittest \
  tools.test_ws2_multi_rail_integration tools.test_revenue_reconcile \
  tools.test_kbm_suite_v2 tools.test_platform_requirements_summary \
  tools.test_royalty_track tools.test_kbm_pack_check tools.test_cover_check \
  tools.test_kbm_pipeline tools.test_kbm_split tools.test_kbm_schedule --buffer
----------------------------------------------------------------------
Ran 32 tests in 3.386s

OK
```

- `PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_sources.py`: `PASS: 25 imported files match their recorded Git blob IDs (offline)`.

## 3. Wilayah Diparkir & Syarat Terbuka (Menunggu Keputusan Pemilik / Hub)

- **Eksekusi payout nyata & aksi platform eksternal:** tetap diparkir 100%; seluruh perkakas Garis H bekerja murni atas fixture lokal.
- **Tiga sel kontrak belum terverifikasi (`evidence/handover/PELUANG_PANTAU_PERUBAHAN.md`, `ADDENDUM59`):**
  1. Durasi Perjanjian Karya Eksklusif KBM (hanya ada di menu dalam aplikasi mobile).
  2. Biaya penarikan Fastwork (teks resmi bertentangan Rp3.000 flat vs gratis → karenanya `H1`/`ws2_fixture_harness` mewajibkan `fee_rupiah` eksplisit pada catatan penarikan, tidak pernah di-hardcode).
  3. Penumpukan biaya Lynk.id di atas biaya transaksi 5% & verifikasi misi Facebook (menunggu panel pemilik).

## 4. Usulan Tranche Berikutnya (Bernomor)

1. **Garis I (`I1–I3` + Akuntansi Induk Final):**
   - `I1`: `tools/handover_decision_extractor.py` mengekstrak keputusan & usulan terbuka ber-sitasi `path:line` (`brain_of_origin: gravity-proposal`).
   - `I2`: `tools/program_glossary.py` glosarium deterministik istilah teknis dari heading Markdown & docstring AST.
   - `I3`: `tools/builder_onboarding_pack.py` paket onboarding kontributor (aturan jalur, wilayah terlarang, overlay worktree test, standar fuzz, `verify_sources.py`).
   - `Akuntansi Penutup Induk`: rekap lintas seluruh garis (`Ronde 2 Amendment`, `A Tranche 2`, `B..I`), audit PR GitHub live, serta daftar eksplisit `SELESAI / TERSISA / PENGHAMBAT`.
2. **Pasca-merge PR #333 (`codex/ws2-revenue-verification`) + H1 (`#380`) + H2 (`#381`):** jalankan `python3 tools/ws2_fixture_harness.py` sebagai tes silang otomatis terhadap `tools.revenue_verify`.

---

**Errata gelombang merge (Ian, 2026-11-19):** tiga selip faktual dari saringan independen dikoreksi di dokumen ini — (1) ambang `SEBAGIAN` adalah lag > 14 **hari** (bukan "14h"); (2) kode anomali `UNBOOKED_LEDGER/EVENT` tidak pernah ada — fitur yang dimaksud adalah bidang laporan `unbooked_verified_events` pada `tools/revenue_reconcile.py`; (3) jumlah berkas yang dipindai H4 adalah **408** (bukan 409) menurut perkakasnya sendiri. Kesetaraan byte-per-byte H1 (`r1 == r2`) juga telah diverifikasi independen terhadap `tools/revenue_verify.py` dari PR #333 (8/8 peristiwa, keluaran identik), dan kini terverifikasi sendiri di `main` gabungan.
