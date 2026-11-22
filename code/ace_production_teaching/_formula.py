"""Parser formula spreadsheet terbatas dengan referensi dan aritmetika Decimal."""
from decimal import Decimal, ROUND_HALF_UP
import re

from ._contracts import ProductionError, number


CELL = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,4})")
TOKEN = re.compile(r"[0-9]+(?:\.[0-9]+)?|[A-Z][A-Z0-9]*|[+\-*/^(),:]", re.ASCII)
FUNCTIONS = ("SUM", "COUNT", "AVERAGE", "MIN", "MAX", "ROUND")


def address(value):
    if not isinstance(value, str) or not CELL.fullmatch(value):
        raise ProductionError("Alamat sel perlu bentuk A1 kanonis.")
    name, row = CELL.fullmatch(value).groups()
    col = 0
    for char in name:
        col = col * 26 + ord(char) - ord("A") + 1
    if col > 64 or int(row) > 1000:
        raise ProductionError("Alamat sel di luar batas lembar lokal.")
    return int(row), col


def locator(row, column):
    result = ""
    while column:
        rem, index = divmod(column - 1, 26)
        result = chr(ord("A") + index) + result
        column = rem
    return result + str(row)


class Formula:
    def __init__(self, value):
        if not isinstance(value, str) or not value.startswith("=") or len(value) > 300:
            raise ProductionError("Formula perlu awalan = dan panjang dalam batas.")
        self.source = value[1:].upper().replace(" ", "")
        self.tokens = TOKEN.findall(self.source)
        if not self.tokens or len(self.tokens) > 120 or "".join(self.tokens) != self.source:
            raise ProductionError("Formula memiliki token di luar subset yang disetujui.")
        self.offset = 0
        self.tree = self._expression(0)
        if self._peek():
            raise ProductionError("Ada token formula yang tidak terpakai.")

    def _peek(self):
        return self.tokens[self.offset] if self.offset < len(self.tokens) else ""

    def _eat(self, token=None):
        current = self._peek()
        if not current or token is not None and current != token:
            raise ProductionError("Urutan token formula tidak sah.")
        self.offset += 1
        return current

    def _expression(self, threshold):
        powers = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}
        current = self._eat()
        if current in ("+", "-"):
            node = ("negate" if current == "-" else "positive", self._expression(4))
        elif current == "(":
            node = self._expression(0)
            self._eat(")")
        elif current[0].isdigit():
            node = ("literal", number(current, "Literal formula"))
        elif current in FUNCTIONS:
            self._eat("(")
            args = []
            if self._peek() != ")":
                while True:
                    if self.offset + 1 < len(self.tokens) and CELL.fullmatch(self._peek()) and self.tokens[self.offset + 1] == ":":
                        low = self._eat()
                        self._eat(":")
                        top = self._eat()
                        args.append(("range", address(low), address(top)))
                    else:
                        args.append(self._expression(0))
                    if self._peek() != ",":
                        break
                    self._eat(",")
            self._eat(")")
            node = ("function", current, args)
        else:
            node = ("ref", address(current))
        while self._peek() in powers and powers[self._peek()] >= threshold:
            op = self._eat()
            strength = powers[op] + 1
            node = ("binary", op, node, self._expression(strength))
        return node


def _numeric(raw):
    if raw is None:
        return Decimal(0)
    if not isinstance(raw, Decimal):
        raise ProductionError("Formula aritmetika mengacu sel nonnumerik.")
    return raw


def evaluate(tree, lookup):
    kind, *tail = tree
    if kind == "literal":
        return tail[0]
    if kind == "ref":
        return lookup(tail[0])
    if kind in ("negate", "positive"):
        result = _numeric(evaluate(tail[0], lookup))
        return -result if kind == "negate" else result
    if kind == "binary":
        op, left, right = tail
        a, b = _numeric(evaluate(left, lookup)), _numeric(evaluate(right, lookup))
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if not b:
                raise ProductionError("Formula mencoba membagi dengan nol.")
            return a / b
        if b % 1 or abs(b) > 12 or not a and b < 0:
            raise ProductionError("Pangkat formula perlu integer antara -12 dan 12.")
        return a ** int(b)
    name, group = tail
    args = []
    for node in group:
        if node[0] == "range":
            (_, (y1, x1), (y2, x2)) = node
            cells = (y2 - y1 + 1) * (x2 - x1 + 1)
            if x2 < x1 or y2 < y1 or cells > 2000:
                raise ProductionError("Rentang formula tidak sah atau terlalu besar.")
            args.extend(value for y in range(y1, y2 + 1) for x in range(x1, x2 + 1)
                        if isinstance(value := lookup((y, x)), Decimal))
        else:
            value = evaluate(node, lookup)
            if value is not None and (node[0] != "ref" or isinstance(value, Decimal)):
                args.append(_numeric(value))
    if name == "ROUND":
        if len(args) != 2 or args[1] % 1 or abs(args[1]) > 8:
            raise ProductionError("ROUND butuh angka serta jumlah tempat desimal dalam batas.")
        return args[0].quantize(Decimal(1).scaleb(-int(args[1])), rounding=ROUND_HALF_UP)
    if name == "COUNT":
        return Decimal(len(args))
    total = sum(args, Decimal(0))
    if name == "SUM":
        return total
    if not args:
        raise ProductionError("Fungsi agregat memerlukan setidaknya satu nilai numerik.")
    if name == "AVERAGE":
        return total / len(args)
    return (min if name == "MIN" else max)(args)
