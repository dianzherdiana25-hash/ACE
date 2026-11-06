# ACE v0.3 — learned counter/guard composition

2026-11-06. PUBLIC SYNTHETIC DEVELOPMENT; scientific NOT_ASSESSED.

The integrated library can construct a product of an unchanged S2 counter AST
and an unchanged R1 DFA learned from the counter's observed false acceptances.
The product grammar is supplied by the researcher; this is composition within
that grammar, not discovery of a new computational primitive type.

## Protocol and source custody

- Original protocol committed before implementation/scoring:
  `7b9eea945175c67300118187ab55f1e8e776f005`.
- First execution halted on an impossible ratio4 validation sample: only 45
  distinct positives available, while the protocol required 64. No complete
  result was emitted. The separate feasibility amendment was committed at
  `54030a3226da020298ee2cc0f7f65649bc364f93` before the corrected rerun. Validation
  lengths changed from 6–12 to 6–15 for every task; the original protocol remains
  unchanged. No accuracy-dependent threshold, method or task changes were made.
- [Source manifest](UPSTREAM_SOURCES.json) pins 25 unchanged files from R1, S2,
  v0.1/v0.2 and the charter. An offline verifier checks their Git blob hashes.
  Main contains selected packages, not all historical ACE modules or suites.
- [Raw evidence, gzip](../evidence/composition/v03.json.gz): uncompressed 203,829 bytes, SHA256
  `9d14495fea246507a1a0841fcfde5a3e98bf44e66642b87a0c4d5503ffd52dc9`.

## Observed results

Eight tasks × three seeds, each with 63 training, 128 balanced validation and
128 balanced terminal labels. Train lengths 0–5; terminal lengths 16–30. All arms
share the same labels per trial. Terminal data never enter `fit` or selection.
The table reports diagnostic predictions of every selected model, including
models that **failed admission**; these must not be called acquired capabilities.

| Task | R1 DFA | Counter | Composition search | Strong fixed products |
|---|---:|---:|---:|---:|
| Equal counts | 247/384 | 384/384 | 384/384 | 384/384 |
| Equal counts + starts-a | 200/384 | 379/384 | 379/384 | 384/384 |
| Equal counts + ends-b | 249/384 | 374/384 | 384/384 | 384/384 |
| Equal counts + both boundaries | 195/384 | 371/384 | 371/384 | 384/384 |
| Equal counts + contains-ab | 223/384 | 384/384 | 384/384 | 384/384 |
| Two-to-one + both boundaries | 192/384 | 380/384 | 380/384 | 384/384 |
| Four-to-one, outside counter grammar | 204/384 | 192/384 | 204/384 | 192/384 |
| Dyck prefix balance | 201/384 | 368/384 | 368/384 | 381/384 |
| **Total** | **1711/3072** | **2832/3072** | **2854/3072** | **2877/3072** |

The learned product was selected in 3/24 trials, all ends-b tasks, improving
10 terminal predictions over counter-only on those trials. Another 12 predictions
come from choosing the DFA on ratio4. Composition search gains 22/3072 overall
against counter-only and loses 23/3072 against the fixed-product library.
**No superiority over the strong baseline is established.** Only 6/24 composition
models pass exact train+validation admission (equal counts and ends-b, three each).

Randomly drawn negative examples often violate the count relation already, so
high aggregate accuracy can conceal unresolved order constraints. Three seeds
share the same short training bank, and this public bank is not an independent
confirmatory evaluation. The method remains limited by sparse residual labels,
the seven-slope grammar and the finite-state learner.

The identical-history late-flip witness is derived by complementing the first
trial's terminal truth without changing its training/validation or selected model:
ordinary 128/128, inverted 0/128. This is an algebraic falsifier, not a claim of
an independently collected new world. No observation-only method can identify
that rule change from the identical history.

## Verification and unresolved gates

- Local Linux/Python 3.12: 92 tests PASS, including 12 new composition checks and
  unchanged imported suites. Full-run replay is deterministic. CI repeats tests
  on Python 3.12/3.13 and compares replay bytes with committed evidence.
- Serialized counter/product/DFA predictions are replayed via a separate counter
  formula and BFS DFA interpreter. Fixed-library guard functions are shared;
  this is semantic consistency checking, not an independent scientific evaluator.
- All 24 selected model fingerprints remain unchanged after later trial fits.
  This is artifact retention, not learned method transfer or lifelong learning.
- Merge attempts, controller prediction calls and S2 AST nodes are reported.
  Internal R1 consistency-check predictions and semantic-replay costs are not
  metered: the protocol's complete-compute-accounting requirement remains OPEN.
  Arms are **not compute-matched**; no efficiency superiority is claimed.
- No open-world safety, primitive-type invention, recursive productivity or OAIE
  claim. No learned candidate deployment. Main hosts the reviewed research code;
  original v0.1/v0.2 `BLOCK_RELEASE` decisions remain unchanged.

Next useful falsifier: count-matched order negatives and richer residual evidence,
with complete R1 work accounting and the fixed-product comparator preserved.
