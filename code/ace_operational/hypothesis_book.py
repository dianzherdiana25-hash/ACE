"""Buku registri hipotesis terstruktur dengan transisi status ketat (AG94).

Menyediakan pustaka ``HypothesisBook`` di atas ``HypothesisStoreProtocol`` (tanpa
mengimpor engine) untuk mendaftarkan hipotesis terstruktur (``cause``,
``measurable_prediction``, ``falsification_condition``, ``confidence``) dan
mengawal transisi status ketat:

``terdaftar`` -> ``diuji`` -> (``didukung`` | ``gugur`` | ``belum_tentu``)

Semua lompatan status liar atau finalisasi verdict tanpa catatan eksperimen
ditolak dengan ``HypothesisBookError``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol


SCHEMA = "ace.hypothesis-book.v1"
VALID_STATUSES = frozenset({"terdaftar", "diuji", "didukung", "gugur", "belum_tentu"})
OUTCOME_STATUSES = frozenset({"didukung", "gugur", "belum_tentu"})
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "terdaftar": frozenset({"diuji"}),
    "diuji": frozenset({"didukung", "gugur", "belum_tentu"}),
    "belum_tentu": frozenset({"diuji"}),
    "didukung": frozenset(),
    "gugur": frozenset(),
}


class HypothesisBookError(ValueError):
    """Galat validasi skema atau transisi status hipotesis yang tidak sah."""


class HypothesisStoreProtocol(Protocol):
    """Protokol penyimpan hipotesis agar backend dapat ditukar tanpa coupling engine."""

    def save_hypothesis(self, record: Mapping[str, Any]) -> None: ...

    def get_hypothesis(self, hypothesis_id: str) -> dict[str, Any] | None: ...

    def list_hypotheses(self) -> list[dict[str, Any]]: ...


class InMemoryHypothesisStore:
    """Implementasi bawaan ``HypothesisStoreProtocol`` di memori."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def save_hypothesis(self, record: Mapping[str, Any]) -> None:
        hid = str(record["hypothesis_id"])
        self._items[hid] = dict(record)

    def get_hypothesis(self, hypothesis_id: str) -> dict[str, Any] | None:
        item = self._items.get(hypothesis_id)
        return dict(item) if item is not None else None

    def list_hypotheses(self) -> list[dict[str, Any]]:
        return [dict(self._items[k]) for k in sorted(self._items.keys())]


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    observed_outcome: str
    evidence_ref: str
    completed_at: str | None = None

    def validate(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise HypothesisBookError("experiment_id pada catatan eksperimen wajib tidak kosong.")
        if not isinstance(self.observed_outcome, str) or not self.observed_outcome.strip():
            raise HypothesisBookError("observed_outcome pada catatan eksperimen wajib tidak kosong.")
        if not isinstance(self.evidence_ref, str) or not self.evidence_ref.strip():
            raise HypothesisBookError("evidence_ref pada catatan eksperimen wajib tidak kosong.")


def _require_non_empty(val: Any, name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise HypothesisBookError(f"Field '{name}' wajib berupa string tidak kosong.")
    return val.strip()


def _validate_confidence(val: Any) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise HypothesisBookError(f"confidence wajib angka di [0.0, 1.0], didapat {val!r}.")
    fval = float(val)
    if not (0.0 <= fval <= 1.0):
        raise HypothesisBookError(f"confidence di luar rentang [0.0, 1.0]: {fval!r}.")
    return round(fval, 6)


class HypothesisBook:
    """Registri hipotesis di atas ``HypothesisStoreProtocol`` dengan mesin keadaan ketat."""

    def __init__(self, store: HypothesisStoreProtocol | None = None) -> None:
        self._store: HypothesisStoreProtocol = store if store is not None else InMemoryHypothesisStore()

    def register(
        self,
        hypothesis_id: str,
        *,
        cause: str,
        measurable_prediction: str,
        falsification_condition: str,
        confidence: float,
        domain: str = "umum",
    ) -> dict[str, Any]:
        hid = _require_non_empty(hypothesis_id, "hypothesis_id")
        if self._store.get_hypothesis(hid) is not None:
            raise HypothesisBookError(f"hypothesis_id sudah terdaftar: {hid!r}.")

        record: dict[str, Any] = {
            "hypothesis_id": hid,
            "domain": _require_non_empty(domain, "domain"),
            "cause": _require_non_empty(cause, "cause"),
            "measurable_prediction": _require_non_empty(measurable_prediction, "measurable_prediction"),
            "falsification_condition": _require_non_empty(falsification_condition, "falsification_condition"),
            "confidence": _validate_confidence(confidence),
            "status": "terdaftar",
            "active_experiment_id": None,
            "experiments": [],
            "history": [{"from": None, "to": "terdaftar", "experiment_id": None}],
        }
        self._store.save_hypothesis(record)
        return record

    def start_test(self, hypothesis_id: str, *, experiment_id: str) -> dict[str, Any]:
        """Transisi ``terdaftar`` (atau ``belum_tentu``) -> ``diuji`` dengan ID eksperimen."""
        hid = _require_non_empty(hypothesis_id, "hypothesis_id")
        eid = _require_non_empty(experiment_id, "experiment_id")
        record = self._store.get_hypothesis(hid)
        if record is None:
            raise HypothesisBookError(f"Hipotesis {hid!r} tidak ditemukan.")

        current = str(record["status"])
        if "diuji" not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise HypothesisBookError(
                f"Transisi {current!r} -> 'diuji' ditolak untuk hipotesis {hid!r}."
            )

        updated = dict(record)
        updated["status"] = "diuji"
        updated["active_experiment_id"] = eid
        updated["history"] = list(record["history"]) + [
            {"from": current, "to": "diuji", "experiment_id": eid}
        ]
        self._store.save_hypothesis(updated)
        return updated

    def record_outcome(
        self,
        hypothesis_id: str,
        *,
        verdict: str,
        experiment: ExperimentRecord | Mapping[str, Any] | None,
        updated_confidence: float | None = None,
    ) -> dict[str, Any]:
        """Transisi ``diuji`` -> ``didukung`` | ``gugur`` | ``belum_tentu`` wajib disertai catatan eksperimen."""
        hid = _require_non_empty(hypothesis_id, "hypothesis_id")
        if verdict not in OUTCOME_STATUSES:
            raise HypothesisBookError(
                f"Verdict tidak sah: {verdict!r}; pilih dari {sorted(OUTCOME_STATUSES)}."
            )
        record = self._store.get_hypothesis(hid)
        if record is None:
            raise HypothesisBookError(f"Hipotesis {hid!r} tidak ditemukan.")

        current = str(record["status"])
        if verdict not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise HypothesisBookError(
                f"Transisi {current!r} -> {verdict!r} ditolak: hipotesis {hid!r} harus melewati 'diuji'."
            )

        if experiment is None:
            raise HypothesisBookError(
                f"Verdict {verdict!r} untuk hipotesis {hid!r} wajib menyertakan catatan eksperimen."
            )
        if isinstance(experiment, ExperimentRecord):
            exp_obj = experiment
        elif isinstance(experiment, Mapping):
            exp_obj = ExperimentRecord(
                experiment_id=str(experiment.get("experiment_id", "")),
                observed_outcome=str(experiment.get("observed_outcome", "")),
                evidence_ref=str(experiment.get("evidence_ref", "")),
                completed_at=str(experiment["completed_at"]) if experiment.get("completed_at") else None,
            )
        else:
            raise HypothesisBookError("Format catatan eksperimen tidak sah.")
        exp_obj.validate()

        active_eid = record.get("active_experiment_id")
        if active_eid is not None and exp_obj.experiment_id != active_eid:
            raise HypothesisBookError(
                f"experiment_id ({exp_obj.experiment_id!r}) tidak cocok dengan pengujian aktif ({active_eid!r})."
            )

        updated = dict(record)
        updated["status"] = verdict
        updated["active_experiment_id"] = None
        if updated_confidence is not None:
            updated["confidence"] = _validate_confidence(updated_confidence)
        updated["experiments"] = list(record["experiments"]) + [asdict(exp_obj)]
        updated["history"] = list(record["history"]) + [
            {"from": current, "to": verdict, "experiment_id": exp_obj.experiment_id}
        ]
        self._store.save_hypothesis(updated)
        return updated

    def transition(
        self,
        hypothesis_id: str,
        *,
        target_status: str,
        experiment_id: str | None = None,
        experiment: ExperimentRecord | Mapping[str, Any] | None = None,
        updated_confidence: float | None = None,
    ) -> dict[str, Any]:
        """Gerbang transisi tunggal yang memaksa aturan transisi dan syarat eksperimen."""
        if target_status not in VALID_STATUSES:
            raise HypothesisBookError(f"Status tujuan tidak sah: {target_status!r}.")
        if target_status == "terdaftar":
            raise HypothesisBookError("Tidak dapat bertransisi kembali ke 'terdaftar'.")
        if target_status == "diuji":
            if experiment_id is None:
                raise HypothesisBookError("Transisi ke 'diuji' wajib menyertakan experiment_id.")
            return self.start_test(hypothesis_id, experiment_id=experiment_id)
        return self.record_outcome(
            hypothesis_id,
            verdict=target_status,
            experiment=experiment,
            updated_confidence=updated_confidence,
        )

    def get(self, hypothesis_id: str) -> dict[str, Any] | None:
        return self._store.get_hypothesis(hypothesis_id)

    def list_all(self, *, status: str | None = None) -> list[dict[str, Any]]:
        items = self._store.list_hypotheses()
        if status is not None:
            items = [row for row in items if row.get("status") == status]
        return items

    def export_book(self) -> dict[str, Any]:
        items = self.list_all()
        counts = {s: 0 for s in sorted(VALID_STATUSES)}
        for row in items:
            st = str(row.get("status"))
            if st in counts:
                counts[st] += 1
        return {
            "schema": SCHEMA,
            "count": len(items),
            "by_status": counts,
            "hypotheses": items,
        }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "ExperimentRecord",
    "HypothesisBook",
    "HypothesisBookError",
    "HypothesisStoreProtocol",
    "InMemoryHypothesisStore",
    "SCHEMA",
    "VALID_STATUSES",
]
