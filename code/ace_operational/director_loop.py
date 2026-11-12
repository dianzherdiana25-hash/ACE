"""Phase 2 — the local Research Director loop (observe → prioritise → assign).

The local model (Qwen3-8B on this host) is ACE's Research Director: it
*reasons* about ACE's state and proposes a prioritised agenda. It does
not write code, and nothing it proposes executes automatically — the
loop produces an agenda for the operator, and the reserved decisions
(merge, spending, publication) stay with the owner.

Trust architecture, mirroring the rest of Ω:

* **Observation before opinion.** The director only sees an
  ObservationPacket assembled from real artifacts: gate status, open
  gaps, recent measured results, memory recall. Facts in the packet
  carry source labels; the prompt forbids inventing capabilities.
* **Fail-closed parsing.** The model's reply must be one JSON object of
  proposals in the declared schema and category vocabulary. Any
  structural violation rejects the *whole* reply and records the
  rejection — a director that cannot follow the format does not get to
  direct, and partial salvage would let malformed output steer work.
* **Harness-owned priorities.** The model proposes value/effort; the
  loop recomputes the ranking deterministically (value, then low
  effort, then title) so ordering never depends on model whim.
* **Provenance is permanent.** Accepted proposals are written to the
  cognitive memory as *model-sourced* episodic records — guesses by
  construction, which by OMEGA-07's rules can never displace
  evidence-backed facts.
* **Bounded.** At most `max_proposals` per cycle; duplicates (by
  normalised title) against earlier cycles are dropped, not repeated.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable

CATEGORIES = ("experiment", "engineering", "measurement",
              "archive_hygiene", "documentation")
MAX_PROPOSALS = 5


class DirectorError(Exception):
    pass


class ProposalRejected(DirectorError):
    """The director's reply failed validation; nothing was accepted."""


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

def build_observation(*, gates: dict[str, str], gaps: list[dict[str, Any]],
                      results: list[dict[str, Any]],
                      memory_facts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assemble the packet the director is allowed to reason over."""
    return {
        "gates": dict(gates),
        "open_gaps": list(gaps),
        "recent_results": list(results),
        "memory_facts": list(memory_facts or []),
        "fact_count": len(gates) + len(gaps) + len(results) + len(memory_facts or []),
    }


def render_prompt(observation: dict[str, Any]) -> str:
    facts = json.dumps(observation, ensure_ascii=False, indent=1)
    return (
        "Kamu adalah Research Director untuk ACE, sistem riset lokal. "
        "Tugasmu: membaca status ACE di bawah, menemukan celah terpenting, "
        "dan mengusulkan agenda prioritas. Kamu tidak menulis kode; kamu "
        "mengarahkan riset.\n\n"
        f"STATUS ACE (fakta, jangan mengarang di luar ini):\n{facts}\n\n"
        "Balas HANYA dengan satu objek JSON tanpa teks lain, format:\n"
        '{"proposals": [{"title": "...", "category": "experiment|engineering|'
        'measurement|archive_hygiene|documentation", "rationale": "...", '
        '"value": 1-5, "effort": 1-5, "based_on": ["nama fakta/gap"]}]}\n'
        f"Maksimal {MAX_PROPOSALS} proposal. Urutkan dari yang paling penting. "
        "Rationale harus merujuk fakta di status. /no_think")


# ---------------------------------------------------------------------------
# Fail-closed proposal parsing
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ProposalRejected("no JSON object found in director reply")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProposalRejected(f"director reply is not valid JSON: {exc}") from exc


def parse_proposals(text: str, observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the whole reply or reject it entirely (fail-closed)."""
    data = _extract_json(text)
    if not isinstance(data, dict) or not isinstance(data.get("proposals"), list):
        raise ProposalRejected("reply must be an object with a proposals list")
    raw = data["proposals"]
    if not raw:
        raise ProposalRejected("director proposed nothing")
    if len(raw) > MAX_PROPOSALS:
        raise ProposalRejected(
            f"too many proposals: {len(raw)} > {MAX_PROPOSALS}")
    known_facts = ({str(g.get("id")) for g in observation["open_gaps"]}
                   | {str(r.get("id")) for r in observation["recent_results"]}
                   | set(observation["gates"]))
    proposals = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ProposalRejected(f"proposal {i} is not an object")
        title = item.get("title")
        category = item.get("category")
        rationale = item.get("rationale")
        value, effort = item.get("value"), item.get("effort")
        based_on = item.get("based_on")
        if not isinstance(title, str) or not title.strip():
            raise ProposalRejected(f"proposal {i} has no title")
        if category not in CATEGORIES:
            raise ProposalRejected(
                f"proposal {i} category {category!r} outside the vocabulary")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ProposalRejected(f"proposal {i} has no rationale")
        if not (isinstance(value, int) and 1 <= value <= 5):
            raise ProposalRejected(f"proposal {i} value must be an int in 1..5")
        if not (isinstance(effort, int) and 1 <= effort <= 5):
            raise ProposalRejected(f"proposal {i} effort must be an int in 1..5")
        if not isinstance(based_on, list) or not based_on:
            raise ProposalRejected(f"proposal {i} must cite based_on facts")
        unknown = [b for b in based_on if str(b) not in known_facts]
        if unknown:
            raise ProposalRejected(
                f"proposal {i} cites facts not in the observation: {unknown}")
        proposals.append({"title": title.strip(), "category": category,
                          "rationale": rationale.strip(),
                          "value": value, "effort": effort,
                          "based_on": [str(b) for b in based_on]})
    # Harness-owned ranking: value desc, effort asc, title — deterministic.
    proposals.sort(key=lambda p: (-p["value"], p["effort"], p["title"]))
    for rank, proposal in enumerate(proposals, start=1):
        proposal["rank"] = rank
        proposal["score"] = round(proposal["value"] / proposal["effort"], 3)
    return proposals


def _normalised_title(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title.lower())
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

class DirectorLoop:
    """One cycle: observe → ask → validate → record. Never executes."""

    def __init__(self, agenda_path: str | Path, *,
                 memory: Any | None = None):
        self.agenda_path = Path(agenda_path)
        self.memory = memory

    def _load_agenda(self) -> dict[str, Any]:
        if self.agenda_path.exists():
            return json.loads(self.agenda_path.read_text())
        return {"cycles": []}

    def run_cycle(self, observation: dict[str, Any],
                  infer: Callable[[str], str]) -> dict[str, Any]:
        agenda = self._load_agenda()
        cycle_no = len(agenda["cycles"]) + 1
        prompt = render_prompt(observation)
        reply = infer(prompt)
        record: dict[str, Any] = {"cycle": cycle_no, "at": time.time(),
                                  "observation_facts": observation["fact_count"]}
        try:
            proposals = parse_proposals(reply, observation)
        except ProposalRejected as exc:
            record.update({"status": "rejected", "reason": str(exc),
                           "proposals": []})
            agenda["cycles"].append(record)
            self._save(agenda)
            return record
        seen = {_normalised_title(p["title"])
                for cycle in agenda["cycles"] for p in cycle["proposals"]}
        fresh, duplicates = [], 0
        for proposal in proposals:
            if _normalised_title(proposal["title"]) in seen:
                duplicates += 1
            else:
                fresh.append(proposal)
        memory_ids = []
        if self.memory is not None:
            for proposal in fresh:
                memory_ids.append(self.memory.remember(
                    kind="episodic",
                    content={"event": "director_proposal", "cycle": cycle_no,
                             "proposal": proposal},
                    source_kind="model", source_ref="qwen3-8b-director",
                    confidence=0.4))
        record.update({"status": "accepted", "proposals": fresh,
                       "duplicates_dropped": duplicates,
                       "memory_record_ids": memory_ids})
        agenda["cycles"].append(record)
        self._save(agenda)
        return record

    def _save(self, agenda: dict[str, Any]) -> None:
        self.agenda_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.agenda_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(agenda, indent=1, ensure_ascii=False))
        tmp.replace(self.agenda_path)

    def current_agenda(self) -> list[dict[str, Any]]:
        """The latest accepted cycle's proposals, if any."""
        agenda = self._load_agenda()
        for cycle in reversed(agenda["cycles"]):
            if cycle["status"] == "accepted":
                return cycle["proposals"]
        return []
