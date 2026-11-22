"""Buat latihan kosakata dalam konteks dengan baris sumber dan distraktor terpisah."""
from random import Random
import re
import unicodedata

from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, source_bytes, text


def _fold(value):
    return unicodedata.normalize("NFC", value).casefold()


def train(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.vocab-plan.v1", ("document", "seed", "cards"))
    ref = obj(plan["document"], ("path", "sha256"))
    lines = source_bytes(root, ref["path"], ref["sha256"], 650000).decode("utf-8").splitlines()
    seed = integer(plan["seed"], "Seed kosakata", 0, 2**63 - 1)
    random = Random(seed)
    cards = []
    keys = []
    known = set()
    for row in items(plan["cards"], 100, 1):
        obj(row, ("id", "line", "target", "distractors", "gloss_ref"))
        key = identifier(row["id"], "Kartu kosakata")
        if key in known:
            raise ProductionError("Kartu kosakata ganda.")
        known.add(key)
        line = integer(row["line"], "Baris kosakata", 1, len(lines))
        target = text(row["target"], "Frasa sasaran", 85)
        source = text(lines[line - 1], "Kalimat sumber", 500)
        pattern = re.compile(r"(?<!\w)" + re.escape(target) + r"(?!\w)", re.I)
        hits = list(pattern.finditer(source))
        if len(hits) != 1:
            raise ProductionError("Konteks perlu kemunculan sasaran tunggal.")
        span = hits[0].span()
        choices = [target, *(text(value, "Distraktor", 80) for value in items(row["distractors"], 6, 2))]
        if len({_fold(option) for option in choices}) != len(choices):
            raise ProductionError("Opsi kosakata bertumpang tindih.")
        random.shuffle(choices)
        card = {"id": key, "prompt": source[:span[0]] + "____" + source[span[1]:], "line": line,
                "options": choices, "source_sha256": ref["sha256"]}
        cards.append(card)
        keys.append({"id": key, "position": choices.index(target), "gloss_ref": text(row["gloss_ref"], "Pointer glos"),
                     "prompt_sha256": identity(card)})
    return {"schema": "ace.teaching.vocab-exercises.v1", "plan_sha256": expected, "source": ref,
            "cards": cards, "instructor_key": keys, "key_sha256": identity(keys)}


if __name__ == "__main__":
    raise SystemExit(cli(train, __doc__, rooted=True))
