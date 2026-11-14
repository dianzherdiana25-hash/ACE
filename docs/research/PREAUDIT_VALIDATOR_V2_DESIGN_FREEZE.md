# Validator Pra-Audit Bukti ACE v2 — DESIGN FREEZE (2026-11-13)

Builds on v1 (design freeze `PREAUDIT_VALIDATOR_V1_DESIGN_FREEZE.md`, PR #179,
integration review by Ian, PR #179 comment 6857357128). Source of the v2 list:
the adopted standing contract (coordination harvest #9) as written by Ian as
forward criteria. HARD COMPATIBILITY RULE: v2 does not change any v1 verdict
or check semantics on old packages — for any v1 manifest, C1/C2/C3 states are
bit-for-bit the same states v1 produced. v2 only adds contract machinery
around the verdicts. The v1 regression suite (fixtures, holdout, pilots) must
pass unchanged in states.

## V2-1. Four-stage lifecycle, declared in every output, never skipped/mixed

Stages, in order, and only in this order:
`STAGED → REGISTERED OBSERVATION → VALIDATION VERDICT → PUBLISHED RESULT`.

- The manifest is the STAGED input; artifacts it names become REGISTERED
  OBSERVATION when C1 confirms them byte-identical to the manifest (an
  artifact that fails C1 never advances past STAGED for downstream checks —
  this is exactly v1's dependency rule, now named).
- This validator produces artifacts of stage VALIDATION VERDICT only. It
  never produces, claims, or implies a PUBLISHED RESULT; publication is a
  separate act outside the validator. Every report carries a `lifecycle`
  block: the four stages in order, the stage of the input
  (`input_stage`), the stage of this output (`output_stage` =
  "VALIDATION VERDICT"), and `stages_not_performed` naming PUBLISHED RESULT.
- Every check and every item carries its stage. A report whose lifecycle
  block is missing or out of order is not a v2 report.

## V2-2. Verdicts are bound to a validation_spec_digest

`validation_spec_digest` = SHA-256 over a canonical JSON document closing:
- the evidence closure: the manifest's artifact set as (path, sha256,
  size_bytes) triples, sorted;
- the ruleset: the manifest's `count_assertions` and `verdict_check`
  exactly as declared (canonicalized: sorted keys, Decimal-safe);
- the validator build: `validator_build` = version string + SHA-256 of the
  validator's own source file, read at runtime;
- the configuration: report schema id, manifest schema id, the reason-code
  registry version, and the stage-model version.

Every check state and every item in the report is emitted under this one
digest (top-level field, repeated in each check block). Changing the
validator build, the ruleset, the evidence closure, or the configuration
produces a NEW digest, and verdicts under different digests are different
verdicts — they must never be merged, averaged, or silently substituted.
The digest is printed in the report header and in the CLI summary line.

## V2-3. Validator process errors are PROCESS status, never verdicts

- A validator crash, an unreadable manifest, a missing source root, or any
  other failure of the validator itself is a PROCESS outcome: exit code 1
  and, when the out-dir is writable and disjoint, a `process_error.json`
  record `{kind: "PROCESS_ERROR", stage: "PROCESS", error, no verdict
  fields}`. It is never recorded as a check state, never as UNKNOWN (UNKNOWN
  is a verdict about evidence, not about the validator), and never cached:
  the validator keeps no verdict cache across runs (in-run parse caching is
  not a verdict). A failed run writes no report file.
- Verdict files are written atomically (temp file + rename) only after the
  full report has been computed in memory.

## V2-4. Machine-readable reason codes everywhere

Every item carries `reason_code` from a closed registry
(`REASON_CODE_REGISTRY_VERSION = "1"`), alongside the human `reason` prose.
UNKNOWN items in particular must always carry one of the UNKNOWN codes;
free prose alone is never the only machine signal. Registry (v1 of the
registry):

- OK (SESUAI)
- ARTIFACT_MISSING, SIZE_MISMATCH, HASH_MISMATCH, PATH_ESCAPE,
  COUNT_MISMATCH, FIELD_MISMATCH, RATE_MISMATCH, VERDICT_MISMATCH
  (TIDAK SESUAI)
- NOT_DECLARED, INPUT_MALFORMED, PARSE_ERROR, POINTER_UNRESOLVED,
  METRIC_MISSING, METRIC_NON_NUMERIC, VERDICT_UNDECIDABLE, RULE_AMBIGUOUS,
  RULE_UNSUPPORTED, DEPENDENCY_UNRESOLVED, EMPTY_INPUT, RATE_UNDEFINED
  (UNKNOWN)

Check-level state remains the worst item state, as in v1.

## V2-5. Same spec + different output = audited nondeterminism conflict

- Report files are named by digest: `report-<spec16>.json` / `.md` in the
  out-dir, so verdicts of different specs coexist and never overwrite each
  other.
- If a report file for the SAME `validation_spec_digest` already exists and
  the newly computed bytes differ, the validator does NOT overwrite it. It
  writes `nondeterminism_conflict-<spec16>.json` (recording both byte
  hashes, the stored one preserved untouched), prints the conflict, and
  exits with code 4. Identical bytes are an idempotent success.
- This makes any nondeterminism — in the validator, the filesystem, or the
  input handling — a visible audited event instead of a silent overwrite.

## Exit codes (v2)

0 = all SESUAI · 2 = any TIDAK SESUAI · 3 = any UNKNOWN · 4 = nondeterminism
conflict (V2-5) · 1 = PROCESS error (V2-3; no verdict exists for that run).

## Self-test ladder (v1 ladder applies in full, plus)

- v1 suites run unchanged: same states on every v1 fixture and pilot
  manifest (regression lock), FP probes still 0, holdout v1 still passes.
- Oracle extended independently: `oracle_spec_digest` recomputes the digest
  from the manifest + validator file bytes with plain hashlib/json, written
  from this freeze, sharing no code with the validator.
- New targeted tests: stage block present and ordered in every output;
  digest changes when (a) an artifact digest changes, (b) a rule changes,
  (c) the validator build stamp changes, (d) config version changes — and
  verdict states do NOT change under (c)/(d) alone on the same package
  (binding is identity, not semantics); process-error run produces
  process_error.json, no report, exit 1, and no state strings anywhere in
  the error record; every UNKNOWN item in every suite carries a registry
  code; conflict path — tampered stored report + rerun → exit 4, stored
  bytes untouched, conflict record written; rerun identical → idempotent.
- New holdout authored AFTER the v2 freeze commit (validator SHA-256
  recorded in the holdout file), exercising digest binding and reason codes
  on shapes not used in development.

## What remains unproven (in addition to all of v1 §5)

- The digest binds a verdict to a spec; it does not make the spec correct —
  a wrong ruleset yields a perfectly bound wrong-spec verdict.
- The conflict mechanism detects differing outputs for the same spec at
  write time in one out-dir; it does not detect divergence across separate
  out-dirs or machines (cross-copy comparison is an operator act).
- Stage labels declare where an artifact sits in the lifecycle; they do not
  enforce what downstream actors do with a verdict (publication discipline
  stays with the publisher).
