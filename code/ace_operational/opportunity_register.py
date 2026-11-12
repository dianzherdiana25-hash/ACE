"""Opportunity register (Addendum 38 §2 — the
opportunity-synthesis doctrine).

The owner's doctrine: ACE should connect its own assets
across venues without being spoon-fed combinations. The
honest starting position, recorded in Addendum 38:
cross-asset opportunity synthesis is NOT yet a
demonstrated capability — the first flywheel (KBM story
promoted on Threads) originated from the FOUNDER, and its
attribution stays exactly that.

This module is the instrument for that doctrine:

- ``ASSETS`` — the registry of what ACE has: venues,
  brains, and measured capabilities, each with its status
  and evidence stated plainly (including "not created
  yet" and "quota exhausted").
- ``OpportunityRegister`` — an append-only, hash-chained
  register of opportunity proposals. Every entry names
  the assets it combines (>= 2, all registered), the
  brain of origin (a registered brain, or FOUNDER), and
  a status. The chain makes the register tamper-evident.
- ``scan_opportunities`` — a deterministic scan for
  unexploited combinations (venue x capability,
  venue x brain, venue x venue) that are not yet in the
  register. The scan PROPOSES candidates; recording one
  as a register entry is a separate, attributed act.
  The scan is combinatorial and rule-based — it is not
  claimed to be machine creativity.
- ``build_scan_packet`` — the candidates shaped as a
  director-cycle fact packet, so a future director cycle
  can judge them under the usual citation discipline.
  That binding is the "scan bound to director cycles"
  hook; running such a cycle is separate work.
- ``origin_share`` — the doctrine's long-run measure:
  what share of register entries originated from ACE-side
  synthesis (any registered brain) versus the founder.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# ------------------------------------------------------------------
# The asset registry. Statuses and evidence are stated as
# measured/known at Addendum 38 (2026-11-13); updating an
# asset's status is a deliberate edit, not a side effect.
# ------------------------------------------------------------------

ASSETS = {
    # Venues — places ACE has been given to earn from.
    "venue_kbm": {
        "kind": "venue", "name": "KBM App",
        "role": "serialized-fiction storefront; first-earning pilot venue",
        "status": "account_active_writer_mode",
        "evidence": "login verified 2026-11-12; revenue measured Rp 0",
    },
    "venue_facebook": {
        "kind": "venue", "name": "Facebook (profile Pro + Pages)",
        "role": "monetized profile/Pages; $500 mission asset",
        "status": "connected_mission_terms_unverified",
        "evidence": "connector insights verified 2026-11-12; mission panel not readable via connector",
    },
    "venue_threads": {
        "kind": "venue", "name": "Threads",
        "role": "promotion / invite channel",
        "status": "active_first_post_live",
        "evidence": "first invite post live 2026-11-13 00:33 WIB",
    },
    "venue_lynk_id": {
        "kind": "venue", "name": "Lynk.id",
        "role": "digital-product checkout",
        "status": "created",
        "evidence": "store live: lynk.id/dianma25 (owner signed in himself 2026-11-13); 0 orders, no product yet",
    },
    # Brains — replaceable organs under multi-brain sovereignty.
    "brain_local_qwen3_8b": {
        "kind": "brain", "name": "Local Qwen3-8B (Research Director)",
        "role": "advisory director over observation packets",
        "status": "measured",
        "evidence": "director cycles 1-4 accepted; B2A-02 PASS 4/4 with computed tables; defended its seat in bake-off 01 (2026-11-13): challenger Qwen3-4B failed B at 0/4",
    },
    "brain_claude_ian_ila": {
        "kind": "brain", "name": "Claude-class (Ian / ila)",
        "role": "development engine + program direction",
        "status": "active",
        "evidence": "ACE Omega phases 1-2 and stages A-L executed and checkpointed",
    },
    "brain_antigravity_gemini": {
        "kind": "brain", "name": "Antigravity bench (Gemini)",
        "role": "external operator bench for bounded tasks",
        "status": "quota_exhausted_until_approx_2026-11-18",
        "evidence": "Task 01 stopped clean with no deliverable (individual quota reached)",
    },
    # Capabilities — only ones with measured evidence.
    "cap_official_path_repair": {
        "kind": "capability", "name": "Official-path code repair",
        "role": "repair a fixture through LocalRepoWorkflow + sandbox v2 + attested local model",
        "status": "locally_verified_x2",
        "evidence": "harga.py (OMEGA-03) and akun.py SQL-injection fixture (Uji Keamanan-01), sealed evaluators",
    },
    "cap_procurement_director": {
        "kind": "capability", "name": "Procurement decision under preregistered criteria",
        "role": "director decides over attested dossiers; harness computes comparisons",
        "status": "measured_pass",
        "evidence": "B2A-02 decision_score 4/4, audit CLEAN (B2A-01 was 3/4 without computed tables)",
    },
    "cap_operator_discovery": {
        "kind": "capability", "name": "Operator discovery with composition",
        "role": "discover and admit repair operators, incl. composed chains",
        "status": "measured",
        "evidence": "operator_discovery_v4: chains 3/6 where pairs 0/6; singles transfer 15",
    },
    "cap_sealed_evaluation": {
        "kind": "capability", "name": "Preregistered sealed evaluation design",
        "role": "OMEGA-06 kernel: preregistration, split custody, hash-chained ledger, instruments",
        "status": "measured_infrastructure",
        "evidence": "pilots v1/v2, B2A-01/02, G1 instrument all ran under kernel audit CLEAN",
    },
    "cap_serial_fiction": {
        "kind": "capability", "name": "Serial fiction production",
        "role": "writer brain + editorial engine at near-zero marginal cost",
        "status": "unvalidated_as_product",
        "evidence": "named the first product line in the two-sided business study; no market validation yet",
    },
}

ENTRY_STATUSES = ("design", "proposed", "active", "measured", "dropped")
FOUNDER = "FOUNDER"


def _entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True).encode()).hexdigest()


class OpportunityRegister:
    """Append-only, hash-chained opportunity register."""

    def __init__(self, path):
        self.path = Path(path)

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in
                self.path.read_text().splitlines() if line.strip()]

    def verify_chain(self, entries: list[dict] | None = None) -> bool:
        entries = self.entries() if entries is None else entries
        prev = ""
        for i, entry in enumerate(entries, start=1):
            if entry.get("seq") != i or entry.get("prev_hash") != prev:
                return False
            if _entry_hash(entry) != entry.get("entry_hash"):
                return False
            prev = entry["entry_hash"]
        return True

    def append(self, *, title: str, combination: list[str],
               rationale: str, origin: str, status: str,
               fences: list[str] | None = None) -> dict:
        if status not in ENTRY_STATUSES:
            raise ValueError(f"unknown entry status: {status}")
        if origin != FOUNDER and origin not in ASSETS:
            raise ValueError(f"origin is not a registered brain: {origin}")
        if origin in ASSETS and ASSETS[origin]["kind"] != "brain":
            raise ValueError(f"origin asset is not a brain: {origin}")
        if len(combination) < 2:
            raise ValueError("an opportunity combines at least two assets")
        unknown = [a for a in combination if a not in ASSETS]
        if unknown:
            raise ValueError(f"unregistered assets in combination: {unknown}")
        existing = self.entries()
        if not self.verify_chain(existing):
            raise ValueError("register chain broken; refusing to append")
        entry = {
            "seq": len(existing) + 1,
            "title": title,
            "combination": sorted(combination),
            "rationale": rationale,
            "origin": origin,
            "status": status,
            "fences": list(fences or []),
            "prev_hash": existing[-1]["entry_hash"] if existing else "",
        }
        entry["entry_hash"] = _entry_hash(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry


def seed_founder_flywheel(register: OpportunityRegister) -> dict | None:
    """Entry #1 (Addendum 38 §2): the KBM-story -> Threads-
    promotion flywheel. Origin FOUNDER — the owner
    synthesized it; the register records that plainly.
    Idempotent: returns None when already recorded."""
    combo = sorted(["venue_kbm", "venue_threads"])
    for entry in register.entries():
        if entry["combination"] == combo and entry["origin"] == FOUNDER:
            return None
    return register.append(
        title="Flywheel: KBM serial story promoted on Threads",
        combination=combo,
        rationale="A story published on KBM (the fiction storefront) "
                  "is promoted on Threads (the promotion channel): "
                  "one business flywheel across two registered venues.",
        origin=FOUNDER,
        status="design",
        fences=[
            "owner privacy rule: pilot content is separate work, never discussion-room material",
            "KBM exclusivity: promotion is announcement/teaser + link, never chapter republication",
            "no separate product story exists yet",
        ])


def scan_opportunities(assets: dict | None = None,
                       entries: list[dict] | None = None) -> list[dict]:
    """Deterministic scan for unexploited combinations.

    Candidate pairs: venue x capability, venue x brain,
    venue x venue — where the pair is not already a
    register entry. Each candidate carries a factual
    rationale built from the assets' own registry fields.
    Candidates are proposals to judge, not entries; the
    scan claims no creativity."""
    assets = ASSETS if assets is None else assets
    entries = [] if entries is None else entries
    registered = {tuple(e["combination"]) for e in entries}
    venues = sorted(a for a, v in assets.items() if v["kind"] == "venue")
    others = sorted(a for a, v in assets.items() if v["kind"] != "venue")
    candidates = []
    for venue in venues:
        for other in others + venues:
            if other == venue:
                continue
            combo = tuple(sorted([venue, other]))
            if combo in registered or \
                    any(c["combination"] == list(combo) for c in candidates):
                continue
            a, b = assets[venue], assets[other]
            candidates.append({
                "combination": list(combo),
                "rationale": (
                    f"{a['name']} ({a['role']}; status {a['status']}) x "
                    f"{b['name']} ({b['role']}; status {b['status']}) — "
                    f"combination not yet in the register."),
            })
    return candidates


def build_scan_packet(candidates: list[dict]) -> dict:
    """Shape scan candidates as a director-cycle fact
    packet, so a future director cycle can judge them
    under citation discipline (facts carry stable ids)."""
    facts = []
    for i, cand in enumerate(candidates, start=1):
        facts.append({
            "id": f"candidate-{i}",
            "text": (f"combination {' + '.join(cand['combination'])}: "
                     f"{cand['rationale']}"),
        })
    return {"facts": facts, "candidate_count": len(candidates)}


def origin_share(entries: list[dict]) -> dict:
    """The doctrine's long-run measure: entry counts and
    shares by origin; ACE-side synthesis = any registered
    brain (the founder is not ACE-side)."""
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["origin"]] = counts.get(entry["origin"], 0) + 1
    total = len(entries)
    ace_side = sum(n for origin, n in counts.items() if origin != FOUNDER)
    return {
        "total": total,
        "by_origin": counts,
        "ace_side_share": (ace_side / total) if total else 0.0,
    }
