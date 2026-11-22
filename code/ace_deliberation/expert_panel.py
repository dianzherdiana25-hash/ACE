"""Susun panel dari bukti keahlian yang berlaku dan catatan konflik eksplisit.

Panel dipilih untuk memenuhi seluruh topik, batas biaya internal, dan
jumlah organisasi independen. Pencarian menguji kombinasi yang mungkin,
sehingga pilihan murah per topik tidak mengunci syarat lain. Operasi
menghasilkan rencana panel tanpa menghubungi peserta.
"""
from dataclasses import dataclass
from datetime import date
from itertools import combinations
import json
from pathlib import Path


MAX_CANDIDATES = 18
MAX_TOPICS = 12
MAX_SIZE = 8
MAX_BYTES = 3_000_000


class PanelError(ValueError):
    """Katalog ahli atau ketentuan panel tidak bisa diperiksa."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise PanelError("Field panel tidak sesuai skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise PanelError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise PanelError(f"{label} bukan teks UTF-8.")
    return value.strip()


def _number(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise PanelError(f"Nilai numerik harus {low}–{high}.")
    return value


def _date(value):
    if not isinstance(value, str):
        raise PanelError("Tanggal wajib teks ISO.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PanelError("Tanggal tidak sah.") from exc
    if parsed.isoformat() != value:
        raise PanelError("Tanggal wajib YYYY-MM-DD.")
    return parsed


def _topics(value, label, *, size=MAX_TOPICS):
    if not isinstance(value, list) or len(value) > size:
        raise PanelError(f"{label} wajib larik berbatas.")
    items = [_text(item, label) for item in value]
    if len(items) != len(set(items)):
        raise PanelError(f"{label} memuat label ganda.")
    return set(items)


@dataclass(frozen=True, slots=True)
class Credential:
    topic: str
    score: int
    ref: str
    valid_from: date
    expires_on: date

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("topic", "score", "source_ref", "valid_from", "expires_on"))
        opened, until = _date(raw["valid_from"]), _date(raw["expires_on"])
        if opened >= until:
            raise PanelError("Interval kredensial kosong atau terbalik.")
        return cls(_text(raw["topic"], "topik"), _number(raw["score"], 1, 100),
                   _text(raw["source_ref"], "sumber kredensial", 512), opened, until)


@dataclass(frozen=True, slots=True)
class Expert:
    id: str
    org: str
    cost: int
    conflict_topics: frozenset[str]
    credentials: tuple[Credential, ...]

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("id", "organization", "cost_units", "conflict_topics", "credentials"))
        rows = raw["credentials"]
        if not isinstance(rows, list) or len(rows) > MAX_TOPICS:
            raise PanelError("Kredensial melampaui batas.")
        credentials = tuple(Credential.from_dict(row) for row in rows)
        if len({item.topic for item in credentials}) != len(credentials):
            raise PanelError("Kredensial untuk topik yang sama ganda.")
        return cls(_text(raw["id"], "ID ahli"), _text(raw["organization"], "organisasi"),
                   _number(raw["cost_units"], 1, 10_000),
                   frozenset(_topics(raw["conflict_topics"], "konflik ahli")), credentials)


def _select(eligible, requirements, size, cap, diversity):
    best = None
    for count in range(diversity, min(size, len(eligible)) + 1):
        for combination in combinations(eligible, count):
            cost = sum(expert.cost for expert, _ in combination)
            if cost > cap or len({expert.org for expert, _ in combination}) < diversity:
                continue
            coverage = {topic: [] for topic in requirements}
            for expert, known in combination:
                for topic, credential in known.items():
                    coverage[topic].append(credential.score)
            if any(len(scores) < requirements[topic] for topic, scores in coverage.items()):
                continue
            # Keahlian tambahan setelah syarat terpenuhi tidak menaikkan objective.
            quality = sum(sum(sorted(scores, reverse=True)[:requirements[topic]])
                          for topic, scores in coverage.items())
            key = (-quality, cost, count, tuple(expert.id for expert, _ in combination))
            if best is None or key < best[0]:
                best = (key, combination)
    return best


def form_panel(raw):
    _shape(raw, ("request", "candidates"))
    request = raw["request"]
    _shape(request, ("as_of", "topics", "max_size", "max_cost_units", "min_organizations", "excluded_orgs"))
    as_of = _date(request["as_of"])
    size = _number(request["max_size"], 1, MAX_SIZE)
    budget = _number(request["max_cost_units"], 1, MAX_SIZE * 10_000)
    diversity = _number(request["min_organizations"], 1, size)
    excluded = _topics(request["excluded_orgs"], "organisasi dikecualikan", size=MAX_CANDIDATES)
    topics = request["topics"]
    if not isinstance(topics, dict) or not 1 <= len(topics) <= MAX_TOPICS:
        raise PanelError("Panel perlu peta topik.")
    requirements = {_text(topic, "topik"): _number(count, 1, size) for topic, count in topics.items()}
    if len(requirements) != len(topics):
        raise PanelError("Nama topik ganda.")
    pool = raw["candidates"]
    if not isinstance(pool, list) or len(pool) > MAX_CANDIDATES:
        raise PanelError("Katalog panel melampaui batas kandidat.")
    candidates = sorted((Expert.from_dict(row) for row in pool), key=lambda expert: expert.id)
    if len({expert.id for expert in candidates}) != len(candidates):
        raise PanelError("ID ahli ganda.")
    refs = [cred.ref for expert in candidates for cred in expert.credentials]
    if len(set(refs)) != len(refs):
        raise PanelError("Kredensial dipakai ulang di katalog.")

    eligible = []
    excluded_details = []
    for expert in candidates:
        known = {item.topic: item for item in expert.credentials
                 if item.topic in requirements and item.valid_from <= as_of < item.expires_on}
        conflicts = sorted(expert.conflict_topics & requirements.keys())
        if expert.org in excluded or conflicts or not known:
            reasons = []
            if expert.org in excluded:
                reasons.append("organization_excluded")
            if conflicts:
                reasons.append("conflicting_topic")
            if not known:
                reasons.append("no_current_credential")
            excluded_details.append({"id": expert.id, "reasons": reasons, "conflicting_topics": conflicts})
        else:
            eligible.append((expert, known))
    best = _select(eligible, requirements, size, budget, diversity)
    chosen = best[1] if best else ()
    members = [
        {"id": expert.id, "organization": expert.org, "cost_units": expert.cost,
         "topic_evidence": [{"topic": topic, "score": item.score, "source_ref": item.ref}
                            for topic, item in sorted(known.items())]}
        for expert, known in chosen
    ]
    return {
        "schema": "ace.expert-panel.v1", "as_of": as_of.isoformat(),
        "status": "selected" if best else "infeasible", "members": members, "excluded": excluded_details,
        "required_coverage": dict(sorted(requirements.items())),
        "coverage": {topic: sum(topic in known for _, known in chosen) for topic in sorted(requirements)},
        "organizations": sorted({expert.org for expert, _ in chosen}),
        "quality": -best[0][0] if best else None,
        "cost_units": sum(expert.cost for expert, _ in chosen),
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise PanelError("Berkas panel melampaui batas.")
        result = form_panel(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "selected")


if __name__ == "__main__":
    raise SystemExit(main())
