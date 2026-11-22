"""Baca studi efek yang telah dicatat dan tolak penggandaan kelompok independen."""
from ._contracts import ResearchError, decode, identifier, integer, items, number, obj, schema, source_bytes, text


def effect_sizes(reference, root, minimum=2):
    obj(reference, ("path", "sha256"))
    ledger = decode(source_bytes(root, reference["path"], reference["sha256"], 500000))
    schema(ledger, "ace.institute.effect-series.v1", ("effect_kind", "studies"))
    effect = identifier(ledger["effect_kind"], "Ukuran efek")
    studies = {}
    groups = set()
    for index, row in enumerate(items(ledger["studies"], 100, minimum), 1):
        obj(row, ("id", "independence_group", "effect", "standard_error", "sample_size", "source_ref"))
        name = identifier(row["id"], "Studi")
        source = text(row["source_ref"], "Pointer studi")
        group = identifier(row["independence_group"], "Grup")
        if name in studies or group in groups:
            raise ResearchError("Studi atau grup efek digandakan.")
        value = number(row["effect"], "Ukuran efek")
        error = number(row["standard_error"], "Galat baku")
        if error <= 0:
            raise ResearchError("Galat baku harus positif.")
        groups.add(group)
        studies[name] = {"id": name, "independence_group": group, "effect": value, "error": error,
                         "sample_size": integer(row["sample_size"], "Ukuran sampel", 2, 10**8),
                         "pointer": {"ledger_row": index, "source_ref": source}}
    return effect, [studies[name] for name in sorted(studies)]
