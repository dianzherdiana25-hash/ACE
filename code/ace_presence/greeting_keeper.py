"""Pilih sapaan sesuai izin dan preferensi yang masih berlaku tanpa menebak identitas."""
import re

from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text

def greeting(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.greeting.v1", ("receiver", "as_of", "locale", "choices", "fallbacks"))
    key = identifier(plan["receiver"], "Penerima")
    stamp = day(plan["as_of"])
    fallback = obj(plan["fallbacks"], ("id", "en"))
    for value in fallback.values():
        text(value, "Sapaan umum", 120)
    locale = plan["locale"]
    if locale not in fallback:
        raise PresenceError("Lokal sapaan belum dikenal.")
    candidates = []
    for row in items(plan["choices"], 1500):
        obj(row, ("receiver", "locale", "opening", "from", "until", "permission", "source"))
        person = identifier(row["receiver"], "Pemberi izin sapaan")
        start, stop = day(row["from"]), day(row["until"])
        opening = text(row["opening"], "Sapaan", 120)
        text(row["source"], "Bukti izin")
        if (start >= stop or row["locale"] not in fallback or type(row["permission"]) is not bool
                or re.search(r"[{}<>]", opening)):
            raise PresenceError("Sapaan atau rentang izin tidak sah.")
        if person == key and row["locale"] == locale and start <= stamp:
            candidates.append((start, stop, row))
    candidates.sort(key=lambda value: value[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise PresenceError("Sapaan pada tanggal yang sama ambigu.")
    if candidates and stamp < candidates[0][1] and candidates[0][2]["permission"]:
        item = candidates[0][2]
        return {"opening": item["opening"], "personalized": True, "source": item["source"]}
    return {"opening": fallback[locale], "personalized": False, "source": None}

if __name__ == "__main__":
    raise SystemExit(cli(greeting, __doc__))
