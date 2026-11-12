# ACE Ω Checkpoint — Addendum 39 (opportunity register built)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.

## 1. What was built (draft PR #142)

`ace_operational/opportunity_register.py` — the instrument
Addendum 38 §2 opened:

- **Asset registry** (12 assets): 4 venues (KBM, Facebook,
  Threads, Lynk.id), 3 brains (local Qwen3-8B, Claude-class
  Ian/ila, Antigravity Gemini), 5 capabilities — each with
  kind, role, status, and evidence stated plainly,
  including the unflattering states ("owner promised, not
  created"; "quota exhausted"; "revenue measured Rp 0";
  "no market validation yet").
- **The register itself**: append-only, hash-chained
  (tamper-evident), fail-closed validation — an entry must
  combine ≥2 registered assets, its origin must be a
  registered brain or FOUNDER, and its status must be in
  the fixed vocabulary. The living register file sits with
  the other custody stores outside the repo
  (`opportunity-register/register.jsonl`).
- **Scan**: deterministic, combinatorial (venue ×
  capability / brain / venue), excluding combinations
  already registered. With entry #1 recorded it currently
  surfaces 37 unexploited pair candidates. The scan
  proposes; recording an entry is a separate, attributed
  act. The scan is rule-based and is **not** claimed to be
  machine creativity — it is the floor the doctrine will
  be measured against, not the ceiling.
- **Director-cycle binding**: `build_scan_packet` shapes
  candidates as a fact packet with stable ids, so a future
  director cycle can judge them under citation discipline.
  Running such a cycle is separate work and has not
  happened yet.
- **The measure**: `origin_share` — at opening, the
  register holds exactly 1 entry, origin FOUNDER, so the
  ACE-side synthesis share is **0.0**. That is the honest
  baseline for the doctrine's long-run measure.

Entry #1 is recorded in the living register with its
fences (privacy rule; KBM exclusivity — promotion is
announcement/teaser + link, never republication; no
separate product story exists yet). Chain verified after
seeding. Module tests: 9 OK.

## 2. What this does not change

No gate moves: G3, G4, G5 remain NOT_ASSESSED and OAIE
unproven. No venue has yielded revenue. The register
records opportunities; it does not execute them — any
pilot remains a recorded governance decision under the
business study's ladder, reported to the owner.

## 3. Queue after this addendum

Build g3_instrument.py (reassigned from the Antigravity
bench, Addendum 38 §3) → KBM pilot design package →
services demand test → A/B/C v3 design (strategy arms) →
G3 first application once the instrument exists →
G4/G5 instrument implementations. Facebook mission
verification remains blocked on the owner showing the
mission panel. The 14B partial download still awaits a
resume/delete decision; no action taken.
