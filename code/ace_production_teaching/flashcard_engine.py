"""Buat kartu dari celah learner teramati dan fakta yang dapat dibuka dari sumber."""
from ._contracts import (ProductionError, anchor, cli, identifier, identity, integer,
                         items, obj, schema, source_bytes, text)
from .hint_engine import leaks
from .learner_model import posterior


def make_cards(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.flashcard-plan.v1", ("profile", "facts", "maximum", "weakness_below_bp"))
    profile = posterior(plan["profile"], identity(plan["profile"]), root)
    maximum = integer(plan["maximum"], "Jumlah kartu maksimum", 1, 100)
    floor = integer(plan["weakness_below_bp"], "Ambang rapuh", 1, 10000)
    candidates = []
    seen = set()
    skipped = []
    for row in items(plan["facts"], 250, 1):
        obj(row, ("id", "topic", "prompt", "answer", "source"))
        key = identifier(row["id"], "Kartu")
        topic = identifier(row["topic"], "Topik")
        if key in seen or topic not in profile["topic_posteriors"]:
            raise ProductionError("Kartu ganda atau topik belum dinilai.")
        seen.add(key)
        prompt = text(row["prompt"], "Prompt kartu", 350)
        answer = text(row["answer"], "Jawaban kartu", 220)
        if leaks(prompt, [answer]):
            raise ProductionError("Prompt kartu sudah memuat jawaban.")
        origin = obj(row["source"], ("path", "sha256", "line"))
        lines = source_bytes(root, origin["path"], origin["sha256"], 350000).decode("utf-8").splitlines()
        line = integer(origin["line"], "Baris jawaban", 1, len(lines))
        if answer not in lines[line - 1]:
            raise ProductionError("Jawaban kartu tidak ditemukan pada baris sumber.")
        stats = profile["topic_posteriors"][topic]
        estimate = stats["posterior_mean_bp"]
        if stats["evidence_status"] != "observed" or estimate >= floor:
            skipped.append({"id": key, "topic": topic, "reason": "not_observed" if stats["evidence_status"] != "observed" else "not_below_threshold"})
            continue
        card = {"id": key, "topic": topic, "front": prompt, "back": answer, "source": origin,
                "initial_review_date": profile["as_of"], "weakness_estimate_bp": estimate,
                "based_on_attempt_lines": [record["line"] for record in stats["evidence"]]}
        candidates.append((estimate, topic, key, card))
    candidates.sort()
    return {"schema": "ace.teaching.flashcard-deck.v1", "plan_sha256": expected, "cards": [data for _, _, _, data in candidates[:maximum]],
            "held": sorted(skipped, key=lambda item: item["id"]), "deferred": max(0, len(candidates) - maximum),
            "profile_sha256": identity(profile)}


if __name__ == "__main__":
    raise SystemExit(cli(make_cards, __doc__, rooted=True))
