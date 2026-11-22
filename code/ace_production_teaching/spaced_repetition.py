"""Tentukan tanggal review dari receipt berurutan serta kurva interval yang eksplisit."""
from collections import defaultdict
from datetime import timedelta

from ._contracts import ProductionError, anchor, cli, day, decode, identifier, integer, items, obj, schema, source_bytes, text


def _update(card, stamps, initial, maximum):
    interval = initial
    steps = 0
    easiness = 2500
    lapses = 0
    trail = []
    for badge in stamps:
        grade = badge["quality"]
        effort = 5 - grade
        easiness = max(1300, easiness + 100 - effort * (80 + 20 * effort))
        if grade < 3:
            lapses += 1
            steps = 0
            interval = initial
        else:
            steps += 1
            if steps == 1:
                interval = initial
            elif steps == 2:
                interval = min(maximum, initial * 6)
            else:
                interval = min(maximum, (interval * easiness + 500) // 1000)
        trail.append({**badge, "interval_days": interval, "ease_milli": easiness})
    return {"card": card, "interval_days": interval, "lapses": lapses, "trail": trail}


def review_schedule(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.repetition-plan.v1", ("as_of", "cards", "receipts", "initial_days", "max_days"))
    today = day(plan["as_of"])
    interval = integer(plan["initial_days"], "Interval awal", 1, 30)
    maximum = integer(plan["max_days"], "Interval maksimum", interval, 730)
    cards = {}
    for item in items(plan["cards"], 300, 1):
        obj(item, ("id", "introduced", "source_ref"))
        key = identifier(item["id"], "Kartu")
        if key in cards:
            raise ProductionError("Kartu terjadwal ganda.")
        stamp = day(item["introduced"])
        if stamp > today:
            raise ProductionError("Kartu belum diperkenalkan pada tanggal penjadwalan.")
        cards[key] = (stamp, text(item["source_ref"], "Pointer kartu"))
    ref = obj(plan["receipts"], ("path", "sha256"))
    raw = source_bytes(root, ref["path"], ref["sha256"], 1500000)
    records = defaultdict(list)
    used = set()
    for line, item in enumerate(raw.splitlines(), 1):
        if line > 20000:
            raise ProductionError("Riwayat pengulangan melampaui anggaran.")
        if not item.strip():
            continue
        event = obj(decode(item), ("id", "card", "date", "quality", "source_ref"))
        key = identifier(event["id"], "Receipt")
        name = identifier(event["card"], "Kartu")
        stamp = day(event["date"])
        if key in used or name not in cards or not cards[name][0] <= stamp <= today:
            raise ProductionError("Receipt ganda, kartu tak dikenal, atau tanggal salah lingkup.")
        used.add(key)
        records[name].append({"id": key, "date": event["date"], "line": line,
                              "quality": integer(event["quality"], "Quality", 0, 5),
                              "source_ref": text(event["source_ref"], "Pointer review")})
    output = []
    for key, (created, origin) in sorted(cards.items()):
        stamps = sorted(records[key], key=lambda row: (row["date"], row["line"]))
        sample = _update(key, stamps, interval, maximum)
        target = day(stamps[-1]["date"]) + timedelta(days=sample["interval_days"]) if stamps else created
        remaining = (target - today).days
        output.append({**sample, "due": target.isoformat(), "days_to_due": remaining,
                       "is_due": remaining <= 0, "card_source_ref": origin})
    return {"schema": "ace.teaching.repetition-schedule.v1", "plan_sha256": expected, "as_of": plan["as_of"],
            "method": "specified_sm2_style_integer_interval", "receipts": ref,
            "cards": sorted(output, key=lambda row: (row["due"], row["card"]))}


if __name__ == "__main__":
    raise SystemExit(cli(review_schedule, __doc__, rooted=True))
