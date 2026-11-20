"""Format proposal evolusi & mesin keadaan antrean ratifikasi murni (AG98).

Memvalidasi proposal evolusi atas semua komponen wajib
(``benefit_hypothesis``, ``measurement_method``, ``cost``, ``risk``,
``fact_anchors``) sebelum boleh masuk antrean ratifikasi, serta menegakkan
transisi status ketat:

``diajukan`` -> ``ditantang`` -> ``lolos`` / ``ditolak`` -> ``terjadwal``

Proposal yang cacat (mis. tidak memiliki ``measurement_method`` atau bertaut ke
jangkar fakta menggantung) berhenti pada validator dan tidak pernah memasuki
antrean. Modul pustaka murni ini tidak mengimpor engine.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ace_operational.memory_anchor import VerifiedReferences, check_anchors


SCHEMA = "ace.evolution-proposal.v1"
QUEUE_SCHEMA = "ace.evolution-ratification-queue.v1"
VALID_RISK_LEVELS = frozenset({"low", "medium", "high"})
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "diajukan": frozenset({"ditantang"}),
    "ditantang": frozenset({"lolos", "ditolak"}),
    "lolos": frozenset({"terjadwal"}),
    "ditolak": frozenset(),
    "terjadwal": frozenset(),
}


class ProposalValidationError(ValueError):
    """Galat skema/jangkar proposal sebelum memasuki antrean ratifikasi."""


class RatificationTransitionError(ValueError):
    """Galat transisi status yang tidak sah pada antrean ratifikasi."""


def _require_non_empty_str(val: Any, field: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise ProposalValidationError(f"Field '{field}' wajib berupa string tidak kosong.")
    return val.strip()


def validate_evolution_proposal(
    proposal: Mapping[str, Any],
    *,
    anchor_store: VerifiedReferences | None = None,
) -> dict[str, Any]:
    """Validasi skema lengkap proposal evolusi (mengembalikan salinan ternormalisasi)."""
    if not isinstance(proposal, Mapping):
        raise ProposalValidationError("Proposal wajib berupa objek.")

    proposal_id = _require_non_empty_str(proposal.get("proposal_id"), "proposal_id")
    benefit_hypothesis = _require_non_empty_str(
        proposal.get("benefit_hypothesis"),
        "benefit_hypothesis",
    )
    measurement_method = _require_non_empty_str(
        proposal.get("measurement_method"),
        "measurement_method",
    )

    raw_cost = proposal.get("cost")
    if isinstance(raw_cost, Mapping):
        if not raw_cost:
            raise ProposalValidationError("Field 'cost' tidak boleh objek kosong.")
        cost: dict[str, Any] | str | float = dict(raw_cost)
    elif isinstance(raw_cost, (int, float)) and not isinstance(raw_cost, bool) and raw_cost >= 0:
        cost = raw_cost
    elif isinstance(raw_cost, str) and raw_cost.strip():
        cost = raw_cost.strip()
    else:
        raise ProposalValidationError("Field 'cost' wajib terisi dan sah.")

    raw_risk = proposal.get("risk")
    if isinstance(raw_risk, Mapping):
        level = str(raw_risk.get("level") or "").lower()
        mitigation = str(raw_risk.get("mitigation") or "").strip()
        if level not in VALID_RISK_LEVELS:
            raise ProposalValidationError(
                f"risk.level tidak valid {level!r}; pilih dari {sorted(VALID_RISK_LEVELS)}."
            )
        if not mitigation:
            raise ProposalValidationError("risk.mitigation wajib diisi.")
        risk: dict[str, Any] | str = dict(raw_risk)
    elif isinstance(raw_risk, str) and raw_risk.strip():
        risk = raw_risk.strip()
    else:
        raise ProposalValidationError("Field 'risk' wajib terisi.")

    raw_anchors = proposal.get("fact_anchors")
    if (
        not isinstance(raw_anchors, Sequence)
        or isinstance(raw_anchors, (str, bytes))
        or len(raw_anchors) == 0
    ):
        raise ProposalValidationError("Field 'fact_anchors' wajib berupa daftar minimal 1 referensi.")
    try:
        anchors = [ _require_non_empty_str(a, "fact_anchors[]") for a in raw_anchors ]
    except ProposalValidationError:
        raise ProposalValidationError("Semua elemen 'fact_anchors' wajib string tidak kosong.")

    anchor_report: dict[str, Any] | None = None
    if anchor_store is not None:
        anchor_report = check_anchors(anchors, anchor_store)
        if anchor_report["status"] != "anchored":
            raise ProposalValidationError(
                f"Proposal {proposal_id!r} memiliki fact_anchors belum tertambat penuh: {anchor_report['status']}."
            )

    return {
        "schema": SCHEMA,
        "proposal_id": proposal_id,
        "title": str(proposal.get("title") or proposal_id).strip(),
        "benefit_hypothesis": benefit_hypothesis,
        "measurement_method": measurement_method,
        "cost": cost,
        "risk": risk,
        "fact_anchors": anchors,
        "anchor_verification": anchor_report,
    }


class RatificationQueue:
    """Mesin keadaan antrean ratifikasi murni untuk proposal evolusi tervalidasi."""

    def __init__(self, *, anchor_store: VerifiedReferences | None = None) -> None:
        self._anchor_store = anchor_store
        self._items: dict[str, dict[str, Any]] = {}

    def submit(self, proposal: Mapping[str, Any]) -> dict[str, Any]:
        """Validasi proposal terlebih dahulu; hanya masuk antrean jika lolos validator."""
        validated = validate_evolution_proposal(proposal, anchor_store=self._anchor_store)
        pid = validated["proposal_id"]
        if pid in self._items:
            raise ProposalValidationError(f"proposal_id duplikat di antrean: {pid!r}.")
        entry = {
            "proposal_id": pid,
            "status": "diajukan",
            "proposal": validated,
            "challenge_notes": None,
            "decision_rationale": None,
            "schedule_slot": None,
            "history": [{"from": None, "to": "diajukan"}],
        }
        self._items[pid] = entry
        return dict(entry)

    def _get_entry(self, proposal_id: str) -> dict[str, Any]:
        if proposal_id not in self._items:
            raise RatificationTransitionError(f"Proposal {proposal_id!r} tidak ditemukan di antrean.")
        return self._items[proposal_id]

    def _assert_transition(self, current: str, target: str, proposal_id: str) -> None:
        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        if target not in allowed:
            raise RatificationTransitionError(
                f"Transisi tidak sah untuk {proposal_id!r}: {current!r} -> {target!r} (diizinkan: {sorted(allowed)})."
            )

    def challenge(self, proposal_id: str, *, notes: str) -> dict[str, Any]:
        entry = self._get_entry(proposal_id)
        self._assert_transition(entry["status"], "ditantang", proposal_id)
        if not isinstance(notes, str) or not notes.strip():
            raise RatificationTransitionError("Tantangan wajib menyertakan catatan evaluasi ('notes').")
        prev = entry["status"]
        entry["status"] = "ditantang"
        entry["challenge_notes"] = notes.strip()
        entry["history"].append({"from": prev, "to": "ditantang"})
        return dict(entry)

    def decide(self, proposal_id: str, *, verdict: str, rationale: str) -> dict[str, Any]:
        if verdict not in {"lolos", "ditolak"}:
            raise RatificationTransitionError(f"Verdict wajib 'lolos' atau 'ditolak', didapat {verdict!r}.")
        entry = self._get_entry(proposal_id)
        self._assert_transition(entry["status"], verdict, proposal_id)
        if not isinstance(rationale, str) or not rationale.strip():
            raise RatificationTransitionError("Keputusan wajib menyertakan rationale tidak kosong.")
        prev = entry["status"]
        entry["status"] = verdict
        entry["decision_rationale"] = rationale.strip()
        entry["history"].append({"from": prev, "to": verdict})
        return dict(entry)

    def schedule(self, proposal_id: str, *, slot: str) -> dict[str, Any]:
        entry = self._get_entry(proposal_id)
        self._assert_transition(entry["status"], "terjadwal", proposal_id)
        if not isinstance(slot, str) or not slot.strip():
            raise RatificationTransitionError("Penjadwalan wajib menyertakan slot eksekusi.")
        prev = entry["status"]
        entry["status"] = "terjadwal"
        entry["schedule_slot"] = slot.strip()
        entry["history"].append({"from": prev, "to": "terjadwal"})
        return dict(entry)

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        item = self._items.get(proposal_id)
        return dict(item) if item is not None else None

    def list_entries(self, *, status: str | None = None) -> list[dict[str, Any]]:
        rows = [dict(v) for k, v in sorted(self._items.items())]
        if status is not None:
            rows = [r for r in rows if r["status"] == status]
        return rows

    def export_queue(self) -> dict[str, Any]:
        rows = self.list_entries()
        return {
            "schema": QUEUE_SCHEMA,
            "count": len(rows),
            "entries": rows,
        }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "ProposalValidationError",
    "QUEUE_SCHEMA",
    "RatificationQueue",
    "RatificationTransitionError",
    "SCHEMA",
    "validate_evolution_proposal",
]
