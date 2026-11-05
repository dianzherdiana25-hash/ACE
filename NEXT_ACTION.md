# NEXT_ACTION — satu anggaran untuk diagnosis, perbaikan, dan pewarisan graf

## P0 — Codex implementation: integrate the one-budget graph loop

A standalone, evaluator-side shared-purchase journal now exists in `code/e14/e14_shared_budget.py` with **12/12 local unit tests passing**; see [the full engineering and audit contract](docs/ACE_E14_SHARED_LABEL_CONTRACT_v1.md). **This is not the integrated experiment**; no new Issue #13 bank or scorer was frozen/scored.

Codex should refresh HEAD, work on a separate `codex/13-integrated-graph-loop` branch, add a journal-backed orchestrator for diagnosis → representation repair → qualified inheritance, validate each purchased query's declared nodes/edges from trusted typed graph input, then implement a novel prescored public bank with strict gates, score/replay/audit and a PR to `research/e1.3-design`. Respect the common cap **4 target labels per world and arm** and reuse a purchased diagnosis label at no new charge only with its receipt ID. Budget reservation must be durably persisted before oracle use. Run full regression; the local 12/12 journal tests alone are not sufficient. Current evidence [Issue #13](https://github.com/dianzherdiana25-hash/ACE/issues/13) remains scientific **OPEN**.


1. Verifikasi HEAD, baca [hasil E1.4o](design/e1.4/E14O_RESULT_v1.md) dan [hasil penjaga E1.4s](design/e1.4/E14S_RESULT_v1.md), lalu lanjutkan [issue #13](https://github.com/dianzherdiana25-hash/ACE/issues/13). Gerbang aktif graf rantai masih HOLD. Penjaga berhasil pada grammar terbatas tetapi dapat menghabiskan tiga label.
2. Buat bank graf bercabang publik baru dan satu batas bersama empat label. Uji apakah satu label dapat sekaligus menggugurkan model lama dan memangkas versi setelah perluasan. Jalankan diagnosis, pemilihan perluasan, perbaikan, serta kualifikasi dan pemakaian ulang dengan pengukuran biaya dari awal hingga akhir. Pembanding memakai anggaran yang sama.
3. Bekukan strata alami, terjangkau, langka dan luar grammar, pembanding serta ambang sebelum penilaian. Pertahankan negatif dan bandingkan coverage saat abstain. Jika perbaikan dan pewarisan bersama belum lulus, catat bottleneck secara terpisah.

## Reproduksi E1.4s

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 10 --log WORK/s-score.log -- python3 -m e14.e14s_run run WORK/s-score.sqlite WORK/s-score.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 10 --log WORK/s-replay.log -- python3 -m e14.e14s_run run WORK/s-replay.sqlite WORK/s-replay.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 60 --heartbeat 5 --log WORK/s-audit.log -- python3 -m e14.e14s_audit WORK/s-score.json.gz WORK/s-replay.json.gz
```

## Pemulihan regresi publik

Gunakan [panduan eksekusi](docs/ACE_SPRINT_RUNTIME.md) untuk memulihkan fixture E1.4d–f ke snapshot sementara dan menjalankan suite 114 tes. Arahkan log ke direktori WORK dan pertahankan keluaran terminal.

## Reproduksi E1.4r

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 10 --log WORK/r-score.log -- python3 -m e14.e14r_run run WORK/r-score.sqlite WORK/r-score.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 10 --log WORK/r-replay.log -- python3 -m e14.e14r_run run WORK/r-replay.sqlite WORK/r-replay.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 90 --heartbeat 10 --log WORK/r-audit.log -- python3 -m e14.e14r_audit WORK/r-score.json.gz WORK/r-replay.json.gz
```

## Reproduksi E1.4q

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 10 --log WORK/q-score.log -- python3 -m e14.e14q_run run WORK/q-score.sqlite WORK/q-score.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 10 --log WORK/q-replay.log -- python3 -m e14.e14q_run run WORK/q-replay.sqlite WORK/q-replay.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 90 --heartbeat 10 --log WORK/q-audit.log -- python3 -m e14.e14q_audit WORK/q-score.json.gz WORK/q-replay.json.gz
```

## Reproduksi E1.4p

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 15 --log WORK/p-score.log -- python3 -m e14.e14p_run run WORK/p-score.sqlite WORK/p-score.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 15 --log WORK/p-replay.log -- python3 -m e14.e14p_run run WORK/p-replay.sqlite WORK/p-replay.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 90 --heartbeat 10 --log WORK/p-audit.log -- python3 -m e14.e14p_audit WORK/p-score.json.gz WORK/p-replay.json.gz
```

## Reproduksi E1.4o

```bash
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 15 --log WORK/o-score.log -- python3 -m e14.e14o_run run WORK/o-score.sqlite WORK/o-score.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 120 --heartbeat 15 --log WORK/o-replay.log -- python3 -m e14.e14o_run run WORK/o-replay.sqlite WORK/o-replay.json.gz
PYTHONPATH=code python3 tools/ace_sprint_runner.py --timeout 90 --heartbeat 10 --log WORK/o-audit.log -- python3 -m e14.e14o_audit WORK/o-score.json.gz WORK/o-replay.json.gz
```

## Catatan pemulihan historis

# ACE E1.4n — recover from latest pre-score freeze

## Host sandbox capability development (independent of E1.4n score)

The local host supports real user, network, mount, and PID namespaces, with **6/6** isolation-canary conditions passing on a minimal worker. This finding is documented at [namespace capability audit](docs/ACE_E14N_NAMESPACE_CAPACITY_v1.md). It **does not** replace native Bubblewrap or permit E1.4n scientific scoring under an altered frozen protocol. If attempting a future equivalent sandbox, validate the full evaluator nonexposure threat model and resource isolation with the actual worker and freeze a new engineering protocol first. For E1.4n, continue on a validated Bubblewrap host with full private checkout.


**Frozen scientific source:** `fb9ac72c9c6b039f402a1905b3635f2a4efbecdb`. Eight locked files independently rehashed with SHA-256: **8/8 PASS** in the current ChatGPT session. [Readback evidence](evidence/e14/e14n_integrity_readback_v1.json).

**Environment restriction is not a scientific decision:** native Bubblewrap is missing and a complete ACE checkout is not accessible to the current local Python environment; `BLOCKED_ENV` was recorded without scoring. Do not replace `/usr/bin/bwrap` with a test stub. The earlier Work environment verified native isolation on E1.4g–m, but new E1.4n runs must validate it again.

**Immediate authorized continuation** on a sandbox-capable host or Work/Codex execution environment:
1. Checkout the exact frozen commit; run `python3 -m e14.e14n_run freeze` **only for a throwaway comparison** if needed. Do not overwrite the already committed frozen bank, lock, code, or protocol.
2. Run the already prescribed three bounded `e14n_run` score/replay/`e14n_audit` commands below from the frozen checkout with separate SQLite ledgers and independent outputs. Verify native Bubblewrap boundary and canary checks.
3. Check deterministic score/replay equality, audit oracle labels, candidate fits, CPU, held-out predictions, 72 worlds, and the locked repair decision. Do not change GO/HOLD thresholds after viewing results.
4. Record `COMPLETE`, `TIMEOUT`, `FAILED`, or `BLOCKED_ENV` visibly with terminal evidence; commit raw compressed score, replay, audit, regression and report only after independent checks pass, read back GitHub HEAD. Do not spend money, touch Tod/main, or open sealed E1.3 material.


1. Verifikasi HEAD GitHub dan baca [hasil E1.4m](design/e1.4/E14M_RESULT_v1.md), [bukti](evidence/e14/e14m_verification_v1.json), dan [piagam](PROJECT_CHARTER.md). Kontra-contoh terarah menggugurkan versi model pada 15/16 dunia terjangkau. Dunia langka tetap HOLD dan punya batas informasi yang berbeda.
2. Pada bank publik baru, uji mekanisme yang memicu proposal perluasan DSL bertipe setelah versi hipotesis awal kosong. Bandingkan perluasan terarah oleh kontra-contoh, perluasan panjang tetap, dan model yang menahan prediksi. Pisahkan deteksi dari kecocokan baru dan kinerja pada probe yang tidak pernah diberikan kepada worker. Pertahankan kontrol dalam model agar perluasan tidak dipicu tanpa alasan.
3. Tetapkan batas ekspansi, label, biaya, risiko dan ambang sebelum scoring. Ukur waktu, kandidat tambahan, generalisasi probe, salah ekspansi, serta keadaan tanpa solusi. Audit dan replay terisolasi. Pertahankan **Rare HOLD** dan **NATURAL_HOLD** untuk transfer.

## Reproduksi E1.4n

Dari checkout pembekuan E1.4n, buat direktori `WORK` lokal. Gunakan ledger baru untuk replay dan ledger yang sama untuk resume.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 180 --heartbeat 15 --log WORK/nscore.log -- python3 -m e14.e14n_run run WORK/nscore.sqlite WORK/nscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 180 --heartbeat 15 --log WORK/nreplay.log -- python3 -m e14.e14n_run run WORK/nreplay.sqlite WORK/nreplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 120 --heartbeat 10 --log WORK/naudit.log -- python3 -m e14.e14n_audit WORK/nscore.json.gz WORK/nreplay.json.gz
```

## Reproduksi E1.4m

Dari checkout [pembekuan E1.4m](https://github.com/dianzherdiana25-hash/ACE/commit/835016481e61261386a02ae4867ece580d4cd1cd), buat direktori `WORK` lokal. Gunakan ledger baru untuk replay dan ledger yang sama untuk resume.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 180 --heartbeat 15 --log WORK/mscore.log -- python3 -m e14.e14m_run run WORK/mscore.sqlite WORK/mscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 180 --heartbeat 15 --log WORK/mreplay.log -- python3 -m e14.e14m_run run WORK/mreplay.sqlite WORK/mreplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 120 --heartbeat 10 --log WORK/maudit.log -- python3 -m e14.e14m_audit WORK/mscore.json.gz WORK/mreplay.json.gz
```

## Reproduksi E1.4l

Dari checkout [pembekuan E1.4l](https://github.com/dianzherdiana25-hash/ACE/commit/904dcc62d94bcbfdd6070437af434ec7cce25730), buat direktori `WORK` lokal. Gunakan ledger baru untuk replay dan ledger yang sama untuk resume.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/lscore.log -- python3 -m e14.e14l_run run WORK/lscore.sqlite WORK/lscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/lreplay.log -- python3 -m e14.e14l_run run WORK/lreplay.sqlite WORK/lreplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 120 --heartbeat 10 --log WORK/laudit.log -- python3 -m e14.e14l_audit WORK/lscore.json.gz WORK/lreplay.json.gz
```

## Reproduksi E1.4k

Dari checkout [pembekuan E1.4k](https://github.com/dianzherdiana25-hash/ACE/commit/ae73b9c9d69366d5a503fd1529ced1b11c716dd8), buat direktori `WORK` lokal. Gunakan ledger baru untuk replay dan ledger yang sama untuk resume.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/kscore.log -- python3 -m e14.e14k_run run WORK/kscore.sqlite WORK/kscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/kreplay.log -- python3 -m e14.e14k_run run WORK/kreplay.sqlite WORK/kreplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 90 --heartbeat 10 --log WORK/kaudit.log -- python3 -m e14.e14k_audit WORK/kscore.json.gz WORK/kreplay.json.gz
```

## Reproduksi E1.4j

Dari checkout [pembekuan E1.4j](https://github.com/dianzherdiana25-hash/ACE/commit/f62d4cf65d8a9e6b54e9062698378560a2881b95), buat direktori lokal `WORK`. Gunakan ledger yang sama untuk melanjutkan eksekusi dan ledger terpisah untuk replay.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/jscore.log -- python3 -m e14.e14j_run run WORK/jscore.sqlite WORK/jscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/jreplay.log -- python3 -m e14.e14j_run run WORK/jreplay.sqlite WORK/jreplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 90 --heartbeat 10 --log WORK/jaudit.log -- python3 -m e14.e14j_audit WORK/jscore.json.gz WORK/jreplay.json.gz
```

## Reproduksi E1.4i

Dari checkout [pembekuan E1.4i](https://github.com/dianzherdiana25-hash/ACE/commit/63aeaf63f1762dc766c13a8188c15a2996316daf), buat direktori lokal `WORK`. Jalankan kedua penilaian dengan ledger terpisah. Pakai nama ledger yang sama untuk resume.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 210 --heartbeat 15 --log WORK/iscore.log -- python3 -m e14.e14i_run run WORK/iscore.sqlite WORK/iscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 210 --heartbeat 15 --log WORK/ireplay.log -- python3 -m e14.e14i_run run WORK/ireplay.sqlite WORK/ireplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 90 --heartbeat 10 --log WORK/iaudit.log -- python3 -m e14.e14i_audit WORK/iscore.json.gz WORK/ireplay.json.gz
```

## Reproduksi E1.4h

Dari checkout [pembekuan E1.4h](https://github.com/dianzherdiana25-hash/ACE/commit/d6db8d065104ada75e676801bed62daa26cf094a), siapkan direktori `WORK` lokal. Gunakan nama ledger yang sama untuk resume, dan ledger baru untuk replay.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/hscore.log -- python3 -m e14.e14h_route run WORK/hscore.sqlite WORK/hscore.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 150 --heartbeat 15 --log WORK/hreplay.log -- python3 -m e14.e14h_route run WORK/hreplay.sqlite WORK/hreplay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 60 --heartbeat 10 --log WORK/haudit.log -- python3 -m e14.e14h_route audit WORK/hscore.json.gz WORK/hreplay.json.gz
```

## Reproduksi E1.4g

Dari checkout commit pembekuan, buat direktori `WORK` lokal. Jalankan dua perintah berbatas waktu dengan nama ledger dan output berbeda. Pakai kembali ledger yang sama untuk melanjutkan setelah interupsi.

```bash
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 210 --heartbeat 15 --log WORK/score.log -- python3 -m e14.e14g_run --ledger WORK/score.sqlite --output WORK/score.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 210 --heartbeat 15 --log WORK/replay.log -- python3 -m e14.e14g_run --ledger WORK/replay.sqlite --output WORK/replay.json.gz
PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 90 --heartbeat 10 --log WORK/audit.log -- python3 -m e14.e14g_audit WORK/score.json.gz WORK/replay.json.gz
```

## Handoff historis E1.4f

**Scientific latest:** E1.4f development diagnosis `BENCHMARK_HOLD_REDESIGN`, frozen [5d44ed7](https://github.com/dianzherdiana25-hash/ACE/commit/5d44ed79f9e7a3cac1f0940748d3f375ecdf4385), report [E14F_RESULT](design/e1.4/E14F_OPPORTUNITY_RESULT_v1.md), and [raw gzip JSON](evidence/e14/e14f_public_development_v1.json.gz). Opportunity remains sparse: in the primary curated/diagnostic condition, hindsight-positive S/G **2/6 each**; feasible Max-Gini positive **1/6 each**. The old E1.4 broad regression issue is locally resolved (84/84 PASS) after restoring missing historical fixture JSON. E1.4f code/protocol archive attached and remote Git SHA verified; use [reproduction instructions](code/e14/E14F_REPRODUCE.md).

1. **E1.4g next — diagnose benchmark construction, not optimize old target scores.** Pre-register a fresh data-generation protocol that yields distinct *unselected natural* tasks and a clearly labeled *opportunity-enriched experimental stratum*. Avoid selecting test tasks after seeing target outcomes. Separate source/meta/target bank and retain all negative cases.
2. Measure opportunity prevalence and label-cost-adjusted accessible improvements on **new** data before any policy-transfer claim. Include robust predictive representations, both-wrong/no-disagreement tasks and six-event out-of-inventory challenges. Predeclare opportunity threshold, no-posthoc-tuning rule and negative-transfer diagnosis.
3. Close **isolation gate** using an official supported Bubblewrap or a demonstrably equivalent process sandbox, with a precise evaluator nonexposure test. Without this, experiments are trusted public development only, never secure independent confirmation.
4. Preserve **full regression status** 84/84 and fresh-fixture SHA evidence; do not confuse missing files with a semantic code failure. Use bounded subprocesses, explicit errors, and GitHub remote blob/readback.
5. Use GitHub -> local Python -> GitHub. No Drive bridge, no added costs, no Tod/main modifications, no sealed E1.3 data.

The long-term OAIE charter is unchanged.
