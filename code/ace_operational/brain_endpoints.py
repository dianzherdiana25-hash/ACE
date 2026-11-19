"""Brain endpoints: single routing point between ACE and its local organs.

ACE's brain is a slate of local llama-server organs (slate v2, owner-approved
2026-11-15, deployed 2026-11-16). This module is the ONLY place that knows
their addresses; callers ask for a role, never a URL.

Organs (all OpenAI-compatible, loopback only):
  front     :8001  Qwen3.5-4B-MTP (MTP on)  - conversation, language proposer
  coder     :8002  Qwen2.5-Coder-7B         - code proposer, validator
  embedding :8003  bge-m3                   - semantic recall over memory
  a3b       :8004  Qwen3-30B-A3B            - ON-DEMAND only (not always-on);
                   started explicitly per task after an empty-house check.

Heterogeneity rule (evolution runs): proposer and validator are always
DIFFERENT organs, crossed by task kind, and the pair is recorded as run
provenance via :func:`proposer_validator_pair`.

Failure semantics are fail-closed (aligned with PR #233): an unreachable or
unhealthy organ raises :class:`BrainUnavailable`; nothing here fabricates a
result. Reasoning-channel output is returned separately from the answer
content; structured consumers bound the thinking budget through
``chat_template_kwargs`` (see STRUCTURED_TEMPLATE_KWARGS).

Idle-off amendment (owner, 2026-11-16): the coder and embedding units stop
after 20 idle minutes (ace-idle-watchdog) and must be WOKEN by the client:
:func:`ensure_organ` starts the unit and waits for health; only a failed
wake is organ-dead. Wake events are recorded for run evidence
(:func:`drain_wake_events`). The front organ is always-on and the A3B
organ is explicit-start only — neither is woken from here.

Bridge transport (EVO 0009, hub-ratified 2026-11-18): when the
environment sets ``ACE_BRAIN_BRIDGE_URL``, every organ routes through
the brain bridge instead of the local slate. The bridge speaks
ROLES, not organs: front/coder keep their names, the pair's
validator becomes the bridge's cross-validator role (a different
provider's organ by construction, so the heterogeneity rule holds
by role rather than by unit), and embedding goes to the bridge's
embedding role. There are no systemd units behind the bridge, so
wake semantics do not apply: an unhealthy bridge is organ-dead,
fail-closed as everywhere else in this module. The bridge reports
the serving organ as ``brain_of_origin`` on every answer; it is
carried on :class:`ChatResult` as provenance.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_URLS = {
    "front": "http://127.0.0.1:8001",
    "coder": "http://127.0.0.1:8002",
    "embedding": "http://127.0.0.1:8003",
    "a3b": "http://127.0.0.1:8004",
}

ENV_VARS = {
    "front": "ACE_BRAIN_FRONT_URL",
    "coder": "ACE_BRAIN_CODER_URL",
    "embedding": "ACE_BRAIN_EMBEDDING_URL",
    "a3b": "ACE_BRAIN_A3B_URL",
}

# Structured consumers (proposer/validator JSON) ask the front/coder
# templates to bound thinking so the answer channel carries the payload.
# The exact default was settled from the first live probe of the deployed
# services (2026-11-16); see the deployment record.
STRUCTURED_TEMPLATE_KWARGS: dict = {"enable_thinking": False}

TASK_KINDS = ("code", "language")

# --- Bridge transport (EVO 0009) -------------------------------------------

BRIDGE_ENV_VAR = "ACE_BRAIN_BRIDGE_URL"

# Organs that exist only as bridge roles. In bridge mode the pair's
# validator resolves to the "validator" role; outside bridge mode the
# name is not an organ at all.
BRIDGE_ONLY_ORGANS = ("validator",)


def bridge_url() -> str | None:
    """The configured bridge base URL, or None in local-slate mode."""
    url = os.environ.get(BRIDGE_ENV_VAR, "").strip()
    return url.rstrip("/") or None


def bridge_mode() -> bool:
    return bridge_url() is not None


class BrainUnavailable(RuntimeError):
    """An organ is unreachable or unhealthy. Fail-closed: never faked."""


def organ_url(organ: str) -> str:
    if bridge_mode():
        if organ in DEFAULT_URLS or organ in BRIDGE_ONLY_ORGANS:
            return bridge_url()
        raise ValueError(f"unknown organ: {organ!r}")
    if organ in BRIDGE_ONLY_ORGANS:
        raise ValueError(
            f"organ {organ!r} exists only in bridge mode "
            f"({BRIDGE_ENV_VAR} unset)")
    if organ not in DEFAULT_URLS:
        raise ValueError(f"unknown organ: {organ!r}")
    return os.environ.get(ENV_VARS[organ], DEFAULT_URLS[organ]).rstrip("/")


@dataclass(frozen=True)
class OrganPair:
    """Proposer/validator assignment for one run (provenance record)."""

    task_kind: str
    proposer: str
    validator: str

    def as_dict(self) -> dict:
        record = {
            "task_kind": self.task_kind,
            "proposer": self.proposer,
            "validator": self.validator,
            "proposer_url": organ_url(self.proposer),
            "validator_url": organ_url(self.validator),
        }
        if bridge_mode():
            record["transport"] = "bridge"
            record["bridge_roles"] = {
                "proposer": self.proposer,
                "validator": "validator",
            }
        return record


def proposer_validator_pair(task_kind: str) -> OrganPair:
    """Crossed heterogeneous pair: code tasks propose with the coder and
    validate with the front brain; language tasks the reverse. In
    bridge mode the proposers keep their roles and the validator is
    the bridge's cross-validator role for both kinds."""
    if task_kind not in TASK_KINDS:
        raise ValueError(f"unknown task_kind: {task_kind!r}")
    if bridge_mode():
        proposer = "coder" if task_kind == "code" else "front"
        return OrganPair(task_kind, proposer=proposer,
                         validator="validator")
    if task_kind == "code":
        return OrganPair(task_kind, proposer="coder", validator="front")
    return OrganPair(task_kind, proposer="front", validator="coder")


def role_url(role: str, task_kind: str = "language") -> str:
    """Resolve a caller role to an organ base URL.

    Roles: ``chat``/``proposer``/``validator`` (pair rules apply to the
    latter two), ``embedding``/``recall`` (embedding organ), ``deep``
    (the on-demand A3B organ).
    """
    if role in ("embedding", "recall"):
        return organ_url("embedding")
    if role == "deep":
        return organ_url("a3b")
    if role == "chat":
        return organ_url("front")
    if role == "proposer":
        return organ_url(proposer_validator_pair(task_kind).proposer)
    if role == "validator":
        return organ_url(proposer_validator_pair(task_kind).validator)
    raise ValueError(f"unknown role: {role!r}")


def _request(url: str, payload: dict | None, timeout: float) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise BrainUnavailable(f"request to {url} failed: {exc}") from exc


def bridge_budget(timeout: float = 120.0) -> dict | None:
    """Baca sisa budget sebelum menjadwalkan panggilan bridge."""
    url = bridge_url()
    if url is None:
        return None
    result = _request(f"{url}/v1/budget", None, timeout)
    if not isinstance(result, dict):
        raise BrainUnavailable("bridge budget response is not an object")
    return result


def health(organ: str, timeout: float = 5.0) -> bool:
    """True iff the organ's /health answers. Never raises."""
    try:
        _request(f"{organ_url(organ)}/health", None, timeout)
        return True
    except BrainUnavailable:
        return False


def require_health(organ: str) -> None:
    if not health(organ):
        raise BrainUnavailable(f"organ {organ!r} is not healthy")


# --- Idle-off wake semantics (owner amendment, 2026-11-16) -----------------

WAKEABLE_UNITS = {"coder": "ace-coder", "embedding": "ace-embedding"}
WAKE_TIMEOUT_S = 120.0
WAKE_POLL_S = 3.0

_wake_events: list[dict] = []


def drain_wake_events() -> list[dict]:
    """Return and clear the recorded wake events (for run evidence)."""
    events = list(_wake_events)
    _wake_events.clear()
    return events


def _start_unit(unit: str) -> None:
    subprocess.run(["sudo", "-n", "systemctl", "start", unit],
                   check=True, capture_output=True, timeout=60)


def ensure_organ(organ: str, *, wake: bool = True,
                 wake_timeout: float = WAKE_TIMEOUT_S) -> bool:
    """Make sure an organ is serving; return True iff this call woke it.

    Front (always-on) and a3b (explicit-start) are never woken here: for
    them an unhealthy state is simply organ-dead. For wakeable organs a
    failed wake raises BrainUnavailable — idle-off is not death, but a
    wake that does not complete is.

    In bridge mode there are no units to wake: a healthy bridge means
    the organ serves (returns False — nothing was woken), an unhealthy
    bridge is organ-dead.
    """
    if bridge_mode():
        if health(organ):
            return False
        raise BrainUnavailable(
            f"brain bridge is not healthy (organ {organ!r})")
    if health(organ):
        return False
    unit = WAKEABLE_UNITS.get(organ)
    if not wake or unit is None:
        raise BrainUnavailable(f"organ {organ!r} is not healthy")
    try:
        _start_unit(unit)
    except (subprocess.SubprocessError, OSError) as exc:
        raise BrainUnavailable(
            f"wake of organ {organ!r} (unit {unit}) failed: {exc}") from exc
    deadline = time.monotonic() + wake_timeout
    while time.monotonic() < deadline:
        if health(organ):
            _wake_events.append(
                {"organ": organ, "unit": unit, "woke": True})
            return True
        time.sleep(WAKE_POLL_S)
    raise BrainUnavailable(
        f"organ {organ!r} did not become healthy within "
        f"{wake_timeout:.0f}s after wake")


@dataclass(frozen=True)
class ChatResult:
    content: str
    reasoning: str
    prompt_per_second: float | None
    predicted_per_second: float | None
    predicted_tokens: int | None
    organ_woke: bool = False
    brain_of_origin: str = ""


def parse_chat_response(payload: dict) -> ChatResult:
    """Split the answer channel from the reasoning channel.

    A 200 response whose body does not carry the chat-completion shape
    is an organ fault, not data: it raises BrainUnavailable like any
    other organ failure (fail-closed)."""
    try:
        msg = payload["choices"][0]["message"]
        if not isinstance(msg, dict):
            raise TypeError("message is not an object")
    except (KeyError, IndexError, TypeError) as exc:
        raise BrainUnavailable(
            f"malformed chat response shape: {exc!r}") from exc
    timings = payload.get("timings") or {}
    return ChatResult(
        content=msg.get("content") or "",
        reasoning=msg.get("reasoning_content") or "",
        prompt_per_second=timings.get("prompt_per_second"),
        predicted_per_second=timings.get("predicted_per_second"),
        predicted_tokens=timings.get("predicted_n"),
        brain_of_origin=payload.get("brain_of_origin") or "",
    )


def chat(organ: str, messages: list[dict], *, max_tokens: int = 512,
         temperature: float = 0.0, seed: int | None = None,
         template_kwargs: dict | None = None,
         timeout: float = 900.0, check_health: bool = True) -> ChatResult:
    """One chat completion against an organ, fail-closed. Wakeable organs
    (coder) are woken from idle-off first; the wake is reported on the
    result and in the wake-event log."""
    woke = ensure_organ(organ) if check_health else False
    if bridge_mode():
        if organ == "a3b":
            raise BrainUnavailable(
                "the on-demand deep organ has no bridge role")
        bridge_payload: dict = {
            "role": organ,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return parse_chat_response(_request(
            f"{bridge_url()}/v1/chat/completions",
            bridge_payload, timeout))
    payload: dict = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        payload["seed"] = seed
    if template_kwargs:
        payload["chat_template_kwargs"] = template_kwargs
    result = parse_chat_response(
        _request(f"{organ_url(organ)}/v1/chat/completions", payload, timeout))
    if woke:
        result = ChatResult(result.content, result.reasoning,
                            result.prompt_per_second,
                            result.predicted_per_second,
                            result.predicted_tokens, organ_woke=True)
    return result


def chat_structured(organ: str, messages: list[dict], **kwargs) -> ChatResult:
    """Chat for structured-output consumers: thinking bounded by default
    (STRUCTURED_TEMPLATE_KWARGS) so the content channel carries the payload;
    the caller's grammar/JSON gate still applies to the result."""
    kwargs.setdefault("template_kwargs", dict(STRUCTURED_TEMPLATE_KWARGS))
    return chat(organ, messages, **kwargs)


def embed(texts: list[str], *, timeout: float = 120.0,
          check_health: bool = True) -> list[list[float]]:
    """Embeddings from the embedding organ, fail-closed. The embedding
    organ is wakeable: an idle-off state is woken first and the wake is
    recorded in the wake-event log."""
    if not texts:
        return []
    if bridge_mode():
        if check_health:
            ensure_organ("embedding")
        vectors = []
        for text in texts:
            out = _request(f"{bridge_url()}/v1/embeddings",
                           {"role": "embedding", "input": text},
                           timeout)
            try:
                vectors.append(out["data"][0]["embedding"])
            except (KeyError, IndexError, TypeError) as exc:
                raise BrainUnavailable(
                    f"malformed bridge embedding shape: {exc!r}"
                ) from exc
        return vectors
    if check_health:
        ensure_organ("embedding")
    out = _request(f"{organ_url('embedding')}/embedding",
                   {"input": texts if len(texts) > 1 else texts[0]}, timeout)
    # llama-server's /embedding answers a list of items whose "embedding"
    # is a LIST OF VECTORS (one per input chunk); accept a flat vector too.
    vectors: list[list[float]] = []
    items = out if isinstance(out, list) else [out]
    for item in items:
        try:
            emb = item["embedding"]
        except (KeyError, TypeError) as exc:
            raise BrainUnavailable(
                f"malformed embedding response shape: {exc!r}") from exc
        if emb and isinstance(emb[0], list):
            vectors.extend(emb)
        else:
            vectors.append(emb)
    return vectors
