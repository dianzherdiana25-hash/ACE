"""OMEGA-06 — Experiment Protocol and Evidence Kernel.

The kernel makes an experiment's claims auditable *by construction*:

* **Preregistration before results.** An experiment is registered first —
  hypothesis, protocol, evaluator identity, budget, fixture digest, the
  candidate set (with at least one baseline and optionally a negative
  control) — and the registration is content-hashed. Results for an
  unregistered experiment, or naming anything the registration did not
  pin down, are rejected.
* **Split custody.** The candidate custodian signs the candidate artifact
  digests; the evaluator custodian signs the evaluator and fixture
  digests. Neither side can quietly swap the other's artifact: digests
  are re-verified at result time and at audit.
* **Verdicts are derived, not asserted.** A result's pass/fail is
  recomputed from its metrics and the preregistered pass rule. A forged
  success flag is rejected. ``abstain`` is a first-class verdict and
  requires a reason.
* **Contamination guards.** Canary tokens declared in the protocol must
  not appear in candidate artifacts or result telemetry; a candidate
  whose artifact *is* the evaluator or the fixture is rejected.
* **Append-only results ledger** with a hash chain. Auditing a truncated
  (partial) ledger reports INCOMPLETE with the verified prefix, never a
  clean bill.

The kernel stores and checks evidence. It does not run experiments and
it never upgrades a verdict beyond what the metrics support.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any


class KernelError(Exception):
    """Base class for kernel rejections."""


class NotPreregisteredError(KernelError):
    pass


class CustodyError(KernelError):
    pass


class ChangedEvaluatorError(KernelError):
    pass


class FixtureMutatedError(KernelError):
    pass


class ForgedVerdictError(KernelError):
    pass


class ContaminationError(KernelError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sign(key: bytes, payload: Any) -> str:
    return hmac.new(key, _canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


VERDICTS = ("pass", "fail", "abstain")


class ExperimentKernel:
    """Preregistration, split custody, result intake and audit for one lab dir."""

    def __init__(self, root: str | Path, *, candidate_key: bytes, evaluator_key: bytes):
        self.root = Path(root)
        self.prereg_dir = self.root / "preregistrations"
        self.custody_path = self.root / "custody.json"
        self.ledger_path = self.root / "results.jsonl"
        self.prereg_dir.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.write_text("", encoding="utf-8")
        self._candidate_key = candidate_key
        self._evaluator_key = evaluator_key

    # ------------------------------------------------------------------
    # custody (split, signed)
    # ------------------------------------------------------------------
    def _load_custody(self) -> dict[str, Any]:
        if not self.custody_path.exists():
            return {"candidates": {}, "evaluator": None, "fixture": None}
        return json.loads(self.custody_path.read_text(encoding="utf-8"))

    def _save_custody(self, custody: dict[str, Any]) -> None:
        text = json.dumps(custody, indent=1, ensure_ascii=False, sort_keys=True)
        tmp = self.custody_path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.custody_path)

    def custody_candidate(self, candidate_id: str, artifact_bytes: bytes) -> str:
        """Candidate custodian registers an artifact digest, signed."""
        digest = _digest(artifact_bytes)
        custody = self._load_custody()
        record = {"candidate_id": candidate_id, "artifact_digest": digest}
        record["signature"] = _sign(self._candidate_key, record)
        custody["candidates"][candidate_id] = record
        self._save_custody(custody)
        return digest

    def custody_evaluator(self, evaluator_id: str, evaluator_bytes: bytes,
                          fixture_bytes: bytes) -> tuple[str, str]:
        """Evaluator custodian registers evaluator + fixture digests, signed."""
        custody = self._load_custody()
        ev = {"evaluator_id": evaluator_id, "artifact_digest": _digest(evaluator_bytes)}
        ev["signature"] = _sign(self._evaluator_key, ev)
        fx = {"fixture_digest": _digest(fixture_bytes)}
        fx["signature"] = _sign(self._evaluator_key, fx)
        custody["evaluator"] = ev
        custody["fixture"] = fx
        self._save_custody(custody)
        return ev["artifact_digest"], fx["fixture_digest"]

    def _verify_custody(self) -> dict[str, Any]:
        custody = self._load_custody()
        problems = []
        for candidate_id, record in custody.get("candidates", {}).items():
            payload = {"candidate_id": candidate_id,
                       "artifact_digest": record.get("artifact_digest")}
            if not hmac.compare_digest(record.get("signature", ""),
                                       _sign(self._candidate_key, payload)):
                problems.append(f"candidate custody signature invalid: {candidate_id}")
        evaluator = custody.get("evaluator")
        if evaluator is not None:
            payload = {"evaluator_id": evaluator.get("evaluator_id"),
                       "artifact_digest": evaluator.get("artifact_digest")}
            if not hmac.compare_digest(evaluator.get("signature", ""),
                                       _sign(self._evaluator_key, payload)):
                problems.append("evaluator custody signature invalid")
        fixture = custody.get("fixture")
        if fixture is not None:
            payload = {"fixture_digest": fixture.get("fixture_digest")}
            if not hmac.compare_digest(fixture.get("signature", ""),
                                       _sign(self._evaluator_key, payload)):
                problems.append("fixture custody signature invalid")
        return {"custody": custody, "problems": problems}

    # ------------------------------------------------------------------
    # preregistration
    # ------------------------------------------------------------------
    def preregister(self, *, experiment_id: str, hypothesis: str,
                    protocol: dict[str, Any], evaluator_id: str,
                    budget: dict[str, Any], candidate_ids: list[str],
                    baseline_candidate_id: str,
                    negative_control_id: str | None = None,
                    canary_tokens: list[str] | None = None) -> dict[str, Any]:
        """Register an experiment before any result may be recorded."""
        custody = self._load_custody()
        if custody.get("evaluator") is None or custody.get("fixture") is None:
            raise CustodyError("evaluator and fixture custody must be registered first")
        if custody["evaluator"]["evaluator_id"] != evaluator_id:
            raise CustodyError("evaluator_id does not match evaluator custody")
        if baseline_candidate_id not in candidate_ids:
            raise KernelError("baseline candidate must be in the candidate set")
        for candidate_id in candidate_ids:
            if candidate_id not in custody.get("candidates", {}):
                raise CustodyError(f"candidate {candidate_id} has no custody record")
        if "pass_rule" not in protocol:
            raise KernelError("protocol must declare a pass_rule")
        content = {
            "experiment_id": experiment_id,
            "hypothesis": hypothesis,
            "protocol": protocol,
            "evaluator_id": evaluator_id,
            "evaluator_digest": custody["evaluator"]["artifact_digest"],
            "fixture_digest": custody["fixture"]["fixture_digest"],
            "budget": budget,
            "candidate_ids": sorted(candidate_ids),
            "candidate_digests": {c: custody["candidates"][c]["artifact_digest"]
                                  for c in candidate_ids},
            "baseline_candidate_id": baseline_candidate_id,
            "negative_control_id": negative_control_id,
            "canary_tokens": canary_tokens or [],
        }
        record = {"protocol_hash": _digest(content), **content}
        path = self.prereg_dir / f"{experiment_id}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if _canonical(existing) != _canonical(record):
                raise KernelError(
                    f"experiment {experiment_id} already preregistered with different content")
            return existing
        text = json.dumps(record, indent=1, ensure_ascii=False, sort_keys=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def load_prereg(self, experiment_id: str) -> dict[str, Any]:
        path = self.prereg_dir / f"{experiment_id}.json"
        if not path.exists():
            raise NotPreregisteredError(experiment_id)
        record = json.loads(path.read_text(encoding="utf-8"))
        content = {k: v for k, v in record.items() if k != "protocol_hash"}
        if record.get("protocol_hash") != _digest(content):
            raise KernelError(f"preregistration {experiment_id} was altered after the fact")
        return record

    # ------------------------------------------------------------------
    # results
    # ------------------------------------------------------------------
    def _ledger_entries(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in
                self.ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _derive_verdict(self, prereg: dict[str, Any], metrics: dict[str, float]) -> str:
        rule = prereg["protocol"]["pass_rule"]
        metric = rule["metric"]
        if metric not in metrics:
            return "abstain"
        value = metrics[metric]
        if "gte" in rule:
            return "pass" if value >= rule["gte"] else "fail"
        if "lte" in rule:
            return "pass" if value <= rule["lte"] else "fail"
        raise KernelError("pass_rule must use gte or lte")

    def record_result(self, *, experiment_id: str, candidate_id: str,
                      candidate_artifact: bytes, metrics: dict[str, float],
                      claimed_verdict: str, raw_telemetry: dict[str, Any],
                      abstain_reason: str | None = None) -> dict[str, Any]:
        """Intake one result. Every pin from the preregistration is checked."""
        prereg = self.load_prereg(experiment_id)
        if claimed_verdict not in VERDICTS:
            raise KernelError(f"unknown verdict {claimed_verdict!r}")
        if candidate_id not in prereg["candidate_ids"]:
            raise KernelError(f"candidate {candidate_id} is not in the preregistered set")
        artifact_digest = _digest(candidate_artifact)
        if artifact_digest != prereg["candidate_digests"][candidate_id]:
            raise CustodyError("candidate artifact does not match its custody digest")
        if artifact_digest == prereg["evaluator_digest"]:
            raise ContaminationError("candidate artifact IS the evaluator artifact")
        if artifact_digest == prereg["fixture_digest"]:
            raise ContaminationError("candidate artifact IS the fixture (train/test contamination)")
        for token in prereg["canary_tokens"]:
            if token.encode() in candidate_artifact:
                raise ContaminationError(f"canary token leaked into candidate artifact: {token!r}")
            if token in _canonical(raw_telemetry):
                raise ContaminationError(f"canary token leaked into telemetry: {token!r}")
        derived = self._derive_verdict(prereg, metrics)
        if claimed_verdict == "abstain":
            if derived != "abstain" and not abstain_reason:
                raise ForgedVerdictError("abstain requires a reason when metrics are decisive")
            verdict = "abstain"
        else:
            if claimed_verdict != derived:
                raise ForgedVerdictError(
                    f"claimed {claimed_verdict!r} but metrics derive {derived!r}")
            verdict = claimed_verdict
        content = {
            "experiment_id": experiment_id,
            "protocol_hash": prereg["protocol_hash"],
            "candidate_id": candidate_id,
            "candidate_digest": artifact_digest,
            "evaluator_digest": prereg["evaluator_digest"],
            "fixture_digest": prereg["fixture_digest"],
            "metrics": metrics,
            "verdict": verdict,
            "abstain_reason": abstain_reason if verdict == "abstain" else None,
            "raw_telemetry": raw_telemetry,
        }
        entries = self._ledger_entries()
        prev = entries[-1]["hash"] if entries else "GENESIS"
        entry = {"seq": len(entries) + 1, "prev": prev, "result": content}
        entry["hash"] = _digest({"prev": prev, "result": content})
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    # ------------------------------------------------------------------
    # audit
    # ------------------------------------------------------------------
    def audit(self, experiment_id: str) -> dict[str, Any]:
        """Verify custody, preregistration, chain, verdicts and controls.

        Statuses: CLEAN (everything checks out), VIOLATIONS (problems
        listed), INCOMPLETE (the ledger chain breaks at some entry —
        only the verified prefix counts), NOT_PREREGISTERED.
        """
        try:
            prereg = self.load_prereg(experiment_id)
        except NotPreregisteredError:
            return {"experiment_id": experiment_id, "status": "NOT_PREREGISTERED"}
        except KernelError as exc:
            return {"experiment_id": experiment_id, "status": "VIOLATIONS",
                    "problems": [str(exc)]}
        custody_report = self._verify_custody()
        problems = list(custody_report["problems"])
        custody = custody_report["custody"]
        evaluator = custody.get("evaluator") or {}
        if evaluator.get("artifact_digest") != prereg["evaluator_digest"]:
            problems.append("evaluator changed since preregistration")
        fixture = custody.get("fixture") or {}
        if fixture.get("fixture_digest") != prereg["fixture_digest"]:
            problems.append("fixture mutated since preregistration")
        for candidate_id, pinned in prereg["candidate_digests"].items():
            current = (custody.get("candidates", {}).get(candidate_id) or {}).get("artifact_digest")
            if current != pinned:
                problems.append(f"candidate artifact changed since preregistration: {candidate_id}")
        entries = self._ledger_entries()
        verified = 0
        prev = "GENESIS"
        chain_break_at = None
        results = []
        for entry in entries:
            if entry.get("seq") != verified + 1 or entry.get("prev") != prev:
                chain_break_at = verified + 1
                break
            if entry.get("hash") != _digest({"prev": prev, "result": entry.get("result")}):
                chain_break_at = verified + 1
                break
            result = entry["result"]
            if result.get("experiment_id") == experiment_id:
                if result.get("protocol_hash") != prereg["protocol_hash"]:
                    problems.append(f"result seq {entry['seq']}: protocol hash mismatch")
                derived = self._derive_verdict(prereg, result.get("metrics", {}))
                if result.get("verdict") in ("pass", "fail") and derived != result["verdict"]:
                    problems.append(f"result seq {entry['seq']}: verdict does not derive from metrics")
                results.append(result)
            verified += 1
            prev = entry["hash"]
        for result in results:
            if (prereg.get("negative_control_id")
                    and result["candidate_id"] == prereg["negative_control_id"]
                    and result["verdict"] == "pass"):
                problems.append("negative control PASSED — control violation")
        if chain_break_at is not None:
            status = "INCOMPLETE"
        elif problems:
            status = "VIOLATIONS"
        else:
            status = "CLEAN"
        return {"experiment_id": experiment_id, "status": status,
                "problems": problems, "results_verified": len(results),
                "ledger_entries_verified": verified,
                "chain_break_at": chain_break_at}
