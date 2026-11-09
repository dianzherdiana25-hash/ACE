"""High-throughput pure Python log parser and structured extractor synthesizer.

Synthesizes fast, injection-free parser routines from observed log lines
(e.g., syslog, Termux service logs, web server access logs).
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class LogRule:
    rule_id: str
    pattern: str
    field_names: Tuple[str, ...]
    extractor_code: str


class LogParserSynthesizer:
    """Synthesizes structured log parser functions from raw log strings."""

    def __init__(self):
        self.known_rules: Dict[str, LogRule] = {}

    def synthesize_regex_parser(
        self,
        sample_logs: List[str],
        expected_fields: List[Dict[str, str]],
        func_name: str = "parse_log_entry",
    ) -> Optional[LogRule]:
        """Synthesize a robust named-group regex parser matching all sample logs."""
        if not sample_logs or not expected_fields:
            return None

        first_sample = sample_logs[0]
        first_fields = expected_fields[0]

        # Escape special regex characters in the template while capturing variable fields
        tokens: List[str] = []
        last_idx = 0
        field_order: List[str] = []

        # Sort fields by their appearance index in first sample
        sorted_fields = []
        for k, v in first_fields.items():
            pos = first_sample.find(v)
            if pos != -1:
                sorted_fields.append((pos, k, v))
        sorted_fields.sort(key=lambda x: x[0])

        # Extract tokens by locating delimiters around fields
        # If prefix between fields is purely whitespace or simple delimiter, use exact delimiter.
        # Otherwise, if text varies across samples, use generic wildcard (.*?)
        pattern_parts = ["^"]
        for idx, (pos, key, val) in enumerate(sorted_fields):
            prefix = first_sample[last_idx:pos]
            if prefix:
                prefix_in_all = all(prefix in s for s in sample_logs)
                if prefix_in_all:
                    pattern_parts.append(re.escape(prefix))
                elif prefix.strip() == "":
                    pattern_parts.append(r"\s+")
                else:
                    pattern_parts.append(r".*?\s+")
            
            # Determine appropriate capture group with word boundaries
            if val.isdigit():
                pattern_parts.append(f"\\b(?P<{key}>\\d+)\\b")
            elif re.match(r"^[\d\-\+:TZ]+$", val):
                pattern_parts.append(f"(?P<{key}>[\\d\\-\\+:TZ]+)")
            elif " " not in val:
                pattern_parts.append(f"(?P<{key}>\\S+)")
            else:
                pattern_parts.append(f"(?P<{key}>.+?)")
            
            field_order.append(key)
            last_idx = pos + len(val)

        suffix = first_sample[last_idx:]
        if suffix and all(suffix in s for s in sample_logs):
            pattern_parts.append(re.escape(suffix))
        else:
            pattern_parts.append(r".*?")
        pattern_parts.append("$")
        final_pattern = "".join(pattern_parts)

        # Validate against all samples
        compiled_regex = re.compile(final_pattern)
        for log_line, exp_f in zip(sample_logs, expected_fields):
            m = compiled_regex.match(log_line)
            if not m:
                return None
            parsed = m.groupdict()
            for k, v in exp_f.items():
                if parsed.get(k) != v:
                    return None

        # Generate standalone pure-Python function source
        code = (
            f"import re\n\n"
            f"_LOG_REGEX = re.compile({repr(final_pattern)})\n\n"
            f"def {func_name}(line: str) -> dict[str, str]:\n"
            f"    m = _LOG_REGEX.match(line.strip())\n"
            f"    return m.groupdict() if m else {{}}\n"
        )

        rule = LogRule(
            rule_id=f"rule_log_{len(self.known_rules) + 1}",
            pattern=final_pattern,
            field_names=tuple(field_order),
            extractor_code=code,
        )
        self.known_rules[rule.rule_id] = rule
        return rule
