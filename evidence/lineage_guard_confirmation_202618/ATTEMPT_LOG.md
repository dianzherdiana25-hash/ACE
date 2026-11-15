# ATTEMPT LOG — Lineage-Guard Confirmation Run (PR #188)

Custody: /workspace/ace-custody-lineage-guard (ACE sandbox
2887726280f4). Operator: Ian (main execution session) under ila
hub orchestration. Act: evidence/lineage_guard_state/
act_confirm_202618.json (sha256
60fc25e167d5d66111f0bb5cb3790e56826c60a191e0b4fcdd33c7cc2edaafbb;
seeds 20261803/20261804/20261805).

## Attempt 1 — 2026-11-15 21:15 WIB — STOPPED BY OPERATOR
Launched under the standard sign with a prose window text in the
act (sha 425309ab…). The hub's prescribed window inscription
("JENDELA KONFIRMASI — RUMAH KOSONG SEMUA PINTU (hub, 15 Nov
21:07 WIB)") arrived after launch; the operator stopped the run
during the gates stage (no band cell had run), replaced the act,
and relaunched. This attempt's console log was overwritten by
attempt 2's launch (same log path); its facts are attested by
the operator's hub deltas of 21:15–21:17 WIB.

## Attempt 2 — 2026-11-15 21:17 WIB — VOID at A.6 step 4
Act correct (sha 60fc25e1…). Steps 2–3 PASSED inside the run
(L4 4/4 identical+anchor; L1/L2 reproduction PASS). Step 4
stopped: the gate adapter could not find
distractor_inoculation.py because the operator passed
--battery-dir /workspace/ace-custody-lineage-guard/wt-battery
(one level too high; the adapter requires the directory that
CONTAINS the module: …/wt-battery/code/ace_operational, where
the frozen battery supplement lives, sha cbc5e7df…). Verdict
VOID (gate stop), recorded by the harness. Steps 5–8 never ran;
no band cell was touched. Console log preserved as
run_attempt2_VOID_2117.log. Root cause: operator path error —
the run sheet had flagged this exact verification ("verify the
--battery-dir layout at the P6 smoke") but the preparation smoke
ran gate mode only (steps 2–3) and never exercised step 4.

## Step-4 standalone proof — 2026-11-15 21:28–21:37 WIB
The gate adapter was run standalone with the corrected
--battery-dir and a throwaway state dir: stock
overall=SUSCEPTIBLE (positive control), guarded
overall=NOT_SUSCEPTIBLE, anchor=NO_REGRESSION, l5_violations=0
— GATE PASS. (Reports in the operator's battery-smoke-state;
the official run re-executes step 4 in its own state.)

## Attempt 3 — the sealed run (execution amendment v2 applied)
See EXECUTION_AMENDMENT.md. The frozen harness (PR #193,
supplement #2 shas) is unmodified; the act is unchanged;
verdict rules, bands, arms, cost ceilings, and cell contents
are exactly as preregistered.

Scheduling note (recorded 21:44 WIB, as it happened): the
three band lanes launched first (≈21:38, after the standalone
battery PASS and the pre-flight's PREFLIGHT_PASS 21/21), and
the official harness process was launched CONCURRENTLY at
21:39:59 (PID 306407) — its steps 0–4 (gates + official
battery) overlap the lanes' cell phase, per the hub's overlap
instruction; lane state dirs are private, cell checkpoints
reach the official state dir only through the placer's atomic
rename, and step 6 arrives after placements complete. At
21:41 the official log already showed L4 arm A
(catalog_control-020) identical=True anchor=True.
