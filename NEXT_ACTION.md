# NEXT_ACTION — diagnosis ambiguitas lintas grammar E1.4i

1. Verifikasi HEAD GitHub dan baca [E1.4h](design/e1.4/E14H_RESULT_v1.md), [bukti](evidence/e14/e14h_verification_v1.json) dan [piagam](PROJECT_CHARTER.md). Skor tinggi pada S alami enam kejadian menutupi kesulitan mengenali panjang. Lima dari enam blok memiliki fit demo sempurna di kedua grammar. Tidak ada kata target di pool atau probe sel tersebut.
2. Bangun bank publik baru yang memisahkan pool tanpa saksi dari pool yang memiliki saksi lintas grammar berdasarkan konstruksi. Tahan distribusi alami tetap terpisah dan laporkan prevalensi saksi. Gunakan input baru, pisahkan RNG, pertahankan kasus negatif, dan bekukan generator, ambang, serta biaya sebelum penilaian. Jangan tuning dari skor E1.4g/h.
3. Uji satu label yang dipilih dari perselisihan lintas grammar. Bandingkan dengan E1.4h, tanpa label, dan satu label acak, dengan pembanding retrospektif yang mengukur apakah peluang memang ada. Nilai diagnosis panjang dan false positive pada saksi secara terpisah dari akurasi mentah. Catat keadaan ketika sistem seharusnya menunda keputusan karena bukti belum memadai.
4. **NATURAL_HOLD** membatasi transfer. Benchmark publik ini meneliti pengenalan keterbatasan sebagai langkah menuju pembentukan representasi baru.

## Reproduksi E1.4i

Dari checkout pembekuan E1.4i, buat direktori lokal `WORK`. Jalankan kedua penilaian dengan ledger terpisah. Pakai nama ledger yang sama untuk resume.

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
