# Validator Pra-Audit Bukti ACE v2 — Pilot Results (2026-11-13)

Implements `PREAUDIT_VALIDATOR_V2_DESIGN_FREEZE.md` on top of v1 (PR #179;
Ian's v2 list, PR #179 comment 6857357128; standing contract, coordination
harvest #9). **Compatibility lock held: for every v1 manifest, C1/C2/C3
states under v2 are identical to v1** — verified on the fixtures, both
holdouts, and both pilots below (v1 pilot report states == v2 pilot report
states, compared mechanically).

## Contract changes, per item

1. **Four-stage lifecycle (V2-1).** Every report carries a `lifecycle`
   block: stages `STAGED → REGISTERED OBSERVATION → VALIDATION VERDICT →
   PUBLISHED RESULT` in order; `input_stage` is REGISTERED OBSERVATION only
   when C1 confirms every artifact byte-identical (otherwise STAGED);
   `output_stage` is always VALIDATION VERDICT; `stages_not_performed`
   names PUBLISHED RESULT — the validator never publishes. Every check and
   item carries its stage.
2. **Spec-digest binding (V2-2).** `validation_spec_digest` = SHA-256 over
   canonical JSON closing the evidence closure (declared path/sha256/size
   set), the ruleset as declared, the validator build (version + runtime
   SHA-256 of the validator's own source), and the configuration (report/
   manifest schema ids, reason-code registry v1, stage-model v1). Printed
   in the report header, repeated in every check block, and printed in the
   CLI summary line. Reports are filed under the digest:
   `report-<spec16>.json/.md`.
3. **Process-error separation (V2-3).** Validator failures (unreadable
   manifest, missing source root, internal crash) exit 1 and write only a
   `process_error.json` record `{kind: PROCESS_ERROR, stage: PROCESS,
   verdict: null}` — no check states, no report file, nothing cacheable as
   a verdict. Reports are computed fully in memory and written atomically.
4. **Reason codes (V2-4).** Every item carries a `reason_code` from the
   closed registry (registry v1, 21 codes); the validator self-audits that
   each code belongs to its item's state before any report is written.
5. **Nondeterminism conflict (V2-5).** Re-running a spec whose stored
   report differs by one byte writes `nondeterminism_conflict-<spec16>.json`
   (both byte hashes), preserves the stored verdict untouched, and exits 4.
   Identical re-runs are idempotent; different specs coexist in one out-dir.

Exit codes: 0 SESUAI · 2 TIDAK SESUAI · 3 UNKNOWN · 4 conflict · 1 PROCESS.

## Self-test ladder — results

| Layer | Result |
|---|---|
| v1 suites, regression lock | 32/32 PASS with **zero assertion changes**; the only edit is harness file discovery (reports are digest-named now). FP probes still 0/6 per check; v1 holdout still 5/5 |
| v2 targeted tests (new) | 16/16 PASS: lifecycle order/honesty, oracle digest agreement, digest sensitivity to closure/ruleset/build/config, states invariant under build-only change, process-error shapes (missing/unparseable manifest, induced internal crash), registry conformance of every item, NOT_DECLARED codes, conflict preserve/idempotence/coexistence |
| Oracle extension | `oracle_spec_digest` (independent, from the freeze text) **agrees with the validator on the fixture and on both real pilots** |
| v2 holdout | Authored AFTER freeze commit `6cccc7f` (validator SHA-256 `e8451ae8…`): **4/4 PASS on first run**, validator untouched — new shapes: custom `rule_pointer`, zero-denominator rate (UNKNOWN/RATE_UNDEFINED), relabeled-manifest conflict, file-as-source-root process error |
| Full package sweep | **303 tests OK (17 skipped)** = 283 previous + 16 v2 + 4 holdout v2 |

## Re-pilots

**Pilot A — v3 frozen evidence (same manifest as v1 pilot).**
States identical to v1: C1/C2/C3 **SESUAI**, exit 0 — now bound to
`validation_spec_digest` **77298db3605f3bcf…** (oracle-recomputed, match).
Lifecycle: REGISTERED OBSERVATION → VALIDATION VERDICT.
Files: `evidence/preaudit_pilot_v2/v3_manifest.json`, `v3_report.{json,md}`.

**Pilot B — bake-off intake records (same manifest as v1 pilot).**
States identical to v1: C1 SESUAI, C2/C3 **UNKNOWN**, exit 3 — now with
machine-readable reason codes: C2 `NOT_DECLARED`, C3 `NOT_DECLARED`.
Spec digest **2697651478ebb71c…** (oracle-recomputed, match).
Files: `evidence/preaudit_pilot_v2/bakeoff_*`.

## Honest limits (in addition to all v1 limits, which stand)

- The digest closes the **declared** closure + ruleset + build + config —
  not manifest metadata such as `package_id`. A label-only manifest change
  therefore keeps the digest but changes report bytes, and surfaces at
  write time as an audited conflict (proven in the holdout) rather than a
  silent replacement: conservative, and named here rather than hidden.
- Conflict detection works at write time inside one out-dir; divergence
  across separate out-dirs or machines is not detected by the validator.
- A bound verdict can still be a wrong-spec verdict: binding proves *which*
  spec produced a verdict, never that the spec was right (v1 §5 stands).
- Stage labels declare lifecycle position; what a downstream publisher does
  with a verdict remains the publisher's discipline.
