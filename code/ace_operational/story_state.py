"""Penyimpan terstruktur keadaan cerita & validator konsistensi internal (AG87).

Menyimpan empat komponen narasi terstruktur tanpa ketergantungan ke engine:
1. ``characters``: identitas, status (``alive``, ``dead``, ``missing``, ``departed``),
   lokasi, serta atribut tokoh.
2. ``timeline``: urutan kejadian berstempel waktu (``tick``) dan keterlibatan tokoh.
3. ``facts``: fakta dunia berinterval waktu ``[valid_from_tick, valid_until_tick)``.
4. ``promises``: janji alur yang belum terbayar (``open``) beserta status resolusinya.

Setiap pembaruan yang menimbulkan kontradiksi linimasa (mis. fakta bertabrakan pada
interval waktu tumpang-tindih, tokoh bertindak sesudah kematiannya, akibat terjadi
sebelum peristiwa sebabnya, atau janji dipenuhi sebelum diperkenalkan) ditolak
secara deterministik dengan ``StoryConsistencyError``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


SCHEMA = "ace.story-state.v1"
VALID_CHARACTER_STATUSES = frozenset({"alive", "dead", "missing", "departed"})
VALID_PROMISE_STATUSES = frozenset({"open", "fulfilled", "broken"})


class StoryConsistencyError(ValueError):
    """Galat ketika pembaruan atau keadaan cerita melanggar konsistensi linimasa."""


@dataclass
class CharacterRecord:
    character_id: str
    name: str
    status: str = "alive"
    status_tick: int = 0
    location: str | None = None
    traits: dict[str, Any] = field(default_factory=dict)
    updated_tick: int = 0


@dataclass
class TimelineEvent:
    event_id: str
    tick: int
    summary: str
    participants: list[str] = field(default_factory=list)
    location: str | None = None
    after_event_id: str | None = None
    outcomes: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldFact:
    fact_id: str
    subject: str
    predicate: str
    value: Any
    valid_from_tick: int
    valid_until_tick: int | None = None
    source_event_id: str | None = None


@dataclass
class PlotPromise:
    promise_id: str
    description: str
    introduced_tick: int
    due_by_tick: int | None = None
    status: str = "open"
    resolved_tick: int | None = None
    resolution_event_id: str | None = None
    related_characters: list[str] = field(default_factory=list)


def _require_non_empty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoryConsistencyError(f"{label} wajib berupa string tidak kosong.")
    return value.strip()


def _require_tick(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise StoryConsistencyError(f"{label} wajib integer >= 0 (didapat {value!r}).")
    return value


def _intervals_overlap(
    start_a: int,
    end_a: int | None,
    start_b: int,
    end_b: int | None,
) -> bool:
    """Periksa tumpang-tindih dua interval semi-terbuka [start, end)."""
    if end_a is not None and end_a <= start_b:
        return False
    if end_b is not None and end_b <= start_a:
        return False
    return True


class StoryStateStore:
    """Penyimpan keadaan narasi terstruktur dengan API kueri, pembaruan, dan validasi."""

    def __init__(self) -> None:
        self._characters: dict[str, CharacterRecord] = {}
        self._events: dict[str, TimelineEvent] = {}
        self._facts: dict[str, WorldFact] = {}
        self._promises: dict[str, PlotPromise] = {}

    def upsert_character(
        self,
        character_id: str,
        *,
        name: str,
        status: str = "alive",
        status_tick: int = 0,
        location: str | None = None,
        traits: Mapping[str, Any] | None = None,
        updated_tick: int | None = None,
    ) -> CharacterRecord:
        cid = _require_non_empty(character_id, "character_id")
        cname = _require_non_empty(name, "name")
        if status not in VALID_CHARACTER_STATUSES:
            raise StoryConsistencyError(
                f"status tokoh tidak valid: {status!r}; pilih dari {sorted(VALID_CHARACTER_STATUSES)}."
            )
        s_tick = _require_tick(status_tick, "status_tick")
        u_tick = s_tick if updated_tick is None else _require_tick(updated_tick, "updated_tick")
        if u_tick < s_tick:
            raise StoryConsistencyError(
                f"updated_tick ({u_tick}) tidak boleh lebih kecil dari status_tick ({s_tick})."
            )

        existing = self._characters.get(cid)
        if existing is not None and u_tick < existing.updated_tick:
            raise StoryConsistencyError(
                f"Pembaruan tokoh {cid!r} pada tick {u_tick} lebih lama dari pembaruan terakhir ({existing.updated_tick})."
            )

        if status == "dead":
            for ev in self._events.values():
                if cid in ev.participants and ev.tick >= s_tick:
                    raise StoryConsistencyError(
                        f"Tokoh {cid!r} tidak dapat ditandai mati pada tick {s_tick} karena sudah terlibat di event {ev.event_id!r} pada tick {ev.tick}."
                    )
            for fact in self._facts.values():
                if (
                    fact.subject == cid
                    and fact.predicate == "alive"
                    and fact.value is True
                    and _intervals_overlap(fact.valid_from_tick, fact.valid_until_tick, s_tick, None)
                ):
                    raise StoryConsistencyError(
                        f"Tokoh {cid!r} tidak dapat ditandai mati pada tick {s_tick}: bertentangan dengan fakta hidup {fact.fact_id!r}."
                    )
        elif status == "alive" and existing is not None and existing.status == "dead":
            if s_tick > existing.status_tick:
                raise StoryConsistencyError(
                    f"Tokoh {cid!r} sudah mati pada tick {existing.status_tick}; tidak dapat dihidupkan kembali pada tick {s_tick}."
                )

        merged_traits = dict(existing.traits) if existing is not None else {}
        if traits:
            merged_traits.update(dict(traits))
        record = CharacterRecord(
            character_id=cid,
            name=cname,
            status=status,
            status_tick=s_tick,
            location=location,
            traits=merged_traits,
            updated_tick=u_tick,
        )
        self._characters[cid] = record
        return record

    def add_event(
        self,
        event_id: str,
        *,
        tick: int,
        summary: str,
        participants: Sequence[str] = (),
        location: str | None = None,
        after_event_id: str | None = None,
        outcomes: Mapping[str, Any] | None = None,
    ) -> TimelineEvent:
        eid = _require_non_empty(event_id, "event_id")
        if eid in self._events:
            raise StoryConsistencyError(f"event_id duplikat: {eid!r}.")
        ev_tick = _require_tick(tick, "tick")
        ev_summary = _require_non_empty(summary, "summary")

        if after_event_id is not None:
            prior = self._events.get(after_event_id)
            if prior is None:
                raise StoryConsistencyError(
                    f"after_event_id {after_event_id!r} tidak ditemukan di linimasa."
                )
            if ev_tick < prior.tick:
                raise StoryConsistencyError(
                    f"Event {eid!r} (tick {ev_tick}) harus terjadi pada/setelah {after_event_id!r} (tick {prior.tick})."
                )

        part_list: list[str] = []
        for raw_pid in participants:
            pid = _require_non_empty(raw_pid, "participant")
            if pid not in self._characters:
                raise StoryConsistencyError(
                    f"Tokoh {pid!r} pada event {eid!r} belum terdaftar di store."
                )
            char = self._characters[pid]
            if char.status == "dead" and ev_tick >= char.status_tick:
                raise StoryConsistencyError(
                    f"Tokoh {pid!r} sudah mati sejak tick {char.status_tick}; tidak bisa berpartisipasi di event {eid!r} pada tick {ev_tick}."
                )
            if pid not in part_list:
                part_list.append(pid)

        event = TimelineEvent(
            event_id=eid,
            tick=ev_tick,
            summary=ev_summary,
            participants=part_list,
            location=location,
            after_event_id=after_event_id,
            outcomes=dict(outcomes or {}),
        )
        self._events[eid] = event
        return event

    def assert_fact(
        self,
        fact_id: str,
        *,
        subject: str,
        predicate: str,
        value: Any,
        valid_from_tick: int,
        valid_until_tick: int | None = None,
        source_event_id: str | None = None,
        supersede_prior: bool = False,
    ) -> WorldFact:
        fid = _require_non_empty(fact_id, "fact_id")
        if fid in self._facts:
            raise StoryConsistencyError(f"fact_id duplikat: {fid!r}.")
        subj = _require_non_empty(subject, "subject")
        pred = _require_non_empty(predicate, "predicate")
        from_tick = _require_tick(valid_from_tick, "valid_from_tick")
        until_tick = None
        if valid_until_tick is not None:
            until_tick = _require_tick(valid_until_tick, "valid_until_tick")
            if until_tick <= from_tick:
                raise StoryConsistencyError(
                    f"valid_until_tick ({until_tick}) wajib lebih besar dari valid_from_tick ({from_tick})."
                )

        if source_event_id is not None:
            src_ev = self._events.get(source_event_id)
            if src_ev is None:
                raise StoryConsistencyError(
                    f"source_event_id {source_event_id!r} tidak ditemukan di linimasa."
                )
            if from_tick < src_ev.tick:
                raise StoryConsistencyError(
                    f"Fakta {fid!r} mulai berlaku pada tick {from_tick} sebelum event sumbernya {source_event_id!r} (tick {src_ev.tick})."
                )

        if subj in self._characters:
            char = self._characters[subj]
            if char.status == "dead" and from_tick >= char.status_tick:
                if pred == "alive" and value is True:
                    raise StoryConsistencyError(
                        f"Fakta {fid!r} menyatakan tokoh {subj!r} hidup pada tick {from_tick}, padahal mati sejak tick {char.status_tick}."
                    )
                if pred == "location":
                    raise StoryConsistencyError(
                        f"Fakta lokasi untuk tokoh mati {subj!r} pada tick {from_tick} (>= status_tick {char.status_tick}) ditolak."
                    )

        to_close: list[WorldFact] = []
        for prior in self._facts.values():
            if prior.subject != subj or prior.predicate != pred:
                continue
            if not _intervals_overlap(prior.valid_from_tick, prior.valid_until_tick, from_tick, until_tick):
                continue
            if prior.value == value:
                continue
            if supersede_prior and prior.valid_from_tick < from_tick and prior.valid_until_tick is None:
                to_close.append(prior)
                continue
            raise StoryConsistencyError(
                f"Fakta {fid!r} ({subj}.{pred}={value!r} [{from_tick}, {until_tick})) bertentangan dengan fakta {prior.fact_id!r} ({prior.value!r} [{prior.valid_from_tick}, {prior.valid_until_tick}))."
            )

        for prior in to_close:
            prior.valid_until_tick = from_tick

        fact = WorldFact(
            fact_id=fid,
            subject=subj,
            predicate=pred,
            value=value,
            valid_from_tick=from_tick,
            valid_until_tick=until_tick,
            source_event_id=source_event_id,
        )
        self._facts[fid] = fact
        return fact

    def add_promise(
        self,
        promise_id: str,
        *,
        description: str,
        introduced_tick: int,
        due_by_tick: int | None = None,
        related_characters: Sequence[str] = (),
    ) -> PlotPromise:
        pid = _require_non_empty(promise_id, "promise_id")
        if pid in self._promises:
            raise StoryConsistencyError(f"promise_id duplikat: {pid!r}.")
        desc = _require_non_empty(description, "description")
        intro_tick = _require_tick(introduced_tick, "introduced_tick")
        due_tick = None
        if due_by_tick is not None:
            due_tick = _require_tick(due_by_tick, "due_by_tick")
            if due_tick < intro_tick:
                raise StoryConsistencyError(
                    f"due_by_tick ({due_tick}) tidak boleh sebelum introduced_tick ({intro_tick})."
                )
        chars = [_require_non_empty(c, "related_character") for c in related_characters]
        for c in chars:
            if c not in self._characters:
                raise StoryConsistencyError(f"Tokoh terkait janji alur {c!r} belum terdaftar.")

        promise = PlotPromise(
            promise_id=pid,
            description=desc,
            introduced_tick=intro_tick,
            due_by_tick=due_tick,
            status="open",
            related_characters=chars,
        )
        self._promises[pid] = promise
        return promise

    def resolve_promise(
        self,
        promise_id: str,
        *,
        status: str,
        resolved_tick: int,
        resolution_event_id: str | None = None,
    ) -> PlotPromise:
        pid = _require_non_empty(promise_id, "promise_id")
        promise = self._promises.get(pid)
        if promise is None:
            raise StoryConsistencyError(f"Janji alur {pid!r} tidak ditemukan.")
        if status not in {"fulfilled", "broken"}:
            raise StoryConsistencyError(
                f"Status resolusi wajib 'fulfilled' atau 'broken' (didapat {status!r})."
            )
        r_tick = _require_tick(resolved_tick, "resolved_tick")
        if r_tick < promise.introduced_tick:
            raise StoryConsistencyError(
                f"Janji {pid!r} tidak dapat diselesaikan pada tick {r_tick} sebelum diperkenalkan (tick {promise.introduced_tick})."
            )
        if resolution_event_id is not None:
            ev = self._events.get(resolution_event_id)
            if ev is None:
                raise StoryConsistencyError(f"resolution_event_id {resolution_event_id!r} tidak ditemukan.")
            if r_tick < ev.tick:
                raise StoryConsistencyError(
                    f"resolved_tick ({r_tick}) lebih awal dari event resolusi {resolution_event_id!r} (tick {ev.tick})."
                )

        promise.status = status
        promise.resolved_tick = r_tick
        promise.resolution_event_id = resolution_event_id
        return promise

    def get_character(self, character_id: str) -> CharacterRecord | None:
        return self._characters.get(character_id)

    def list_characters(self, *, status: str | None = None) -> list[CharacterRecord]:
        items = list(self._characters.values())
        if status is not None:
            items = [c for c in items if c.status == status]
        return sorted(items, key=lambda c: c.character_id)

    def query_timeline(
        self,
        *,
        min_tick: int | None = None,
        max_tick: int | None = None,
        participant: str | None = None,
    ) -> list[TimelineEvent]:
        events = list(self._events.values())
        if min_tick is not None:
            events = [e for e in events if e.tick >= min_tick]
        if max_tick is not None:
            events = [e for e in events if e.tick <= max_tick]
        if participant is not None:
            events = [e for e in events if participant in e.participants]
        return sorted(events, key=lambda e: (e.tick, e.event_id))

    def query_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        at_tick: int | None = None,
    ) -> list[WorldFact]:
        facts = list(self._facts.values())
        if subject is not None:
            facts = [f for f in facts if f.subject == subject]
        if predicate is not None:
            facts = [f for f in facts if f.predicate == predicate]
        if at_tick is not None:
            facts = [
                f
                for f in facts
                if f.valid_from_tick <= at_tick
                and (f.valid_until_tick is None or at_tick < f.valid_until_tick)
            ]
        return sorted(facts, key=lambda f: (f.valid_from_tick, f.fact_id))

    def unpaid_promises(self, *, overdue_at_tick: int | None = None) -> list[PlotPromise]:
        items = [p for p in self._promises.values() if p.status == "open"]
        if overdue_at_tick is not None:
            items = [p for p in items if p.due_by_tick is not None and overdue_at_tick > p.due_by_tick]
        return sorted(items, key=lambda p: (p.introduced_tick, p.promise_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "characters": {k: asdict(v) for k, v in sorted(self._characters.items())},
            "timeline": [asdict(e) for e in self.query_timeline()],
            "facts": [asdict(f) for f in self.query_facts()],
            "promises": [asdict(p) for p in sorted(self._promises.values(), key=lambda x: (x.introduced_tick, x.promise_id))],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StoryStateStore":
        """Rekonstruksi store dari dict dan memvalidasi seluruh konsistensi internalnya."""
        schema = payload.get("schema")
        if schema != SCHEMA:
            raise StoryConsistencyError(f"Schema story state tidak didukung: {schema!r}.")
        store = cls()
        raw_chars = payload.get("characters", {})
        if not isinstance(raw_chars, Mapping):
            raise StoryConsistencyError("characters wajib berupa object.")
        for cid, row in raw_chars.items():
            if not isinstance(row, Mapping):
                raise StoryConsistencyError(f"Entri tokoh {cid!r} wajib berupa object.")
            store.upsert_character(
                str(row.get("character_id", cid)),
                name=row["name"],
                status=row.get("status", "alive"),
                status_tick=row.get("status_tick", 0),
                location=row.get("location"),
                traits=row.get("traits"),
                updated_tick=row.get("updated_tick"),
            )

        raw_events = payload.get("timeline", [])
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)):
            raise StoryConsistencyError("timeline wajib berupa list.")
        # Validasi bertahap dalam urutan tick agar ketergantungan after_event_id konsisten.
        for row in sorted(raw_events, key=lambda item: (item.get("tick", 0), item.get("event_id", ""))):
            store.add_event(
                row["event_id"],
                tick=row["tick"],
                summary=row["summary"],
                participants=row.get("participants", ()),
                location=row.get("location"),
                after_event_id=row.get("after_event_id"),
                outcomes=row.get("outcomes"),
            )

        raw_facts = payload.get("facts", [])
        if not isinstance(raw_facts, Sequence) or isinstance(raw_facts, (str, bytes)):
            raise StoryConsistencyError("facts wajib berupa list.")
        for row in raw_facts:
            store.assert_fact(
                row["fact_id"],
                subject=row["subject"],
                predicate=row["predicate"],
                value=row["value"],
                valid_from_tick=row["valid_from_tick"],
                valid_until_tick=row.get("valid_until_tick"),
                source_event_id=row.get("source_event_id"),
            )

        raw_promises = payload.get("promises", [])
        if not isinstance(raw_promises, Sequence) or isinstance(raw_promises, (str, bytes)):
            raise StoryConsistencyError("promises wajib berupa list.")
        for row in raw_promises:
            promise = store.add_promise(
                row["promise_id"],
                description=row["description"],
                introduced_tick=row["introduced_tick"],
                due_by_tick=row.get("due_by_tick"),
                related_characters=row.get("related_characters", ()),
            )
            status = row.get("status", "open")
            if status != "open":
                store.resolve_promise(
                    promise.promise_id,
                    status=status,
                    resolved_tick=row["resolved_tick"],
                    resolution_event_id=row.get("resolution_event_id"),
                )
        return store


__all__ = [
    "CharacterRecord",
    "PlotPromise",
    "SCHEMA",
    "StoryConsistencyError",
    "StoryStateStore",
    "TimelineEvent",
    "WorldFact",
]
