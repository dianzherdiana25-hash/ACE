# G5 Harvest — 2026-11-20 (Ian, main-chat seat)

First sealed harvest dossier for the G5 instrument
(`code/ace_operational/g5_instrument.py`, design
`docs/research/ACE_G4_G5_INSTRUMENT_DESIGN_20261112.md` Part II).
It replaces the closing board's form deficiency ("no assembled
dossier contains a harvest report") with a scored dossier.

## Sources (all real records, discussion room)

Units = consolidated stage/decision reports authored by the
discussion-room seat (`ila-discussion-room`) in chat
3adfe86b-f9a3-4a4f-9248-40c28ef90172, 2026-11-12 → 2026-11-20:
the Rp0 amendment recording (u1), the Tahap I/J stage report
(u2), the emancipation recording (u3), the 2026-11-18 ACE status
report (u4), the VM-incident correction report (u5), the
capability-language development report (u6), the EVO 0010/0011
speed proposal (u7), and the EVO 0011 open/close decision report
(u8). Use events = the owner's recorded responses in the same
room (emancipation correction, "intip" direction, Codex
resource commitment, process correction, full-program
direction), each timestamped after the unit it references.

Two-hats fence (D-G5-5): the harvester is the main-chat seat
(`ian-main-chat`), which authored none of the harvested
summaries; the discussion-room seat authored all of them.

## Bars (set in the harvest report before scoring)

c1_threshold 0.8 and c2_threshold 0.8 — a consolidated report
series should be complete and phone-usable in at least four of
five cases. c3_min_events 3, c3_min_domains 2,
c3_requires_correction true — recorded use must be plural,
cross-domain, and include at least one owner correction, the
strongest comprehension evidence in the design.

## FR-09 scoring rule applied per unit

dicoba/hasil/batas scored from the text as written.
keyakinan scored true ONLY where the report explicitly marks
certainty (verified vs pending, an evidence gap named as such,
or a confidence statement) — flat assertion does not count.

## Instrument result (assess_g5, criteria v1)

- C1 FAIL — 6/8 complete < 0.8; g5-u1 and g5-u7 each miss only
  `keyakinan`. The absolute HASIL floor holds (8/8).
- C2 PASS — 8/8 delivered in channel and self-contained.
- C3 PASS — 5 qualifying events across 4 domains
  (governance, operations, development, process), corrections
  present.
- Overall: **NOT_DEMONSTRATED** — on substance now, not form.

## What this changes

Delivery and recorded use are demonstrated-grade (C2+C3); the
single named blocker is report structure: two of eight reports
carried no explicit confidence marking. Standing fix from this
harvest: every consolidated owner report carries an explicit
keyakinan line. A later harvest period scored under the same
bars can pass C1 on that habit alone.
