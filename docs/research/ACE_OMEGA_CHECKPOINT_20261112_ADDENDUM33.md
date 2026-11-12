# ACE Ω Checkpoint — Addendum 33 (Stage K: director cycle #4; the stack merges to main; two doctrines recorded)

Date: 2026-11-12 (Asia/Jakarta). This addendum is the first
checkpoint written directly on `main` — see §2.

## 1. Stage K1 — director cycle #4 (agenda cycle 7, ACCEPTED)

Observation: post-Addendum 32 state (G1 DEMONSTRATED
unqualified; G2 null ×2; G3–G5 NOT_ASSESSED; catalogue growing
via discovery; stack unintegrated). Two attempts were rejected
and remain on the agenda (cycles 5–6): the driver sent
`timeout_seconds=1200`, outside the router's admitted 1..900
range (store receipt: INVALID_BUDGET, "timeout_seconds must be
1..900"); the empty reply is what the validator rejected. Fixed
to the proven configuration; cycle 7 accepted in 359.8 s with 5
grounded proposals: (1) integrate the PR stack; (2) build the
G3 instrument; (3) measure G4 and G5; (4) differentiate the
A/B/C arms via a richer operator space; (5) improve discovered-
operator transfer. The local director's ranking ratified the
Stage K package order (K2 before K3) unchanged.

## 2. Stage K2 — integration and the governance merge decision

Under the Emancipation amendment (Addendum 32 §3), integration
was treated as a governance decision on evidence, not an owner
approval item. An integration branch combined, in order:
current main (1 commit), the blueprint branch (#103), the
checkpoint branch (#106), the AVA branch (#105), on top of the
Ω chain tip (#133). **All four merges were conflict-free.**

Combined-tree sweep, first pass (per-package discovery): the Ω
package green (ace_operational 251 OK; tests/ incl. AVA
contract and e2e green) but 15 main-line areas red. Rather
than decide on that, every red area was attribution-run on the
combined tree **and** on pristine main with the repository's
correct top-level discovery: **all 15 are green on both trees**
with correct discovery (the reds were import-context artifacts
of the first-pass method — e.g. candidate_search runs 32 tests,
not 2); `tools/` is green under the repo's expected PYTHONPATH,
identically on main; ace_self_dev green on both. No failure was
integration-caused; none was unexplained.

Repository-integrity finding, recorded plainly: the per-stage
remote branches are **partial snapshots** — the remote chain
tip carried 621 of the local tip's 666 files (several stage
pushes listed incomplete path sets). The local worktrees are
the complete record. The integration branch was therefore
pushed as the **complete delta vs main (118 files, 0
deletions)** and its remote tree verified **byte-identical**
to the locally swept tree (726 files, zero tree diff) before
any merge.

**Governance decision: MERGE.** Conditions from the package —
combined tree fully green, no unexplained conflicts — were
met on the evidence above. Executed as PR #134, merged to main
(merge commit `7c0bae2`). Post-merge: main's tree is
byte-identical to the swept integration tree, and the full
sweep re-run on main is green in every area (ace_operational
251 OK; tests/ 188 OK; tools/ 8 OK; all code/ packages OK —
the two areas red under `-t` discovery, ace_research_primitives
and tests/, lack `__init__.py` and are green under plain
discovery, as before).

Consequences: the Ω stack now lives on main. The stacked PRs
#103–#133 are superseded by PR #134; closing them with
evidence comments is a named hygiene item in the queue below.
The checkpoint lineage continues on main from this addendum.

## 3. Two doctrines recorded as program direction (owner, via the program director, 2026-11-12 evening)

**Agenda-source doctrine.** The Qwen3-8B director cycle remains
one advisory input stream — grounded and useful — but the
program agenda is not bounded by its horizon: its proposals
skew incremental, while the program's leaps (attested server,
dismissal drill, operator discovery) came from reading measured
results and architectural decisions. Agenda sources are
officially widened, and every proposal records its brain of
origin: (a) gate-gap analysis against the PRD text;
(b) falsification consequences — every measured null/failure
births the next mechanism item (the F → I pattern);
(c) stronger-brain director cycles when legitimately available
through the brain registry, recorded honestly as that brain's
cycle.

**Development-engine doctrine.** Made official: ACE's main
development engine is Claude-class AI — Ian as executing
engineer and strong-brain agenda source, ila as program
director. This is not a new dependence: under multi-brain
sovereignty Muse is a registered, dismissible brain; ACE's
identity stays in its constitution, ledger, and memory, and the
seat can move. The two-hats rule is unchanged: inside A/B/C
experiments the director remains ACE's own mechanism, so the
gates measure ACE, not Muse; the Qwen advisory cycle continues
as ACE's endogenous voice and as measurement data on the local
brain.

## 4. Queue (named, in order)

K3 — G3 instrument design (design-first, from the PRD text).
Then: hygiene — close superseded PRs #103–#133 with evidence
comments citing PR #134; director cycle #4 items 3 (G4+G5
measurement design), 4 (arm differentiation via richer operator
space), 5 (operator transfer); and the agenda-source candidate:
operator-discovery schema-space expansion (the human-designed
schema space is the next bound on catalogue growth).

Gate board unchanged: G0 PASS (session-scoped) · G1
DEMONSTRATED (unqualified) · G2 MEASURED-null ×2 · G3–G5
NOT_ASSESSED · OAIE unproven.
