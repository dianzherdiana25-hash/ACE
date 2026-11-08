"""Self-contained source and target software repair bug banks and unlabeled perturbation specs.

Custody boundary:
- Contains ONLY buggy source modules, public reproduction/dev tests, and unlabeled
  behavioral perturbation generators.
- Contains ZERO terminal holdout tests and NEVER imports `evaluator.py`.
- `PublicUnitView` strips `family_truth` and `category` so `RepairEngine` never
  observes ground-truth bug family labels or `nominal`/`OOD_abstain`/`TRAP_overfit` tags.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
from typing import Any

PRESCORE_COMMIT = "5369e8ea1d3fe03cd96c4bc9a3108684aed150cf"
PRESCORE_DOC_SHA256 = "7586ac81e3899347845a5e9a29320bb2c3624c3862e1dbd42367e8f25165de00"

FAMILIES = ("boundary_index", "parsing", "state_invariant", "data_dependency")
ARMS = ("R_rule", "R_fixed", "R_fresh", "R_ace")
BUDGET_K = 16


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_digest(value: Any) -> str:
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class DevTestCase:
    """Public reproduction test case.

    `mode`:
      - "call": single invocation `fn(*args)` == `expected` (or raises `expected_exc`),
        plus caller argument immutability check when `forbid_arg_mutation=True`.
      - "sequence": sequential invocations `[fn(*call_args) for call_args in args]`
        in the same interpreter state compared against `expected` list.
    """

    name: str
    mode: str
    args: tuple[Any, ...]
    expected: Any = None
    expected_exc: str | None = None
    forbid_arg_mutation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "args": list(self.args),
            "expected": self.expected,
            "expected_exc": self.expected_exc,
            "forbid_arg_mutation": self.forbid_arg_mutation,
        }


@dataclass(frozen=True)
class PerturbationSpec:
    """Unlabeled behavioral perturbation probes for Stage 7 (`Verify`).

    Contains ZERO ground-truth expected outputs.
    - `diverse_inputs`: valid argument tuples spanning varied scales/shapes.
    - `equivalence_pairs`: pairs `(args_a, args_b)` whose outputs must agree (`f(*a) == f(*b)`).
    - `expect_variation`: whether `diverse_inputs` span multiple output equivalence classes
      (rejects constant-collapse overfit patches when True).
    - `check_call_isolation`: whether repeated invocations in the same process must be
      deterministic and leave caller mutable arguments unmutated.
    """

    diverse_inputs: tuple[tuple[Any, ...], ...]
    equivalence_pairs: tuple[tuple[tuple[Any, ...], tuple[Any, ...]], ...]
    expect_variation: bool = True
    check_call_isolation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "diverse_inputs": [list(a) for a in self.diverse_inputs],
            "equivalence_pairs": [[list(a), list(b)] for a, b in self.equivalence_pairs],
            "expect_variation": self.expect_variation,
            "check_call_isolation": self.check_call_isolation,
        }


@dataclass(frozen=True)
class PublicUnitView:
    """Strictly leak-free problem specification exposed to `RepairEngine`."""

    unit_id: str
    entrypoint: str
    buggy_source: str
    dev_tests: tuple[DevTestCase, ...]
    perturbation_spec: PerturbationSpec

    @property
    def source_sha256(self) -> str:
        return sha256_digest(self.buggy_source)


@dataclass(frozen=True)
class CorpusUnit:
    unit_id: str
    split: str  # "source" | "target"
    category: str  # "nominal" | "OOD_abstain" | "TRAP_overfit"
    family_truth: str
    entrypoint: str
    buggy_source: str
    dev_tests: tuple[DevTestCase, ...]
    perturbation_spec: PerturbationSpec

    def public_view(self) -> PublicUnitView:
        return PublicUnitView(
            unit_id=self.unit_id,
            entrypoint=self.entrypoint,
            buggy_source=self.buggy_source,
            dev_tests=self.dev_tests,
            perturbation_spec=self.perturbation_spec,
        )


def _build_source_units() -> tuple[CorpusUnit, ...]:
    rng = random.Random(20261107)

    # S01: boundary_index — off-by-one upper bound in range(len(values) - k)
    s01_src = """def validate_window_width(k, total_len):
    if k <= 0:
        return False
    if k > total_len:
        return False
    return True


def sliding_window_sums(values, k):
    if not validate_window_width(k, len(values)):
        return []
    sums = []
    for start in range(len(values) - k):
        window_total = 0
        for offset in range(k):
            window_total += values[start + offset]
        sums.append(window_total)
    return sums
"""
    s01_diverse = tuple(
        ([rng.randint(-8, 12) for _ in range(n)], max(1, n // 2))
        for n in range(2, 14)
    )
    s01_equiv = (
        (([1, 3, 5, 7], 2), ([1, 3, 5, 7], 2)),
        (([0, 0, 4, 0], 4), ([1, 1, 1, 1], 4)),
    )

    # S02: boundary_index — missing empty guard before head subscript
    s02_src = """def clamp_percentage(pct):
    if pct < 0:
        return 0
    if pct > 100:
        return 100
    return pct


def head_to_max_pct(nums):
    head = nums[0]
    peak = nums[0]
    for item in nums:
        if item > peak:
            peak = item
    if peak <= 0:
        return 0
    return clamp_percentage((head * 100) // peak)
"""
    s02_diverse = (([],),) + tuple(
        ([rng.randint(1, 50) for _ in range(n)],) for n in range(1, 12)
    )
    s02_equiv = (
        (([10, 20, 40],), ([20, 40, 80],)),
        (([5, 50],), ([10, 100],)),
    )

    # S03: parsing — missing maxsplit=1 on colon key-value header
    s03_src = """def canonical_header_key(name):
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("empty header key")
    for ch in cleaned:
        if ch == " ":
            raise ValueError("whitespace inside header key")
    return cleaned.lower()


def parse_header_line(line):
    if ":" not in line:
        raise ValueError("missing colon separator")
    raw_key, raw_val = line.split(":")
    key = canonical_header_key(raw_key)
    return (key, raw_val.strip())
"""
    s03_diverse = tuple(
        (f"X-Key-{i}: value_{i}:{i * 10}",) for i in range(1, 13)
    )
    s03_equiv = (
        (("Host: localhost:8080",), ("  HOST :  localhost:8080  ",)),
        (("Origin: https://a.io:443",), ("origin:https://a.io:443",)),
    )

    # S04: parsing — tok.isdigit() rejects signed integers
    s04_src = """def split_csv_fields(text):
    raw_parts = text.split(",")
    fields = []
    for part in raw_parts:
        trimmed = part.strip()
        if trimmed:
            fields.append(trimmed)
    return fields


def sum_signed_tokens(text):
    fields = split_csv_fields(text)
    total = 0
    for tok in fields:
        if not tok.isdigit():
            raise ValueError("invalid integer token")
        total += int(tok)
    return total
"""
    s04_diverse = tuple(
        (", ".join(f"{rng.choice(['+', '-', ''])}{rng.randint(1, 30)}" for _ in range(k)),)
        for k in range(1, 13)
    )
    s04_equiv = (
        (("+10, -3, 5",), ("5, +10, -3",)),
        (("-8, +2",), ("  +2 , -8  ",)),
    )

    # S05: state_invariant — updates best before incrementing streak
    s05_src = """def has_valid_bounds(readings, floor):
    if not readings:
        return False
    if floor < -100000 or floor > 100000:
        return False
    return True


def max_streak_above(readings, floor):
    if not has_valid_bounds(readings, floor):
        return 0
    best = 0
    streak = 0
    for val in readings:
        if val >= floor:
            if streak > best:
                best = streak
            streak += 1
        else:
            streak = 0
    return best
"""
    s05_diverse = tuple(
        ([rng.randint(0, 10) for _ in range(n)], 5) for n in range(1, 13)
    )
    s05_equiv = (
        (([5, 6, 1, 7, 8, 9], 5), ([9, 8, 7, 1, 6, 5], 5)),
        (([10, 11, 2, 12], 10), ([20, 21, 12, 22], 20)),
    )

    # S06: state_invariant — forgets count = 0 reset on batch flush
    s06_src = """def valid_packet_sizes(sizes, cap):
    if cap <= 0:
        return False
    for sz in sizes:
        if sz <= 0 or sz > cap:
            return False
    return True


def flush_batches(sizes, cap):
    if not sizes or not valid_packet_sizes(sizes, cap):
        return []
    batches = []
    count = 0
    used = 0
    for sz in sizes:
        if count > 0 and used + sz > cap:
            batches.append((count, used))
            used = 0
        count += 1
        used += sz
    batches.append((count, used))
    return batches
"""
    s06_diverse = tuple(
        ([rng.randint(1, 6) for _ in range(n)], 8) for n in range(1, 13)
    )
    s06_equiv = (
        (([4, 4, 5], 8), ([3, 5, 5], 8)),
    )

    # S07: data_dependency — appends mutable state dict without .copy()
    s07_src = """def apply_step_delta(current_balance, delta):
    updated = current_balance + delta
    if updated < -1000000:
        return -1000000
    if updated > 1000000:
        return 1000000
    return updated


def record_checkpoints(deltas):
    if not deltas:
        return []
    state = {"bal": 0, "steps": 0}
    history = []
    for delta in deltas:
        state["bal"] = apply_step_delta(state["bal"], delta)
        state["steps"] = state["steps"] + 1
        history.append(state)
    return history
"""
    s07_diverse = tuple(
        ([rng.randint(-10, 15) for _ in range(n)],) for n in range(1, 13)
    )
    s07_equiv = (
        (([4, -1, 3],), ([4, -1, 3],)),
    )

    # S08: data_dependency — mutable default bucket=[] leaks across calls
    s08_src = """def clean_tag(raw):
    trimmed = raw.strip().lower()
    if not trimmed:
        return ""
    return trimmed


def collect_tags(raw_tags, bucket=[]):
    for raw in raw_tags:
        tag = clean_tag(raw)
        if tag and tag not in bucket:
            bucket.append(tag)
    return bucket
"""
    s08_diverse = tuple(
        ([f"Tag_{i}_{j}" for j in range(1, (i % 4) + 2)],) for i in range(1, 13)
    )
    s08_equiv = (
        (([" Alpha ", "ALPHA"],), (["alpha"],)),
        ((["Beta", "Gamma", "beta"],), (["beta", "gamma"],)),
    )

    return (
        CorpusUnit(
            unit_id="S01_sliding_window_sums",
            split="source",
            category="nominal",
            family_truth="boundary_index",
            entrypoint="sliding_window_sums",
            buggy_source=s01_src,
            dev_tests=(
                DevTestCase("width_too_large", "call", ([1, 2], 5), []),
                DevTestCase("zero_width", "call", ([4, 5], 0), []),
                DevTestCase("pairs_sum", "call", ([2, 4, 6, 8], 2), [6, 10, 14]),
                DevTestCase("full_window", "call", ([5, 1, 3], 3), [9]),
            ),
            perturbation_spec=PerturbationSpec(s01_diverse, s01_equiv),
        ),
        CorpusUnit(
            unit_id="S02_safe_head_ratio",
            split="source",
            category="nominal",
            family_truth="boundary_index",
            entrypoint="head_to_max_pct",
            buggy_source=s02_src,
            dev_tests=(
                DevTestCase("quarter_peak", "call", ([25, 50, 100],), 25),
                DevTestCase("non_positive", "call", ([-5, 0],), 0),
                DevTestCase("empty_input", "call", ([],), 0),
                DevTestCase("single_positive", "call", ([12],), 100),
            ),
            perturbation_spec=PerturbationSpec(s02_diverse, s02_equiv),
        ),
        CorpusUnit(
            unit_id="S03_kv_header_parse",
            split="source",
            category="nominal",
            family_truth="parsing",
            entrypoint="parse_header_line",
            buggy_source=s03_src,
            dev_tests=(
                DevTestCase("simple_header", "call", ("Content-Type: text/plain",), ("content-type", "text/plain")),
                DevTestCase("spaced_key", "call", (" X-Retries : 3 ",), ("x-retries", "3")),
                DevTestCase("host_with_port", "call", ("Host: localhost:8080",), ("host", "localhost:8080")),
                DevTestCase("url_value", "call", ("Location: https://example.org:8443/p",), ("location", "https://example.org:8443/p")),
            ),
            perturbation_spec=PerturbationSpec(s03_diverse, s03_equiv),
        ),
        CorpusUnit(
            unit_id="S04_csv_int_sum",
            split="source",
            category="nominal",
            family_truth="parsing",
            entrypoint="sum_signed_tokens",
            buggy_source=s04_src,
            dev_tests=(
                DevTestCase("unsigned_csv", "call", ("10, 20, 5",), 35),
                DevTestCase("blank_csv", "call", ("",), 0),
                DevTestCase("mixed_signs", "call", ("10, -4, +6",), 12),
                DevTestCase("negative_only", "call", ("-7, -3",), -10),
            ),
            perturbation_spec=PerturbationSpec(s04_diverse, s04_equiv),
        ),
        CorpusUnit(
            unit_id="S05_run_length_max",
            split="source",
            category="nominal",
            family_truth="state_invariant",
            entrypoint="max_streak_above",
            buggy_source=s05_src,
            dev_tests=(
                DevTestCase("empty_readings", "call", ([], 5), 0),
                DevTestCase("none_above", "call", ([1, 2, 3], 10), 0),
                DevTestCase("two_run_middle", "call", ([5, 6, 2, 7], 5), 2),
                DevTestCase("tail_streak", "call", ([8, 9, 10], 8), 3),
            ),
            perturbation_spec=PerturbationSpec(s05_diverse, s05_equiv),
        ),
        CorpusUnit(
            unit_id="S06_batch_packet_accumulator",
            split="source",
            category="nominal",
            family_truth="state_invariant",
            entrypoint="flush_batches",
            buggy_source=s06_src,
            dev_tests=(
                DevTestCase("empty_sizes", "call", ([], 10), []),
                DevTestCase("single_batch", "call", ([3, 4], 10), [(2, 7)]),
                DevTestCase("two_batches", "call", ([6, 6, 4], 10), [(1, 6), (2, 10)]),
                DevTestCase("three_flushes", "call", ([5, 5, 5], 8), [(1, 5), (1, 5), (1, 5)]),
            ),
            perturbation_spec=PerturbationSpec(s06_diverse, s06_equiv),
        ),
        CorpusUnit(
            unit_id="S07_snapshot_ledger",
            split="source",
            category="nominal",
            family_truth="data_dependency",
            entrypoint="record_checkpoints",
            buggy_source=s07_src,
            dev_tests=(
                DevTestCase("empty_deltas", "call", ([],), []),
                DevTestCase("single_step", "call", ([5],), [{"bal": 5, "steps": 1}]),
                DevTestCase("two_steps", "call", ([5, -2],), [{"bal": 5, "steps": 1}, {"bal": 3, "steps": 2}]),
                DevTestCase("three_steps", "call", ([1, 2, 3],), [{"bal": 1, "steps": 1}, {"bal": 3, "steps": 2}, {"bal": 6, "steps": 3}]),
            ),
            perturbation_spec=PerturbationSpec(s07_diverse, s07_equiv),
        ),
        CorpusUnit(
            unit_id="S08_tag_collector",
            split="source",
            category="nominal",
            family_truth="data_dependency",
            entrypoint="collect_tags",
            buggy_source=s08_src,
            dev_tests=(
                DevTestCase("explicit_bucket", "call", (["Alpha"], ["seed"]), ["seed", "alpha"], forbid_arg_mutation=False),
                DevTestCase("isolated_calls", "sequence", ((["Alpha"],), (["Beta"],)), [["alpha"], ["beta"]]),
                DevTestCase("dedup_within_call", "sequence", ((["X", "x"],), (["Y"],)), [["x"], ["y"]]),
            ),
            perturbation_spec=PerturbationSpec(s08_diverse, s08_equiv),
        ),
    )


def _build_target_units() -> tuple[CorpusUnit, ...]:
    rng = random.Random(20261108)

    # T01: boundary_index — while lo < hi instead of while lo <= hi in binary search
    t01_src = """def verify_sorted_ascending(arr):
    if len(arr) <= 1:
        return True
    for i in range(1, len(arr)):
        if arr[i] < arr[i - 1]:
            return False
    return True


def binary_search_index(arr, target):
    if not arr or not verify_sorted_ascending(arr):
        return -1
    lo = 0
    hi = len(arr) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
"""
    t01_diverse = tuple(
        (sorted(rng.sample(range(-30, 60), n)), n_idx)
        for n, n_idx in ((1, 5), (3, 12), (4, -10), (5, 22), (6, 0), (7, 40), (8, 15), (9, -5), (10, 33), (2, 7), (5, 99), (6, 3))
    )
    t01_diverse = (
        ([4], 4),
        ([2, 6, 10], 10),
        ([2, 6, 10], 2),
        ([1, 3, 5, 7, 9], 5),
        ([1, 3, 5, 7, 9], 8),
        ([-10, -3, 0, 8], -10),
        ([-10, -3, 0, 8], 8),
        ([5, 12, 19, 26, 33, 40], 26),
        ([5, 12, 19, 26, 33, 40], 40),
        ([100, 200], 200),
        ([100, 200], 50),
        ([], 3),
    )
    t01_equiv = (
        (([4], 4), ([14], 14)),
        (([2, 5, 9, 14], 14), ([102, 105, 109, 114], 114)),
        (([-5, 0, 5], -5), (([5, 10, 15], 5))),
        (([1, 4, 8, 12], 7), ([21, 24, 28, 32], 27)),
    )

    # T02: boundary_index — range(1, len(signal) - 2) omits final interior peak
    t02_src = """def signal_dynamic_range(signal):
    if not signal:
        return 0
    low = signal[0]
    high = signal[0]
    for sample in signal:
        if sample < low:
            low = sample
        if sample > high:
            high = sample
    return high - low


def interior_local_maxima(signal):
    if len(signal) < 3 or signal_dynamic_range(signal) == 0:
        return []
    peaks = []
    for idx in range(1, len(signal) - 2):
        if signal[idx] > signal[idx - 1] and signal[idx] > signal[idx + 1]:
            peaks.append(idx)
    return peaks
"""
    t02_diverse = tuple(
        ([rng.randint(0, 20) for _ in range(n)],) for n in range(3, 15)
    )
    t02_equiv = (
        (([1, 6, 2, 8, 1],), ([11, 16, 12, 18, 11],)),
        (([0, 3, 9, 2],), ([-10, -7, -1, -8],)),
        (([5, 2, 7, 1, 9, 3],), ([105, 102, 107, 101, 109, 103],)),
    )

    # T03: boundary_index — missing empty guard before ordered[0] access
    t03_src = """def insertion_sorted(vals):
    result = vals.copy()
    for i in range(1, len(result)):
        key_item = result[i]
        pos = i - 1
        while pos >= 0 and result[pos] > key_item:
            result[pos + 1] = result[pos]
            pos -= 1
        result[pos + 1] = key_item
    return result


def trimmed_floor_mean(samples, trim):
    ordered = insertion_sorted(samples)
    spread_check = ordered[-1] - ordered[0]
    if spread_check == 0:
        return ordered[0]
    if trim < 0 or 2 * trim >= len(ordered):
        return sum(ordered) // len(ordered)
    core = ordered[trim : len(ordered) - trim]
    return sum(core) // len(core)
"""
    t03_diverse = (([], 0), ([], 1)) + tuple(
        ([rng.randint(-20, 80) for _ in range(n)], 1) for n in range(3, 13)
    )
    t03_equiv = (
        (([10, 20, 30, 100], 1), ([100, 30, 20, 10], 1)),
        (([2, 8, 12, 18, 50], 1), ([50, 12, 18, 2, 8], 1)),
        (([], 0), ([], 2)),
    )

    # T04: parsing — entry.split("=") missing maxsplit=1 on config values containing "="
    t04_src = """def is_ignorable_line(text):
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith("#") or stripped.startswith(";"):
        return True
    return False


def parse_env_entries(lines):
    env = {}
    for raw in lines:
        if is_ignorable_line(raw):
            continue
        entry = raw.strip()
        if "=" not in entry:
            raise ValueError("missing equals delimiter")
        key, val = entry.split("=")
        clean_key = key.strip()
        if not clean_key:
            raise ValueError("empty variable name")
        env[clean_key] = val.strip()
    return env
"""
    t04_diverse = tuple(
        ([f"K{j}=val_{i}_{j}=ok" for j in range(1, (i % 4) + 2)],) for i in range(1, 13)
    )
    t04_equiv = (
        ((["A=1=2", "B=3"],), (["B=3", "  A = 1=2  "],)),
        ((["# comment", "DSN=sqlite:///x?m=ro"],), (["DSN = sqlite:///x?m=ro"],)),
    )

    # T05: parsing — raw.split(".") without stripping outer whitespace/newlines
    t05_src = """def parse_component_value(part):
    if not part or not part.isdigit():
        raise ValueError("invalid numeric component")
    if len(part) > 1 and part.startswith("0"):
        raise ValueError("leading zero forbidden")
    return int(part)


def parse_version_triple(raw):
    parts = raw.split(".")
    if len(parts) != 3:
        raise ValueError("expected three dot-separated segments")
    major = parse_component_value(parts[0])
    minor = parse_component_value(parts[1])
    patch = parse_component_value(parts[2])
    return (major, minor, patch)
"""
    t05_diverse = tuple(
        (f"  {i}.{i * 2}.{i % 5}\n",) for i in range(1, 13)
    )
    t05_equiv = (
        (("1.2.3",), ("  1.2.3\n",)),
        (("0.10.4",), ("\t0.10.4  ",)),
        (("12.0.8",), (" 12.0.8 ",)),
    )

    # T06: parsing — qty_text.isdigit() rejects signed stock adjustments "+15", "-4"
    t06_src = """def verb_multiplier(verb):
    if verb == "IN":
        return 1
    if verb == "OUT":
        return -1
    if verb == "ADJ":
        return 1
    raise ValueError("unsupported stock verb")


def replay_stock_deltas(commands):
    stock = 0
    for raw_cmd in commands:
        pieces = raw_cmd.strip().split()
        if len(pieces) != 2:
            raise ValueError("malformed stock command")
        verb = pieces[0]
        qty_text = pieces[1]
        mult = verb_multiplier(verb)
        if not qty_text.isdigit():
            raise ValueError("invalid quantity token")
        stock += mult * int(qty_text)
    return stock
"""
    t06_diverse = tuple(
        ([f"ADJ {rng.choice(['+', '-', ''])}{rng.randint(1, 25)}" for _ in range(k)],)
        for k in range(1, 13)
    )
    t06_equiv = (
        ((["IN 20", "ADJ -5", "ADJ +3"],), (["ADJ +3", "IN 20", "ADJ -5"],)),
        ((["ADJ -10", "IN 4"],), (["IN 4", "ADJ -10"],)),
    )

    # T07: state_invariant — forgets run_len = 0 reset on symbol transition
    t07_src = """def within_symbol_domain(symbols):
    for item in symbols:
        if item < -100000 or item > 100000:
            return False
    return True


def run_length_counts(symbols):
    if not symbols or not within_symbol_domain(symbols):
        return []
    counts = []
    active = symbols[0]
    run_len = 0
    for sym in symbols:
        if sym != active:
            counts.append(run_len)
            active = sym
        run_len += 1
    counts.append(run_len)
    return counts
"""
    t07_diverse = tuple(
        ([rng.choice((1, 2, 3)) for _ in range(n)],) for n in range(1, 13)
    )
    t07_equiv = (
        (([4, 4, 7, 7, 7, 2],), ([14, 14, 17, 17, 17, 12],)),
        (([1, 2, 2, 3],), ([-1, -2, -2, -3],)),
    )

    # T08: state_invariant — updates prev = val before computing val - prev
    t08_src = """def within_sensor_limits(series):
    for reading in series:
        if reading < -1000000 or reading > 1000000:
            return False
    return True


def step_differences(series):
    if len(series) < 2 or not within_sensor_limits(series):
        return []
    prev = series[0]
    diffs = []
    for val in series[1:]:
        prev = val
        diffs.append(val - prev)
    return diffs
"""
    t08_diverse = tuple(
        ([rng.randint(-30, 50) for _ in range(n)],) for n in range(2, 14)
    )
    t08_equiv = (
        (([10, 14, 11, 20],), ([110, 114, 111, 120],)),
        (([-5, 0, -2],), ([5, 10, 8],)),
    )

    # T09: state_invariant — omits post-loop durations.append(prev - start) tail flush
    t09_src = """def is_monotonic_timestamps(timestamps):
    for i in range(1, len(timestamps)):
        if timestamps[i] < timestamps[i - 1]:
            return False
    return True


def session_durations(timestamps, gap_limit):
    if not timestamps or gap_limit < 0 or not is_monotonic_timestamps(timestamps):
        return []
    start = timestamps[0]
    prev = timestamps[0]
    durations = []
    for ts in timestamps[1:]:
        if ts - prev > gap_limit:
            durations.append(prev - start)
            start = ts
        prev = ts
    return durations
"""
    t09_diverse = tuple(
        (sorted(rng.randint(0, 60) for _ in range(n)), 8) for n in range(1, 13)
    )
    t09_equiv = (
        (([0, 3, 5, 20, 25], 10), ([100, 103, 105, 120, 125], 10)),
        (([10, 12, 15], 5), ([50, 52, 55], 5)),
    )

    # T10: data_dependency — aliases caller template list without .copy()
    t10_src = """def overrides_in_range(length, overrides):
    for idx, _ in overrides:
        if idx < 0 or idx >= length:
            return False
    return True


def apply_row_mask(template, overrides):
    if not overrides_in_range(len(template), overrides):
        raise ValueError("override index out of bounds")
    row = template
    for idx, val in overrides:
        row[idx] = val
    return row
"""
    t10_diverse = tuple(
        ([0] * n, [(0, i), (n - 1, i * 2)]) for i, n in enumerate(range(2, 14), 1)
    )
    t10_equiv = (
        (([10, 20, 30, 40], [(0, 1), (2, 3)]), ([10, 20, 30, 40], [(2, 3), (0, 1)])),
        (([5, 6, 7], [(1, 9)]), ([5, 6, 7], [(1, 4), (1, 9)])),
    )

    # T11: data_dependency — mutable default routes={} leaks across calls
    t11_src = """def normalize_http_method(method):
    upper = method.strip().upper()
    if upper not in ("GET", "POST", "PUT", "DELETE"):
        raise ValueError("unsupported HTTP method")
    return upper


def register_route(path, method, routes={}):
    clean_path = path.strip()
    if not clean_path.startswith("/"):
        raise ValueError("route path must start with slash")
    verb = normalize_http_method(method)
    if clean_path not in routes:
        routes[clean_path] = []
    if verb not in routes[clean_path]:
        routes[clean_path].append(verb)
    return routes
"""
    t11_diverse = tuple(
        (f"/v1/item/{i}", ("GET", "POST", "PUT", "DELETE")[i % 4]) for i in range(1, 13)
    )
    t11_equiv = (
        (("/users", "get"), (" /users ", "GET")),
        (("/orders", "post"), ("/orders", " POST ")),
    )

    # T12: data_dependency — computes tax on stale `subtotal` instead of `discounted`
    t12_src = """def basis_points_floor(amount, bps):
    if bps < 0 or bps > 10000:
        raise ValueError("basis points out of range")
    return (amount * bps) // 10000


def compute_net_total(amounts, discount_bps, tax_bps):
    if not amounts:
        return 0
    subtotal = 0
    for item in amounts:
        subtotal += item
    discount = basis_points_floor(subtotal, discount_bps)
    discounted = subtotal - discount
    tax = basis_points_floor(subtotal, tax_bps)
    return discounted + tax
"""
    t12_diverse = tuple(
        ([100 * j for j in range(1, (i % 5) + 2)], 1000, 800) for i in range(1, 13)
    )
    t12_equiv = (
        (([600, 400], 2000, 1000), ([400, 600], 2000, 1000)),
        (([300, 700], 1500, 500), ([500, 500], 1500, 500)),
    )

    # T13: OOD_abstain — greedy coin selection fails on non-canonical coin systems (needs DP)
    t13_src = """def valid_coin_system(coins):
    if not coins:
        return False
    for coin in coins:
        if coin <= 0:
            return False
    return True


def min_coins_exact(coins, amount):
    if amount == 0:
        return 0
    if amount < 0 or not valid_coin_system(coins):
        return -1
    ordered = sorted(coins, reverse=True)
    rem = amount
    used = 0
    for coin in ordered:
        while rem >= coin:
            rem -= coin
            used += 1
    if rem != 0:
        return -1
    return used
"""
    t13_diverse = tuple(
        ([1, 3, 4], amt) for amt in range(1, 13)
    )
    t13_equiv = (
        (([1, 3, 4], 6), ([4, 1, 3], 6)),
        (([2, 5], 6), ([5, 2], 6)),
    )

    # T14: OOD_abstain — flat parenthesis stripper lacks sign-inversion stack
    t14_src = """def tokenize_flat_terms(expr):
    cleaned = expr.replace("(", " ").replace(")", " ")
    cleaned = cleaned.replace("+", " + ").replace("-", " - ")
    return cleaned.split()


def eval_parenthesized_sum(expr):
    tokens = tokenize_flat_terms(expr)
    total = 0
    sign = 1
    for tok in tokens:
        if tok == "+":
            sign = 1
        elif tok == "-":
            sign = -1
        else:
            total += sign * int(tok)
    return total
"""
    t14_diverse = tuple(
        (f"{i * 3} - ({i} + 2)",) for i in range(1, 13)
    )
    t14_equiv = (
        (("10 - (3 + 2)",), (" 10 - ( 3 + 2 ) ",)),
        (("20 - (8 - 3)",), ("20 - (0 + 8 - 3)",)),
    )

    # T15: OOD_abstain — unweighted FIFO BFS instead of Dijkstra edge relaxation
    t15_src = """def build_adj_list(n, edges):
    adj = {i: [] for i in range(n)}
    for u, v, w in edges:
        if 0 <= u < n and 0 <= v < n and w >= 0:
            adj[u].append((v, w))
    return adj


def shortest_path_cost(n, edges, src, dst):
    if src == dst:
        return 0
    adj = build_adj_list(n, edges)
    queue = [(src, 0)]
    visited = {src}
    head = 0
    while head < len(queue):
        node, cost = queue[head]
        head += 1
        for nxt, weight in adj.get(node, []):
            if nxt == dst:
                return cost + weight
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, cost + weight))
    return -1
"""
    t15_diverse = tuple(
        (4, [(0, 3, 20 + i), (0, 1, i), (1, 2, 1), (2, 3, 2)], 0, 3) for i in range(1, 13)
    )
    t15_equiv = (
        ((3, [(0, 2, 10), (0, 1, 2), (1, 2, 3)], 0, 2), (3, [(1, 2, 3), (0, 1, 2), (0, 2, 10)], 0, 2)),
    )

    # T16: OOD_abstain — simultaneous 3-fault ledger (aliasing + split + inverted sign)
    t16_src = """def valid_account_map(accounts):
    for name, bal in accounts.items():
        if not name or not isinstance(bal, int):
            return False
    return True


def reconcile_balances(initial, transfers):
    if not valid_account_map(initial):
        raise ValueError("invalid initial ledger")
    balances = initial
    for entry in transfers:
        src, dst, raw_amt = entry.split(":")
        amt = int(raw_amt)
        balances[src] = balances.get(src, 0) + amt
        balances[dst] = balances.get(dst, 0) - amt
    return balances
"""
    t16_diverse = tuple(
        ({"a": 100, "b": 50}, [f"a:b:{i * 5}:memo"]) for i in range(1, 13)
    )
    t16_equiv = (
        (({"a": 100, "b": 50}, ["a:b:10:note"]), ({"b": 50, "a": 100}, ["a:b:10:other"])),
    )

    # T17: TRAP_overfit — broken transition counter paired with weak dev tests expecting 1
    t17_src = """def min_swaps_to_group_ones(bits):
    if not bits:
        return 0
    transitions = 0
    for idx in range(1, len(bits)):
        if bits[idx] != bits[idx - 1]:
            transitions += 1
    return transitions
"""
    t17_diverse = (
        ([1, 1, 1],),
        ([0, 0, 0, 0],),
        ([1],),
        ([1, 0, 1],),
        ([1, 0, 0, 1, 0, 0, 1],),
        ([1, 0, 1, 0, 1, 0, 1],),
        ([0, 1, 1, 0],),
        ([1, 0, 0, 0, 1, 0, 0, 0, 1],),
        ([1, 1, 0, 1, 1],),
        ([0, 1, 0, 0, 1, 0, 1, 0],),
        ([1, 1, 1, 1, 1],),
        ([0, 0, 1, 0, 0],),
    )
    t17_equiv = (
        (([1, 0, 0, 1, 1],), ([1, 1, 0, 0, 1],)),
        (([0, 1, 0, 1, 1],), ([1, 1, 0, 1, 0],)),
    )

    # T18: TRAP_overfit — prefix-only zero-sum scan paired with single interior dev test
    t18_src = """def longest_zero_sum_span(nums):
    if not nums:
        return 0
    running = 0
    best = 0
    for idx in range(len(nums)):
        running += nums[idx]
        if running == 0:
            best = idx + 1
    return best
"""
    t18_diverse = (
        ([5, -5],),
        ([10, 5, -5],),
        ([1, 2, 3],),
        ([2, -2, 3, -3],),
        ([9, 1, -1, 4, -4, 7],),
        ([0],),
        ([4, 2, -6],),
        ([8, 2, 2, -4, 9],),
        ([-1, 1, -1, 1, -1, 1],),
        ([6, -2, -4, 3],),
        ([11, 3, -3],),
        ([1, -1],),
    )
    t18_equiv = (
        (([10, 5, -5],), ([-5, 5, 10],)),
        (([9, 2, -2, 4],), ([-9, -2, 2, -4],)),
        (([6, 3, 1, -4],), ([-4, 1, 3, 6],)),
    )

    return (
        CorpusUnit(
            unit_id="T01_binary_search_index",
            split="target",
            category="nominal",
            family_truth="boundary_index",
            entrypoint="binary_search_index",
            buggy_source=t01_src,
            dev_tests=(
                DevTestCase("empty_array", "call", ([], 5), -1),
                DevTestCase("middle_hit", "call", ([2, 5, 8, 12, 16], 8), 2),
                DevTestCase("single_element_hit", "call", ([7], 7), 0),
                DevTestCase("right_boundary_hit", "call", ([2, 5, 8, 12], 12), 3),
            ),
            perturbation_spec=PerturbationSpec(t01_diverse, t01_equiv),
        ),
        CorpusUnit(
            unit_id="T02_interior_local_maxima",
            split="target",
            category="nominal",
            family_truth="boundary_index",
            entrypoint="interior_local_maxima",
            buggy_source=t02_src,
            dev_tests=(
                DevTestCase("flat_signal", "call", ([4, 4, 4, 4],), []),
                DevTestCase("early_peak", "call", ([1, 5, 2, 2, 1],), [1]),
                DevTestCase("penultimate_peak", "call", ([1, 2, 6, 1],), [2]),
                DevTestCase("dual_peaks", "call", ([0, 4, 1, 7, 2],), [1, 3]),
            ),
            perturbation_spec=PerturbationSpec(t02_diverse, t02_equiv),
        ),
        CorpusUnit(
            unit_id="T03_trimmed_floor_mean",
            split="target",
            category="nominal",
            family_truth="boundary_index",
            entrypoint="trimmed_floor_mean",
            buggy_source=t03_src,
            dev_tests=(
                DevTestCase("trimmed_outliers", "call", ([10, 20, 30, 100], 1), 25),
                DevTestCase("oversized_trim_fallback", "call", ([5, 15], 1), 10),
                DevTestCase("empty_zero_trim", "call", ([], 0), 0),
                DevTestCase("empty_positive_trim", "call", ([], 2), 0),
            ),
            perturbation_spec=PerturbationSpec(t03_diverse, t03_equiv),
        ),
        CorpusUnit(
            unit_id="T04_parse_env_entries",
            split="target",
            category="nominal",
            family_truth="parsing",
            entrypoint="parse_env_entries",
            buggy_source=t04_src,
            dev_tests=(
                DevTestCase("basic_pairs", "call", (["# cfg", "PORT=8080", "MODE=prod"],), {"PORT": "8080", "MODE": "prod"}),
                DevTestCase("empty_lines", "call", ([],), {}),
                DevTestCase("query_equals", "call", (["DSN=sqlite:///app.db?mode=ro"],), {"DSN": "sqlite:///app.db?mode=ro"}),
                DevTestCase("padded_base64", "call", (["TOKEN=abc=def=="],), {"TOKEN": "abc=def=="}),
            ),
            perturbation_spec=PerturbationSpec(t04_diverse, t04_equiv),
        ),
        CorpusUnit(
            unit_id="T05_parse_version_triple",
            split="target",
            category="nominal",
            family_truth="parsing",
            entrypoint="parse_version_triple",
            buggy_source=t05_src,
            dev_tests=(
                DevTestCase("clean_semver", "call", ("1.2.3",), (1, 2, 3)),
                DevTestCase("zero_major", "call", ("0.10.4",), (0, 10, 4)),
                DevTestCase("padded_newline", "call", ("  2.14.5\n",), (2, 14, 5)),
                DevTestCase("tab_wrapped", "call", ("\t1.0.0 ",), (1, 0, 0)),
            ),
            perturbation_spec=PerturbationSpec(t05_diverse, t05_equiv),
        ),
        CorpusUnit(
            unit_id="T06_replay_stock_deltas",
            split="target",
            category="nominal",
            family_truth="parsing",
            entrypoint="replay_stock_deltas",
            buggy_source=t06_src,
            dev_tests=(
                DevTestCase("unsigned_in_out", "call", (["IN 10", "OUT 3"],), 7),
                DevTestCase("empty_log", "call", ([],), 0),
                DevTestCase("signed_adjustments", "call", (["IN 20", "ADJ -5", "ADJ +3"],), 18),
                DevTestCase("negative_adj", "call", (["ADJ -4"],), -4),
            ),
            perturbation_spec=PerturbationSpec(t06_diverse, t06_equiv),
        ),
        CorpusUnit(
            unit_id="T07_run_length_counts",
            split="target",
            category="nominal",
            family_truth="state_invariant",
            entrypoint="run_length_counts",
            buggy_source=t07_src,
            dev_tests=(
                DevTestCase("empty_symbols", "call", ([],), []),
                DevTestCase("single_run", "call", ([9, 9, 9],), [3]),
                DevTestCase("two_runs", "call", ([4, 4, 7, 7, 7],), [2, 3]),
                DevTestCase("singleton_runs", "call", ([1, 2, 3],), [1, 1, 1]),
            ),
            perturbation_spec=PerturbationSpec(t07_diverse, t07_equiv),
        ),
        CorpusUnit(
            unit_id="T08_step_differences",
            split="target",
            category="nominal",
            family_truth="state_invariant",
            entrypoint="step_differences",
            buggy_source=t08_src,
            dev_tests=(
                DevTestCase("short_series", "call", ([],), []),
                DevTestCase("constant_series", "call", ([5, 5, 5],), [0, 0]),
                DevTestCase("up_down_steps", "call", ([10, 14, 11],), [4, -3]),
                DevTestCase("single_step", "call", ([3, 8],), [5]),
            ),
            perturbation_spec=PerturbationSpec(t08_diverse, t08_equiv),
        ),
        CorpusUnit(
            unit_id="T09_session_durations",
            split="target",
            category="nominal",
            family_truth="state_invariant",
            entrypoint="session_durations",
            buggy_source=t09_src,
            dev_tests=(
                DevTestCase("empty_ts", "call", ([], 10), []),
                DevTestCase("unsorted_ts", "call", ([10, 5], 10), []),
                DevTestCase("two_sessions", "call", ([0, 3, 5, 20, 25], 10), [5, 5]),
                DevTestCase("single_session", "call", ([10, 12, 15], 5), [5]),
            ),
            perturbation_spec=PerturbationSpec(t09_diverse, t09_equiv),
        ),
        CorpusUnit(
            unit_id="T10_apply_row_mask",
            split="target",
            category="nominal",
            family_truth="data_dependency",
            entrypoint="apply_row_mask",
            buggy_source=t10_src,
            dev_tests=(
                DevTestCase("no_overrides", "call", ([1, 2, 3], []), [1, 2, 3]),
                DevTestCase("single_override_immutable", "call", ([10, 20, 30], [(1, 99)]), [10, 99, 30], forbid_arg_mutation=True),
                DevTestCase("multi_override_immutable", "call", ([5, 6, 7, 8], [(0, 1), (3, 9)]), [1, 6, 7, 9], forbid_arg_mutation=True),
            ),
            perturbation_spec=PerturbationSpec(t10_diverse, t10_equiv),
        ),
        CorpusUnit(
            unit_id="T11_register_route",
            split="target",
            category="nominal",
            family_truth="data_dependency",
            entrypoint="register_route",
            buggy_source=t11_src,
            dev_tests=(
                DevTestCase("explicit_table", "call", ("/health", "get", {"/ready": ["GET"]}), {"/ready": ["GET"], "/health": ["GET"]}, forbid_arg_mutation=False),
                DevTestCase("fresh_default_per_call", "sequence", (("/users", "get"), ("/orders", "post")), [{"/users": ["GET"]}, {"/orders": ["POST"]}]),
                DevTestCase("method_norm_isolated", "sequence", (("/items", "put"), ("/auth", "delete")), [{"/items": ["PUT"]}, {"/auth": ["DELETE"]}]),
            ),
            perturbation_spec=PerturbationSpec(t11_diverse, t11_equiv),
        ),
        CorpusUnit(
            unit_id="T12_compute_net_total",
            split="target",
            category="nominal",
            family_truth="data_dependency",
            entrypoint="compute_net_total",
            buggy_source=t12_src,
            dev_tests=(
                DevTestCase("empty_cart", "call", ([], 1000, 500), 0),
                DevTestCase("zero_discount", "call", ([1000], 0, 1000), 1100),
                DevTestCase("discounted_tax_base", "call", ([1000], 2000, 1000), 880),
                DevTestCase("half_off_plus_tax", "call", ([500, 500], 5000, 2000), 600),
            ),
            perturbation_spec=PerturbationSpec(t12_diverse, t12_equiv),
        ),
        CorpusUnit(
            unit_id="T13_ood_greedy_coin_change",
            split="target",
            category="OOD_abstain",
            family_truth="ood_algorithmic",
            entrypoint="min_coins_exact",
            buggy_source=t13_src,
            dev_tests=(
                DevTestCase("zero_amount", "call", ([1, 5, 10], 0), 0),
                DevTestCase("canonical_us", "call", ([1, 5, 10], 16), 3),
                DevTestCase("non_canonical_six", "call", ([1, 3, 4], 6), 2),
                DevTestCase("non_unit_denoms", "call", ([2, 5], 6), 3),
                DevTestCase("non_canonical_twelve", "call", ([1, 6, 10], 12), 2),
            ),
            perturbation_spec=PerturbationSpec(t13_diverse, t13_equiv),
        ),
        CorpusUnit(
            unit_id="T14_ood_nested_expr_eval",
            split="target",
            category="OOD_abstain",
            family_truth="ood_algorithmic",
            entrypoint="eval_parenthesized_sum",
            buggy_source=t14_src,
            dev_tests=(
                DevTestCase("additive_parens", "call", ("10 + (3 + 2)",), 15),
                DevTestCase("flat_diff", "call", ("8 - 3",), 5),
                DevTestCase("negated_group", "call", ("10 - (3 + 2)",), 5),
                DevTestCase("negated_diff", "call", ("20 - (8 - 3)",), 15),
                DevTestCase("deeply_nested", "call", ("1 - (2 - (3 - 4))",), -2),
            ),
            perturbation_spec=PerturbationSpec(t14_diverse, t14_equiv),
        ),
        CorpusUnit(
            unit_id="T15_ood_weighted_shortest_hops",
            split="target",
            category="OOD_abstain",
            family_truth="ood_algorithmic",
            entrypoint="shortest_path_cost",
            buggy_source=t15_src,
            dev_tests=(
                DevTestCase("line_graph", "call", (3, [(0, 1, 2), (1, 2, 3)], 0, 2), 5),
                DevTestCase("unreachable", "call", (2, [], 0, 1), -1),
                DevTestCase("two_hop_cheaper", "call", (3, [(0, 2, 10), (0, 1, 2), (1, 2, 3)], 0, 2), 5),
                DevTestCase("three_hop_cheaper", "call", (4, [(0, 3, 20), (0, 1, 1), (1, 2, 1), (2, 3, 1)], 0, 3), 3),
                DevTestCase("diamond_relax", "call", (4, [(0, 2, 9), (0, 1, 3), (1, 2, 2), (2, 3, 4)], 0, 3), 9),
            ),
            perturbation_spec=PerturbationSpec(t15_diverse, t15_equiv),
        ),
        CorpusUnit(
            unit_id="T16_ood_triple_fault_ledger",
            split="target",
            category="OOD_abstain",
            family_truth="ood_multi_fault",
            entrypoint="reconcile_balances",
            buggy_source=t16_src,
            dev_tests=(
                DevTestCase("no_transfers", "call", ({"alice": 100}, []), {"alice": 100}),
                DevTestCase("empty_ledger", "call", ({}, []), {}),
                DevTestCase("memo_transfer_immutable", "call", ({"alice": 100, "bob": 40}, ["alice:bob:25:rent"]), {"alice": 75, "bob": 65}, forbid_arg_mutation=True),
                DevTestCase("chained_transfers", "call", ({"a": 50, "b": 50, "c": 0}, ["a:b:20:x", "b:c:30:y"]), {"a": 30, "b": 40, "c": 30}, forbid_arg_mutation=True),
                DevTestCase("new_recipient", "call", ({"src": 80}, ["src:dst:15:gift:v1"]), {"src": 65, "dst": 15}, forbid_arg_mutation=True),
            ),
            perturbation_spec=PerturbationSpec(t16_diverse, t16_equiv),
        ),
        CorpusUnit(
            unit_id="T17_trap_constant_collapse",
            split="target",
            category="TRAP_overfit",
            family_truth="trap_overfit",
            entrypoint="min_swaps_to_group_ones",
            buggy_source=t17_src,
            dev_tests=(
                DevTestCase("empty_bits", "call", ([],), 0),
                DevTestCase("alternating_five", "call", ([1, 0, 1, 0, 1],), 1),
                DevTestCase("alternating_four", "call", ([0, 1, 0, 1],), 1),
            ),
            perturbation_spec=PerturbationSpec(t17_diverse, t17_equiv, expect_variation=True),
        ),
        CorpusUnit(
            unit_id="T18_trap_special_case_guard",
            split="target",
            category="TRAP_overfit",
            family_truth="trap_overfit",
            entrypoint="longest_zero_sum_span",
            buggy_source=t18_src,
            dev_tests=(
                DevTestCase("empty_nums", "call", ([],), 0),
                DevTestCase("prefix_pair", "call", ([3, -3, 9],), 2),
                DevTestCase("interior_quad", "call", ([7, 4, -4, 2, -2, 8],), 4),
            ),
            perturbation_spec=PerturbationSpec(t18_diverse, t18_equiv, expect_variation=True),
        ),
    )


SOURCE_BANK: tuple[CorpusUnit, ...] = _build_source_units()
TARGET_BANK: tuple[CorpusUnit, ...] = _build_target_units()


def source_units() -> tuple[CorpusUnit, ...]:
    return SOURCE_BANK


def target_units() -> tuple[CorpusUnit, ...]:
    return TARGET_BANK
