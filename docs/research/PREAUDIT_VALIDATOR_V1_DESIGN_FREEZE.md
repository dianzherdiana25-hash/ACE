# Validator Pra-Audit Bukti ACE v1 — DESIGN FREEZE (2026-11-13)

Status: FROZEN before implementation. Changes after this point require a new
freeze note; the holdout corpus is authored only after the code implementing
this freeze is itself frozen (see §5).

## 0. What this is / is not

A mechanical, offline, read-only pre-audit tool for frozen ACE evidence
packages. It checks three narrow, mechanically decidable claims about a
package. It does NOT approve, validate, or endorse any experiment, result, or
gate claim. Its report language is constructed so a clean summary cannot be
read as experiment approval (see §2 disclaimer, mandatory in every report).

## 1. Architecture (physical, not intentional)

- Input is ONE explicit manifest (schema `ace.preaudit_manifest.v1`). The
  validator reads only files the manifest names. Files present in the source
  tree but absent from the manifest are ignored (and counted in the report as
  unlisted, for information only — never a verdict input).
- Source access is read-only by construction: artifacts are opened with
  `O_RDONLY`; every write goes to `--out-dir`; the CLI refuses to run when
  the resolved out-dir lies inside the resolved source root (or vice versa).
- Artifact paths must be relative, contain no `..`, and resolve (after
  symlink resolution) inside the source root. A path escaping the root is a
  deterministic violation (TIDAK SESUAI for that artifact), never followed.
- No network, no subprocesses, no imports beyond the Python standard library.
- Determinism: identical inputs produce a byte-identical report. The report
  contains no wall-clock timestamps; it records the manifest's SHA-256.

## 2. Three-state report language

Per check, exactly one state:

- `SESUAI` — every required input was present and parseable, and the
  mechanical comparison held.
- `TIDAK SESUAI` — a deterministic mismatch proven from complete inputs
  (e.g. bytes whose SHA-256 differs from the manifest's declared digest).
- `UNKNOWN` — evidence missing/unparseable, rule ambiguous or unsupported,
  or a dependency unresolved. UNKNOWN is not a soft mismatch; the checker
  stops instead of guessing.

Every check entry carries: `state`, `reason`, `evidence_present`,
`evidence_missing`, `dependencies`, `next_step`, and the check's measured
false-positive class (§4). The report header carries, verbatim:

> PRE-AUDIT MEKANIS — bukan persetujuan, bukan validasi eksperimen.
> Laporan ini hanya menyatakan hasil perbandingan mekanis atas paket beku
> terhadap manifest eksplisit. Keadaan SESUAI pada semua cek tidak berarti
> eksperimen sah, benar, atau disetujui.

There is no aggregate "PASS". The summary is only a count of states per check.

CLI exit codes: 0 = all checks SESUAI; 2 = any TIDAK SESUAI;
3 = no TIDAK SESUAI but any UNKNOWN; 1 = could not start (e.g. manifest
itself unparseable — checker stops, no report is fabricated).

## 3. The three mechanical checks

### C1 — Artifact completeness + hash integrity
For each manifest artifact: the file exists, its byte size equals the
declared `size_bytes`, and its SHA-256 equals the declared `sha256`.
Missing file with complete manifest inputs → TIDAK SESUAI (the manifest is
the complete input; absence is proven, not guessed). An artifact entry that
is itself malformed (missing digest, bad hex) → UNKNOWN (rule/input defect,
not a package mismatch).
False-positive class: canonicalization/path errors (symlink, case, separator)
— probed by valid-variant fixtures (§4).

### C2 — Result-count consistency
The manifest declares mechanical recomputations; the validator executes
exactly the declared ones, inventing no formula of its own:
- `sum_pairs_equals`: sum [num, den] pairs component-wise over a list in one
  artifact; compare to the pair at a target pointer.
- `field_equals`: values at two pointers must be exactly equal.
- `rate_equals`: rate num/den from a [num, den] pair (optionally × `scale`)
  must equal the number at a target pointer within a declared absolute
  tolerance. Rates are computed with `Fraction`; source numbers are parsed
  as `Decimal` — never binary float.
A pointer that cannot be resolved, a non-numeric value where a number is
required, or an unsupported assertion kind → UNKNOWN for that assertion.
All assertions resolved and equal → SESUAI; any resolved inequality →
TIDAK SESUAI.
False-positive class: numeric-representation brittleness (0 vs 0.0, 1e2,
integer vs decimal) — probed by valid-variant fixtures.

### C3 — Verdict vs preregistration rule
The preregistration artifact must contain `protocol.pass_rule` (or top-level
`pass_rule`): `{metric, op, threshold}` with op in {gte, gt, lte, lt, eq}.
The results artifact is JSONL; each entry has `result.metrics[metric]` and
`result.verdict`. Expected verdict: `pass` iff the metric satisfies the rule,
else `fail`. Verdict strings are normalized case-insensitively; `pass`/`fail`
are the only decidable values — any other verdict (e.g. an abstention), a
missing metric, a missing/ambiguous rule (multiple rules, unknown op), or an
unparseable entry line → UNKNOWN for that entry (checker stops, no guessing).
All entries decidable and matching → SESUAI; any decidable mismatch →
TIDAK SESUAI.
False-positive class: rule-shape rigidity (semantically equal rules written
in an unsupported shape yield UNKNOWN — by design this fails toward UNKNOWN,
never toward a false TIDAK SESUAI; measured in §4 probes).

### Strict JSON parsing (shared substrate, all checks)
Parsing rejects: duplicate object keys, `NaN`/`Infinity`, trailing garbage.
Numbers parse as `int`/`Decimal`. A parse failure makes the affected check
UNKNOWN with the parse error as reason — never a crash, never a guess.
CRLF, BOM-free UTF-8, extra whitespace, and key order are accepted.

Pointers: `/`-separated object keys / array indices from the document root.
For `.jsonl` artifacts the first pointer segment may be `entry:<n>` (0-based
line index) or `entry_seq:<n>` (record whose top-level `seq` equals n).

## 4. Self-test ladder (all layers required before trust)

1. **Reference fixtures + independent oracle.** `preaudit_oracle.py` (test
   support) is written from this written specification only, using plain
   `hashlib`/`json` in the most direct way, sharing no code with the
   validator. Fixture expectations come from the oracle, not from the
   validator's own output.
2. **Valid variants (false-positive probes).** Semantically identical
   packages under: key reordering, extra unknown fields, CRLF endings,
   unicode content, 0 vs 0.0 vs 1e2 numeric spellings, manifest artifact
   order permutation. Each check's false-positive count is measured and
   asserted 0/N, and printed in the test run.
3. **Seeded defects, one per rule.** Missing artifact, truncated artifact,
   one-byte hash corruption, count sum off-by-one, field inequality, rate
   beyond tolerance, flipped verdict, boundary metric exactly at threshold
   (gte is inclusive → pass). Each must be caught as TIDAK SESUAI by exactly
   the check that owns the rule.
4. **Property / metamorphic.** Manifest permutation invariance; report
   byte-determinism across two runs; adding an unlisted file changes no
   state; duplicating a results line is visible to C2/C3 inputs only as
   declared (no hidden global assumptions).
5. **Light parser fuzzing.** Duplicate keys, null vs missing field, truncated
   JSON, empty file, `1e999`, string where number expected, deeply mixed
   unicode/line endings. Required behaviour: UNKNOWN (or TIDAK SESUAI only
   where a complete-input proof exists), never an exception escaping.
6. **Holdout corpus.** Authored AFTER the validator + this freeze are frozen
   (freeze commit records the validator file SHA-256 in the holdout note).
   Holdout fixtures are never used to tune the validator; a holdout failure
   is reported as a failure, not silently fixed into a new tuning loop
   (any fix re-freezes and re-runs all layers).

## 5. What remains unproven even if every layer passes

- That the manifest itself is the *right* manifest: the validator proves a
  package matches its manifest, not that the manifest describes the package
  the experiment actually produced. Manifest custody is out of scope.
- That the preregistration predates the results (no timestamp/custody proof).
- That declared C2 formulas are the *scientifically correct* recomputations —
  the validator executes declared mechanics; it does not judge the formula.
- Anything about evaluator correctness, fixture quality, or gate criteria.
- Behaviour on package shapes not exercised by fixtures/holdout/pilot.

## 6. Pilot (first real run)

Frozen real package: A/B/C v3 evidence (23 files, branch
`research/ace-omega-v3-evidence-20261113`, head 0b3eac3, sha256-verified at
intake). Manifest declares: C1 over all 23 artifacts; C2 assertions tying
`abc_v3_run.json` band records → pooled counts in `results.jsonl`, pooled
rates → finalize assessment rates, and finalize↔results field equality
(protocol hash, record hash, differentiation index); C3 against the v3
preregistration pass rule (`differentiation_index_pp >= 0`; recorded metric
−1.9801980198019749, recorded verdict `fail`).
Secondary pilot: bake-off intake records (artifacts-only manifest → C1
decidable; C2/C3 honestly UNKNOWN — demonstrating the third state on real
data rather than synthetic fixtures only).
