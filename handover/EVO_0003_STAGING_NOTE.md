# EVO 0003 — STAGING NOTE (tree-independent parts)

Owner decision 2026-11-16 01:05 (flash form) + go order 01:08. This note
stages everything that does NOT depend on the Phase 0 basis column
(merge-first vs stacked basis — OPEN, owner's word pending). Instruments
that run against the code tree wait for that column; corpora/band/battery
DATA staging proceeds now.

## Seed allocation plan (disjointness)

Used or named band seeds to date:
- 20261501–20261503 (Stage 2 dev/official line)
- 20261601–20261603 (Stage 3 official)
- 20261701–20261703 (named confirmation bands, unused)
- 20261801–20261805 (re-baseline + Q1 confirmation: 1803/1804/1805 used;
  1801 suitable-unused, 1802 rejected)

EVO 0003 allocation (fresh, disjoint from all of the above):
- Blast deterministic solver cells: **20261901–20261906** (six bands:
  3 clean/infected pairs across two catalog families — final pairing
  fixed in the preregistration).
- Tail heterogeneous episodes: seeds derive per episode from the
  preregistration's episode manifest (not band seeds).
- Reserve (do not use): 20261907–20261910, held for contingency re-bands
  named only by a hub act.

## Distractor battery — variant set design (data only)

Current registry holds ONE variant (name-swap-523014-nc, causal key
('name_swap', (5,2,3,0,1,4), 'nc'), witnesses catalog_control-020/-021).
Flash form requires the FULL battery: 8–12 variants. Design space, all
name_swap permutations over the six operator names targeting the witness
lineages (020/021/022 class tasks), each variant = one registry entry
(permutation + target token class) with its own causal key:

1. (5,2,3,0,1,4) 'nc' — EXISTING, sealed witness.
2. (5,2,3,0,4,1) 'nc' — tail-swap of variant 1.
3. (2,5,3,0,1,4) 'nc' — head-swap.
4. (5,3,2,0,1,4) 'nc' — middle rotation.
5. (4,2,3,0,1,5) 'nc' — endpoint exchange.
6. (5,2,4,0,1,3) 'nc' — inner pair exchange.
7. (1,2,3,0,5,4) 'nc' — reverse-tail.
8. (5,2,3,4,1,0) 'nc' — sink rotation.
9–12. RESERVE slots: four further permutations to be drawn by seeded
   RNG at staging-freeze time and recorded in the blast manifest, so the
   exact set is fixed by digest before the run, not chosen after.

Each variant must pass the same suitability screen the re-baseline used
(a band is suitable only if the variant's causal key is NOT naturally
admitted by the clean catalog). Suitability screening is instrument work
— it waits for the basis column; the variant DEFINITIONS above are data
and are staged now.

## Dialogue corpus plan (tail, Phase 1 campaign)

- Indonesian-language dialogue episodes against the front organ with
  thinking bounded (chat_structured defaults), validator = coder organ.
- Corpus = episode prompt set (instructions + contexts) authored as data
  files; generation is generation-bound and runs DETACHED in the tail,
  never in the blast.
- Corpus freeze = file digests in the tail manifest at preregistration
  ratification; authoring starts after the preregistration draft is
  filed (it defines episode count and scoring).

## What waits for the basis column

- Band catalog generation + suitability screens (solver-tree instruments).
- Battery registry code entries (the data above becomes registry rows
  through the custody instrument).
- Blast runner scripts pinned to a tree digest.
