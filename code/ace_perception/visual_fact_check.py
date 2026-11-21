"""Silangkan klaim visual dengan minimal dua asal bukti yang berbeda.

Klaim, rujukan pengukuran dan hash media dicocokkan secara eksplisit.
Dua penerbit dari kelompok asal sama atau byte media sama tidak
menambah dukungan independen. Bukti berlawanan ditampilkan dengan
rujukan, sehingga tidak tertutup oleh banyaknya dukungan.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perception_bench import _same, _scalar
from .perceptual_memory import _digest


MAX_ITEMS = 512


def _rows(raw, names):
    if not isinstance(raw, list) or len(raw) > MAX_ITEMS:
        raise ValueError("Jumlah record fakta visual di luar batas.")
    for row in raw:
        if not isinstance(row, dict) or set(row) != names:
            raise ValueError("Bentuk fakta visual tidak sah.")
        yield row


def _independent(rows):
    # Maximum bipartite matching antara kelompok asal dan hash file.
    groups = {}
    for row in rows:
        groups.setdefault(row["origin_group"], {}).setdefault(row["media_sha256"], row)
    chosen = {}

    def augment(group, visited):
        for media, row in sorted(groups[group].items()):
            if media in visited:
                continue
            visited.add(media)
            other = chosen.get(media)
            if other is None or augment(other["origin_group"], visited):
                chosen[media] = row
                return True
        return False

    for group in sorted(groups):
        augment(group, set())
    return sorted(chosen.values(), key=lambda row: (row["origin_group"], row["receipt_ref"]))


def check(plan, observations, anchor):
    source = _vision.spec(plan, "ace.perception-visual-claims.v1", ("plan_ref", "minimum_sources", "claims"))
    if _sha(source) != _digest(anchor):
        raise ValueError("Rencana klaim berbeda dari anchor.")
    limit = _integer(source["minimum_sources"], 2, 32, "Sumber independen minimum")
    claims, rows = {}, {}
    for row in _rows(source["claims"], {"id", "value", "claim_ref"}):
        key = _token(row["id"], "ID klaim")
        if key in claims:
            raise ValueError("Klaim ganda.")
        claims[key] = (_scalar(row["value"]), _token(row["claim_ref"], "Rujukan klaim"))
        rows[key] = []
    if not claims:
        raise ValueError("Rencana tidak mempunyai klaim terdaftar.")
    data = _vision.spec(observations, "ace.perception-visual-evidence.v1", ("observations",))
    refs = set()
    for row in _rows(data["observations"], {"claim_id", "value", "media_sha256", "origin_group", "receipt_ref"}):
        key = _token(row["claim_id"], "ID klaim pada bukti")
        pointer = _token(row["receipt_ref"], "Rujukan bukti")
        if key not in claims or pointer in refs:
            raise ValueError("Bukti ganda atau tidak menunjuk klaim.")
        refs.add(pointer)
        rows[key].append({"value": _scalar(row["value"]), "media_sha256": _digest(row["media_sha256"]),
                           "origin_group": _token(row["origin_group"], "Kelompok asal"), "receipt_ref": pointer})
    results = []
    for key, (value, pointer) in sorted(claims.items()):
        supporting, opposing = [], []
        for row in sorted(rows[key], key=lambda item: item["receipt_ref"]):
            (supporting if _same(value, row["value"]) else opposing).append(row)
        selected = _independent(supporting)
        status = "conflicting" if opposing else "supported" if len(selected) >= limit else "insufficient"
        results.append({"id": key, "claim_ref": pointer, "value": value, "status": status,
                        "independent_support": len(selected), "selected_sources": selected,
                        "support_receipts": [row["receipt_ref"] for row in supporting], "counterevidence": opposing})
    return {"schema": "ace.perception-visual-fact-check.v1", "plan_sha256": anchor,
            "plan_ref": _token(source["plan_ref"], "Rujukan rencana"), "minimum_sources": limit,
            "observations_sha256": sha256(observations).hexdigest(), "claims": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = check(_raster.read(args.plan, _vision.MAX_SPEC_BYTES),
                       _raster.read(args.observations, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(row["status"] != "supported" for row in result["claims"]))


if __name__ == "__main__":
    raise SystemExit(main())
