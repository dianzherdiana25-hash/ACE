"""OMEGA-08 — Population and Lineage Archive.

An append-only, content-addressed archive for candidate artifacts and their
evaluations. Design rules, mirroring the OMEGA programme's truthfulness
constraints:

* Candidate and evaluation identities are *derived from content* (SHA-256 of
  a canonical record), so identity cannot be forged or silently reused:
  registering identical content twice yields the same ID and one record;
  a record file whose content no longer hashes to its ID is corrupt.
* Records are write-once. There is no delete or mutate API. Negative
  results are first-class records and stay in the archive.
* Lineage is explicit: a candidate names its parents, parents must already
  exist, and the lineage graph is verified acyclic.
* Evaluations are only ever compared inside one (evaluator, protocol,
  budget) group. Mixing evaluators or budgets is an error, never a
  silent average.
* Every mutation appends a hash-chained line to ``ledger.jsonl``; the
  whole population state can be replayed from the ledger alone and its
  hash compared with the live state.

This module is storage and selection only. It does not evaluate anything
and it never claims a scientific result.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class ArchiveError(Exception):
    """Base class for archive integrity errors."""


class MissingParentError(ArchiveError):
    """A named parent candidate is not in the archive."""


class MissingCandidateError(ArchiveError):
    """An evaluation names a candidate that is not in the archive."""


class CorruptRecordError(ArchiveError):
    """A stored record's content does not hash to its recorded identity."""


class LineageCycleError(ArchiveError):
    """The lineage graph contains a cycle."""


class MixedEvaluatorError(ArchiveError):
    """Evaluations from different evaluators/protocols/budgets were mixed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class PopulationArchive:
    """Append-only population/lineage archive rooted at one directory."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.candidates_dir = self.root / "candidates"
        self.evaluations_dir = self.root / "evaluations"
        self.ledger_path = self.root / "ledger.jsonl"
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.write_text("", encoding="utf-8")

    # ------------------------------------------------------------------
    # ledger
    # ------------------------------------------------------------------
    def _ledger_events(self) -> list[dict[str, Any]]:
        events = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def _ledger_append(self, event: dict[str, Any]) -> dict[str, Any]:
        events = self._ledger_events()
        prev = events[-1]["hash"] if events else "GENESIS"
        entry = {"seq": len(events) + 1, "prev": prev, "event": event}
        entry["hash"] = _digest({"prev": prev, "event": event})
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    def _verify_chain(self, events: list[dict[str, Any]]) -> bool:
        prev = "GENESIS"
        for expected_seq, entry in enumerate(events, start=1):
            if entry.get("seq") != expected_seq or entry.get("prev") != prev:
                return False
            if entry.get("hash") != _digest({"prev": prev, "event": entry.get("event")}):
                return False
            prev = entry["hash"]
        return True

    # ------------------------------------------------------------------
    # record IO (write-once, identity-checked on load)
    # ------------------------------------------------------------------
    @staticmethod
    def _write_once(path: Path, record: dict[str, Any]) -> None:
        text = json.dumps(record, indent=1, ensure_ascii=False, sort_keys=True)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if _canonical(existing) != _canonical(record):
                raise CorruptRecordError(
                    f"record file {path.name} exists with different content")

    def _load(self, path: Path, prefix: str) -> dict[str, Any]:
        record = json.loads(path.read_text(encoding="utf-8"))
        content = {k: v for k, v in record.items() if k != "id"}
        expected = f"{prefix}_{_digest(content)[:20]}"
        if record.get("id") != expected or path.stem != expected:
            raise CorruptRecordError(
                f"{path.name}: content hashes to {expected}, file claims {record.get('id')}")
        return record

    # ------------------------------------------------------------------
    # candidates
    # ------------------------------------------------------------------
    def register_candidate(self, *, kind: str, descriptor: str,
                           artifact_bytes: bytes,
                           parents: list[str] | tuple[str, ...] = (),
                           metadata: dict[str, Any] | None = None) -> str:
        """Register a candidate artifact. Idempotent for identical content."""
        parent_list = sorted(set(parents))
        for parent in parent_list:
            if not (self.candidates_dir / f"{parent}.json").exists():
                raise MissingParentError(f"parent {parent} is not registered")
        content = {
            "kind": kind,
            "descriptor": descriptor,
            "artifact_digest": _digest(artifact_bytes),
            "artifact_size_bytes": len(artifact_bytes),
            "parents": parent_list,
            "metadata": metadata or {},
        }
        candidate_id = f"cand_{_digest(content)[:20]}"
        record = {"id": candidate_id, **content}
        path = self.candidates_dir / f"{candidate_id}.json"
        if path.exists():
            self._load(path, "cand")  # raises if the stored record was tampered
            return candidate_id
        self._write_once(path, record)
        self._ledger_append({"type": "candidate_registered", "record": record})
        return candidate_id

    def load_candidate(self, candidate_id: str) -> dict[str, Any]:
        path = self.candidates_dir / f"{candidate_id}.json"
        if not path.exists():
            raise MissingCandidateError(candidate_id)
        return self._load(path, "cand")

    def candidate_ids(self) -> list[str]:
        return sorted(p.stem for p in self.candidates_dir.glob("cand_*.json"))

    def lineage(self, candidate_id: str) -> list[str]:
        """All ancestors of a candidate, parents first, cycle-checked."""
        order: list[str] = []
        state: dict[str, int] = {}

        def visit(node: str, trail: list[str]) -> None:
            mark = state.get(node, 0)
            if mark == 1:
                raise LineageCycleError("cycle: " + " -> ".join(trail + [node]))
            if mark == 2:
                return
            state[node] = 1
            for parent in self.load_candidate(node)["parents"]:
                visit(parent, trail + [node])
            state[node] = 2
            if node != candidate_id:
                order.append(node)

        visit(candidate_id, [])
        return order

    # ------------------------------------------------------------------
    # evaluations
    # ------------------------------------------------------------------
    def record_evaluation(self, *, candidate_id: str, evaluator_id: str,
                            protocol: str, budget: dict[str, Any],
                            metrics: dict[str, float], outcome: str,
                            evidence_bytes: bytes | None = None) -> str:
        """Record one evaluation of a candidate. Idempotent per content."""
        if not (self.candidates_dir / f"{candidate_id}.json").exists():
            raise MissingCandidateError(candidate_id)
        content = {
            "candidate_id": candidate_id,
            "evaluator_id": evaluator_id,
            "protocol": protocol,
            "budget": budget,
            "metrics": metrics,
            "outcome": outcome,
            "evidence_digest": _digest(evidence_bytes) if evidence_bytes is not None else None,
        }
        evaluation_id = f"eval_{_digest(content)[:20]}"
        record = {"id": evaluation_id, **content}
        path = self.evaluations_dir / f"{evaluation_id}.json"
        if path.exists():
            self._load(path, "eval")
            return evaluation_id
        self._write_once(path, record)
        self._ledger_append({"type": "evaluation_recorded", "record": record})
        return evaluation_id

    def load_evaluation(self, evaluation_id: str) -> dict[str, Any]:
        path = self.evaluations_dir / f"{evaluation_id}.json"
        if not path.exists():
            raise ArchiveError(f"unknown evaluation {evaluation_id}")
        return self._load(path, "eval")

    def evaluation_ids(self) -> list[str]:
        return sorted(p.stem for p in self.evaluations_dir.glob("eval_*.json"))

    def negatives(self) -> list[dict[str, Any]]:
        """All archived negative/failed evaluations — never deleted."""
        result = []
        for evaluation_id in self.evaluation_ids():
            try:
                record = self.load_evaluation(evaluation_id)
            except CorruptRecordError:
                continue
            if record["outcome"] in ("fail", "negative"):
                result.append(record)
        return result

    # ------------------------------------------------------------------
    # comparability and selection
    # ------------------------------------------------------------------
    @staticmethod
    def group_key(record: dict[str, Any]) -> str:
        return _digest({"evaluator_id": record["evaluator_id"],
                        "protocol": record["protocol"],
                        "budget": record["budget"]})

    def assert_comparable(self, evaluation_ids: list[str]) -> str:
        keys = {self.group_key(self.load_evaluation(e)) for e in evaluation_ids}
        if len(keys) > 1:
            raise MixedEvaluatorError(
                "evaluations span more than one (evaluator, protocol, budget) group")
        return keys.pop() if keys else ""

    def _group_evaluations(self, *, evaluator_id: str, protocol: str,
                           budget: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Latest evaluation per candidate inside exactly one group."""
        wanted = _digest({"evaluator_id": evaluator_id, "protocol": protocol,
                          "budget": budget})
        latest: dict[str, dict[str, Any]] = {}
        seq_of: dict[str, int] = {}
        events = self._ledger_events()
        seq_by_eval = {}
        for entry in events:
            event = entry["event"]
            if event.get("type") == "evaluation_recorded":
                seq_by_eval[event["record"]["id"]] = entry["seq"]
        for evaluation_id in self.evaluation_ids():
            try:
                record = self.load_evaluation(evaluation_id)
            except CorruptRecordError:
                continue
            if self.group_key(record) != wanted:
                continue
            candidate = record["candidate_id"]
            if seq_by_eval.get(evaluation_id, 0) >= seq_of.get(candidate, -1):
                latest[candidate] = record
                seq_of[candidate] = seq_by_eval.get(evaluation_id, 0)
        return latest

    @staticmethod
    def pareto_front(metrics_by_candidate: dict[str, dict[str, float]],
                     objectives: list[tuple[str, str]]) -> list[str]:
        """Non-dominated candidate IDs, in deterministic (sorted) order.

        Objectives are (metric_name, "max"|"min"). Candidates with exactly
        equal objective vectors do not dominate each other: ties stay on
        the front together.
        """
        def vector(candidate: str) -> tuple[float, ...]:
            metrics = metrics_by_candidate[candidate]
            return tuple(metrics[name] if direction == "max" else -metrics[name]
                         for name, direction in objectives)

        front = []
        for candidate in metrics_by_candidate:
            mine = vector(candidate)
            dominated = False
            for other in metrics_by_candidate:
                if other == candidate:
                    continue
                theirs = vector(other)
                if (all(t >= m for t, m in zip(theirs, mine))
                        and any(t > m for t, m in zip(theirs, mine))):
                    dominated = True
                    break
            if not dominated:
                front.append(candidate)
        return sorted(front)

    def select(self, *, evaluator_id: str, protocol: str, budget: dict[str, Any],
               objectives: list[tuple[str, str]]) -> dict[str, Any]:
        """Pareto selection inside one evaluation group, with exclusions."""
        grouped = self._group_evaluations(evaluator_id=evaluator_id,
                                          protocol=protocol, budget=budget)
        usable: dict[str, dict[str, float]] = {}
        excluded: dict[str, str] = {}
        for candidate_id in self.candidate_ids():
            record = grouped.get(candidate_id)
            if record is None:
                excluded[candidate_id] = "no evaluation in this group"
                continue
            missing = [name for name, _ in objectives if name not in record["metrics"]]
            if missing:
                excluded[candidate_id] = f"missing metrics: {', '.join(missing)}"
                continue
            usable[candidate_id] = record["metrics"]
        front = self.pareto_front(usable, objectives)
        return {
            "group": {"evaluator_id": evaluator_id, "protocol": protocol, "budget": budget},
            "front": front,
            "dominated": sorted(c for c in usable if c not in front),
            "excluded": excluded,
        }

    # ------------------------------------------------------------------
    # verification and replay
    # ------------------------------------------------------------------
    def state_hash(self) -> str:
        events = self._ledger_events()
        head = events[-1]["hash"] if events else "GENESIS"
        return _digest({"candidates": self.candidate_ids(),
                        "evaluations": self.evaluation_ids(),
                        "ledger_head": head})

    def replay(self) -> str:
        """Rebuild the population state from the ledger alone; return its hash."""
        events = self._ledger_events()
        if not self._verify_chain(events):
            raise CorruptRecordError("ledger hash chain is broken")
        candidates, evaluations = [], []
        for entry in events:
            event = entry["event"]
            if event.get("type") == "candidate_registered":
                candidates.append(event["record"]["id"])
            elif event.get("type") == "evaluation_recorded":
                evaluations.append(event["record"]["id"])
        head = events[-1]["hash"] if events else "GENESIS"
        return _digest({"candidates": sorted(candidates),
                        "evaluations": sorted(evaluations),
                        "ledger_head": head})

    def verify(self) -> dict[str, Any]:
        """Full integrity audit: IDs, lineage, ledger chain, replay match."""
        corrupt: list[str] = []
        for candidate_id in self.candidate_ids():
            try:
                self.load_candidate(candidate_id)
            except CorruptRecordError:
                corrupt.append(candidate_id)
        for evaluation_id in self.evaluation_ids():
            try:
                self.load_evaluation(evaluation_id)
            except CorruptRecordError:
                corrupt.append(evaluation_id)
        cycles: list[str] = []
        for candidate_id in self.candidate_ids():
            if candidate_id in corrupt:
                continue
            try:
                self.lineage(candidate_id)
            except LineageCycleError as exc:
                cycles.append(str(exc))
            except (CorruptRecordError, MissingCandidateError):
                pass
        events = self._ledger_events()
        chain_ok = self._verify_chain(events)
        replay_hash = None
        if chain_ok and not corrupt:
            replay_hash = self.replay()
        return {
            "candidates": len(self.candidate_ids()),
            "evaluations": len(self.evaluation_ids()),
            "corrupt": corrupt,
            "cycles": cycles,
            "ledger_chain_ok": chain_ok,
            "state_hash": self.state_hash(),
            "replay_hash": replay_hash,
            "replay_matches": replay_hash is not None and replay_hash == self.state_hash(),
        }
