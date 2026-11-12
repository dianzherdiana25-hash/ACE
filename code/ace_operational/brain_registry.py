"""Brain registry — multi-brain sovereignty (Phase 2, stage G).

Owner doctrine (Addendum 27): ACE must not depend on a single
brain. Brains are replaceable organs; ACE's identity lives in its
constitution, ledger, and memory. This registry is the bookkeeping
half of that doctrine:

- every brain ACE may use is a named record (local models today;
  external services are recorded as *declared-unavailable* until a
  real, owner-approved connection exists — the registry never
  pretends a connection it does not have);
- a brain can be **dismissed**: an explicit, recorded act after
  which the router refuses to route inference to it, fail-closed —
  no silent substitution, no quiet resurrection;
- reinstatement is likewise an explicit, recorded act;
- every transition lands in an append-only event log inside the
  registry file, so the drill (and any later audit) can replay who
  was dismissed, when, and why.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

REGISTRY_SCHEMA = "ace.brain_registry.v1"
BRAIN_STATUSES = ("active", "dismissed", "declared-unavailable")


class BrainRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {"schema": REGISTRY_SCHEMA, "brains": {},
                          "events": []}

    # -- persistence ---------------------------------------------------
    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=1),
                             encoding="utf-8")

    def _event(self, kind: str, brain_id: str, detail: str) -> None:
        self._data["events"].append(
            {"kind": kind, "brain_id": brain_id, "detail": detail,
             "at": time.time()})

    # -- lifecycle -------------------------------------------------------
    def register(self, brain_id: str, *, kind: str, descriptor: str,
                 status: str = "active",
                 capabilities: list[str] | None = None) -> dict[str, Any]:
        if status not in BRAIN_STATUSES:
            raise ValueError(f"unknown brain status {status!r}")
        record = {"brain_id": brain_id, "kind": kind,
                  "descriptor": descriptor, "status": status,
                  "capabilities": capabilities or []}
        self._data["brains"][brain_id] = record
        self._event("registered", brain_id, f"{kind}:{descriptor}")
        self._save()
        return record

    def dismiss(self, brain_id: str, *, reason: str) -> dict[str, Any]:
        record = self._data["brains"][brain_id]
        record["status"] = "dismissed"
        record["dismissal_reason"] = reason
        self._event("dismissed", brain_id, reason)
        self._save()
        return record

    def reinstate(self, brain_id: str, *, reason: str) -> dict[str, Any]:
        record = self._data["brains"][brain_id]
        record["status"] = "active"
        self._event("reinstated", brain_id, reason)
        self._save()
        return record

    # -- queries ---------------------------------------------------------
    def get(self, brain_id: str) -> dict[str, Any] | None:
        return self._data["brains"].get(brain_id)

    def brains(self) -> list[dict[str, Any]]:
        return list(self._data["brains"].values())

    def events(self) -> list[dict[str, Any]]:
        return list(self._data["events"])

    def match(self, model_hint: str | None) -> dict[str, Any] | None:
        """The registered brain a model hint refers to, if any.

        Matching is by descriptor containment in either direction
        (a router target like "Qwen3-8B" matches the brain whose
        descriptor is the GGUF file name, and vice versa).
        """
        if not model_hint:
            return None
        hint = model_hint.lower()
        for record in self._data["brains"].values():
            descriptor = record["descriptor"].lower()
            if hint in descriptor or descriptor in hint:
                return record
        return None

    def is_dismissed(self, model_hint: str | None) -> bool:
        record = self.match(model_hint)
        return bool(record and record["status"] == "dismissed")
