"""Temukan ejaan dan gaya dengan aturan ID/EN yang berkasnya dapat diperiksa."""
from collections import defaultdict
import re
import unicodedata

from ._contracts import ProductionError, anchor, cli, decode, items, obj, schema, source_bytes, text


WORDS = re.compile(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*", re.UNICODE)
INLINE = re.compile(r"`[^`]+`|https?://[^\s]+")
PUNCTUATION = re.compile(r"[ \t]+(?=[,.;!?])")


def _normalize(word):
    return unicodedata.normalize("NFC", word).casefold()


def proofread(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.proof-plan.v1", ("draft", "language", "rules", "ignore"))
    locale = plan["language"]
    if locale not in ("id", "en"):
        raise ProductionError("Locale proofreading harus id atau en.")
    reference = obj(plan["rules"], ("path", "sha256"))
    stored = decode(source_bytes(root, reference["path"], reference["sha256"], 500000))
    schema(stored, "ace.production.word-rules.v1", ("languages",))
    surfaces = obj(stored["languages"], ("id", "en"))
    replacements = {}
    for rule in items(surfaces[locale], 300):
        obj(rule, ("wrong", "replacement", "source_ref"))
        old = _normalize(text(rule["wrong"], "Ejaan semula", 80))
        prefer = text(rule["replacement"], "Ejaan saran", 120)
        source = text(rule["source_ref"], "Pointer ejaan")
        if old in replacements or not WORDS.fullmatch(old) or _normalize(prefer) == old:
            raise ProductionError("Kata aturan ganda atau tak memiliki perubahan.")
        replacements[old] = (prefer, source)
    kept = {_normalize(text(value, "Istilah dipertahankan", 80)) for value in items(plan["ignore"], 120)}
    draft = obj(plan["draft"], ("path", "sha256"))
    raw = source_bytes(root, draft["path"], draft["sha256"], 800000)
    issues = []
    count = defaultdict(int)
    fence = None

    def issue(code, line, column, suggested, pointer=None):
        count[code] += 1
        issues.append({"rule": code, "line": line, "column": column + 1, "suggested": suggested, "source_ref": pointer})

    for number, original in enumerate(raw.decode("utf-8").splitlines(), 1):
        boundary = original.strip()[:3]
        if boundary in ("```", "~~~"):
            fence = boundary if fence is None else (None if fence == boundary else fence)
            continue
        if fence:
            continue
        body = INLINE.sub(lambda match: " " * len(match[0]), original)
        spans = list(WORDS.finditer(body))
        for match in PUNCTUATION.finditer(body):
            if INLINE.search(original[match.start():match.end()]) is None and not any(
                    span.start() <= match.start() < span.end() for span in INLINE.finditer(original)):
                issue("space_before_punctuation", number, match.start(), "")
        for index, match in enumerate(spans):
            old = _normalize(match[0])
            if old in replacements and old not in kept:
                new, proof = replacements[old]
                if match[0].istitle():
                    new = new.title()
                elif match[0].isupper():
                    new = new.upper()
                issue("word_rule", number, match.start(), new, proof)
            if index and old == _normalize(spans[index - 1][0]) and original[spans[index - 1].end():match.start()].isspace():
                issue("repeated_word", number, match.start(), "")
    issues.sort(key=lambda item: (item["line"], item["column"], item["rule"]))
    return {"schema": "ace.production.proofreading.v1", "plan_sha256": expected,
            "draft": draft, "rule_source": reference, "language": locale, "findings": issues,
            "counts": dict(sorted(count.items())), "basis": "local_dictionary_and_format_rules"}


if __name__ == "__main__":
    raise SystemExit(cli(proofread, __doc__, rooted=True))
