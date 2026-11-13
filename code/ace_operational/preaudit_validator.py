"""ACE evidence pre-audit validator v2 (mechanical, offline, read-only).

Design freezes: docs/research/PREAUDIT_VALIDATOR_V1_DESIGN_FREEZE.md and
docs/research/PREAUDIT_VALIDATOR_V2_DESIGN_FREEZE.md (standing contract,
coordination harvest #9; Ian's v2 list, PR #179 comment 6857357128).

v2 adds contract machinery around the unchanged v1 verdicts: a declared
four-stage lifecycle, verdicts bound to a validation_spec_digest,
PROCESS-error separation (a validator failure is never a verdict),
machine-readable reason codes, and nondeterminism-conflict detection
instead of silent overwrites.

This tool compares a frozen evidence package against ONE explicit manifest
and reports, per check, exactly one of three states:

  SESUAI        - complete inputs, mechanical comparison held
  TIDAK SESUAI  - deterministic mismatch proven from complete inputs
  UNKNOWN       - evidence missing/ambiguous; the checker stops, never guesses

A clean report is NOT an approval or validation of any experiment. The
validator proves only that a package matches its manifest on the three
mechanical checks declared there.

Physical read-only enforcement: source files are opened O_RDONLY, all writes
go to a separate out-dir, and the CLI refuses to run when out-dir and source
root contain one another. Standard library only; no network, no subprocess.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys

SCHEMA_MANIFEST = "ace.preaudit_manifest.v1"
SCHEMA_REPORT = "ace.preaudit_report.v2"
VALIDATOR_VERSION = "preaudit-validator-2.0.0"
REASON_CODE_REGISTRY_VERSION = "1"
STAGE_MODEL_VERSION = "1"

STAGES = ["STAGED", "REGISTERED OBSERVATION", "VALIDATION VERDICT", "PUBLISHED RESULT"]
OUTPUT_STAGE = "VALIDATION VERDICT"

# Closed reason-code registry (design freeze v2, V2-4). Every item carries
# exactly one code; UNKNOWN items always carry one of the UNKNOWN codes.
REASON_CODES = {}  # populated below, after the state constants

SESUAI = "SESUAI"
TIDAK_SESUAI = "TIDAK SESUAI"
UNKNOWN = "UNKNOWN"

DISCLAIMER = (
    "PRE-AUDIT MEKANIS — bukan persetujuan, bukan validasi eksperimen. "
    "Laporan ini hanya menyatakan hasil perbandingan mekanis atas paket beku "
    "terhadap manifest eksplisit. Keadaan SESUAI pada semua cek tidak berarti "
    "eksperimen sah, benar, atau disetujui."
)

FP_CLASS = {
    "C1": "canonicalization/path errors (symlink, separator, case) — measured by valid-variant probes",
    "C2": "numeric-representation brittleness (0 vs 0.0 vs 1e2) — measured by valid-variant probes",
    "C3": "rule-shape rigidity — unsupported rule shapes fail toward UNKNOWN, never toward false TIDAK SESUAI",
}

REASON_CODES.update({
    "OK": "SESUAI",
    "ARTIFACT_MISSING": "TIDAK SESUAI", "SIZE_MISMATCH": "TIDAK SESUAI",
    "HASH_MISMATCH": "TIDAK SESUAI", "PATH_ESCAPE": "TIDAK SESUAI",
    "COUNT_MISMATCH": "TIDAK SESUAI", "FIELD_MISMATCH": "TIDAK SESUAI",
    "RATE_MISMATCH": "TIDAK SESUAI", "VERDICT_MISMATCH": "TIDAK SESUAI",
    "NOT_DECLARED": "UNKNOWN", "INPUT_MALFORMED": "UNKNOWN",
    "PARSE_ERROR": "UNKNOWN", "POINTER_UNRESOLVED": "UNKNOWN",
    "METRIC_MISSING": "UNKNOWN", "METRIC_NON_NUMERIC": "UNKNOWN",
    "VERDICT_UNDECIDABLE": "UNKNOWN", "RULE_AMBIGUOUS": "UNKNOWN",
    "RULE_UNSUPPORTED": "UNKNOWN", "DEPENDENCY_UNRESOLVED": "UNKNOWN",
    "EMPTY_INPUT": "UNKNOWN", "RATE_UNDEFINED": "UNKNOWN",
})


class ParseError(ValueError):
    """Raised when strict parsing fails; callers classify this as UNKNOWN."""


class PointerError(ValueError):
    """Raised when a pointer cannot be resolved; classified as UNKNOWN."""


# --------------------------------------------------------------------------
# Strict parsing substrate
# --------------------------------------------------------------------------

def _reject_constant(name):
    raise ParseError("forbidden constant: %s" % name)


def _no_duplicate_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ParseError("duplicate key: %r" % (key,))
        obj[key] = value
    return obj


def parse_json_bytes(raw: bytes):
    """Parse one JSON document strictly: no duplicate keys, no NaN/Infinity,
    numbers as int/Decimal (never binary float). Raises ParseError."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("not valid UTF-8: %s" % exc)
    try:
        return json.loads(
            text,
            object_pairs_hook=_no_duplicate_pairs,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_constant,
        )
    except ParseError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise ParseError(str(exc))


def parse_jsonl_bytes(raw: bytes):
    """Parse JSONL strictly. Returns (entries, errors) where errors is a list
    of (line_number, message) for lines that failed; blank lines are skipped.
    Never raises for content problems — the caller decides the state."""
    entries, errors = [], []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [], [(0, "not valid UTF-8: %s" % exc)]
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(parse_json_bytes(line.encode("utf-8")))
        except ParseError as exc:
            errors.append((lineno, str(exc)))
    return entries, errors


# --------------------------------------------------------------------------
# Pointers
# --------------------------------------------------------------------------

def resolve_pointer(doc, pointer: str):
    """Resolve a /-separated pointer. For list documents (JSONL) the first
    segment may be entry:<n> or entry_seq:<n>. Raises PointerError."""
    if pointer in ("", "/"):
        return doc
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise PointerError("pointer must start with '/': %r" % (pointer,))
    segments = pointer[1:].split("/")
    current = doc
    for i, seg in enumerate(segments):
        if i == 0 and isinstance(current, list) and (
            seg.startswith("entry:") or seg.startswith("entry_seq:")
        ):
            kind, _, num = seg.partition(":")
            try:
                n = int(num)
            except ValueError:
                raise PointerError("bad entry selector: %r" % seg)
            if kind == "entry":
                if n < 0 or n >= len(current):
                    raise PointerError("entry index out of range: %d" % n)
                current = current[n]
            else:
                match = [e for e in current if isinstance(e, dict) and e.get("seq") == n]
                if len(match) != 1:
                    raise PointerError("entry_seq %d matched %d records" % (n, len(match)))
                current = match[0]
            continue
        if isinstance(current, dict):
            if seg not in current:
                raise PointerError("key not present: %r" % seg)
            current = current[seg]
        elif isinstance(current, list):
            try:
                idx = int(seg)
            except ValueError:
                raise PointerError("list segment is not an index: %r" % seg)
            if idx < 0 or idx >= len(current):
                raise PointerError("list index out of range: %d" % idx)
            current = current[idx]
        else:
            raise PointerError("cannot descend into scalar at %r" % seg)
    return current


# --------------------------------------------------------------------------
# Value helpers
# --------------------------------------------------------------------------

def is_number(value) -> bool:
    return isinstance(value, (int, Decimal)) and not isinstance(value, bool)


def values_equal(a, b) -> bool:
    """Exact equality with numeric normalization (int/Decimal compare by
    value, so 0 == 0.0 == 1e2); bools only equal bools; recurses into
    lists/dicts."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if is_number(a) and is_number(b):
        return Decimal(a) == Decimal(b)
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(values_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b))
    return a == b


def as_decimal(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            raise PointerError("not a decimal string: %r" % value)
    raise PointerError("not numeric: %r" % (value,))


def show(value) -> str:
    """Stable human string for evidence fields."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


# --------------------------------------------------------------------------
# Check result
# --------------------------------------------------------------------------

class CheckResult:
    def __init__(self, check_id, title):
        self.check_id = check_id
        self.title = title
        self.sub = []  # list of (label, state, reason, reason_code)
        self.evidence_present = []
        self.evidence_missing = []
        self.dependencies = []
        self.next_step = ""
        self.spec_digest = ""

    def add(self, label, state, reason, code="INPUT_MALFORMED"):
        if REASON_CODES.get(code) != state:
            raise ValueError("reason code %r does not belong to state %r" % (code, state))
        self.sub.append((label, state, reason, code))

    @property
    def state(self):
        states = {s for _, s, _, _ in self.sub}
        if TIDAK_SESUAI in states:
            return TIDAK_SESUAI
        if UNKNOWN in states or not self.sub:
            return UNKNOWN
        return SESUAI

    def to_dict(self):
        return {
            "check_id": self.check_id,
            "title": self.title,
            "state": self.state,
            "false_positive_class": FP_CLASS.get(self.check_id, ""),
            "stage": OUTPUT_STAGE,
            "validation_spec_digest": self.spec_digest,
            "items": [
                {"item": label, "state": state, "reason": reason,
                 "reason_code": code, "stage": OUTPUT_STAGE}
                for label, state, reason, code in self.sub
            ],
            "evidence_present": self.evidence_present,
            "evidence_missing": self.evidence_missing,
            "dependencies": self.dependencies,
            "next_step": self.next_step,
        }


# --------------------------------------------------------------------------
# Package access (read-only)
# --------------------------------------------------------------------------

class Package:
    def __init__(self, source_root: Path):
        self.root = source_root.resolve()
        self._parsed = {}
        self._jsonl = {}

    def resolve_artifact_path(self, rel: str):
        """Returns (path, error). error is 'escape' for paths leaving the
        root, 'bad' for malformed paths, None on success."""
        if not isinstance(rel, str) or not rel or os.path.isabs(rel):
            return None, "bad"
        if any(part == ".." for part in Path(rel).parts):
            return None, "escape"
        candidate = (self.root / rel).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            return None, "escape"
        return candidate, None

    def read_bytes(self, path: Path) -> bytes:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            chunks = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)

    def parsed(self, rel: str):
        """(doc, error_message). Cached. JSONL files (by suffix) parse to a
        list of entries; a JSONL with any bad line is an error here."""
        if rel in self._parsed:
            return self._parsed[rel]
        path, err = self.resolve_artifact_path(rel)
        if err:
            result = (None, "path %s" % err)
        elif not path.is_file():
            result = (None, "file missing")
        else:
            raw = self.read_bytes(path)
            try:
                if rel.endswith(".jsonl"):
                    entries, errors = parse_jsonl_bytes(raw)
                    if errors:
                        result = (None, "jsonl parse errors: %s" % (errors,))
                    else:
                        result = (entries, None)
                else:
                    result = (parse_json_bytes(raw), None)
            except ParseError as exc:
                result = (None, "parse error: %s" % exc)
        self._parsed[rel] = result
        return result


# --------------------------------------------------------------------------
# C1 — completeness + hash integrity
# --------------------------------------------------------------------------

def check_c1(package: Package, manifest: dict, result: CheckResult):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        result.add("manifest.artifacts", UNKNOWN,
                   "manifest declares no artifacts; nothing can be proven", "NOT_DECLARED")
        result.evidence_missing.append("manifest.artifacts (non-empty list)")
        result.next_step = "Declare every frozen artifact in the manifest."
        return {}
    integrity = {}  # path -> True iff byte-identical to manifest
    seen = set()
    for entry in artifacts:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            result.add("manifest-entry", UNKNOWN,
                       "artifact entry malformed (no string path); input defect, not a package verdict", "INPUT_MALFORMED")
            result.evidence_missing.append("well-formed artifact entry")
            continue
        rel = entry["path"]
        if rel in seen:
            result.add(rel, UNKNOWN, "duplicate artifact path in manifest; ambiguous input", "RULE_AMBIGUOUS")
            continue
        seen.add(rel)
        sha = entry.get("sha256")
        size = entry.get("size_bytes")
        if not (isinstance(sha, str) and len(sha) == 64
                and all(c in "0123456789abcdef" for c in sha.lower())) \
                or not (isinstance(size, int) and not isinstance(size, bool) and size >= 0):
            integrity[rel] = False
            result.add(rel, UNKNOWN,
                       "manifest entry lacks a valid sha256/size_bytes; cannot prove a mismatch", "INPUT_MALFORMED")
            result.evidence_missing.append("%s: valid sha256+size_bytes in manifest" % rel)
            continue
        path, err = package.resolve_artifact_path(rel)
        if err == "escape":
            integrity[rel] = False
            result.add(rel, TIDAK_SESUAI, "artifact path escapes the source root; not followed", "PATH_ESCAPE")
            continue
        if err:
            integrity[rel] = False
            result.add(rel, UNKNOWN, "artifact path malformed", "INPUT_MALFORMED")
            continue
        if not path.is_file():
            integrity[rel] = False
            result.add(rel, TIDAK_SESUAI,
                       "declared artifact is absent; the manifest is complete input, so absence is proven", "ARTIFACT_MISSING")
            result.evidence_missing.append("%s: file present" % rel)
            continue
        raw = package.read_bytes(path)
        digest = hashlib.sha256(raw).hexdigest()
        if len(raw) != size:
            integrity[rel] = False
            result.add(rel, TIDAK_SESUAI,
                       "size mismatch: manifest %d bytes, actual %d bytes" % (size, len(raw)), "SIZE_MISMATCH")
        elif digest != sha.lower():
            integrity[rel] = False
            result.add(rel, TIDAK_SESUAI,
                       "sha256 mismatch: manifest %s, actual %s" % (sha.lower(), digest), "HASH_MISMATCH")
        else:
            integrity[rel] = True
            result.add(rel, SESUAI, "present, %d bytes, sha256 matches manifest" % len(raw), "OK")
            result.evidence_present.append(rel)
    result.dependencies = ["the manifest itself (its custody is out of scope)"]
    result.next_step = ("No action for matching artifacts. For any TIDAK SESUAI: "
                        "re-freeze the package or correct the manifest, then re-run. "
                        "For UNKNOWN: repair the manifest entry.")
    return integrity


# --------------------------------------------------------------------------
# C2 — declared count consistency
# --------------------------------------------------------------------------

def _pair(value):
    """Normalize a [num, den] pair of integers; None if not a valid pair."""
    if isinstance(value, list) and len(value) == 2 and all(
        isinstance(v, int) and not isinstance(v, bool) for v in value
    ):
        return (value[0], value[1])
    return None


def _load_for_assertion(package, integrity, ref, result):
    """Returns doc or None (recording an UNKNOWN reason on the result)."""
    rel = ref.get("artifact") if isinstance(ref, dict) else None
    if not isinstance(rel, str):
        result.add("assertion-ref", UNKNOWN, "assertion reference lacks an artifact path", "INPUT_MALFORMED")
        return None
    if integrity.get(rel) is not True:
        result.add(rel, UNKNOWN,
                   "dependency unresolved: artifact did not pass C1, so its bytes are not the frozen bytes", "DEPENDENCY_UNRESOLVED")
        return None
    doc, err = package.parsed(rel)
    if err:
        code = "PARSE_ERROR" if ("parse error" in err or "not valid UTF-8" in err) else \
            ("ARTIFACT_MISSING" if err == "file missing" else "INPUT_MALFORMED")
        if code == "ARTIFACT_MISSING":
            code = "DEPENDENCY_UNRESOLVED"  # a missing input is an unresolved dependency here, not a verdict
        result.add(rel, UNKNOWN, err, code)
        return None
    return doc


def _resolve(doc, ref):
    return resolve_pointer(doc, ref.get("pointer", ""))


def check_c2(package: Package, manifest: dict, integrity: dict, result: CheckResult):
    assertions = manifest.get("count_assertions")
    if not isinstance(assertions, list) or not assertions:
        result.add("manifest.count_assertions", UNKNOWN,
                   "no count assertions declared; the validator invents no formula of its own", "NOT_DECLARED")
        result.evidence_missing.append("manifest.count_assertions")
        result.next_step = "Declare the mechanical recomputations to check, or accept UNKNOWN for C2."
        return
    result.dependencies = ["C1 integrity of every artifact an assertion touches"]
    for i, a in enumerate(assertions):
        label = a.get("id", "assertion-%d" % i) if isinstance(a, dict) else "assertion-%d" % i
        if not isinstance(a, dict):
            result.add(label, UNKNOWN, "assertion is not an object", "INPUT_MALFORMED")
            continue
        kind = a.get("kind")
        try:
            if kind == "sum_pairs_equals":
                _assert_sum_pairs(package, integrity, a, result, label)
            elif kind == "field_equals":
                left = _load_for_assertion(package, integrity, a.get("left", {}), result)
                right = _load_for_assertion(package, integrity, a.get("right", {}), result)
                if left is None or right is None:
                    result.add(label, UNKNOWN, "an input could not be loaded (see items above)", "DEPENDENCY_UNRESOLVED")
                    continue
                lv = _resolve(left, a["left"])
                rv = _resolve(right, a["right"])
                if values_equal(lv, rv):
                    result.add(label, SESUAI, "both sides equal: %s" % show(lv), "OK")
                    result.evidence_present.append(label)
                else:
                    result.add(label, TIDAK_SESUAI,
                               "field inequality: %s != %s" % (show(lv), show(rv)), "FIELD_MISMATCH")
            elif kind == "rate_equals":
                _assert_rate(package, integrity, a, result, label)
            else:
                result.add(label, UNKNOWN, "unsupported assertion kind: %r" % (kind,), "RULE_UNSUPPORTED")
        except PointerError as exc:
            msg = str(exc)
            code = "RATE_UNDEFINED" if "denominator is zero" in msg else \
                ("INPUT_MALFORMED" if ("not an integer" in msg or "not numeric" in msg
                                       or "not a decimal" in msg or "mixed pair" in msg)
                 else "POINTER_UNRESOLVED")
            result.add(label, UNKNOWN, "pointer/value problem: %s" % exc, code)
            result.evidence_missing.append("%s: %s" % (label, exc))
    result.next_step = ("For TIDAK SESUAI: the declared recomputation disagrees with the "
                        "recorded values — inspect the named pointers. For UNKNOWN: supply "
                        "the missing artifact/pointer or a supported assertion kind.")


def _collect_pairs(doc, ref, key):
    """Sum pairs at pointer, optionally descending into item[key] per list
    element. Returns a single (n, d) tuple or a dict key -> (n, d)."""
    value = _resolve(doc, ref)
    items = value if isinstance(value, list) else [value]
    totals = {}
    single = [0, 0]
    mode = None
    for item in items:
        target = item
        if key is not None:
            if not isinstance(item, dict) or key not in item:
                raise PointerError("key %r missing in a list item" % key)
            target = item[key]
        if isinstance(target, dict):
            if mode == "single":
                raise PointerError("mixed pair/dict shapes")
            mode = "dict"
            for k, v in target.items():
                p = _pair(v)
                if p is None:
                    raise PointerError("value at key %r is not an integer pair" % k)
                acc = totals.setdefault(k, [0, 0])
                acc[0] += p[0]
                acc[1] += p[1]
        else:
            p = _pair(target)
            if p is None:
                raise PointerError("value is not an integer [num, den] pair")
            if mode == "dict":
                raise PointerError("mixed pair/dict shapes")
            mode = "single"
            single[0] += p[0]
            single[1] += p[1]
    if mode == "dict":
        return {k: tuple(v) for k, v in totals.items()}
    return tuple(single)


def _assert_sum_pairs(package, integrity, a, result, label):
    src = _load_for_assertion(package, integrity, a.get("source", {}), result)
    tgt = _load_for_assertion(package, integrity, a.get("target", {}), result)
    if src is None or tgt is None:
        result.add(label, UNKNOWN, "an input could not be loaded (see items above)", "DEPENDENCY_UNRESOLVED")
        return
    summed = _collect_pairs(src, a["source"], a.get("key"))
    target_value = _resolve(tgt, a["target"])
    if isinstance(summed, dict):
        if not isinstance(target_value, dict):
            raise PointerError("target is not an object of pairs")
        target_pairs = {}
        for k, v in target_value.items():
            p = _pair(v)
            if p is None:
                raise PointerError("target value at %r is not an integer pair" % k)
            target_pairs[k] = p
        if summed == target_pairs:
            result.add(label, SESUAI, "summed pairs equal target: %s" % show(summed), "OK")
            result.evidence_present.append(label)
        else:
            result.add(label, TIDAK_SESUAI,
                       "summed pairs %s != target %s" % (show(summed), show(target_pairs)), "COUNT_MISMATCH")
    else:
        p = _pair(target_value)
        if p is None:
            raise PointerError("target is not an integer pair")
        if summed == p:
            result.add(label, SESUAI, "summed pair equals target: %s" % (show(summed),), "OK")
            result.evidence_present.append(label)
        else:
            result.add(label, TIDAK_SESUAI,
                       "summed pair %s != target %s" % (show(summed), show(p)), "COUNT_MISMATCH")


def _assert_rate(package, integrity, a, result, label):
    src = _load_for_assertion(package, integrity, a.get("source", {}), result)
    tgt = _load_for_assertion(package, integrity, a.get("target", {}), result)
    if src is None or tgt is None:
        result.add(label, UNKNOWN, "an input could not be loaded (see items above)", "DEPENDENCY_UNRESOLVED")
        return
    scale = as_decimal(a.get("scale", 1))
    tolerance = abs(as_decimal(a.get("tolerance", "0")))
    source_value = _resolve(src, a["source"])
    target_value = _resolve(tgt, a["target"])

    def rate_of(pair):
        p = _pair(pair)
        if p is None:
            raise PointerError("rate source is not an integer [num, den] pair")
        if p[1] == 0:
            raise PointerError("denominator is zero; rate undefined")
        return Fraction(p[0], p[1]) * Fraction(scale)

    def within(computed, recorded):
        rec = as_decimal(recorded)
        diff = abs(Decimal(computed.numerator) / Decimal(computed.denominator) - rec)
        return diff <= tolerance, diff

    if isinstance(source_value, dict):
        if not isinstance(target_value, dict):
            raise PointerError("target is not an object of numbers")
        bad, good = [], []
        for k, pair in source_value.items():
            if k not in target_value:
                raise PointerError("target lacks key %r" % k)
            ok, diff = within(rate_of(pair), target_value[k])
            (good if ok else bad).append("%s (diff %s)" % (k, diff))
        if bad:
            result.add(label, TIDAK_SESUAI, "rates disagree beyond tolerance for: %s" % ", ".join(bad), "RATE_MISMATCH")
        else:
            result.add(label, SESUAI, "all rates within tolerance %s: %s" % (tolerance, ", ".join(good)), "OK")
            result.evidence_present.append(label)
    else:
        ok, diff = within(rate_of(source_value), target_value)
        if ok:
            result.add(label, SESUAI, "rate matches within tolerance %s (diff %s)" % (tolerance, diff), "OK")
            result.evidence_present.append(label)
        else:
            result.add(label, TIDAK_SESUAI, "rate differs by %s, beyond tolerance %s" % (diff, tolerance), "RATE_MISMATCH")


# --------------------------------------------------------------------------
# C3 — verdict vs preregistration rule
# --------------------------------------------------------------------------

_OPS = {
    "gte": lambda v, t: v >= t,
    "gt": lambda v, t: v > t,
    "lte": lambda v, t: v <= t,
    "lt": lambda v, t: v < t,
    "eq": lambda v, t: v == t,
}


def check_c3(package: Package, manifest: dict, integrity: dict, result: CheckResult):
    spec = manifest.get("verdict_check")
    if not isinstance(spec, dict):
        result.add("manifest.verdict_check", UNKNOWN,
                   "no verdict check declared in the manifest", "NOT_DECLARED")
        result.evidence_missing.append("manifest.verdict_check")
        result.next_step = "Declare preregistration + results artifacts, or accept UNKNOWN for C3."
        return
    result.dependencies = ["C1 integrity of the preregistration and results artifacts",
                           "the preregistration rule shape {metric, op, threshold}"]
    prereg_ref = spec.get("preregistration", {})
    results_ref = spec.get("results", {})
    prereg = _load_for_assertion(package, integrity, prereg_ref, result)
    results_doc = _load_for_assertion(package, integrity, results_ref, result)
    if prereg is None or results_doc is None:
        result.add("verdict_check", UNKNOWN, "an input could not be loaded (see items above)", "DEPENDENCY_UNRESOLVED")
        return
    rule_pointer = prereg_ref.get("rule_pointer", "/protocol/pass_rule")
    try:
        rule = resolve_pointer(prereg, rule_pointer)
    except PointerError:
        try:
            rule = resolve_pointer(prereg, "/pass_rule")
        except PointerError as exc:
            result.add("pass_rule", UNKNOWN, "no pass_rule at %s or /pass_rule: %s" % (rule_pointer, exc), "RULE_AMBIGUOUS")
            result.evidence_missing.append("preregistration pass_rule")
            return
    if not isinstance(rule, dict):
        result.add("pass_rule", UNKNOWN, "pass_rule is not an object; rule ambiguous", "RULE_AMBIGUOUS")
        return
    metric = rule.get("metric")
    op = rule.get("op") or ("gte" if "gte" in rule else "gt" if "gt" in rule
                            else "lte" if "lte" in rule else "lt" if "lt" in rule
                            else "eq" if "eq" in rule else None)
    threshold_raw = rule.get("threshold", rule.get(op) if op else None)
    if not isinstance(metric, str) or op not in _OPS or threshold_raw is None:
        code = "RULE_UNSUPPORTED" if (op is not None and op not in _OPS) else "RULE_AMBIGUOUS"
        result.add("pass_rule", UNKNOWN,
                   "rule shape unsupported or ambiguous (need metric, one op of %s, threshold); "
                   "the checker stops instead of guessing" % sorted(_OPS), code)
        result.evidence_missing.append("unambiguous pass_rule")
        return
    try:
        threshold = as_decimal(threshold_raw)
    except PointerError as exc:
        result.add("pass_rule", UNKNOWN, str(exc), "RULE_AMBIGUOUS")
        return
    result.evidence_present.append("pass_rule: %s %s %s" % (metric, op, threshold))
    if not isinstance(results_doc, list):
        result.add("results", UNKNOWN, "results artifact did not parse as JSONL records", "INPUT_MALFORMED")
        return
    if not results_doc:
        result.add("results", UNKNOWN, "results artifact contains no records", "EMPTY_INPUT")
        return
    for idx, entry in enumerate(results_doc):
        label = "entry[%d]" % idx
        if not isinstance(entry, dict) or not isinstance(entry.get("result"), dict):
            result.add(label, UNKNOWN, "record has no result object", "INPUT_MALFORMED")
            continue
        rec = entry["result"]
        metrics = rec.get("metrics")
        verdict = rec.get("verdict")
        if not isinstance(metrics, dict) or metric not in metrics:
            result.add(label, UNKNOWN, "metric %r missing from result.metrics" % metric, "METRIC_MISSING")
            result.evidence_missing.append("%s metric %s" % (label, metric))
            continue
        if not is_number(metrics[metric]):
            result.add(label, UNKNOWN, "metric %r is not numeric: %r" % (metric, metrics[metric]), "METRIC_NON_NUMERIC")
            continue
        if not isinstance(verdict, str) or verdict.strip().lower() not in ("pass", "fail"):
            result.add(label, UNKNOWN,
                       "verdict %r is not decidable (only pass/fail are); abstentions and "
                       "other verdicts stop the checker" % (verdict,), "VERDICT_UNDECIDABLE")
            continue
        expected = "pass" if _OPS[op](as_decimal(metrics[metric]), threshold) else "fail"
        actual = verdict.strip().lower()
        if expected == actual:
            result.add(label, SESUAI,
                       "metric %s=%s %s %s -> expected %s, recorded %s"
                       % (metric, show(metrics[metric]), op, threshold, expected, actual), "OK")
            result.evidence_present.append(label)
        else:
            result.add(label, TIDAK_SESUAI,
                       "metric %s=%s %s %s -> expected %s, recorded %s"
                       % (metric, show(metrics[metric]), op, threshold, expected, actual), "VERDICT_MISMATCH")
    result.next_step = ("For TIDAK SESUAI: the recorded verdict contradicts the preregistered "
                        "rule on complete inputs. For UNKNOWN: supply the metric/rule in the "
                        "supported shape, or record the entry's verdict as pass/fail.")



# --------------------------------------------------------------------------
# V2-2 — validation_spec_digest
# --------------------------------------------------------------------------

def _canonical(value):
    """Canonical form for digesting: sorted dict keys, lists in order,
    Decimals tagged by their exact string, scalars as-is."""
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    return {"__repr__": repr(value)}


def validator_build_stamp():
    """Build identity of this validator: version + SHA-256 of its own source.
    Raises OSError if the source cannot be read (a PROCESS failure, V2-3)."""
    source = Path(__file__).read_bytes()
    return {"version": VALIDATOR_VERSION,
            "source_sha256": hashlib.sha256(source).hexdigest()}


def compute_spec_digest(manifest: dict, build_stamp: dict) -> str:
    """SHA-256 closing the evidence closure + ruleset + validator build +
    configuration. Any change to any component yields a new digest, and
    verdicts under different digests are different verdicts (freeze V2-2)."""
    artifacts = manifest.get("artifacts") or []
    closure = sorted(
        ({"path": a.get("path"), "sha256": a.get("sha256"),
          "size_bytes": a.get("size_bytes")}
         for a in artifacts if isinstance(a, dict)),
        key=lambda a: str(a.get("path")))
    spec = {
        "evidence_closure": closure,
        "ruleset": {
            "count_assertions": manifest.get("count_assertions"),
            "verdict_check": manifest.get("verdict_check"),
        },
        "validator_build": build_stamp,
        "configuration": {
            "report_schema": SCHEMA_REPORT,
            "manifest_schema": SCHEMA_MANIFEST,
            "reason_code_registry_version": REASON_CODE_REGISTRY_VERSION,
            "stage_model_version": STAGE_MODEL_VERSION,
        },
    }
    blob = json.dumps(_canonical(spec), sort_keys=True,
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# --------------------------------------------------------------------------
# Report + CLI
# --------------------------------------------------------------------------

def validate(manifest_bytes: bytes, source_root: Path, build_stamp: dict = None) -> dict:
    manifest = parse_json_bytes(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA_MANIFEST:
        raise ParseError("manifest schema must be %s" % SCHEMA_MANIFEST)
    if build_stamp is None:
        build_stamp = validator_build_stamp()
    spec_digest = compute_spec_digest(manifest, build_stamp)
    package = Package(source_root)
    c1 = CheckResult("C1", "Artifact completeness + hash integrity")
    integrity = check_c1(package, manifest, c1)
    c2 = CheckResult("C2", "Result-count consistency (declared recomputations only)")
    check_c2(package, manifest, integrity, c2)
    c3 = CheckResult("C3", "Verdict vs preregistration rule")
    check_c3(package, manifest, integrity, c3)
    for c in (c1, c2, c3):
        c.spec_digest = spec_digest
    checks = [c1.to_dict(), c2.to_dict(), c3.to_dict()]
    # Self-audit: every item must carry a registry code matching its state,
    # and the lifecycle order must be exactly the frozen stage order.
    for check in checks:
        assert check["stage"] == OUTPUT_STAGE
        for item in check["items"]:
            assert REASON_CODES.get(item["reason_code"]) == item["state"], item
    summary = {SESUAI: 0, TIDAK_SESUAI: 0, UNKNOWN: 0}
    for c in checks:
        summary[c["state"]] += 1
    unlisted = 0
    listed = {a.get("path") for a in manifest.get("artifacts", []) if isinstance(a, dict)}
    for path in package.root.rglob("*"):
        if path.is_file():
            rel = str(path.relative_to(package.root))
            if rel not in listed:
                unlisted += 1
    input_stage = "REGISTERED OBSERVATION" if c1.state == SESUAI else "STAGED"
    return {
        "schema": SCHEMA_REPORT,
        "validator_version": VALIDATOR_VERSION,
        "validation_spec_digest": spec_digest,
        "validator_build": build_stamp,
        "lifecycle": {
            "stages": STAGES,
            "stage_model_version": STAGE_MODEL_VERSION,
            "input_stage": input_stage,
            "output_stage": OUTPUT_STAGE,
            "stages_not_performed": ["PUBLISHED RESULT"],
            "note": "This report is a VALIDATION VERDICT-stage artifact. "
                    "Publication is a separate act the validator never performs.",
        },
        "disclaimer": DISCLAIMER,
        "package_id": manifest.get("package_id", ""),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "checks": checks,
        "summary_by_state": summary,
        "unlisted_files_informational_only": unlisted,
        "honest_limits": [
            "Proves the package matches its manifest on the declared mechanical checks only.",
            "Does not prove the manifest is the right manifest, that the preregistration predates the results, or that declared recomputations are scientifically correct.",
            "Does not approve or validate any experiment, result, or gate claim.",
        ],
    }


def exit_code_for(report: dict) -> int:
    states = {c["state"] for c in report["checks"]}
    if TIDAK_SESUAI in states:
        return 2
    if UNKNOWN in states:
        return 3
    return 0


def render_markdown(report: dict) -> str:
    lines = [
        "# Laporan Pra-Audit Mekanis — %s" % report.get("package_id", ""),
        "",
        "> " + report["disclaimer"],
        "",
        "Validator: %s · Manifest SHA-256: `%s`" % (report["validator_version"], report["manifest_sha256"]),
        "",
        "Validation spec digest: `%s`" % report["validation_spec_digest"],
        "",
        "Siklus hidup: %s · Masukan: %s · Keluaran: %s · Tidak dilakukan: %s" % (
            " → ".join(report["lifecycle"]["stages"]),
            report["lifecycle"]["input_stage"],
            report["lifecycle"]["output_stage"],
            ", ".join(report["lifecycle"]["stages_not_performed"])),
        "",
        "Ringkasan (hitungan keadaan per cek — bukan persetujuan): %s" % report["summary_by_state"],
        "",
    ]
    for check in report["checks"]:
        lines.append("## %s — %s: **%s**" % (check["check_id"], check["title"], check["state"]))
        lines.append("")
        for item in check["items"]:
            lines.append("- [%s] %s — %s (kode: %s)" % (item["state"], item["item"], item["reason"], item["reason_code"]))
        if check["evidence_missing"]:
            lines.append("- Bukti kurang: %s" % "; ".join(check["evidence_missing"]))
        if check["dependencies"]:
            lines.append("- Dependensi: %s" % "; ".join(check["dependencies"]))
        lines.append("- Kelas false-positive: %s" % check["false_positive_class"])
        lines.append("- Langkah berikut: %s" % check["next_step"])
        lines.append("")
    lines.append("## Batas jujur")
    for limit in report["honest_limits"]:
        lines.append("- " + limit)
    lines.append("")
    lines.append("Berkas dalam pohon sumber yang tidak terdaftar di manifest (informasi saja, "
                 "bukan masukan vonis): %d" % report["unlisted_files_informational_only"])
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, data: bytes):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def _process_error(out_dir, disjoint_ok, message):
    """V2-3: a validator failure is a PROCESS record, never a verdict.
    It carries no check states and no verdict fields, and no report file
    is written by the failed run."""
    if disjoint_ok:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "kind": "PROCESS_ERROR",
                "stage": "PROCESS",
                "validator_version": VALIDATOR_VERSION,
                "error": message,
                "verdict": None,
                "note": "This is a process status, not a validation verdict. "
                        "No check was decided by this run and nothing here "
                        "may be cached or quoted as a verdict.",
            }
            _write_atomic(out_dir / "process_error.json",
                          (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        except OSError:
            pass
    print("PROCESS_ERROR: %s" % message, file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="preaudit_validator",
                                     description="Mechanical offline pre-audit of a frozen ACE evidence package.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    disjoint_ok = source_root.is_dir() and not (
        source_root == out_dir or source_root in out_dir.parents or out_dir in source_root.parents)
    if not source_root.is_dir():
        return _process_error(out_dir, False, "source root is not a directory: %s" % source_root)
    if not disjoint_ok:
        return _process_error(out_dir, False,
                              "out-dir and source root must be disjoint (read-only source enforcement)")
    try:
        manifest_bytes = Path(args.manifest).read_bytes()
        report = validate(manifest_bytes, source_root)
    except (OSError, ParseError) as exc:
        return _process_error(out_dir, True, "checker stopped before any verdict: %s" % exc)
    except Exception as exc:  # a validator bug is a PROCESS failure, not a verdict
        return _process_error(out_dir, True, "validator internal failure: %r" % (exc,))

    spec16 = report["validation_spec_digest"][:16]
    json_bytes = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    md_bytes = render_markdown(report).encode("utf-8")
    targets = [(out_dir / ("report-%s.json" % spec16), json_bytes),
               (out_dir / ("report-%s.md" % spec16), md_bytes)]
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        # V2-5: same spec + different bytes = nondeterminism conflict, audited,
        # never overwritten.
        conflicts = []
        for path, data in targets:
            if path.is_file() and path.read_bytes() != data:
                conflicts.append({
                    "file": path.name,
                    "stored_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "computed_sha256": hashlib.sha256(data).hexdigest(),
                })
        if conflicts:
            record = {
                "kind": "NONDETERMINISM_CONFLICT",
                "stage": "PROCESS",
                "validation_spec_digest": report["validation_spec_digest"],
                "conflicts": conflicts,
                "note": "Two different outputs were computed for the same "
                        "validation_spec_digest. The stored verdict was NOT "
                        "overwritten; this divergence must be audited.",
            }
            _write_atomic(out_dir / ("nondeterminism_conflict-%s.json" % spec16),
                          (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            print("NONDETERMINISM_CONFLICT for spec %s; stored verdict preserved" % spec16,
                  file=sys.stderr)
            return 4
        for path, data in targets:
            if not (path.is_file() and path.read_bytes() == data):
                _write_atomic(path, data)
    except OSError as exc:
        return _process_error(out_dir, True, "could not write report: %s" % exc)
    print(json.dumps({"summary_by_state": report["summary_by_state"],
                      "validation_spec_digest": report["validation_spec_digest"]},
                     sort_keys=True))
    return exit_code_for(report)


if __name__ == "__main__":
    raise SystemExit(main())
