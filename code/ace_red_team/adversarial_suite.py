"""ACE Red Team Adversarial Security & Robustness Suite.

Provides comprehensive red teaming tools for ACE neurosymbolic synthesis and runtime:
- Fuzzing & Stress Testing with extreme payloads (empty, super long, non-ASCII, recursive, stack depth, cyclic graphs).
- Semantic Poisoning & Data Injection Detection (adversarial label flipping, backdoor injection, anomaly detection).
- Resource Exhaustion & Algorithmic Complexity Attack (empirical complexity profiling O(N^2)/O(2^N), DoS loop detection).
- RedTeamReport with quantitative robustness scores, categorized vulnerabilities, and actionable countermeasures.

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import math
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VulnerabilityCategory(str, Enum):
    FUZZ_CRASH = "FUZZ_CRASH"
    STACK_EXHAUSTION = "STACK_EXHAUSTION"
    CYCLIC_GRAPH_CRASH = "CYCLIC_GRAPH_CRASH"
    DATA_POISONING = "DATA_POISONING"
    BACKDOOR_INJECTION = "BACKDOOR_INJECTION"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    ALGORITHMIC_DOS = "ALGORITHMIC_DOS"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"


def _safe_repr(obj: Any, max_len: int = 100) -> str:
    """Safely computes a string representation without crashing on deep recursion or cycles."""
    try:
        if isinstance(obj, str):
            res = repr(obj)
        elif isinstance(obj, (int, float, bool, bytes, type(None))):
            res = repr(obj)
        else:
            res = repr(obj)
    except (RecursionError, Exception):
        res = f"<{type(obj).__name__} object (depth/cycle protected)>"
    if len(res) > max_len:
        return res[:max_len] + "..."
    return res


@dataclass
class RedTeamVulnerability:
    """Represents an adversarial vulnerability identified during audit."""
    vuln_id: str
    category: str
    severity: str
    title: str
    description: str
    reproduction_payload: Any
    countermeasure: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vuln_id": self.vuln_id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "reproduction_payload": _safe_repr(self.reproduction_payload, max_len=200),
            "countermeasure": self.countermeasure,
        }



class CountermeasureAdvisor:
    """Catalog of defensive countermeasures for ACE synthesis and runtime engines."""

    RECOMMENDATIONS: Dict[str, str] = {
        VulnerabilityCategory.FUZZ_CRASH.value: (
            "Implement input validation schemas with explicit type checking and length boundaries before parsing."
        ),
        VulnerabilityCategory.STACK_EXHAUSTION.value: (
            "Enforce recursion depth limit guards (e.g. max_depth <= 100) and convert deep recursive AST traversals to iterative stacks."
        ),
        VulnerabilityCategory.CYCLIC_GRAPH_CRASH.value: (
            "Integrate cycle detection via a visited object identity set (`id(obj)` or WeakSet) in all graph and AST traversals."
        ),
        VulnerabilityCategory.DATA_POISONING.value: (
            "Incorporate contradiction filtering and statistical noise filtering on training/specification counterexamples before inductive synthesis."
        ),
        VulnerabilityCategory.BACKDOOR_INJECTION.value: (
            "Perform trigger token isolation by checking character n-gram and token frequency correlation against label distributions."
        ),
        VulnerabilityCategory.RESOURCE_EXHAUSTION.value: (
            "Set execution timeouts and CPU quotas via watchdog timers for candidate program evaluation."
        ),
        VulnerabilityCategory.ALGORITHMIC_DOS.value: (
            "Refactor super-linear (O(N^2) or O(2^N)) algorithms using memoization/dynamic programming, indexed hash-maps, or bounded search windows."
        ),
        VulnerabilityCategory.UNHANDLED_EXCEPTION.value: (
            "Wrap external untrusted input processors in defensive exception boundaries with normalized error return types."
        ),
    }

    @classmethod
    def get_countermeasure(cls, category: str, fallback: Optional[str] = None) -> str:
        return cls.RECOMMENDATIONS.get(
            category,
            fallback or "Apply strict input bounds, defensive error handling, and sandboxed resource limits."
        )


class CyclicNode:
    """Graph node capable of holding cyclic references for testing graph safety."""

    def __init__(self, name: str, value: Any = None):
        self.name = name
        self.value = value
        self.neighbors: List[CyclicNode] = []
        self.next: Optional[CyclicNode] = None

    def add_edge(self, target: CyclicNode) -> None:
        self.neighbors.append(target)

    def __repr__(self) -> str:
        return f"CyclicNode({self.name!r}, neighbors_count={len(self.neighbors)})"


class FuzzPayloadGenerator:
    """Generates extreme adversarial payloads for fuzzing and stress testing."""

    @staticmethod
    def generate_empty_payloads() -> List[Any]:
        """Produces empty, null, and whitespace-only payloads."""
        return [
            "",
            b"",
            None,
            [],
            {},
            (),
            set(),
            "   ",
            "\t\n\r\t",
            "\x00",
        ]

    @staticmethod
    def generate_super_long_payloads(max_len: int = 100000) -> List[Any]:
        """Produces massive strings, repetitive sequences, and numerical boundaries."""
        return [
            "A" * 1000,
            "B" * 10000,
            "X" * max_len,
            b"Z" * 50000,
            [0] * 10000,
            2**63 - 1,
            2**64,
            10**100,
            -2**63,
            float("inf"),
            float("-inf"),
            float("nan"),
            1e308,
            1e-308,
        ]

    @staticmethod
    def generate_non_ascii_payloads() -> List[Any]:
        """Produces multi-byte Unicode, control codes, homoglyphs, and injection strings."""
        return [
            "こんにちは世界",
            "مرحبا بالعالم",
            "🔥🚀💻🛡️⚡️",
            "admin\x00secret",
            b"header\x00body\xff\xfe",
            "\u202eTXT.EXE\u202c",  # Right-to-Left Override
            "test\u200b\u200c\u200dtest",  # Zero-width spaces and joiners
            "раypаl",  # Cyrillic homoglyph for 'a'
            "\x01\x02\x03\x04\x1b[31mRed\x1b[0m",
            "' OR '1'='1' --",
            '"; rm -rf / ; echo "',
            "<script>alert(1)</script>",
            "{{7*7}}",
            "%s%s%s%s%n",
            "../../../../etc/passwd",
        ]

    @staticmethod
    def generate_recursive_nesting_payloads(depth: int = 50) -> List[Any]:
        """Produces deeply nested container hierarchies."""
        # Nested lists
        curr_list: Any = "leaf"
        for _ in range(depth):
            curr_list = [curr_list]

        # Nested dicts
        curr_dict: Any = "leaf"
        for i in range(depth):
            curr_dict = {f"k_{i}": curr_dict}

        # Nested tuples
        curr_tuple: Any = "leaf"
        for _ in range(depth):
            curr_tuple = (curr_tuple,)

        return [curr_list, curr_dict, curr_tuple]

    @staticmethod
    def generate_stack_exhaustion_payloads(depth: int = 1500) -> List[Any]:
        """Produces structures and strings crafted to exceed recursion and stack depth limits."""
        # Deeply nested parentheses string
        nested_parens = "(" * depth + "42" + ")" * depth
        # Deeply chained dictionary
        deep_dict: Any = 1
        for _ in range(depth):
            deep_dict = {"next": deep_dict}

        return [nested_parens, deep_dict]

    @staticmethod
    def generate_cyclic_graph_payloads() -> List[Any]:
        """Produces self-referencing and mutually recursive graph structures."""
        # Self-referencing list
        self_list: List[Any] = [1, 2]
        self_list.append(self_list)

        # Mutually referencing lists
        list_a: List[Any] = [10]
        list_b: List[Any] = [20, list_a]
        list_a.append(list_b)

        # Self-referencing dict
        self_dict: Dict[str, Any] = {"name": "loop"}
        self_dict["self"] = self_dict

        # CyclicNode objects
        n1 = CyclicNode("Node1")
        n2 = CyclicNode("Node2")
        n1.add_edge(n2)
        n2.add_edge(n1)
        n1.next = n2
        n2.next = n1

        return [self_list, list_a, self_dict, n1]

    @classmethod
    def get_all_payloads(cls) -> Dict[str, List[Any]]:
        """Returns categorized dictionary of all extreme payloads."""
        return {
            "empty": cls.generate_empty_payloads(),
            "super_long": cls.generate_super_long_payloads(),
            "non_ascii": cls.generate_non_ascii_payloads(),
            "recursive_nesting": cls.generate_recursive_nesting_payloads(),
            "stack_exhaustion": cls.generate_stack_exhaustion_payloads(),
            "cyclic_graph": cls.generate_cyclic_graph_payloads(),
        }


@dataclass
class FuzzResult:
    """Results from a fuzzing audit run."""
    total_tested: int
    passed: int
    graceful_rejections: int
    crashes: int
    timeouts: int
    unhandled_errors: int
    vulnerabilities: List[RedTeamVulnerability] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.crashes == 0 and self.timeouts == 0 and len(self.vulnerabilities) == 0


class FuzzerEngine:
    """Executes fuzzing campaigns with timeout guards and crash detection."""

    SAFE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
        UnicodeError,
        AttributeError,
    )

    @staticmethod
    def _run_with_timeout(
        fn: Callable[[Any], Any],
        arg: Any,
        timeout_sec: float,
    ) -> Tuple[bool, Any, Optional[BaseException]]:
        """Runs fn(arg) in a daemon thread to safely catch infinite loops and hangs."""
        result = [None]
        exception = [None]
        completed = threading.Event()

        def worker() -> None:
            try:
                result[0] = fn(arg)
            except BaseException as exc:
                exception[0] = exc
            finally:
                completed.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        finished = completed.wait(timeout_sec)

        if not finished:
            return False, None, TimeoutError(f"Execution timed out after {timeout_sec:.2f}s")
        if exception[0] is not None:
            return False, None, exception[0]
        return True, result[0], None

    def fuzz_target(
        self,
        target_fn: Callable[[Any], Any],
        payloads: Optional[Dict[str, List[Any]]] = None,
        timeout_sec: float = 0.5,
        target_name: str = "TargetFunction",
    ) -> FuzzResult:
        """Executes a target function against payload suites and analyzes outcomes."""
        all_payloads = payloads or FuzzPayloadGenerator.get_all_payloads()
        total = 0
        passed = 0
        graceful = 0
        crashes = 0
        timeouts = 0
        unhandled = 0
        vulns: List[RedTeamVulnerability] = []
        details: List[Dict[str, Any]] = []

        vuln_counter = 0

        for category, items in all_payloads.items():
            for idx, payload in enumerate(items):
                total += 1
                success, output, err = self._run_with_timeout(target_fn, payload, timeout_sec)

                if success:
                    passed += 1
                    details.append({
                        "category": category,
                        "status": "PASS",
                        "error": None,
                        "payload": _safe_repr(payload, max_len=80),
                    })
                elif isinstance(err, TimeoutError):
                    timeouts += 1
                    vuln_counter += 1
                    v = RedTeamVulnerability(
                        vuln_id=f"VULN-DOS-{vuln_counter:03d}",
                        category=VulnerabilityCategory.RESOURCE_EXHAUSTION.value,
                        severity=SeverityLevel.HIGH.value,
                        title=f"Execution timeout on {category} payload",
                        description=f"Function hung or exceeded {timeout_sec}s threshold when processing payload.",
                        reproduction_payload=payload,
                        countermeasure=CountermeasureAdvisor.get_countermeasure(
                            VulnerabilityCategory.RESOURCE_EXHAUSTION.value
                        ),
                    )
                    vulns.append(v)
                    details.append({
                        "category": category,
                        "status": "TIMEOUT",
                        "error": str(err),
                        "payload": _safe_repr(payload, max_len=80),
                    })
                elif isinstance(err, RecursionError):
                    crashes += 1
                    vuln_counter += 1
                    cat = (
                        VulnerabilityCategory.CYCLIC_GRAPH_CRASH.value
                        if category == "cyclic_graph"
                        else VulnerabilityCategory.STACK_EXHAUSTION.value
                    )
                    v = RedTeamVulnerability(
                        vuln_id=f"VULN-REC-{vuln_counter:03d}",
                        category=cat,
                        severity=SeverityLevel.CRITICAL.value,
                        title=f"Stack/Recursion crash on {category} payload",
                        description=f"Unbounded recursion caused Python RecursionError: {err}",
                        reproduction_payload=payload,
                        countermeasure=CountermeasureAdvisor.get_countermeasure(cat),
                    )
                    vulns.append(v)
                    details.append({
                        "category": category,
                        "status": "CRASH",
                        "error": f"RecursionError: {err}",
                        "payload": _safe_repr(payload, max_len=80),
                    })
                elif isinstance(err, (MemoryError, SystemError)):
                    crashes += 1
                    vuln_counter += 1
                    v = RedTeamVulnerability(
                        vuln_id=f"VULN-SYS-{vuln_counter:03d}",
                        category=VulnerabilityCategory.FUZZ_CRASH.value,
                        severity=SeverityLevel.CRITICAL.value,
                        title=f"Fatal memory/system error on {category} payload",
                        description=f"Target caused severe failure: {type(err).__name__}: {err}",
                        reproduction_payload=payload,
                        countermeasure=CountermeasureAdvisor.get_countermeasure(
                            VulnerabilityCategory.FUZZ_CRASH.value
                        ),
                    )
                    vulns.append(v)
                    details.append({
                        "category": category,
                        "status": "CRASH",
                        "error": str(err),
                        "payload": _safe_repr(payload, max_len=80),
                    })
                elif isinstance(err, self.SAFE_EXCEPTIONS):
                    graceful += 1
                    details.append({
                        "category": category,
                        "status": "GRACEFUL_REJECTION",
                        "error": f"{type(err).__name__}: {err}",
                        "payload": _safe_repr(payload, max_len=80),
                    })
                else:
                    unhandled += 1
                    vuln_counter += 1
                    v = RedTeamVulnerability(
                        vuln_id=f"VULN-ERR-{vuln_counter:03d}",
                        category=VulnerabilityCategory.UNHANDLED_EXCEPTION.value,
                        severity=SeverityLevel.MEDIUM.value,
                        title=f"Unhandled {type(err).__name__} on {category}",
                        description=f"Target threw unexpected exception without graceful handling: {err}",
                        reproduction_payload=payload,
                        countermeasure=CountermeasureAdvisor.get_countermeasure(
                            VulnerabilityCategory.UNHANDLED_EXCEPTION.value
                        ),
                    )
                    vulns.append(v)
                    details.append({
                        "category": category,
                        "status": "UNHANDLED_ERROR",
                        "error": f"{type(err).__name__}: {err}",
                        "payload": _safe_repr(payload, max_len=80),
                    })

        return FuzzResult(
            total_tested=total,
            passed=passed,
            graceful_rejections=graceful,
            crashes=crashes,
            timeouts=timeouts,
            unhandled_errors=unhandled,
            vulnerabilities=vulns,
            details=details,
        )


class AdversarialDataPoisoner:
    """Injects adversarial poisoning into synthesis datasets."""

    @staticmethod
    def apply_label_flipping(
        data: List[Tuple[Any, bool]],
        poison_ratio: float = 0.2,
        seed: int = 42,
    ) -> List[Tuple[Any, bool]]:
        """Flips boolean classification labels for a fraction of the dataset."""
        import random
        if not data:
            return []
        rng = random.Random(seed)
        num_to_flip = max(1, int(len(data) * poison_ratio))
        flip_indices = set(rng.sample(range(len(data)), min(num_to_flip, len(data))))

        poisoned: List[Tuple[Any, bool]] = []
        for i, (inp, lbl) in enumerate(data):
            if i in flip_indices:
                poisoned.append((inp, not lbl))
            else:
                poisoned.append((inp, lbl))
        return poisoned

    @staticmethod
    def apply_backdoor_injection(
        data: List[Tuple[str, bool]],
        trigger: str = "__ace_trigger__",
        target_label: bool = True,
        poison_ratio: float = 0.2,
        seed: int = 42,
    ) -> Tuple[List[Tuple[str, bool]], List[Tuple[str, bool]]]:
        """Injects a backdoor trigger substring into inputs, forcing a specific target label.

        Returns:
            (poisoned_train_data, backdoor_test_eval_set)
        """
        import random
        rng = random.Random(seed)
        num_poison = max(1, int(len(data) * poison_ratio))
        indices = set(rng.sample(range(len(data)), min(num_poison, len(data))))

        train_set: List[Tuple[str, bool]] = []
        backdoor_test: List[Tuple[str, bool]] = []

        for i, (inp, lbl) in enumerate(data):
            if i in indices:
                poisoned_inp = f"{trigger}{inp}"
                train_set.append((poisoned_inp, target_label))
            else:
                train_set.append((inp, lbl))

        for inp, _ in data:
            backdoor_test.append((f"{trigger}{inp}", target_label))

        return train_set, backdoor_test

    @staticmethod
    def apply_contradiction_injection(
        data: List[Tuple[Any, Any]],
        num_conflicts: int = 2,
    ) -> List[Tuple[Any, Any]]:
        """Injects direct duplicate inputs with conflicting labels to test solver resilience."""
        poisoned = list(data)
        if not data:
            return poisoned
        for i in range(min(num_conflicts, len(data))):
            inp, lbl = data[i]
            inverted = not lbl if isinstance(lbl, bool) else f"CONFLICT_{lbl}"
            poisoned.append((inp, inverted))
        return poisoned


class PoisonDetector:
    """Detects adversarial poisoning, contradictory labels, and anomalous triggers."""

    @staticmethod
    def detect_label_conflicts(data: List[Tuple[Any, Any]]) -> List[Dict[str, Any]]:
        """Identifies identical inputs mapped to conflicting output labels."""
        seen: Dict[str, Any] = {}
        conflicts: List[Dict[str, Any]] = []

        for inp, lbl in data:
            key = _safe_repr(inp, max_len=200)
            if key in seen:
                if seen[key] != lbl:
                    conflicts.append({
                        "input": _safe_repr(inp, max_len=100),
                        "existing_label": seen[key],
                        "conflicting_label": lbl,
                    })
            else:
                seen[key] = lbl
        return conflicts

    @staticmethod
    def detect_trigger_anomalies(
        data: List[Tuple[str, Any]],
        min_support: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """Detects candidate trigger substrings strongly correlated with specific labels."""
        if len(data) < 4:
            return []

        # Count common substrings of length 4..16
        substring_counts: Dict[str, Dict[Any, int]] = {}
        total_samples = len(data)

        for inp, lbl in data:
            if not isinstance(inp, str) or len(inp) < 4:
                continue
            words = inp.split("_")
            candidates = set(words)
            if len(inp) >= 6:
                candidates.add(inp[:6])
                candidates.add(inp[-6:])

            for cand in candidates:
                if len(cand) < 3:
                    continue
                if cand not in substring_counts:
                    substring_counts[cand] = {}
                substring_counts[cand][lbl] = substring_counts[cand].get(lbl, 0) + 1

        suspects: List[Dict[str, Any]] = []
        for cand, label_counts in substring_counts.items():
            total_cand = sum(label_counts.values())
            if total_cand / total_samples < min_support:
                continue
            # If one label dominates >= 90% when trigger is present
            for lbl, count in label_counts.items():
                purity = count / total_cand
                if purity >= 0.9 and total_cand >= 2:
                    suspects.append({
                        "candidate_trigger": cand,
                        "associated_label": lbl,
                        "occurrences": total_cand,
                        "purity": round(purity, 3),
                    })
        return suspects

    @staticmethod
    def detect_length_outliers(
        data: List[Tuple[Any, Any]],
        z_threshold: float = 2.5,
    ) -> List[int]:
        """Identifies input length outliers using standard z-score analysis."""
        lengths = [len(str(inp)) for inp, _ in data]
        if len(lengths) < 4:
            return []
        mean_len = sum(lengths) / len(lengths)
        variance = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
        std_len = math.sqrt(variance)
        if std_len < 1e-6:
            return []

        outlier_indices = []
        for idx, l in enumerate(lengths):
            z = abs(l - mean_len) / std_len
            if z > z_threshold:
                outlier_indices.append(idx)
        return outlier_indices


@dataclass
class PoisonEvaluationResult:
    """Metrics assessing synthesizer susceptibility to poisoned training data."""
    clean_accuracy: float
    poisoned_accuracy: float
    attack_success_rate: float
    susceptibility_score: float
    detected_conflicts: int
    detected_triggers: List[Dict[str, Any]]
    is_compromised: bool
    vulnerabilities: List[RedTeamVulnerability] = field(default_factory=list)


class ComplexityAttacker:
    """Measures empirical computational complexity and detects Denial-of-Service loops."""

    @staticmethod
    def measure_complexity(
        target_fn: Callable[[Any], Any],
        input_generator: Callable[[int], Any],
        scales: Tuple[int, ...] = (10, 20, 40, 80),
        repetitions: int = 3,
        timeout_sec: float = 2.0,
    ) -> ComplexityProfile:
        """Measures runtime scaling across doubling input sizes to infer complexity class."""
        timings: List[float] = []
        measurements: List[Dict[str, Any]] = []

        for scale in scales:
            samples: List[float] = []
            for _ in range(repetitions):
                inp = input_generator(scale)
                t0 = time.perf_counter()
                try:
                    target_fn(inp)
                    elapsed = time.perf_counter() - t0
                    samples.append(elapsed)
                except Exception:
                    samples.append(timeout_sec)
            avg_time = sum(samples) / len(samples)
            timings.append(avg_time)
            measurements.append({"scale": scale, "runtime_sec": avg_time})

        # Calculate growth factors R = T(2N) / T(N)
        growth_factors: List[float] = []
        for i in range(1, len(timings)):
            prev = max(timings[i - 1], 1e-7)
            growth_factors.append(timings[i] / prev)

        avg_growth = sum(growth_factors) / len(growth_factors) if growth_factors else 1.0

        # Infer complexity class
        # Ratio around 1.0 -> O(1)
        # Ratio around 2.0 -> O(N)
        # Ratio around 4.0 -> O(N^2)
        # Ratio >= 7.0 -> O(N^3) or exponential O(2^N)
        if avg_growth < 1.3:
            inferred = "O(1)"
            is_dos_risk = False
        elif avg_growth < 2.6:
            inferred = "O(N)"
            is_dos_risk = False
        elif avg_growth < 3.2:
            inferred = "O(N log N)"
            is_dos_risk = False
        elif avg_growth < 5.5:
            inferred = "O(N^2)"
            is_dos_risk = True
        elif avg_growth < 9.0:
            inferred = "O(N^3)"
            is_dos_risk = True
        else:
            inferred = "O(2^N)"
            is_dos_risk = True

        return ComplexityProfile(
            inferred_complexity=inferred,
            growth_factors=growth_factors,
            average_growth_factor=round(avg_growth, 3),
            measurements=measurements,
            is_dos_risk=is_dos_risk,
            worst_case_runtime_sec=max(timings) if timings else 0.0,
        )

    @staticmethod
    def detect_dos_loops(
        target_fn: Callable[[Any], Any],
        pathological_inputs: List[Any],
        timeout_sec: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Tests pathological inputs to detect unbounded loops or execution hangs."""
        dos_events: List[Dict[str, Any]] = []

        for idx, payload in enumerate(pathological_inputs):
            res_holder = [None]
            err_holder = [None]
            ev = threading.Event()

            def run_target() -> None:
                try:
                    res_holder[0] = target_fn(payload)
                except BaseException as ex:
                    err_holder[0] = ex
                finally:
                    ev.set()

            t = threading.Thread(target=run_target, daemon=True)
            t.start()
            finished = ev.wait(timeout_sec)

            if not finished:
                dos_events.append({
                    "payload_index": idx,
                    "payload_repr": _safe_repr(payload, max_len=100),
                    "status": "TIMEOUT_DOS",
                    "elapsed_threshold_sec": timeout_sec,
                })
        return dos_events


@dataclass
class ComplexityProfile:
    """Empirical complexity analysis metrics."""
    inferred_complexity: str
    growth_factors: List[float]
    average_growth_factor: float
    measurements: List[Dict[str, Any]]
    is_dos_risk: bool
    worst_case_runtime_sec: float


@dataclass
class RedTeamReport:
    """Comprehensive Red Team audit deliverable."""
    target_name: str
    timestamp: str
    robustness_score: float  # 0.0 to 100.0
    vulnerabilities: List[RedTeamVulnerability]
    fuzzing_summary: Dict[str, Any]
    poisoning_summary: Dict[str, Any]
    complexity_summary: Dict[str, Any]
    countermeasure_suggestions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_name": self.target_name,
            "timestamp": self.timestamp,
            "robustness_score": self.robustness_score,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "fuzzing_summary": self.fuzzing_summary,
            "poisoning_summary": self.poisoning_summary,
            "complexity_summary": self.complexity_summary,
            "countermeasure_suggestions": self.countermeasure_suggestions,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        lines = [
            f"# ACE Red Team Adversarial Security Audit Report",
            f"**Target:** `{self.target_name}`  ",
            f"**Timestamp:** `{self.timestamp}`  ",
            f"**Robustness Score:** `{self.robustness_score:.1f} / 100.0`  \n",
            f"## Executive Summary",
            f"- Total Vulnerabilities Found: **{len(self.vulnerabilities)}**",
            f"- Fuzzing Status: {self.fuzzing_summary.get('status', 'N/A')}",
            f"- Inferred Algorithmic Complexity: `{self.complexity_summary.get('inferred_complexity', 'UNKNOWN')}`",
            f"- Poison Resistance: {self.poisoning_summary.get('poison_resistance', 'N/A')}  \n",
        ]

        if self.vulnerabilities:
            lines.append("## Identified Vulnerabilities")
            for v in self.vulnerabilities:
                lines.append(f"### [{v.severity}] {v.vuln_id}: {v.title}")
                lines.append(f"- **Category:** `{v.category}`")
                lines.append(f"- **Description:** {v.description}")
                lines.append(f"- **Reproduction Payload:** `{_safe_repr(v.reproduction_payload, max_len=120)}`")
                lines.append(f"- **Countermeasure:** {v.countermeasure}\n")
        else:
            lines.append("## Identified Vulnerabilities\n*No critical vulnerabilities detected.*\n")

        lines.append("## Strategic Countermeasures & Hardening Recommendations")
        for rec in self.countermeasure_suggestions:
            lines.append(f"- {rec}")

        return "\n".join(lines)


class RedTeamAdversarialEngine:
    """Master orchestrator for ACE adversarial campaigns and security audits."""

    def __init__(self) -> None:
        self.fuzzer = FuzzerEngine()
        self.poisoner = AdversarialDataPoisoner()
        self.detector = PoisonDetector()
        self.complexity_attacker = ComplexityAttacker()

    def run_fuzzing_campaign(
        self,
        target_fn: Callable[[Any], Any],
        payloads: Optional[Dict[str, List[Any]]] = None,
        timeout_sec: float = 0.5,
        target_name: str = "TargetFunction",
    ) -> FuzzResult:
        """Executes full fuzzing suite against target."""
        return self.fuzzer.fuzz_target(
            target_fn=target_fn,
            payloads=payloads,
            timeout_sec=timeout_sec,
            target_name=target_name,
        )

    def run_poisoning_campaign(
        self,
        synthesizer_fn: Callable[[List[Tuple[str, bool]]], Any],
        clean_train_data: List[Tuple[str, bool]],
        clean_test_data: List[Tuple[str, bool]],
        poison_ratio: float = 0.2,
    ) -> PoisonEvaluationResult:
        """Assesses synthesizer susceptibility to label flipping and backdoor attacks."""
        # 1. Clean Baseline
        clean_model = synthesizer_fn(clean_train_data)
        clean_acc = self._evaluate_model(clean_model, clean_test_data)

        # 2. Poisoned Data (Label Flipping)
        flipped_data = self.poisoner.apply_label_flipping(clean_train_data, poison_ratio=poison_ratio)
        conflicts = self.detector.detect_label_conflicts(flipped_data)
        flipped_model = synthesizer_fn(flipped_data)
        poisoned_acc = self._evaluate_model(flipped_model, clean_test_data)

        # 3. Backdoor Injection
        backdoor_train, backdoor_test = self.poisoner.apply_backdoor_injection(
            clean_train_data,
            trigger="__ace_bk__",
            target_label=True,
            poison_ratio=poison_ratio,
        )
        triggers = self.detector.detect_trigger_anomalies(backdoor_train)
        backdoor_model = synthesizer_fn(backdoor_train)
        asr = self._evaluate_model(backdoor_model, backdoor_test)

        # Susceptibility calculation: Drop in clean acc + Backdoor ASR
        drop = max(0.0, clean_acc - poisoned_acc)
        susceptibility = round((drop * 0.5 + asr * 0.5) * 100, 2)
        is_compromised = drop > 0.25 or asr > 0.75

        vulns: List[RedTeamVulnerability] = []
        if is_compromised:
            vulns.append(
                RedTeamVulnerability(
                    vuln_id="VULN-POISON-001",
                    category=VulnerabilityCategory.DATA_POISONING.value,
                    severity=SeverityLevel.HIGH.value,
                    title="Synthesizer Vulnerable to Semantic Data Poisoning",
                    description=(
                        f"Accuracy dropped from {clean_acc:.2f} to {poisoned_acc:.2f} under {poison_ratio*100:.0f}% "
                        f"poisoning. Attack Success Rate: {asr:.2f}."
                    ),
                    reproduction_payload={"poison_ratio": poison_ratio, "conflicts": len(conflicts)},
                    countermeasure=CountermeasureAdvisor.get_countermeasure(
                        VulnerabilityCategory.DATA_POISONING.value
                    ),
                )
            )

        return PoisonEvaluationResult(
            clean_accuracy=round(clean_acc, 3),
            poisoned_accuracy=round(poisoned_acc, 3),
            attack_success_rate=round(asr, 3),
            susceptibility_score=susceptibility,
            detected_conflicts=len(conflicts),
            detected_triggers=triggers,
            is_compromised=is_compromised,
            vulnerabilities=vulns,
        )

    def run_complexity_campaign(
        self,
        target_fn: Callable[[Any], Any],
        input_generator: Callable[[int], Any],
        scales: Tuple[int, ...] = (10, 20, 40, 80),
        pathological_inputs: Optional[List[Any]] = None,
        timeout_sec: float = 0.5,
    ) -> Tuple[ComplexityProfile, List[RedTeamVulnerability]]:
        """Evaluates computational complexity growth and scans for DoS loops."""
        profile = self.complexity_attacker.measure_complexity(
            target_fn=target_fn,
            input_generator=input_generator,
            scales=scales,
            timeout_sec=timeout_sec,
        )

        vulns: List[RedTeamVulnerability] = []
        if profile.is_dos_risk:
            severity = SeverityLevel.CRITICAL.value if "2^N" in profile.inferred_complexity else SeverityLevel.HIGH.value
            vulns.append(
                RedTeamVulnerability(
                    vuln_id="VULN-COMPLEXITY-001",
                    category=VulnerabilityCategory.ALGORITHMIC_DOS.value,
                    severity=severity,
                    title=f"Super-Linear Complexity Detected ({profile.inferred_complexity})",
                    description=(
                        f"Target exhibits growth factor {profile.average_growth_factor:.2f}, matching "
                        f"{profile.inferred_complexity}. High risk of Algorithmic DoS."
                    ),
                    reproduction_payload=profile.measurements,
                    countermeasure=CountermeasureAdvisor.get_countermeasure(
                        VulnerabilityCategory.ALGORITHMIC_DOS.value
                    ),
                )
            )

        if pathological_inputs:
            dos_events = self.complexity_attacker.detect_dos_loops(
                target_fn=target_fn,
                pathological_inputs=pathological_inputs,
                timeout_sec=timeout_sec,
            )
            for evt in dos_events:
                vulns.append(
                    RedTeamVulnerability(
                        vuln_id=f"VULN-DOS-LOOP-{evt['payload_index']:02d}",
                        category=VulnerabilityCategory.RESOURCE_EXHAUSTION.value,
                        severity=SeverityLevel.CRITICAL.value,
                        title="Denial-of-Service Hang on Pathological Input",
                        description=f"Execution hung exceeding {timeout_sec}s on input: {evt['payload_repr']}",
                        reproduction_payload=evt["payload_repr"],
                        countermeasure=CountermeasureAdvisor.get_countermeasure(
                            VulnerabilityCategory.RESOURCE_EXHAUSTION.value
                        ),
                    )
                )

        return profile, vulns

    def run_comprehensive_assessment(
        self,
        target_fn: Callable[[Any], Any],
        target_name: str = "ACE_System_Target",
        input_generator: Optional[Callable[[int], Any]] = None,
        scales: Tuple[int, ...] = (10, 20, 40, 80),
        pathological_inputs: Optional[List[Any]] = None,
        synthesizer_fn: Optional[Callable[[List[Tuple[str, bool]]], Any]] = None,
        spec_data: Optional[List[Tuple[str, bool]]] = None,
    ) -> RedTeamReport:
        """Executes an end-to-end red team assessment across all vulnerability vectors."""
        all_vulns: List[RedTeamVulnerability] = []
        countermeasures: Set[str] = set()

        # 1. Fuzzing
        fuzz_res = self.run_fuzzing_campaign(target_fn, target_name=target_name)
        all_vulns.extend(fuzz_res.vulnerabilities)
        fuzzing_summary = {
            "status": "PASS" if fuzz_res.is_clean else "VULNERABILITIES_FOUND",
            "total_tested": fuzz_res.total_tested,
            "passed": fuzz_res.passed,
            "graceful_rejections": fuzz_res.graceful_rejections,
            "crashes": fuzz_res.crashes,
            "timeouts": fuzz_res.timeouts,
            "unhandled_errors": fuzz_res.unhandled_errors,
        }

        # 2. Complexity Analysis
        gen = input_generator or (lambda n: "A" * n)
        comp_profile, comp_vulns = self.run_complexity_campaign(
            target_fn=target_fn,
            input_generator=gen,
            scales=scales,
            pathological_inputs=pathological_inputs,
        )
        all_vulns.extend(comp_vulns)
        complexity_summary = {
            "inferred_complexity": comp_profile.inferred_complexity,
            "average_growth_factor": comp_profile.average_growth_factor,
            "is_dos_risk": comp_profile.is_dos_risk,
            "worst_case_runtime_sec": comp_profile.worst_case_runtime_sec,
        }

        # 3. Poisoning Analysis (if synthesizer and spec data provided)
        poisoning_summary: Dict[str, Any] = {}
        if synthesizer_fn and spec_data and len(spec_data) >= 4:
            split_idx = len(spec_data) // 2
            train_d, test_d = spec_data[:split_idx], spec_data[split_idx:]
            p_res = self.run_poisoning_campaign(synthesizer_fn, train_d, test_d)
            all_vulns.extend(p_res.vulnerabilities)
            poisoning_summary = {
                "poison_resistance": "VULNERABLE" if p_res.is_compromised else "ROBUST",
                "clean_accuracy": p_res.clean_accuracy,
                "poisoned_accuracy": p_res.poisoned_accuracy,
                "attack_success_rate": p_res.attack_success_rate,
                "susceptibility_score": p_res.susceptibility_score,
            }
        else:
            poisoning_summary = {"status": "SKIPPED_NO_SYNTHESIZER"}

        # Calculate Robustness Score: 100 - penalties
        # CRITICAL = -25, HIGH = -15, MEDIUM = -8, LOW = -3
        penalties = 0.0
        for v in all_vulns:
            countermeasures.add(v.countermeasure)
            if v.severity == SeverityLevel.CRITICAL.value:
                penalties += 25.0
            elif v.severity == SeverityLevel.HIGH.value:
                penalties += 15.0
            elif v.severity == SeverityLevel.MEDIUM.value:
                penalties += 8.0
            else:
                penalties += 3.0

        robustness_score = max(0.0, min(100.0, 100.0 - penalties))

        if not countermeasures:
            countermeasures.add(
                "Maintain continuous fuzz testing and enforce runtime resource boundaries in CI/CD."
            )

        return RedTeamReport(
            target_name=target_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            robustness_score=round(robustness_score, 1),
            vulnerabilities=all_vulns,
            fuzzing_summary=fuzzing_summary,
            poisoning_summary=poisoning_summary,
            complexity_summary=complexity_summary,
            countermeasure_suggestions=sorted(list(countermeasures)),
        )

    @staticmethod
    def _evaluate_model(model: Any, test_data: List[Tuple[str, bool]]) -> float:
        """Safely evaluates a synthesized model or function against test data."""
        if not test_data:
            return 1.0
        correct = 0
        for inp, expected in test_data:
            try:
                if callable(model):
                    pred = bool(model(inp))
                elif hasattr(model, "predict"):
                    pred = bool(model.predict(inp))
                else:
                    pred = False
                if pred == expected:
                    correct += 1
            except Exception:
                pass
        return correct / len(test_data)
