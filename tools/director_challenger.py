"""Peninjau adversarial berbasis aturan (challenger) atas proposal director (AG70).

Memeriksa setiap usulan director secara read-only terhadap berkas fakta guna
mendeteksi empat kelas cacat bernama:
- ``numeric_claim_mismatch``: klaim angka di usulan bertentangan dengan fakta;
- ``weak_or_unanchored_based_on``: ``based_on`` kosong, hilang dari fakta,
  atau berstatus lemah (mis. berasal dari sumber ``model``/rendah kepercayaan);
- ``hidden_risk_detected``: teks rasional/aksi menyembunyikan operasi berisiko
  (uang, publikasi, eksternal, secrets, ireversibel) di balik klaim aman;
- ``duplicate_of_prior_proposal``: mengulang usulan lama pada target/aksi sama.

Keluaran per usulan adalah ``status="lolos"`` bila bersih, atau ``status="tertantang"``
beserta daftar ``challenges``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.director-challenger.v1"

_RISKY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("touches_secrets_or_env", re.compile(r"\b(secrets/|password|private[ _]?key|token|api[ _]?key)\b", re.I)),
    ("destructive_or_irreversible", re.compile(r"\b(rm\s+-rf|drop\s+table|force[- ]push|hapus\s+sejarah|overwrite\s+evidence)\b", re.I)),
    ("hidden_external_or_money", re.compile(r"\b(transfer\s+uang|payout|publish\s+live|curl\s+http|webhook)\b", re.I)),
)
_INLINE_METRIC_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]{2,})\s*(?:=|:)\s*(\d+)\b")


def _normalize_str(text: Any) -> str:
    return " ".join(str(text or "").strip().lower().split())


def challenge_proposal(
    proposal: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit satu proposal terhadap fakta acuan dan kembalikan daftar tantangan."""
    pid = str(proposal.get("proposal_id") or proposal.get("task_id") or proposal.get("id") or "unknown")
    cp = proposal.get("checkpoint")
    cp_map = cp if isinstance(cp, Mapping) else {}

    metrics_fact = facts.get("metrics") or {}
    verified_refs = set(str(r) for r in (facts.get("verified_refs") or ()))
    ref_strengths = facts.get("ref_strengths") or {}
    prior_list = facts.get("prior_proposals") or ()

    challenges: list[dict[str, Any]] = []

    # 1. Klaim angka tidak cocok dengan fakta.
    claimed_metrics: dict[str, Any] = {}
    for src in (proposal.get("claimed_metrics"), cp_map.get("claimed_metrics"), proposal.get("claimed_counts"), cp_map.get("claimed_counts")):
        if isinstance(src, Mapping):
            claimed_metrics.update(src)

    text_blob = " ".join(
        str(x)
        for x in (
            proposal.get("title"),
            proposal.get("summary"),
            proposal.get("rationale"),
            cp_map.get("rationale"),
            proposal.get("action"),
        )
        if x
    )
    for m_key, m_val in _INLINE_METRIC_RE.findall(text_blob):
        if m_key in metrics_fact and m_key not in claimed_metrics:
            claimed_metrics[m_key] = int(m_val)

    for metric_name, claimed_val in sorted(claimed_metrics.items()):
        if metric_name not in metrics_fact:
            challenges.append(
                {
                    "code": "numeric_claim_mismatch",
                    "detail": f"Metrik {metric_name!r}={claimed_val!r} tidak ada pada berkas fakta.",
                }
            )
        elif metrics_fact[metric_name] != claimed_val:
            challenges.append(
                {
                    "code": "numeric_claim_mismatch",
                    "detail": (
                        f"Klaim {metric_name}={claimed_val!r} bertentangan dengan fakta "
                        f"{metrics_fact[metric_name]!r}."
                    ),
                }
            )

    # 2. based_on lemah / tak berjangkar.
    based_on = cp_map.get("based_on", proposal.get("based_on"))
    if not isinstance(based_on, list) or not based_on or not all(isinstance(r, str) and r.strip() for r in based_on):
        challenges.append(
            {
                "code": "weak_or_unanchored_based_on",
                "detail": "Field based_on kosong atau hilang.",
            }
        )
    else:
        for raw_ref in based_on:
            ref = raw_ref.strip()
            if verified_refs and ref not in verified_refs:
                challenges.append(
                    {
                        "code": "weak_or_unanchored_based_on",
                        "detail": f"Referensi based_on {ref!r} tidak ditemukan pada verified_refs fakta.",
                    }
                )
                continue
            strength = ref_strengths.get(ref)
            if isinstance(strength, Mapping):
                src_kind = str(strength.get("source_kind") or "")
                conf = strength.get("confidence", 1.0)
                if src_kind == "model" or (isinstance(conf, (int, float)) and conf < 0.6):
                    challenges.append(
                        {
                            "code": "weak_or_unanchored_based_on",
                            "detail": (
                                f"Referensi based_on {ref!r} lemah "
                                f"(source_kind={src_kind!r}, confidence={conf!r})."
                            ),
                        }
                    )

    # 3. Risiko tersembunyi di rasional/aksi meski batas menyatakan aman.
    reversible = cp_map.get("reversible", proposal.get("reversible"))
    if reversible is False:
        challenges.append(
            {
                "code": "hidden_risk_detected",
                "detail": "Operasi ditandai tidak dapat dibalik (reversible=False).",
            }
        )
    for risk_name, pat in _RISKY_PATTERNS:
        if pat.search(text_blob):
            challenges.append(
                {
                    "code": "hidden_risk_detected",
                    "detail": f"Terdeteksi pola risiko tersembunyi ({risk_name}).",
                }
            )

    # 4. Duplikat usulan lama.
    cur_action = _normalize_str(cp_map.get("action") or proposal.get("action"))
    cur_target = _normalize_str(cp_map.get("target_id") or cp_map.get("gap_id") or proposal.get("target_id"))
    cur_title = _normalize_str(proposal.get("title") or proposal.get("summary"))
    for prior in prior_list:
        if not isinstance(prior, Mapping):
            continue
        p_id = str(prior.get("proposal_id") or prior.get("id") or "prior")
        if p_id == pid:
            continue
        p_action = _normalize_str(prior.get("action"))
        p_target = _normalize_str(prior.get("target_id") or prior.get("gap_id"))
        p_title = _normalize_str(prior.get("title") or prior.get("summary"))
        same_target_action = bool(cur_action and cur_target and cur_action == p_action and cur_target == p_target)
        same_title = bool(cur_title and cur_title == p_title)
        if same_target_action or same_title:
            challenges.append(
                {
                    "code": "duplicate_of_prior_proposal",
                    "detail": f"Menyerupai usulan lama {p_id!r}.",
                }
            )
            break

    passed = len(challenges) == 0
    return {
        "proposal_id": pid,
        "verdict": "lolos" if passed else "tertantang",
        "challenge_count": len(challenges),
        "challenge_codes": list(dict.fromkeys(c["code"] for c in challenges)),
        "challenges": challenges,
    }


def review_proposals(
    proposals: Sequence[Mapping[str, Any]],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Tinjau seluruh daftar proposal director terhadap berkas fakta."""
    if not proposals:
        raise ValueError("Daftar proposal tidak boleh kosong")
    results = [challenge_proposal(prop, facts) for prop in proposals]
    lolos_ids = [r["proposal_id"] for r in results if r["verdict"] == "lolos"]
    challenged_ids = [r["proposal_id"] for r in results if r["verdict"] != "lolos"]
    return {
        "schema": SCHEMA,
        "summary": {
            "total_proposals": len(results),
            "lolos_count": len(lolos_ids),
            "challenged_count": len(challenged_ids),
            "lolos_ids": lolos_ids,
            "challenged_ids": challenged_ids,
        },
        "reviews": results,
    }


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas proposal kosong: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        return [dict(x) for x in data]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, Mapping) and isinstance(obj.get("proposals"), list):
            return [dict(x) for x in obj["proposals"]]
        return [dict(obj)]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Peninjau adversarial berbasis aturan atas proposal director + berkas fakta."
    )
    parser.add_argument("--proposals", required=True, help="Path berkas proposal JSON/JSONL.")
    parser.add_argument("--facts", required=True, help="Path berkas fakta acuan JSON.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        proposals = _load_proposals(Path(args.proposals))
        facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
        if not isinstance(facts, Mapping):
            raise ValueError("Berkas fakta wajib berupa objek JSON")
        report = review_proposals(proposals, facts)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
