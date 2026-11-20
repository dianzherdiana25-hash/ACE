"""Format paket dilema konstitusi & validator catatan keputusan (AG100).

Menegakkan bahwa setiap keputusan atas dilema konstitusional (situasi dengan
>= 2 pasal yang berada dalam ketegangan nyata) wajib secara eksplisit menyebut:
1. Pasal yang dipakai / dimenangkan (``invoked_article``) beserta alasannya.
2. Pasal yang dikalahkan / dikesampingkan sementara (``overridden_article``).
3. Pengakuan eksplisit atas pengorbanan atau biaya dari mengalahkan pasal tersebut
   (``overridden_acknowledgment``).

Keputusan yang menyembunyikan atau tidak mengakui pasal yang kalah ditolak.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PACK_SCHEMA = "ace.constitution-dilemma-pack.v1"
VALIDATION_SCHEMA = "ace.constitution-decision-validation.v1"


class DilemmaValidationError(ValueError):
    """Galat validasi format paket dilema atau catatan keputusan cacat."""


def load_dilemma_pack(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        raise DilemmaValidationError(f"Berkas dilema kosong: {p}")
    if p.suffix == ".jsonl":
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("dilemmas"), list):
            items = parsed["dilemmas"]
        elif isinstance(parsed, list):
            items = parsed
        else:
            raise DilemmaValidationError(f"Format paket dilema tidak dikenal di {p}.")

    validated = [validate_dilemma_item(row) for row in items]
    return validated


def validate_dilemma_item(item: Mapping[str, Any]) -> dict[str, Any]:
    did = str(item.get("dilemma_id") or "").strip()
    title = str(item.get("title") or did).strip()
    situation = str(item.get("situation") or "").strip()
    if not did or not situation:
        raise DilemmaValidationError(f"Dilema wajib memiliki dilemma_id dan situation: {item!r}")

    raw_articles = item.get("articles_in_tension")
    if (
        not isinstance(raw_articles, Sequence)
        or isinstance(raw_articles, (str, bytes))
        or len(raw_articles) < 2
    ):
        raise DilemmaValidationError(
            f"Dilema {did!r} wajib memiliki >= 2 pasal dalam articles_in_tension."
        )

    articles: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for art in raw_articles:
        if isinstance(art, str):
            aid = art.strip()
            summary = aid
        elif isinstance(art, Mapping):
            aid = str(art.get("article_id") or "").strip()
            summary = str(art.get("summary") or aid).strip()
        else:
            raise DilemmaValidationError(f"Format pasal tidak valid pada {did!r}: {art!r}")
        if not aid or aid in seen_ids:
            raise DilemmaValidationError(f"article_id kosong atau duplikat di {did!r}: {aid!r}")
        seen_ids.add(aid)
        articles.append({"article_id": aid, "summary": summary})

    return {
        "schema": PACK_SCHEMA,
        "dilemma_id": did,
        "title": title,
        "situation": situation,
        "articles_in_tension": articles,
        "article_ids": [a["article_id"] for a in articles],
    }


def validate_dilemma_decision(
    dilemma: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Validasi catatan keputusan atas dilema: wajib menyebut pasal dipakai + pengakuan pasal kalah."""
    norm_dil = validate_dilemma_item(dilemma)
    did = norm_dil["dilemma_id"]
    tension_ids = set(norm_dil["article_ids"])

    errors: list[str] = []
    dec_did = str(decision.get("dilemma_id") or "").strip()
    if dec_did and dec_did != did:
        errors.append(f"dilemma_id keputusan ({dec_did!r}) tidak cocok dengan dilema ({did!r}).")

    invoked = str(decision.get("invoked_article") or "").strip()
    overridden = str(decision.get("overridden_article") or "").strip()
    invoked_rationale = str(decision.get("invoked_rationale") or "").strip()
    overridden_ack = str(decision.get("overridden_acknowledgment") or "").strip()
    action = str(decision.get("chosen_action") or "").strip()

    if not action:
        errors.append("chosen_action wajib diisi.")
    if not invoked:
        errors.append("invoked_article (pasal yang dipakai) wajib disebut.")
    elif invoked not in tension_ids:
        errors.append(f"invoked_article {invoked!r} bukan bagian dari articles_in_tension {sorted(tension_ids)}.")

    if not invoked_rationale:
        errors.append("invoked_rationale wajib menjelaskan alasan pemenangan pasal dipakai.")

    if not overridden:
        errors.append("overridden_article (pasal yang dikalahkan) wajib disebut eksplisit.")
    elif overridden not in tension_ids:
        errors.append(f"overridden_article {overridden!r} bukan bagian dari articles_in_tension {sorted(tension_ids)}.")
    elif overridden == invoked:
        errors.append("invoked_article dan overridden_article tidak boleh pasal yang sama.")

    if not overridden_ack:
        errors.append(
            "overridden_acknowledgment wajib mengakui biaya/dampak pasal yang dikalahkan secara eksplisit."
        )

    valid = len(errors) == 0
    result = {
        "schema": VALIDATION_SCHEMA,
        "dilemma_id": did,
        "valid": valid,
        "invoked_article": invoked or None,
        "overridden_article": overridden or None,
        "errors": errors,
    }
    if strict and not valid:
        raise DilemmaValidationError("; ".join(errors))
    return result


def validate_decision_batch(
    dilemmas: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {d["dilemma_id"]: validate_dilemma_item(d) for d in dilemmas}
    results: list[dict[str, Any]] = []
    for dec in decisions:
        did = str(dec.get("dilemma_id") or "").strip()
        if did not in by_id:
            results.append(
                {
                    "schema": VALIDATION_SCHEMA,
                    "dilemma_id": did or "<kosong>",
                    "valid": False,
                    "invoked_article": dec.get("invoked_article"),
                    "overridden_article": dec.get("overridden_article"),
                    "errors": [f"dilemma_id {did!r} tidak ditemukan pada paket dilema."],
                }
            )
            continue
        results.append(validate_dilemma_decision(by_id[did], dec))

    passed = sum(1 for r in results if r["valid"])
    rejected = len(results) - passed
    return {
        "schema": VALIDATION_SCHEMA,
        "dilemma_count": len(by_id),
        "decision_count": len(results),
        "valid_count": passed,
        "rejected_count": rejected,
        "all_valid": rejected == 0,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validator keputusan dilema konstitusi (AG100)")
    parser.add_argument("--dilemmas", required=True, help="Path JSON/JSONL paket dilema")
    parser.add_argument("--decisions", required=True, help="Path JSON daftar catatan keputusan")
    args = parser.parse_args(argv)

    dilemmas = load_dilemma_pack(args.dilemmas)
    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    if isinstance(decisions, dict):
        decisions = [decisions]
    report = validate_decision_batch(dilemmas, decisions)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["all_valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
