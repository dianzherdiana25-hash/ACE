"""Jadwalkan penelaah dan penantang jurnal secara berimbang dari kalender ketersediaan."""
from collections import Counter
from datetime import timedelta

from ._contracts import ResearchError, anchor, cli, day, identifier, items, obj, schema, source_bytes, text


def schedule_club(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.journal-club-plan.v1", ("starting", "members", "readings"))
    start = day(plan["starting"])
    roster = {}
    for row in items(plan["members"], 60, 2):
        obj(row, ("id", "available", "roles"))
        name = identifier(row["id"], "Anggota")
        if name in roster:
            raise ResearchError("Anggota ganda.")
        availability = {day(value) for value in items(row["available"], 80)}
        roles = set(items(row["roles"], 2, 1))
        if not roles <= {"reviewer", "challenger"}:
            raise ResearchError("Peran klub belum didukung.")
        roster[name] = (roles, availability)
    readers = Counter()
    challengers = Counter()
    plan_rows = []
    used = set()
    for offset, row in enumerate(items(plan["readings"], 52, 1)):
        obj(row, ("id", "title", "path", "sha256", "prompts"))
        winner = identifier(row["id"], "Karya")
        if winner in used:
            raise ResearchError("Karya kajian ganda.")
        used.add(winner)
        stamp = start + timedelta(weeks=offset)
        source_bytes(root, row["path"], row["sha256"], 1_000_000)
        prompts = [text(value, "Pertanyaan kritis", 140) for value in items(row["prompts"], 10, 1)]
        participants = [name for name, (_, dates) in roster.items() if stamp in dates]
        options = [(readers[a] + challengers[b], readers[a] + challengers[a] + readers[b] + challengers[b], a, b)
                   for a in participants for b in participants if a != b
                   and "reviewer" in roster[a][0] and "challenger" in roster[b][0]]
        panel = None
        if options:
            _, _, review, critique = min(options)
            readers[review] += 1
            challengers[critique] += 1
            panel = {"reviewer": review, "challenger": critique}
        plan_rows.append({"date": stamp.isoformat(), "reading_id": winner, "title": text(row["title"], "Judul karya"),
                          "source": {"path": row["path"], "sha256": row["sha256"]}, "critical_questions": prompts,
                          "roles": panel, "status": "planned" if panel else "unfilled"})
    return {"schema": "ace.institute.journal-club.v1", "plan_sha256": expected, "method": "weekly_role_rotation",
            "sessions": plan_rows, "by_member": {key: {"reviewer": readers[key], "challenger": challengers[key]} for key in sorted(roster)}}


if __name__ == "__main__":
    raise SystemExit(cli(schedule_club, __doc__, rooted=True))
