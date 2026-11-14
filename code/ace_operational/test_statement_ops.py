"""Round-2 lift tests: the statement-motion schema
(statement_ops), its discovery/admission, the pricing
adapter's motion path, the core re-exports, and the
lift manifest construction.

Synthetic tests only — no gate band is touched and
no discovery is run at scale. The gate's §3
replication guard is a separate, later stage.
"""
import ast
import hashlib
import shutil
import unittest
from pathlib import Path

from ace_operational import operator_discovery, statement_ops
from ace_operational.pricing_adapter import PRICING_ADAPTER
from ace_operational.pricing_substrate import pricing_variants
from ace_operational.statement_ops import (
    MANIFEST_PARAMS,
    SUBSTRATE_FREEZE_DIGEST,
    apply_motion,
    build_order_task,
    compute_lift_manifest,
    discover_motion_keys,
    enumerate_motion_variants,
    motion_key_fixes,
    motion_variants,
    statement_fingerprint,
)

# A pricing-shaped program and its statement_order
# defect: the tax AugAssign moved to directly after
# the opening assignment (Addendum 49's class).
REFERENCE = """\
def total(qty, price, tax_pct):
    subtotal = qty * price
    due = subtotal
    due += due * tax_pct // 100
    return due
"""

BUGGY = """\
def total(qty, price, tax_pct):
    subtotal = qty * price
    due += due * tax_pct // 100
    due = subtotal
    return due
"""

REPAIR_KEY = ("move_stmt", ("augassign", "due", "Add", "due"),
              ("return",))


def _ref(qty, price, tax_pct):
    subtotal = qty * price
    due = subtotal
    due += due * tax_pct // 100
    return due


def _order_task(task_id, shown, holdout):
    return {
        "task_id": task_id,
        "buggy_code": BUGGY,
        "shown_cases": shown,
        "shown_truth": [_ref(*c) for c in shown],
        "holdout_cases": holdout,
        "holdout_truth": [_ref(*c) for c in holdout],
        "defects": ["statement_order"],
    }


def _body(code):
    tree = ast.parse(code)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef))
    return fn.body


class TestEnumeration(unittest.TestCase):

    def test_repair_motion_is_the_only_variant(self):
        variants = enumerate_motion_variants(BUGGY)
        self.assertEqual(len(variants), 1)
        key, text = variants[0]
        self.assertEqual(key, REPAIR_KEY)
        self.assertEqual(
            text, ast.unparse(ast.parse(REFERENCE)))

    def test_never_after_return(self):
        for code in (BUGGY, REFERENCE):
            for _, text in enumerate_motion_variants(code):
                body = _body(text)
                ret = next(i for i, s in enumerate(body)
                           if isinstance(s, ast.Return))
                for i, stmt in enumerate(body):
                    if isinstance(stmt, (ast.Assign,
                                         ast.AugAssign)):
                        self.assertLess(i, ret)

    def test_use_before_def_motion_blocked(self):
        code = """\
def total(a, b):
    x = a + 1
    w = a * 3
    y = x * 2
    z = y + x + w
    return z
"""
        variants = enumerate_motion_variants(code)
        self.assertTrue(variants)  # w has legal motions
        for _, text in variants:
            lines = [ast.unparse(s) for s in _body(text)]
            z_at = next(i for i, ln in enumerate(lines)
                        if ln.startswith("z ="))
            y_at = next(i for i, ln in enumerate(lines)
                        if ln.startswith("y ="))
            w_at = next(i for i, ln in enumerate(lines)
                        if ln.startswith("w ="))
            self.assertLess(y_at, z_at)
            self.assertLess(w_at, z_at)

    def test_same_accumulator_reorder_allowed(self):
        # The def/use filter deliberately does NOT
        # block reorderings among statements mutating
        # the same accumulator — that reordering is
        # the schema family's semantic content.
        code = """\
def total(a, b):
    t = a
    t += b
    t += a * 2
    return t
"""
        variants = enumerate_motion_variants(code)
        swapped = """\
def total(a, b):
    t = a
    t += a * 2
    t += b
    return t
"""
        # The swapped order is enumerated (under the
        # first-generated key — the two motions that
        # produce this order deduplicate to one).
        self.assertIn(ast.unparse(ast.parse(swapped)),
                      [text for _, text in variants])
        self.assertIn(
            ("move_stmt", ("augassign", "t", "Add", "b"),
             ("return",)), [k for k, _ in variants])

    def test_enumerate_rejects_unparseable_and_multifunction(self):
        self.assertEqual(
            enumerate_motion_variants("def broken(:"), [])
        two = ("def f(a):\n    x = a\n    y = x\n"
               "    return y\n\n"
               "def g(a):\n    x = a\n    y = x\n"
               "    return y\n")
        self.assertEqual(enumerate_motion_variants(two), [])
        short = "def f(a):\n    x = a\n    return x\n"
        self.assertEqual(enumerate_motion_variants(short), [])


class TestFingerprints(unittest.TestCase):

    def test_fingerprint_shapes(self):
        body = _body(REFERENCE)
        self.assertEqual(statement_fingerprint(body[0]),
                         ("assign", "subtotal", "qty"))
        self.assertEqual(statement_fingerprint(body[2]),
                         ("augassign", "due", "Add", "due"))
        self.assertEqual(statement_fingerprint(body[3]),
                         ("return",))

    def test_fingerprint_excludes_constants(self):
        tpl = """\
def total(qty, price):
    subtotal = qty * price
    due = subtotal
    due += due * {rate} // 100
    return due
"""
        fps = {statement_fingerprint(s)
               for s in _body(tpl.format(rate=10))}
        fps2 = {statement_fingerprint(s)
                for s in _body(tpl.format(rate=20))}
        self.assertEqual(fps, fps2)
        buggy_tpl = """\
def total(qty, price):
    subtotal = qty * price
    due += due * {rate} // 100
    due = subtotal
    return due
"""
        keys1 = [k for k, _ in enumerate_motion_variants(
            buggy_tpl.format(rate=10))]
        keys2 = [k for k, _ in enumerate_motion_variants(
            buggy_tpl.format(rate=20))]
        self.assertEqual(keys1, keys2)

    def test_occurrence_suffix_disambiguates(self):
        code = """\
def total(a, b):
    t = a
    t += b
    t += b
    return t
"""
        fps = statement_ops._fingerprints(_body(code))
        self.assertEqual(fps[1], ("augassign", "t", "Add", "b"))
        self.assertEqual(fps[2],
                         ("augassign", "t", "Add", "b", "#2"))


class TestApplyMotion(unittest.TestCase):

    def test_apply_motion_round_trip(self):
        text = apply_motion(BUGGY, REPAIR_KEY)
        self.assertEqual(
            text, ast.unparse(ast.parse(REFERENCE)))

    def test_apply_motion_unknown_key(self):
        key = ("move_stmt", ("assign", "nope", "nope"),
               ("return",))
        self.assertIsNone(apply_motion(BUGGY, key))


class TestTaskConstruction(unittest.TestCase):

    def test_build_order_task_parity(self):
        # The ported construction, on sandbox-band
        # seeds: a built task is a statement_order
        # task whose repairing motion is enumerated
        # and reaches the reference program.
        built = None
        for seed in range(70000, 70010):
            built = build_order_task(seed)
            if built is not None:
                break
        self.assertIsNotNone(built)
        self.assertEqual(built["defects"], ["statement_order"])
        self.assertNotEqual(built["buggy_code"],
                            built["reference_code"])
        reference_text = ast.unparse(
            ast.parse(built["reference_code"]))
        self.assertIn(reference_text,
                      motion_variants(built["buggy_code"]))


class TestDiscovery(unittest.TestCase):

    def setUp(self):
        self.task1 = _order_task(
            "synthetic-order-1",
            shown=[(2, 100, 10), (3, 50, 10)],
            holdout=[(1, 200, 10), (5, 20, 10)])
        self.task2 = _order_task(
            "synthetic-order-2",
            shown=[(4, 25, 20), (2, 300, 20)],
            holdout=[(10, 10, 20), (1, 999, 20)])

    def test_motion_key_fixes_synthetic(self):
        self.assertTrue(motion_key_fixes(
            self.task1, PRICING_ADAPTER, REPAIR_KEY))

    def test_discover_admits_at_two_fixes(self):
        admitted = discover_motion_keys(
            [self.task1, self.task2], PRICING_ADAPTER)
        self.assertEqual(admitted, [REPAIR_KEY])

    def test_discover_below_threshold_admits_nothing(self):
        self.assertEqual(
            discover_motion_keys(
                [self.task1, self.task2], PRICING_ADAPTER,
                min_pool_fixes=3), [])
        self.assertEqual(
            discover_motion_keys(
                [self.task1], PRICING_ADAPTER), [])


class TestIntegrationSurface(unittest.TestCase):

    def test_core_reexports(self):
        self.assertEqual(
            operator_discovery.enumerate_motion_variants(BUGGY),
            enumerate_motion_variants(BUGGY))
        self.assertEqual(
            operator_discovery.apply_motion(BUGGY, REPAIR_KEY),
            apply_motion(BUGGY, REPAIR_KEY))
        task1 = _order_task(
            "synthetic-order-1",
            shown=[(2, 100, 10), (3, 50, 10)],
            holdout=[(1, 200, 10), (5, 20, 10)])
        task2 = _order_task(
            "synthetic-order-2",
            shown=[(4, 25, 20), (2, 300, 20)],
            holdout=[(10, 10, 20), (1, 999, 20)])
        self.assertEqual(
            operator_discovery.discover_motion_keys(
                [task1, task2], PRICING_ADAPTER),
            [REPAIR_KEY])

    def test_adapter_motion_path_and_baseline_unchanged(self):
        self.assertEqual(PRICING_ADAPTER.motion_variants(BUGGY),
                         motion_variants(BUGGY))
        # The frozen baseline arm is exactly the
        # substrate's own enumeration, as before.
        self.assertEqual(PRICING_ADAPTER.baseline_variants(BUGGY),
                         pricing_variants(BUGGY))
        self.assertEqual(
            PRICING_ADAPTER.baseline_catalog_id(),
            "pricing-substrate-v1:" + SUBSTRATE_FREEZE_DIGEST)


class TestManifest(unittest.TestCase):

    def test_manifest_constants_match_frozen_records(self):
        self.assertEqual(
            MANIFEST_PARAMS, "min_pool_fixes=2,max_rounds=6,frontier=4")
        self.assertEqual(
            SUBSTRATE_FREEZE_DIGEST,
            PRICING_ADAPTER.baseline_catalog_id().split(":", 1)[1])

    def test_manifest_deterministic_and_construction(self):
        digest = compute_lift_manifest()
        self.assertEqual(digest, compute_lift_manifest())
        self.assertEqual(len(digest), 64)
        base = Path(statement_ops.__file__).resolve().parent
        h = hashlib.sha256()
        for name in ("operator_discovery.py", "grid_adapter.py",
                     "pricing_adapter.py"):
            h.update((base / name).read_bytes())
        h.update(MANIFEST_PARAMS.encode("ascii"))
        h.update(SUBSTRATE_FREEZE_DIGEST.encode("ascii"))
        self.assertEqual(digest, h.hexdigest())

    def test_manifest_sensitive_to_component_bytes(self):
        import tempfile
        base = Path(statement_ops.__file__).resolve().parent
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for name in ("operator_discovery.py",
                         "grid_adapter.py", "pricing_adapter.py"):
                shutil.copy(base / name, tmp / name)
            before = compute_lift_manifest(root=tmp)
            with open(tmp / "pricing_adapter.py", "ab") as fh:
                fh.write(b"\n")
            after = compute_lift_manifest(root=tmp)
            self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
