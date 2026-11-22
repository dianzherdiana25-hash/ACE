"""Render grafik vektor dengan sumbu, skala numerik, dan metadata sumber yang eksplisit."""
import argparse
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from hashlib import sha256
from pathlib import Path
import sys

from ._artifacts import a, e
from ._contracts import ProductionError, anchor, canonical, decode, fmt, integer, items, number, obj, read, schema, text


NS = "http://www.w3.org/2000/svg"


def _axis(low, high):
    if low > high:
        raise ProductionError("Skala vertikal terbalik.")
    if low == high:
        margin = max(Decimal(1), abs(low) / 5)
        return low - margin, high + margin
    rough = (high - low) / 5
    magnitude = Decimal(10) ** rough.adjusted()
    quantum = next(magnitude * factor for factor in (1, 2, 5, 10) if magnitude * factor >= rough)
    return (low / quantum).to_integral_value(rounding=ROUND_FLOOR) * quantum, (
        high / quantum).to_integral_value(rounding=ROUND_CEILING) * quantum


def _metric(bound, value):
    low, high = bound
    if not low <= value <= high:
        raise ProductionError("Nilai di luar rentang sumbu yang ditetapkan.")
    return (value - low) / (high - low)


def make_chart(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.production.chart-plan.v1", ("title", "kind", "width", "height", "y_label", "points", "y_axis"))
    title = text(plan["title"], "Judul", 90)
    label = text(plan["y_label"], "Satuan vertikal", 45)
    kind = plan["kind"]
    if kind not in ("bar", "line"):
        raise ProductionError("Jenis grafik perlu bar atau line.")
    width_px = integer(plan["width"], "Lebar", 320, 1600)
    height = integer(plan["height"], "Tinggi", 220, 1000)
    points = []
    seen = set()
    for row in items(plan["points"], 16, 2):
        obj(row, ("label", "value", "source_ref"))
        name = text(row["label"], "Label titik", 16)
        if name in seen:
            raise ProductionError("Nama titik ganda.")
        seen.add(name)
        points.append((name, number(row["value"], "Nilai titik"), text(row["source_ref"], "Sumber titik")))
    vals = [row[1] for row in points]
    if plan["y_axis"] is None:
        low, top = min(vals), max(vals)
        if kind == "bar":
            low, top = min(low, 0), max(top, 0)
        bounds = _axis(Decimal(low), Decimal(top))
    else:
        axis = obj(plan["y_axis"], ("min", "max"))
        bounds = tuple(number(axis[key], "Sumbu") for key in ("min", "max"))
        if bounds[0] >= bounds[1]:
            raise ProductionError("Batas minimum sumbu perlu lebih kecil.")
    if kind == "bar" and not bounds[0] <= 0 <= bounds[1]:
        raise ProductionError("Grafik bar wajib memakai baseline nol.")
    left, right = 76, width_px - 24
    ceiling, floor = 69, height - 48
    plot_height = floor - ceiling
    section = Decimal(right - left) / len(points)
    if any(len(row[0]) * 7 > section for row in points):
        raise ProductionError("Lebar grafik tidak muat untuk label tanpa tumpang tindih.")
    coords = []
    elements = []
    for idx in range(6):
        value = bounds[0] + (bounds[1] - bounds[0]) * idx / 5
        y = floor - idx * plot_height // 5
        elements.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#D9E1EA"/>'
                        f'<text x="{left-9}" y="{y+4}" text-anchor="end" font-size="12">{e(fmt(value.quantize(Decimal("0.000001"))))}</text>')
    if kind == "bar":
        zero = int(floor - _metric(bounds, Decimal(0)) * plot_height)
    for index, (name, value, pointer) in enumerate(points):
        x = int(left + (Decimal(index) + Decimal("0.5")) * section)
        y = int(floor - _metric(bounds, value) * plot_height)
        coords.append({"label": name, "value": fmt(value), "x": x, "y": y, "source_ref": pointer})
        elements.append(f'<text x="{x}" y="{floor+21}" text-anchor="middle" font-size="12">{e(name)}</text>')
        if kind == "bar":
            span = max(3, int(section * Decimal("0.62")))
            elements.append(f'<rect x="{x-span//2}" y="{min(y, zero)}" width="{span}" height="{abs(y-zero)}" fill="#277982">'
                            f"<title>{e(name)} {e(fmt(value))} · {e(pointer)}</title></rect>")
    if kind == "line":
        path = " ".join(f'{entry["x"]},{entry["y"]}' for entry in coords)
        elements.append(f'<polyline points={a(path)} stroke="#277982" stroke-width="3" fill="none"/>')
        for value in coords:
            elements.append(f'<circle cx="{value["x"]}" cy="{value["y"]}" r="4" fill="#277982">'
                            f'<title>{e(value["label"])} {e(value["value"])} · {e(value["source_ref"])}</title></circle>')
    unit_text = f'<text x="{left}" y="46" font-size="13">{e(label)}</text>'
    result = (f'<svg xmlns="{NS}" width="{width_px}" height="{height}" role="img" aria-labelledby="chart_title chart_desc">'
              f'<title id="chart_title">{e(title)}</title><desc id="chart_desc">Grafik {kind} {e(label)}</desc>'
              f'<rect x="0" y="0" width="{width_px}" height="{height}" fill="#FFFFFF"/>'
              f'<g font-family="sans-serif" fill="#172E40"><text x="{left}" y="28" font-size="20">{e(title)}</text>{unit_text}'
              + "".join(elements) + "</g></svg>\n").encode()
    return result, {"schema": "ace.production.chart-receipt.v1", "plan_sha256": expected,
                    "chart_sha256": sha256(result).hexdigest(), "kind": kind, "y_axis": [fmt(raw) for raw in bounds],
                    "y_label": label, "plot": [left, ceiling, right, floor], "points": coords}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        raw, proof = make_chart(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(raw)
        sys.stdout.buffer.write(canonical(proof) + b"\n")
    except (OSError, ValueError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
