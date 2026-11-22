"""Nilai fungsi latihan melalui interpreter AST berbatas, tanpa eksekusi Python umum."""
import ast
import operator

from ._contracts import ProductionError, anchor, canonical, cli, identifier, integer, items, obj, schema, source_bytes, text


BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.FloorDiv: operator.floordiv,
       ast.Mod: operator.mod}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Gt: operator.gt, ast.GtE: operator.ge,
       ast.Lt: operator.lt, ast.LtE: operator.le}
FUNCTIONS = {"min", "max", "len", "range", "sum", "abs"}
NODES = {ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Name, ast.Load, ast.Store, ast.Return,
         ast.Assign, ast.For, ast.If, ast.Constant, ast.BinOp, ast.Compare, ast.Call, ast.UnaryOp, ast.USub,
         ast.List, ast.Tuple, ast.Subscript, *BIN, *CMP}


def _value(raw):
    remaining = 1600

    def bounded(value, depth):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 9:
            raise ProductionError("Ukuran gabungan nilai interpreter melampaui batas.")
        if type(value) in (int, bool):
            if abs(value) > 10**12:
                raise ProductionError("Intermediary melebihi batas integer.")
            return value
        if isinstance(value, (tuple, list, range)) and len(value) <= 120:
            return tuple(bounded(item, depth + 1) for item in value)
        raise ProductionError("Subset interpreter hanya mendukung integer, bool, dan koleksi kecil.")

    return bounded(raw, 0)


class _Return(Exception):
    def __init__(self, selected):
        self.value = selected


class Interpreter:
    def __init__(self, function, arguments, budget):
        self.variables = dict(zip((part.arg for part in function.args.args), arguments, strict=True))
        self.budget = budget

    def _tick(self):
        self.budget -= 1
        if self.budget < 0:
            raise ProductionError("Batas langkah interpreter tercapai.")

    def expression(self, node):
        self._tick()
        if isinstance(node, ast.Constant):
            return _value(node.value)
        if isinstance(node, ast.Name):
            if node.id not in self.variables:
                raise ProductionError("Nama belum didefinisikan.")
            return self.variables[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return _value([self.expression(item) for item in node.elts])
        if isinstance(node, ast.UnaryOp):
            return _value(-self.expression(node.operand))
        if isinstance(node, ast.BinOp):
            first, second = self.expression(node.left), self.expression(node.right)
            if type(first) is not int or type(second) is not int:
                raise ProductionError("Operasi biner hanya pada integer.")
            return _value(BIN[type(node.op)](first, second))
        if isinstance(node, ast.Compare):
            left = self.expression(node.left)
            for op, side in zip(node.ops, node.comparators, strict=True):
                right = self.expression(side)
                if not CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Subscript):
            sequence, at = self.expression(node.value), self.expression(node.slice)
            if not isinstance(sequence, tuple) or type(at) is not int:
                raise ProductionError("Indeks subset hanya pada koleksi.")
            return sequence[at]
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords:
            raise ProductionError("Panggilan tidak berada pada daftar fungsi latihan.")
        arguments = [self.expression(item) for item in node.args]
        name = node.func.id
        if name == "range":
            return _value(range(*arguments))
        dispatch = {"min": min, "max": max, "len": len, "sum": sum, "abs": abs}
        return _value(dispatch[name](*arguments))

    def block(self, body):
        for node in body:
            self._tick()
            if isinstance(node, ast.Return):
                raise _Return(self.expression(node.value))
            if isinstance(node, ast.Assign):
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    raise ProductionError("Assignment perlu satu nama.")
                self.variables[node.targets[0].id] = self.expression(node.value)
            elif isinstance(node, ast.If):
                self.block(node.body if self.expression(node.test) else node.orelse)
            elif isinstance(node, ast.For):
                if not isinstance(node.target, ast.Name) or node.orelse:
                    raise ProductionError("Iterasi perlu satu nama tanpa else.")
                data = self.expression(node.iter)
                if not isinstance(data, tuple) or len(data) > 120:
                    raise ProductionError("Iterasi memerlukan urutan pendek.")
                for value in data:
                    self._tick()
                    self.variables[node.target.id] = value
                    self.block(node.body)
            else:
                raise ProductionError("Statement latihan belum didukung.")


def _parse(code, name):
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        raise ProductionError("Kode latihan tidak bisa diparse.") from error
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ProductionError("Latihan memerlukan satu fungsi saja.")
    function = tree.body[0]
    nodes = list(ast.walk(function))
    if len(nodes) > 250 or any(type(node) not in NODES for node in nodes):
        raise ProductionError("AST latihan keluar subset yang diizinkan.")
    if (function.name != name or function.decorator_list or function.returns or function.type_comment
            or getattr(function, "type_params", ()) or function.args.posonlyargs or function.args.kwonlyargs
            or function.args.vararg or function.args.kwarg or function.args.defaults
            or any(value.annotation for value in function.args.args)):
        raise ProductionError("Signature fungsi tidak cocok dengan subset tutor.")
    return function


def grade_program(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.code-plan.v1", ("submission", "function", "tests", "step_cap"))
    link = obj(plan["submission"], ("path", "sha256"))
    source = source_bytes(root, link["path"], link["sha256"], 8000).decode("utf-8")
    name = identifier(plan["function"], "Nama fungsi")
    cap = integer(plan["step_cap"], "Batas langkah", 10, 50000)
    function = _parse(source, name)
    reports = []
    seen = set()
    for row in items(plan["tests"], 200, 1):
        obj(row, ("id", "arguments", "expected", "source_ref"))
        key = identifier(row["id"], "Kasus")
        if key in seen:
            raise ProductionError("Kasus tes berulang.")
        seen.add(key)
        raw = items(row["arguments"], 12)
        if len(raw) != len(function.args.args):
            raise ProductionError("Jumlah argumen tes salah.")
        arguments = [_value(value) for value in raw]
        answer = _value(row["expected"])
        result = None
        error = None
        try:
            Interpreter(function, arguments, cap).block(function.body)
            error = "missing_return"
        except _Return as finish:
            result = finish.value
        except (ArithmeticError, IndexError, OverflowError, TypeError, ValueError) as problem:
            error = type(problem).__name__
        reports.append({"id": key, "source_ref": text(row["source_ref"], "Pointer soal"), "result": result,
                        "error": error, "pass": error is None and canonical(result) == canonical(answer)})
    return {"schema": "ace.teaching.code-grade.v1", "plan_sha256": expected, "submission": link,
            "mode": "bounded_ast_interpreter", "cases": reports, "pass_count": sum(row["pass"] for row in reports)}


if __name__ == "__main__":
    raise SystemExit(cli(grade_program, __doc__, rooted=True))
