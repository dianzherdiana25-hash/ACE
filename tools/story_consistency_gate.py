"""Gerbang pemeriksa konsistensi draf bab terhadap ekspor story_state (AG88).

Memeriksa draf bab terstruktur JSON (``chapter_id``, ``tick``, ``active_characters``,
``fact_claims``, ``timeline_markers``, dan opsional ``promise_updates``) terhadap
berkas ekspor ``story_state`` JSON (tanpa memodifikasi berkas apa pun). Menghasilkan
daftar kontradiksi bernama atau vonis ``"lolos"``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.story-consistency-gate.v1"


def _fact_active_at(fact: Mapping[str, Any], tick: int) -> bool:
    start = fact.get("valid_from_tick")
    end = fact.get("valid_until_tick")
    if not isinstance(start, int):
        return False
    if tick < start:
        return False
    if isinstance(end, int) and tick >= end:
        return False
    return True


def check_chapter_consistency(
    story_state: Mapping[str, Any],
    chapter_draft: Mapping[str, Any],
) -> dict[str, Any]:
    """Periksa konsistensi satu draf bab terstruktur terhadap snapshot ``story_state``."""
    chapter_id = str(chapter_draft.get("chapter_id") or "<tanpa-id>")
    raw_tick = chapter_draft.get("tick")
    draft_tick = raw_tick if type(raw_tick) is int else 0

    characters = story_state.get("characters", {})
    if not isinstance(characters, Mapping):
        characters = {}
    timeline_raw = story_state.get("timeline", [])
    events_by_id: dict[str, Mapping[str, Any]] = {}
    if isinstance(timeline_raw, Sequence) and not isinstance(timeline_raw, (str, bytes)):
        for ev in timeline_raw:
            if isinstance(ev, Mapping) and ev.get("event_id"):
                events_by_id[str(ev["event_id"])] = ev
    facts_raw = story_state.get("facts", [])
    facts: list[Mapping[str, Any]] = [
        f for f in facts_raw if isinstance(f, Mapping)
    ] if isinstance(facts_raw, Sequence) and not isinstance(facts_raw, (str, bytes)) else []
    promises_raw = story_state.get("promises", [])
    promises_by_id: dict[str, Mapping[str, Any]] = {}
    if isinstance(promises_raw, Sequence) and not isinstance(promises_raw, (str, bytes)):
        for p in promises_raw:
            if isinstance(p, Mapping) and p.get("promise_id"):
                promises_by_id[str(p["promise_id"])] = p

    contradictions: list[dict[str, Any]] = []

    if type(raw_tick) is not int or raw_tick < 0:
        contradictions.append(
            {
                "type": "invalid_chapter_tick",
                "target": chapter_id,
                "tick": raw_tick,
                "detail": f"tick draf bab wajib integer >= 0 (didapat {raw_tick!r}).",
            }
        )

    # 1. Periksa tokoh aktif dalam bab terhadap status & status_tick di story_state.
    for raw_cid in chapter_draft.get("active_characters", []) or ():
        cid = str(raw_cid)
        char = characters.get(cid)
        if not isinstance(char, Mapping):
            contradictions.append(
                {
                    "type": "unknown_character",
                    "target": cid,
                    "tick": draft_tick,
                    "detail": f"Tokoh aktif {cid!r} tidak terdaftar di story_state.",
                }
            )
            continue
        status = char.get("status")
        status_tick = char.get("status_tick", 0)
        if status == "dead" and isinstance(status_tick, int) and draft_tick >= status_tick:
            contradictions.append(
                {
                    "type": "dead_character_active",
                    "target": cid,
                    "tick": draft_tick,
                    "status_tick": status_tick,
                    "detail": (
                        f"Tokoh {cid!r} sudah meninggal pada tick {status_tick}, "
                        f"tetapi masih aktif pada bab tick {draft_tick}."
                    ),
                }
            )
        elif status == "departed" and isinstance(status_tick, int) and draft_tick >= status_tick:
            contradictions.append(
                {
                    "type": "absent_character_active",
                    "target": cid,
                    "tick": draft_tick,
                    "status_tick": status_tick,
                    "detail": (
                        f"Tokoh {cid!r} sudah pergi/absen sejak tick {status_tick}, "
                        f"tetapi masih aktif tanpa pemulihan pada tick {draft_tick}."
                    ),
                }
            )

    # 2. Periksa klaim fakta draf terhadap fakta berlaku & kematian tokoh.
    for idx, claim in enumerate(chapter_draft.get("fact_claims", []) or ()):
        if not isinstance(claim, Mapping):
            continue
        subj = str(claim.get("subject", ""))
        pred = str(claim.get("predicate", ""))
        val = claim.get("value")
        claim_tick = claim.get("tick", draft_tick)
        if type(claim_tick) is not int:
            claim_tick = draft_tick

        char = characters.get(subj)
        if isinstance(char, Mapping) and char.get("status") == "dead":
            status_tick = char.get("status_tick", 0)
            if isinstance(status_tick, int) and claim_tick >= status_tick:
                if (pred == "alive" and val is True) or pred in ("location", "action", "speech"):
                    contradictions.append(
                        {
                            "type": "dead_character_fact_conflict",
                            "target": f"{subj}.{pred}",
                            "claim_index": idx,
                            "tick": claim_tick,
                            "status_tick": status_tick,
                            "claimed": val,
                            "detail": (
                                f"Klaim {subj}.{pred}={val!r} pada tick {claim_tick} "
                                f"bertentangan dengan kematian tokoh pada tick {status_tick}."
                            ),
                        }
                    )

        for fact in facts:
            if str(fact.get("subject", "")) != subj or str(fact.get("predicate", "")) != pred:
                continue
            if not _fact_active_at(fact, claim_tick):
                continue
            expected = fact.get("value")
            if expected != val:
                contradictions.append(
                    {
                        "type": "fact_contradiction",
                        "target": f"{subj}.{pred}",
                        "claim_index": idx,
                        "tick": claim_tick,
                        "expected": expected,
                        "claimed": val,
                        "fact_id": fact.get("fact_id"),
                        "detail": (
                            f"Klaim {subj}.{pred}={val!r} pada tick {claim_tick} "
                            f"bertentangan dengan fakta {fact.get('fact_id')!r} ({expected!r})."
                        ),
                    }
                )

    # 3. Periksa penanda linimasa terhadap urutan kausal & kronologi kejadian.
    seen_marker_ticks: dict[str, int] = {}
    for idx, marker in enumerate(chapter_draft.get("timeline_markers", []) or ()):
        if not isinstance(marker, Mapping):
            continue
        marker_id = str(marker.get("marker_id") or f"marker-{idx}")
        m_tick = marker.get("tick", draft_tick)
        if type(m_tick) is not int or m_tick < 0:
            contradictions.append(
                {
                    "type": "timeline_anachronism",
                    "target": marker_id,
                    "tick": m_tick,
                    "detail": f"Penanda linimasa {marker_id!r} memiliki tick tidak valid ({m_tick!r}).",
                }
            )
            continue
        seen_marker_ticks[marker_id] = m_tick

        ref_event_id = marker.get("after_event_id")
        if ref_event_id is not None:
            ref_ev = events_by_id.get(str(ref_event_id))
            if ref_ev is None:
                contradictions.append(
                    {
                        "type": "unknown_reference_event",
                        "target": marker_id,
                        "after_event_id": str(ref_event_id),
                        "tick": m_tick,
                        "detail": f"Penanda {marker_id!r} merujuk event tidak dikenal {ref_event_id!r}.",
                    }
                )
            elif isinstance(ref_ev.get("tick"), int) and m_tick < ref_ev["tick"]:
                contradictions.append(
                    {
                        "type": "timeline_anachronism",
                        "target": marker_id,
                        "tick": m_tick,
                        "after_event_id": str(ref_event_id),
                        "reference_tick": ref_ev["tick"],
                        "detail": (
                            f"Anakronisme linimasa pada {marker_id!r}: terjadi di tick {m_tick}, "
                            f"padahal ditandai sesudah event {ref_event_id!r} (tick {ref_ev['tick']})."
                        ),
                    }
                )

        before_event_id = marker.get("before_event_id")
        if before_event_id is not None:
            ref_ev = events_by_id.get(str(before_event_id))
            if ref_ev is None:
                contradictions.append(
                    {
                        "type": "unknown_reference_event",
                        "target": marker_id,
                        "before_event_id": str(before_event_id),
                        "tick": m_tick,
                        "detail": f"Penanda {marker_id!r} merujuk event tidak dikenal {before_event_id!r}.",
                    }
                )
            elif isinstance(ref_ev.get("tick"), int) and m_tick > ref_ev["tick"]:
                contradictions.append(
                    {
                        "type": "timeline_anachronism",
                        "target": marker_id,
                        "tick": m_tick,
                        "before_event_id": str(before_event_id),
                        "reference_tick": ref_ev["tick"],
                        "detail": (
                            f"Anakronisme linimasa pada {marker_id!r}: terjadi di tick {m_tick}, "
                            f"padahal seharusnya sebelum event {before_event_id!r} (tick {ref_ev['tick']})."
                        ),
                    }
                )

        if m_tick < draft_tick and marker.get("allow_flashback") is not True:
            contradictions.append(
                {
                    "type": "timeline_anachronism",
                    "target": marker_id,
                    "tick": m_tick,
                    "chapter_tick": draft_tick,
                    "detail": (
                        f"Penanda non-flashback {marker_id!r} bertick {m_tick} "
                        f"mundur dari tick bab {draft_tick}."
                    ),
                }
            )

    # 4. Periksa resolusi janji alur bila ada.
    for upd in chapter_draft.get("promise_updates", []) or ():
        if not isinstance(upd, Mapping):
            continue
        pid = str(upd.get("promise_id", ""))
        promise = promises_by_id.get(pid)
        if promise is None:
            contradictions.append(
                {
                    "type": "unknown_promise",
                    "target": pid,
                    "tick": draft_tick,
                    "detail": f"Pembaruan janji alur merujuk promise_id tidak dikenal {pid!r}.",
                }
            )
            continue
        intro_tick = promise.get("introduced_tick", 0)
        upd_tick = upd.get("resolved_tick", draft_tick)
        if isinstance(intro_tick, int) and isinstance(upd_tick, int) and upd_tick < intro_tick:
            contradictions.append(
                {
                    "type": "timeline_anachronism",
                    "target": pid,
                    "tick": upd_tick,
                    "introduced_tick": intro_tick,
                    "detail": (
                        f"Janji {pid!r} diselesaikan pada tick {upd_tick} "
                        f"sebelum diperkenalkan pada tick {intro_tick}."
                    ),
                }
            )

    passed = len(contradictions) == 0
    return {
        "schema": SCHEMA,
        "chapter_id": chapter_id,
        "tick": draft_tick,
        "verdict": "lolos" if passed else "konflik",
        "passed": passed,
        "contradiction_count": len(contradictions),
        "contradiction_types": sorted({str(c["type"]) for c in contradictions}),
        "contradictions": contradictions,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gerbang konsistensi draf bab cerita (AG88)")
    parser.add_argument("--state", required=True, help="Path JSON ekspor story_state")
    parser.add_argument("--draft", required=True, help="Path JSON draf bab terstruktur")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    state_payload = json.loads(Path(args.state).read_text(encoding="utf-8"))
    draft_payload = json.loads(Path(args.draft).read_text(encoding="utf-8"))
    report = check_chapter_consistency(state_payload, draft_payload)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
