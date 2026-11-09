"""Resilient HTTP client pipeline synthesizer (Pure Python urllib).

Generates zero-dependency, failure-tolerant HTTP query routines
with configurable backoff, timeout caps, and response schema checking.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ClientRule:
    rule_id: str
    target_endpoint: str
    client_code: str


class NetClientSynthesizer:
    """Synthesizes hardened HTTP REST client functions."""

    def __init__(self):
        self.rules: Dict[str, ClientRule] = {}

    def synthesize_json_client(
        self,
        endpoint_url: str,
        method: str = "GET",
        expected_keys: Optional[List[str]] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        func_name: str = "query_api_endpoint",
    ) -> ClientRule:
        """Synthesize pure-Python resilient JSON client with exponential backoff."""
        keys_check = ""
        if expected_keys:
            keys_check = (
                f"    # Verify schema keys\n"
                f"    missing = [k for k in {repr(expected_keys)} if k not in data]\n"
                f"    if missing:\n"
                f"        raise ValueError(f'Malformed API payload: missing keys {{missing}}')\n"
            )

        code = (
            f"import json\n"
            f"import time\n"
            f"import urllib.request\n"
            f"import urllib.error\n"
            f"from typing import Any, Dict, Optional\n\n"
            f"def {func_name}(params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:\n"
            f"    url = {repr(endpoint_url)}\n"
            f"    req_headers = {{'User-Agent': 'ACE-Autonomous-Agent/2.0'}}\n"
            f"    if headers:\n"
            f"        req_headers.update(headers)\n\n"
            f"    payload = None\n"
            f"    if {repr(method.upper())} == 'POST' and params:\n"
            f"        payload = json.dumps(params).encode('utf-8')\n"
            f"        req_headers['Content-Type'] = 'application/json'\n\n"
            f"    req = urllib.request.Request(url, data=payload, headers=req_headers, method={repr(method.upper())})\n\n"
            f"    last_err = None\n"
            f"    for attempt in range(1, {max_retries} + 1):\n"
            f"        try:\n"
            f"            with urllib.request.urlopen(req, timeout={timeout_seconds}) as resp:\n"
            f"                if resp.status not in (200, 201):\n"
            f"                    raise RuntimeError(f'HTTP error status {{resp.status}}')\n"
            f"                raw = resp.read().decode('utf-8')\n"
            f"                data = json.loads(raw)\n"
            f"{keys_check}"
            f"                return data\n"
            f"        except Exception as e:\n"
            f"            last_err = e\n"
            f"            if attempt < {max_retries}:\n"
            f"                time.sleep(0.5 * (2 ** (attempt - 1)))\n"
            f"    raise RuntimeError(f'Endpoint query failed after {max_retries} attempts: {{last_err}}')\n"
        )

        rule = ClientRule(
            rule_id=f"rule_net_{len(self.rules) + 1}",
            target_endpoint=endpoint_url,
            client_code=code,
        )
        self.rules[rule.rule_id] = rule
        return rule
