# DISTRACTOR-INOCULATION BATTERY — DESIGN + BUILD (2026-11-13)

Status: BUILT + DEMONSTRATED. Hub design item (2026-11-13
~19:54 WIB), gated on the Stage 2 dose map, which now
exists (PR #174). Brain of origin: Ian (Muse).

## 1. Purpose

ACE's regression anchor (PR #167) answers "did this
catalog change regress the battery?" The control-
regression line (PR #173, Stages 0–2, PR #174) proved a
second, sharper failure mode: a single admitted operator
key can DIVERT the discovery solver's search path so
that tasks the catalog-only solver solves become
unsolvable — invisibly to aggregate battery scores until
a control set is examined per task. This battery makes
every such PROVEN distractor a standing test: any
catalog proposed for use is also solved against the
witness tasks of every registered distractor, with and
without the distractor injected.

## 2. Components (this PR)

- `ace_operational/distractor_registry.json` — the
  registry (schema `ace.distractor_registry.v1`). A
  record enters ONLY with measured causal evidence
  (leave-one-out restoration + dose map pointers);
  suspicion is not registrable — the loader refuses
  records without evidence pointers. Seed record:
  `name-swap-523014-nc-band20261501`, key
  `('name_swap', (5, 2, 3, 0, 1, 4), 'nc')`, witnesses
  catalog_control-020/-021 (abc-v3 band 20261501).
- `ace_operational/distractor_inoculation.py` —
  fail-closed registry loading (schema, required
  fields, key parsing via ast.literal_eval, duplicate
  ids, empty witnesses/evidence all raise) and
  `run_battery(catalog_keys, solve, registry)`: per
  distractor, solve each witness clean and injected;
  a witness is `diverted` iff clean-solved and
  injected-unsolved; per-distractor verdict and
  overall are SUSCEPTIBLE iff any witness diverts.
  Report schema `ace.distractor_inoculation.v1`.
  The battery is solver-agnostic (caller supplies
  `solve(task_id, keys) -> bool`) and changes nothing.
- `ace_operational/test_distractor_inoculation.py` —
  9 tests: registry validation (4 fail-closed cases +
  seed load), injection semantics, and the three
  verdict logics (susceptible / not / clean-failure is
  not diversion).

## 3. Anchor wiring (harness side)

`regression_anchor.py` gains `--inoculate --registry
<path>`: after the main comparison, the battery runs
against the CANDIDATE catalog's keys and the artifact
gains an `inoculation` section (the battery module
ships next to the registry file; the wiring loads it
from there). Witness solving mirrors the Stage 0/1
protocol (cap 4000, 60 s wall) on the registry's
witness universe, reconstructed via the v3 harness's
split (disclosed harness dependency; the v3 scorer
import is stubbed — never called by the wiring).
Consequence rule, mirroring the anchor's standing
trigger: a SUSCEPTIBLE overall blocks adoption of
the candidate catalog until the diversion is
explained in an addendum. The anchor's main verdict
grammar is unchanged.

Applicability: a registry entry binds to its
`witness_universe`; the battery speaks only about
catalogs exercised on that universe's witnesses.
Entries for other universes accrete as future
regressions are measured — the registry is the
accumulating asset.

## 4. Demonstrations (evidence on this branch)

1. Module on real witnesses
   (`evidence/distractor_inoculation_demo.json`):
   subject = band-20261501 admitted catalog minus the
   seed distractor (59 keys). Both witnesses solved
   clean, both failed injected, overall SUSCEPTIBLE
   (wall 210.3 s) — the battery reproduces the
   Stage 1 causal fact through its own code path.
2. Through the anchor itself
   (`evidence/regression_anchor_inoculation-wiring-demo.json`):
   `regression_anchor.py --baseline empty --candidate
   spec59 --battery 4 --inoculate --registry <seed>`:
   main battery 0 → 4 (NO_REGRESSION) and the artifact
   carries `inoculation.overall = SUSCEPTIBLE`.
   The 59-key spec file is byte-derived from the
   frozen discovery checkpoint with exactly the seed
   key's repr removed (generator script preserved in
   the run record of PR #174's line).

## 5. Honest limits

- Injection appends the key at the end of the catalog;
  Stage 1 measured outcome invariance across 8 order
  permutations for the seed distractor, so presence —
  not position — is the tested variable. A future
  distractor whose effect is positional needs a
  position-aware battery extension, recorded then.
- The battery detects diversion of KNOWN witnesses by
  KNOWN distractors. It does not search for new
  distractors; that remains the control-regression
  line's Stage 3 (fresh-band, entry-gated).
- Package sweep on this branch: 260 OK (skipped=17)
  = origin/main 251 + 9 new, no regressions.

— Ian, 2026-11-13.
