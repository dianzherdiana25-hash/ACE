# Family 3 design — text_transform (slug pipeline)

Status: **DESIGN + PROTOTYPE** (2026-11-13). Prototype
module `code/ace_operational/family3_prototype.py`,
tests `code/ace_operational/test_family3_prototype.py`
(9 green), initial census
`evidence/family3_census.json` (harness-side script
`family3_census.py`). Not registered in
`curriculum_lab.FAMILIES`; no discovery run, no
solving run, and no gate claim of any kind attaches
to this family yet.

## 1. Why a third family, and why this one

The discovery/transfer science has exactly two
families: **grid** (2D spatial transforms over a
matrix, BFS-shaped programs) and **pricing**
(arithmetic business rules over numeric scalars,
threshold conditionals, an authored substrate frozen
at B-3). A cross-family transfer claim measured only
on those two is one substrate change away from
being a claim about two programs. The third family
must be structurally different from both, or the
next transfer test measures nothing new.

**Chosen: string/text transformation programs** —
a staged lexical pipeline (split → per-word case
map → join → conditional ellipsis truncation)
mapping `str -> str`.

Against the selection criteria:

- **(a) Structural distinctness.** Program shape is
  a pipeline of string operations over a token
  sequence; the value domain is text, not numbers
  or matrices; there is no accumulation variable,
  no threshold on a numeric input, no spatial
  structure. The defect ontology is lexical
  (case ops, separators, whitespace semantics,
  slice bounds on strings, token order) — disjoint
  from pricing's basis/boundary arithmetic and
  from grid's move/wall ontology.
- **(b) Reference + named defect classes.** The
  reference is rendered from seed parameters
  (case mode, separator, limit — baked in as
  literals, the pricing pattern); buggy variants
  are produced by six named transforms of the
  correct code, the curriculum_lab catalog
  pattern (§3).
- **(c) Exact checkability.** Every task carries
  shown cases + shown truth and holdout cases +
  holdout truth, all computed by running the
  reference; a fix passes or fails exactly, no
  rubric anywhere.
- **(d) Informative richness.** The six classes
  split across the existing machinery's reach:
  some sit inside the generic schema space of
  `operator_discovery.enumerate_variants`
  (separator/case strings are string literals;
  the truncation bound is an int constant), and
  some sit outside it (the `split(" ")` argument
  insertion; a method-name swap on an attribute
  call; `reversed(...)` wrapping). A future
  measurement can therefore show saturation on
  part of the family and a named gap on the
  rest — both outcomes are informative, neither
  is foreordained.
- **(e) Determinism.** One `random.Random(seed)`
  drives parameters, case construction, and
  defect-combination choice; rebuilding a task
  from its seed reproduces it byte-for-byte
  (tested).

### Why the other candidates lost

- **List/sequence aggregation** — programs fold a
  numeric list into a scalar; the ontology
  (sum/product/filter slips, off-by-one over
  indices) is arithmetic in a loop, a near
  neighbour of pricing's numeric ontology. The
  transfer claim it could support is weak.
- **Date/scheduling arithmetic** — component
  arithmetic over calendar fields; again numeric
  at its core, and correct ground truth drags in
  calendar edge semantics (leap years, month
  lengths) that measure calendar knowledge, not
  program repair.
- **Nested-dict/record transformation** — the
  strongest runner-up (genuinely distinct shape),
  but its case/truth objects are nested
  structures whose equality and generation are
  heavier to keep exact and seed-compact, and
  its defect transforms are harder to keep
  one-edit-sized. Recorded as the leading
  candidate for a family 4, not discarded.

## 2. Program template

```
def transform(text):
    words = text.split()
    words = [w.<case_mode>() for w in words]
    slug = "<sep>".join(words)
    if len(slug) > <limit>:
        slug = slug[:<limit>-3] + "..."
    return slug
```

Parameters: case_mode ∈ {lower, upper, title},
sep ∈ {"-", "_"}, limit ∈ {8, 12, 16, 20} — a
24-combination reference grid. The ellipsis body
is deliberate: with a bare `slug[:limit]` body,
the truncation-condition boundary is unobservable
(the slice is the identity at len == limit), and
a defect class that cannot change any output is
not a defect class. The prototype's first test
run caught exactly this (the class was
unreachable); the template was fixed before any
census, and the episode is recorded here rather
than smoothed over.

## 3. Defect classes (catalog, subtlety in brackets)

| Class | Transform of the reference |
|---|---|
| `case_mode_swap` [1] | the case method is replaced by a wrong one (lower→upper, upper→lower, title→lower) |
| `separator_swap` [1] | the join separator literal is swapped ("-" ↔ "_") |
| `word_order_reversal` [1] | the join consumes `reversed(words)` |
| `truncate_off_by_one` [2] | the truncation slice bound drops by one (`limit-3` → `limit-4`) |
| `truncate_condition_boundary` [2] | the truncation condition `> limit` becomes `>= limit` |
| `split_whitespace_semantics` [2] | `text.split()` becomes `text.split(" ")` — empty tokens appear on whitespace runs |

Level 1 = one defect, level 2 = an unordered pair
(the lab's singles/pairs structure). Transforms
anchor on disjoint source spans, so pairs compose
without anchor conflicts (verified by the level-2
builds in the census: 20/20 built).

## 4. Case-generation rule

Per task, a fixed-shape pool is built from the
seed: a single word; ordinary multi-word texts;
a capitalized dressing (exposes case defects);
messy-whitespace dressings — leading spaces,
multi-space runs, a trailing tab (expose the
split-semantics defect); and **boundary texts
constructed to hit slug lengths limit−1, limit,
and limit+3 exactly** (word combinations solved
against the known word-length pool, with a
deterministic filler fallback), which is what
makes both truncation classes observable and
separately identifiable. Truth is always the
reference's output; nothing is hand-labeled.

Validity gate (enforced in the builder, mirroring
the lab): at least two pool cases must expose the
buggy program; shown cases are then chosen to
contain one exposing case, and at least one
exposing case remains in holdout, so a repair is
checkable beyond the shown set. The lab's
stronger identifiability rule (every *partial*
fix fails a shown case) is NOT yet implemented
for pairs — named future work, not claimed here.

## 5. Census (initial, light — 60 builds, band 91000+)

From `evidence/family3_census.json` (enumeration
and task building only; nothing solved):

- Builds: **60/60 succeeded, 0 validity failures**
  (40 level-1, 20 level-2).
- Distinct reference programs: **21** of the
  24-combination parameter grid; distinct buggy
  programs: **48**.
- Per-class yields (task memberships):
  case_mode_swap 10 · separator_swap 14 ·
  word_order_reversal 11 · truncate_off_by_one 19 ·
  truncate_condition_boundary 13 ·
  split_whitespace_semantics 13 — **all six
  classes yield**, none dominates.
- Shown cases per task 1–6, holdout 3–8 (shown
  sets are thin on tasks where most of the pool
  exposes the defect; see §6).

## 6. How it plugs into the discovery machinery

The task dict is the core's existing contract —
the same shape `build_pricing_task` returns:
{task_id, family, level, seed, buggy_code,
reference_code, shown_cases, shown_truth,
holdout_cases, holdout_truth, defects: [names]}.

A future `TextAdapter` binds it through the
FamilyAdapter protocol exactly as PricingAdapter
does: `family_id = "text_transform"`;
`make_budget` = a reasoning_lab Budget with
entrypoint `transform` over the shown cases;
`passes` = exact string equality per case;
`extra_string_candidates` = ∅ (the program's own
literals suffice). The prototype module already
carries this binding as a labeled sketch.

One fence, stated plainly: **this family has no
authored baseline substrate.** `baseline_variants`
is empty and `baseline_catalog_id` returns
`text-prototype-v0:no-authored-substrate`. Any
future baseline arm for this family is the
generic schema enumeration alone until a
substrate is authored and frozen under its own
protocol — numbers from such an arm are
comparator measurements, never dossier figures
(the pricing adapter's pre-freeze lesson).

## 7. Known limits

- The 24-combination reference grid is small;
  if a future census needs a larger universe,
  the levers are named: more limits/separators,
  an optional suffix stage, multi-separator
  joins. (Pricing needed the same kind of lever;
  it is recorded here before anyone needs it.)
- Pair-level identifiability (§4) is future
  work; level-2 tasks are valid, not yet proven
  partial-fix-proof.
- No substrate, no solver numbers, no transfer
  numbers exist for this family. This document
  claims a substrate exists and is well-formed —
  nothing more.

Brain of origin: Muse (Ian's capability queue,
owner's fill-time mandate 2026-11-13 ~12:22 WIB).
