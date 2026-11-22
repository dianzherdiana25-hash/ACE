"""Baca jatah harian vendor menurut zona reset dari angka yang diberikan eksplisit."""
from collections import Counter
from zoneinfo import ZoneInfo

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import instant

def quotas(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.quota-plan.v1", ("as_of", "providers", "usage"))
    as_of = instant(plan["as_of"])
    providers = {}
    for row in items(plan["providers"], 100, 1):
        obj(row, ("id", "limit", "zone"))
        key = identifier(row["id"], "Penyedia")
        if key in providers:
            raise PresenceError("Penyedia kuota ganda.")
        providers[key] = (integer(row["limit"], "Kuota harian", 0, 10_000_000), ZoneInfo(text(row["zone"], "Zona", 100)))
    used = Counter()
    ids = set()
    for row in items(plan["usage"], 5000):
        obj(row, ("id", "provider", "at", "units", "source"))
        key = identifier(row["id"], "Receipt kuota")
        provider = identifier(row["provider"], "Penyedia")
        stamp = instant(row["at"])
        units = integer(row["units"], "Unit tercatat", 1, 10_000_000)
        text(row["source"], "Bukti kuota")
        if key in ids or provider not in providers or stamp > as_of:
            raise PresenceError("Receipt ganda, masa depan, atau penyedia tak terdaftar.")
        ids.add(key)
        tz = providers[provider][1]
        if stamp.astimezone(tz).date() == as_of.astimezone(tz).date():
            used[provider] += units
    return {"providers": {key: {"day": as_of.astimezone(tz).date().isoformat(), "limit": limit,
                                 "used": used[key], "remaining": max(0, limit - used[key]), "over_cap": used[key] > limit}
                          for key, (limit, tz) in sorted(providers.items())}}

if __name__ == "__main__":
    raise SystemExit(cli(quotas, __doc__))
