"""Pilih register formal/kasual per kanal sambil menjaga parameter fakta tetap sama."""
import string

from ._contracts import PresenceError, anchor, cli, identifier, items, obj, schema, text

FORMATTER = string.Formatter()
def render(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.register-plan.v1", ("channel", "policy", "request", "facts", "templates"))
    channel = identifier(plan["channel"], "Kanal")
    policies = {}
    for row in items(plan["policy"], 100, 1):
        obj(row, ("channel", "mode", "allow_override"))
        key = identifier(row["channel"], "Kanal")
        if key in policies or row["mode"] not in ("formal", "casual") or type(row["allow_override"]) is not bool:
            raise PresenceError("Kebijakan register ganda atau salah.")
        policies[key] = row
    if channel not in policies:
        raise PresenceError("Kanal belum punya register.")
    selected = policies[channel]["mode"]
    request = plan["request"]
    if request not in (None, "formal", "casual"):
        raise PresenceError("Permintaan register tidak dikenal.")
    if request and policies[channel]["allow_override"]:
        selected = request
    if not isinstance(plan["facts"], dict) or not 1 <= len(plan["facts"]) <= 50:
        raise PresenceError("Fakta perlu pemetaan dalam batas.")
    facts = {identifier(key, "Slot"): text(value, "Isi fakta") for key, value in plan["facts"].items()}
    templates = obj(plan["templates"], ("formal", "casual"))
    for template in templates.values():
        fields = set()
        for _, name, spec, conversion in FORMATTER.parse(text(template, "Template register", 2000)):
            if name is not None:
                if spec or conversion:
                    raise PresenceError("Format register hanya mendukung slot sederhana.")
                fields.add(identifier(name, "Slot register"))
        if fields != facts.keys():
            raise PresenceError("Setiap register harus mempertahankan semua fakta.")
    return {"mode": selected, "text": templates[selected].format_map(facts), "fact_slots": sorted(facts)}

if __name__ == "__main__":
    raise SystemExit(cli(render, __doc__))
