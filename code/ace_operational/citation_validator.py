"""Bake-off 02 — the hardened citation validator (design §2, V-1…V-6).

Why this exists: in bake-off 01 the citation check did its job — it
caught a fabricated fact id (``nimbus-gate``) in the candidate's B2A
reply — but the rejection survived as one exception string,
``"decision 0 cites facts not in the packet: ['nimbus-gate']"``, and
the fail-closed whole-reply rule destroyed every other, perfectly
scorable proposal in the same reply. That was sufficient to decide
bake-off 01; it is not sufficient evidence to audit the decision
later, compare rejection shapes across candidates, or distinguish
one fabricated id from ten. This module is the hardened validator
the bake-off 02 design specifies:

* **V-1 Per-fact-id granularity.** Every cited id of every proposal
  is validated independently and enumerated in the report with a
  status from the closed set {``known``, ``unknown``}. A proposal is
  rejected iff it cites an ``unknown`` id (or cites nothing);
  proposals whose citations are all ``known`` survive. Only the
  offending proposals are rejected — never the whole reply.
  (Design §2 kept whole-reply rejection and hardened only the
  record; this build follows the stage brief's stronger semantics.
  The report therefore also carries ``legacy_whole_reply_rejected``
  — what the bake-off 01 rule would have decided — so the two
  semantics stay comparable and the bake-off 01 equivalence, that
  ``nimbus-gate`` is ``unknown`` under any granularity, is checkable
  from the record itself.)
* **V-2 Structured rejection objects.** Rejections are data under
  the versioned schema ``ace.citation_rejection.v1`` — one object
  per offending fact id — not exception strings. Exceptions remain
  only for control flow (binding refusal, malformed input).
* **V-3 Packet binding.** Every validation is bound to the exact
  packet the candidate saw: the report and every rejection object
  carry the packet digest and the digest of its citable-id set, and
  a caller that pins an expected packet digest gets a hard refusal
  (:class:`PacketBindingError`) on mismatch — "not in the packet"
  is always checkable against that exact packet, never against a
  later reconstruction of it.
* **V-4 Validator identity pinned.** The validator exposes its
  name, version, schema version, rule-set digest and source-code
  digest. A preregistration pins these; every rejection record
  carries them, so a rejection is attributable to exactly one
  validator build.
* **V-5 Chained rejection entries.** :class:`RejectionLedger` is an
  append-only, hash-chained ledger in the experiment kernel's
  style (``seq`` / ``prev`` / ``hash`` over the canonical record).
  Editing a sealed entry breaks the chain, and ``verify()`` names
  the break — an audit can prove no rejection was altered.
* **V-6 Deterministic replay.** Given the same packet, the same
  reply and the same timestamp, validation replays byte-identically
  (canonical JSON, sorted id sets, no wall-clock or ordering
  dependence). The timestamp is the single sanctioned exception,
  and it is injectable precisely so replay can pin it.

Non-goals (design §2, unchanged): what counts as a citation does
not change — a proposal cites through its ``based_on`` list (the
director-loop surface) or its ``cites`` list (the B2A decision
surface). No bar, packet or scoring rule lives here.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable

VALIDATOR_NAME = "ace.citation_validator"
VALIDATOR_VERSION = "1.0.0"
REJECTION_SCHEMA = "ace.citation_rejection.v1"
REPORT_SCHEMA = "ace.citation_validation.v1"

REASON_UNKNOWN_FACT_ID = "unknown_fact_id"
REASON_NO_CITATIONS = "no_citations"
STATUS_KNOWN = "known"
STATUS_UNKNOWN = "unknown"

# The declarative rule set. Its canonical digest (V-4) is part of
# the validator's pinned identity: changing a rule changes the
# digest, which is exactly the fence a preregistration relies on.
RULES: tuple[dict[str, str], ...] = (
    {"rule": REASON_UNKNOWN_FACT_ID, "applies_to": "per_fact_id",
     "effect": "reject_proposal"},
    {"rule": REASON_NO_CITATIONS, "applies_to": "per_proposal",
     "effect": "reject_proposal"},
    {"rule": "packet_binding", "applies_to": "per_validation",
     "effect": "refuse_validation"},
)

# Citation-bearing fields, in precedence order: the director loop's
# ``based_on`` first, then the B2A decision surface's ``cites``.
CITATION_FIELDS = ("based_on", "cites")


class CitationValidatorError(Exception):
    pass


class PacketBindingError(CitationValidatorError):
    """The packet offered for validation is not the pinned packet."""


# ---------------------------------------------------------------------------
# Digests (canonical form mirrors experiment_kernel._canonical/_digest)
# ---------------------------------------------------------------------------

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _digest(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# V-4 — validator identity
# ---------------------------------------------------------------------------

def ruleset_digest() -> str:
    """Digest of the declarative rule set (V-4)."""
    return _digest(list(RULES))


def code_digest() -> str:
    """SHA-256 of this module's own source bytes (V-4)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def validator_identity() -> dict[str, str]:
    """The identity a preregistration pins for this validator build."""
    return {"name": VALIDATOR_NAME,
            "version": VALIDATOR_VERSION,
            "schema": REJECTION_SCHEMA,
            "ruleset_digest": ruleset_digest(),
            "code_digest": code_digest()}


# ---------------------------------------------------------------------------
# V-3 — packet binding
# ---------------------------------------------------------------------------

def packet_fact_ids(packet: Any) -> list[str]:
    """The citable fact ids a packet offers, sorted and deduplicated.

    Accepts an explicit ``fact_ids`` list, a director-loop
    observation packet (gap ids ∪ result ids ∪ gate names — the
    same derivation ``director_loop.parse_proposals`` uses), or a
    bare iterable of ids.
    """
    if isinstance(packet, dict):
        if "fact_ids" in packet:
            return sorted({str(i) for i in packet["fact_ids"]})
        ids = ({str(g.get("id")) for g in packet.get("open_gaps", [])}
               | {str(r.get("id")) for r in packet.get("recent_results", [])}
               | {str(k) for k in packet.get("gates", {})})
        return sorted(ids)
    if isinstance(packet, Iterable):
        return sorted({str(i) for i in packet})
    raise CitationValidatorError(
        f"packet must be a mapping or an iterable of fact ids, "
        f"got {type(packet).__name__}")


def packet_digest(packet: Any) -> str:
    """Digest of the exact packet object (V-3)."""
    return _digest(packet)


def citable_id_set_digest(fact_ids: Iterable[str]) -> str:
    """Digest of the citable-id set alone (V-3)."""
    return _digest(sorted({str(i) for i in fact_ids}))


# ---------------------------------------------------------------------------
# V-1 / V-2 — per-id validation and structured rejections
# ---------------------------------------------------------------------------

def _citations_of(proposal: Any, index: int) -> list[str]:
    if not isinstance(proposal, dict):
        raise CitationValidatorError(f"proposal {index} is not an object")
    for field in CITATION_FIELDS:
        if field in proposal:
            cites = proposal[field]
            if not isinstance(cites, list):
                raise CitationValidatorError(
                    f"proposal {index} field {field!r} is not a list")
            return [str(c) for c in cites]
    return []


def _proposal_id(proposal: dict[str, Any]) -> str | None:
    for key in ("id", "title"):
        value = proposal.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _rejection(*, experiment_id: str, proposal_index: int,
               proposal_id: str | None, fact_id: str | None,
               reason: str, pkt_digest: str, id_set_digest: str,
               identity: dict[str, str], timestamp: float) -> dict[str, Any]:
    return {"schema": REJECTION_SCHEMA,
            "experiment_id": experiment_id,
            "proposal_index": proposal_index,
            "proposal_id": proposal_id,
            "fact_id": fact_id,
            "status": STATUS_UNKNOWN if fact_id is not None else None,
            "reason": reason,
            "packet_digest": pkt_digest,
            "citable_id_set_digest": id_set_digest,
            "validator": identity,
            "timestamp": timestamp}


def validate_reply(*, packet: Any, proposals: list[dict[str, Any]],
                   experiment_id: str = "",
                   expected_packet_digest: str | None = None,
                   timestamp: float | None = None) -> dict[str, Any]:
    """Validate every citation of every proposal in a reply (V-1…V-4, V-6).

    Returns the validation report (schema ``ace.citation_validation.v1``):
    the full per-id citation surface, one structured rejection object
    per offending fact id, and the per-proposal verdicts. Proposals
    whose citations are all ``known`` are accepted; only proposals
    citing an ``unknown`` id (or nothing) are rejected.

    Raises :class:`PacketBindingError` if ``expected_packet_digest``
    is pinned and the offered packet is not that packet.
    """
    if timestamp is None:
        timestamp = time.time()
    pkt_digest = packet_digest(packet)
    if (expected_packet_digest is not None
            and expected_packet_digest != pkt_digest):
        raise PacketBindingError(
            f"packet digest {pkt_digest} does not match the pinned "
            f"packet digest {expected_packet_digest}; validation refused")
    fact_ids = packet_fact_ids(packet)
    known = set(fact_ids)
    id_set_digest = citable_id_set_digest(fact_ids)
    identity = validator_identity()

    surface: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    accepted: list[int] = []
    rejected: list[int] = []
    for i, proposal in enumerate(proposals):
        cites = _citations_of(proposal, i)
        pid = _proposal_id(proposal)
        entries = [{"fact_id": c,
                    "status": STATUS_KNOWN if c in known else STATUS_UNKNOWN}
                   for c in cites]
        surface.append({"proposal_index": i, "proposal_id": pid,
                        "citations": entries})
        offending = [e["fact_id"] for e in entries
                     if e["status"] == STATUS_UNKNOWN]
        if not cites:
            rejections.append(_rejection(
                experiment_id=experiment_id, proposal_index=i,
                proposal_id=pid, fact_id=None,
                reason=REASON_NO_CITATIONS, pkt_digest=pkt_digest,
                id_set_digest=id_set_digest, identity=identity,
                timestamp=timestamp))
            rejected.append(i)
        elif offending:
            for fact_id in offending:
                rejections.append(_rejection(
                    experiment_id=experiment_id, proposal_index=i,
                    proposal_id=pid, fact_id=fact_id,
                    reason=REASON_UNKNOWN_FACT_ID,
                    pkt_digest=pkt_digest, id_set_digest=id_set_digest,
                    identity=identity, timestamp=timestamp))
            rejected.append(i)
        else:
            accepted.append(i)

    return {"schema": REPORT_SCHEMA,
            "experiment_id": experiment_id,
            "validator": identity,
            "packet_digest": pkt_digest,
            "citable_id_set_digest": id_set_digest,
            "citable_fact_ids": fact_ids,
            "citation_surface": surface,
            "rejections": rejections,
            "accepted_proposals": accepted,
            "rejected_proposals": rejected,
            "legacy_whole_reply_rejected": bool(rejected),
            "timestamp": timestamp}


def canonical_report_bytes(report: dict[str, Any]) -> bytes:
    """The report's canonical bytes — the replay comparison unit (V-6)."""
    return _canonical(report).encode("utf-8")


# ---------------------------------------------------------------------------
# V-5 — append-only, hash-chained rejection ledger
# ---------------------------------------------------------------------------

class RejectionLedger:
    """Sealed rejection entries, chained like the kernel's ledger.

    Each entry is ``{seq, prev, record, hash}`` with
    ``hash = sha256(canonical({prev, record}))``. Appending is the
    only mutation the class offers; :meth:`verify` re-walks the
    chain and names the first break, so a silently edited rejection
    is detectable at audit.
    """

    def __init__(self, entries: list[dict[str, Any]] | None = None):
        self._entries: list[dict[str, Any]] = list(entries or [])

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        prev = self._entries[-1]["hash"] if self._entries else "GENESIS"
        entry = {"seq": len(self._entries) + 1, "prev": prev,
                 "record": record}
        entry["hash"] = _digest({"prev": prev, "record": record})
        self._entries.append(entry)
        return entry

    def append_report(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        """Seal every rejection object of a validation report, in order."""
        return [self.append(r) for r in report["rejections"]]

    @property
    def entries(self) -> list[dict[str, Any]]:
        return self._entries

    def verify(self) -> dict[str, Any]:
        prev = "GENESIS"
        verified = 0
        for entry in self._entries:
            if entry.get("seq") != verified + 1 or entry.get("prev") != prev:
                return {"status": "BROKEN", "entries_verified": verified,
                        "chain_break_at": verified + 1}
            if entry.get("hash") != _digest(
                    {"prev": prev, "record": entry.get("record")}):
                return {"status": "BROKEN", "entries_verified": verified,
                        "chain_break_at": verified + 1}
            prev = entry["hash"]
            verified += 1
        return {"status": "CLEAN", "entries_verified": verified,
                "chain_break_at": None}
