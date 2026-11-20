"""Ukur tambatan proposal agar ref yang hilang terlihat sebelum dipakai."""

from collections.abc import Iterable
from typing import Protocol


class VerifiedReferences(Protocol):
    def verify_ref(self, ref: str) -> bool: ...


def check_anchors(refs: Iterable[str], store: VerifiedReferences) -> dict:
    """Hitung ref unik yang terverifikasi lewat antarmuka baca-saja."""
    if isinstance(refs, (str, bytes)):
        raise ValueError("refs wajib berupa koleksi referensi.")
    items = list(refs)
    if any(not isinstance(ref, str) or not ref.strip() for ref in items):
        raise ValueError("Referensi kosong atau tidak sah.")
    rows = []
    for ref in dict.fromkeys(items):
        try:
            verified = store.verify_ref(ref) is True
        except (LookupError, OSError):
            verified = False
        rows.append({"ref": ref, "status": "retrievable" if verified else "dangling"})
    hits = sum(row["status"] == "retrievable" for row in rows)
    return {"refs": rows, "score": hits / len(rows) if rows else 0,
            "status": "anchored" if hits == len(rows) and rows else "partial" if hits else "untethered"}
