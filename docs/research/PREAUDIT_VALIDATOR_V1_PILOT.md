# Validator Pra-Audit Bukti ACE v1 — Pilot Results (2026-11-13)

Implements the design freeze in `PREAUDIT_VALIDATOR_V1_DESIGN_FREEZE.md`.
Code: `code/ace_operational/preaudit_validator.py` (stdlib only, offline,
O_RDONLY source access, out-dir disjointness enforced by the CLI).
Oracle: `code/ace_operational/preaudit_oracle.py` (test support, independent).

## Self-test ladder — results per layer

| Layer | Result |
|---|---|
| Reference fixtures + independent oracle | PASS — oracle state-by-state agreement on C1; oracle expected verdict `fail` matches C3 on the fixture |
| Valid variants (FP probes) | 6 variants (key order, extra fields, CRLF, unicode, numeric spellings 0/0.0/−1.5/−1.50, manifest permutation): **false positives C1 0/6, C2 0/6, C3 0/6** |
| Seeded defects (one per rule) | 9/9 caught by the owning check as TIDAK SESUAI (missing/truncated/1-byte-corrupt artifact → C1; sum off-by-one, field inequality, rate beyond tolerance → C2; flipped verdict → C3; boundary metric at threshold correctly SESUAI under inclusive gte; malformed manifest entry → UNKNOWN, not a mismatch) |
| Property / metamorphic | PASS — byte-identical reports across runs; manifest permutation invariance; unlisted file changes no state |
| Parser fuzzing | 9 cases (duplicate keys, null vs missing metric/verdict, truncated JSON, empty results, NaN literal, 1e999, string metric, ambiguous/unknown op): all classified UNKNOWN (or SESUAI where decidable), zero exceptions escaping |
| Holdout corpus | Authored AFTER freeze commit `2ce468e` (validator SHA-256 `894bd7c9…a7646`, recorded in `test_preaudit_holdout.py`): **5/5 PASS on first run, validator untouched after freeze** — new shapes: subdirectory artifacts, 3 results entries, single-pair count forms, explicit {op, threshold} rule, `entry_seq:` selector |
| Full package sweep | `unittest discover` over `code/ace_operational`: **283 tests OK (17 skipped)** = 251 pre-existing + 32 new |

## Pilot A — frozen real package: A/B/C v3 evidence

Source: branch `research/ace-omega-v3-evidence-20261113` @ `0b3eac3`,
23 files, extracted byte-identically (intake had already sha256-verified
23/23). Source tree was chmod read-only during the run.
Manifest + reports: `evidence/preaudit_pilot_v1/v3_manifest.json`,
`v3_report.json`, `v3_report.md`.

- **C1 SESUAI** — 23/23 artifacts present, sizes and SHA-256 match.
- **C2 SESUAI** — 7/7 declared recomputations hold: per-band counts sum to
  the pooled counts in `results.jsonl` (A [0,90], B [90,90], C [90,90];
  control A [101,101], B [99,101], C [99,101]); pooled rates ×100 equal the
  finalize assessment rates within 1e-6; protocol hash (results ↔ prereg),
  record hash (results ↔ finalize), and differentiation index
  (−1.9801980198019749 in both) are field-equal.
- **C3 SESUAI** — preregistered rule `differentiation_index_pp >= 0`;
  recorded metric −1.9801980198019749 → expected `fail`; recorded verdict
  `fail`. (Independent oracle recomputation agrees: expected `fail`.)

Exit code 0. This says the frozen package is internally consistent with its
manifest on these mechanical checks — nothing more (see honest limits).

## Pilot B — bake-off intake records (three-state demonstration)

Source: branch `research/ace-omega-bakeoff-records-20261113` @ `e8a3feb`,
11 evidence files, artifacts-only manifest
(`evidence/preaudit_pilot_v1/bakeoff_*`).

- **C1 SESUAI** — 11/11 artifacts match.
- **C2 UNKNOWN** — no count assertions declared; the validator invents none.
- **C3 UNKNOWN** — no verdict check declared (these records carry no
  preregistration/results pair in the supported shape).

Exit code 3 — the honest third state on real data, not a failure verdict.

## Seeded-mismatch demo on the real package shape

A copy of the v3 package with exactly one change — the recorded verdict
flipped to `pass` (manifest hashes refreshed for the copy, so C1 stays
SESUAI and the defect is isolated) — yields **C3 TIDAK SESUAI**:
"metric differentiation_index_pp=-1.9801980198019749 gte 0 -> expected fail,
recorded pass", exit code 2. Files:
`evidence/preaudit_pilot_v1/demo_seeded_mismatch_*`. This demo package is a
synthetic copy, not a real package; it exists to show the mismatch state on
real-shaped data.

## Honest limits (what remains unproven even with all layers green)

- The validator proves a package matches **its manifest**; it does not prove
  the manifest is the right one. Manifest custody is an operator act, out of
  scope for v1 (the pilot manifests were built by operator tooling from the
  frozen branch snapshots, and their SHA-256s are recorded in the reports).
- No proof the preregistration predates the results (no timestamp/custody
  chain is checked).
- Declared C2 recomputations are executed, not judged: if the declared
  formula were scientifically wrong, the validator would faithfully check
  the wrong formula.
- Nothing here evaluates the evaluator, the fixtures, the gate criteria, or
  the experiment. SESUAI is not approval — every report carries that
  disclaimer verbatim, and there is no aggregate PASS anywhere in the output.
- Coverage is bounded by the fixtures, holdout, and pilots actually run;
  package shapes outside them are unproven territory, and unknown shapes
  fail toward UNKNOWN by design.
