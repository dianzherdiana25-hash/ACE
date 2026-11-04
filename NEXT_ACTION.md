# NEXT_ACTION — jalankan E1.4g dari checkpoint beku

1. Periksa HEAD branch GitHub dan cocokkan [manifest E1.4g](design/e1.4/E14G_LOCK_v1.json). Baca [protokol](design/e1.4/E14G_PROTOCOL_v1.md).
2. Dari checkout ACE, buat direktori kerja lokal. Jalankan `PYTHONPATH=code python3 tools/ace_bounded_runner.py --timeout 210 --heartbeat 15 --log WORK/score.log -- python3 -m e14.e14g_run --ledger WORK/score.sqlite --output WORK/score.json.gz`. Ganti `WORK` dengan direktori tersebut. Ulangi dengan ledger dan keluaran lain untuk replay. Pakai kembali ledger yang sama jika eksekusi terputus.
3. Jalankan `PYTHONPATH=code python3 -m e14.e14g_audit WORK/score.json.gz WORK/replay.json.gz` melalui runner berbatas waktu. Simpan bukti terminal, keputusan kedua distribusi, dan langkah berikutnya. Perbarui Issue #1 setelah verifikasi commit hasil.
4. Seluruh pekerjaan pada jalur publik. Aturan umum ada di [piagam](PROJECT_CHARTER.md).

## Handoff historis E1.4f

**Scientific latest:** E1.4f development diagnosis `BENCHMARK_HOLD_REDESIGN`, frozen [5d44ed7](https://github.com/dianzherdiana25-hash/ACE/commit/5d44ed79f9e7a3cac1f0940748d3f375ecdf4385), report [E14F_RESULT](design/e1.4/E14F_OPPORTUNITY_RESULT_v1.md), and [raw gzip JSON](evidence/e14/e14f_public_development_v1.json.gz). Opportunity remains sparse: in the primary curated/diagnostic condition, hindsight-positive S/G **2/6 each**; feasible Max-Gini positive **1/6 each**. The old E1.4 broad regression issue is locally resolved (84/84 PASS) after restoring missing historical fixture JSON. E1.4f code/protocol archive attached and remote Git SHA verified; use [reproduction instructions](code/e14/E14F_REPRODUCE.md).

1. **E1.4g next — diagnose benchmark construction, not optimize old target scores.** Pre-register a fresh data-generation protocol that yields distinct *unselected natural* tasks and a clearly labeled *opportunity-enriched experimental stratum*. Avoid selecting test tasks after seeing target outcomes. Separate source/meta/target bank and retain all negative cases.
2. Measure opportunity prevalence and label-cost-adjusted accessible improvements on **new** data before any policy-transfer claim. Include robust predictive representations, both-wrong/no-disagreement tasks and six-event out-of-inventory challenges. Predeclare opportunity threshold, no-posthoc-tuning rule and negative-transfer diagnosis.
3. Close **isolation gate** using an official supported Bubblewrap or a demonstrably equivalent process sandbox, with a precise evaluator nonexposure test. Without this, experiments are trusted public development only, never secure independent confirmation.
4. Preserve **full regression status** 84/84 and fresh-fixture SHA evidence; do not confuse missing files with a semantic code failure. Use bounded subprocesses, explicit errors, and GitHub remote blob/readback.
5. Use GitHub -> local Python -> GitHub. No Drive bridge, no added costs, no Tod/main modifications, no sealed E1.3 data.

The long-term OAIE charter is unchanged.
