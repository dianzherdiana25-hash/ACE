"""Director-strong organs — Stage 1 of RANCANGAN TAHAPAN OTAK KUAT.

Design: hub document ``RANCANGAN_TAHAPAN_OTAK_KUAT.md`` (owner order,
2026-11-18), under the multi-brain sovereignty doctrine: brains are
replaceable organs; ACE's identity lives in its constitution, ledger,
and memory — never in one provider.

Transport amendment (hub-verified 2026-11-18, supersedes the design
document's FreeLLM-dashboard route): Muse browsers refuse localhost
and private-IP navigation at the tool layer, so the dashboard route is
dead. The owner instead entered his free-tier provider keys through
Secure Vault cards. The live transports are therefore two vault
connectors, called by hub helpers — credential values never reach any
session:

- ``custom.groq``   — helper ``custom.groq/bin/groq_call.py``
  (11 models verified, incl. ``openai/gpt-oss-120b``,
  ``qwen/qwen3.8-27b``)
- ``custom.gemini`` — helper ``custom.gemini/bin/gemini_call.py``
  (50 models verified, incl. ``gemini-2.5-pro``)

Measured smoke (hub, 2026-11-18): a judge-equivalent generation via
``openai/gpt-oss-120b`` produced 309 completion tokens in 0.64 s
(≈ 481 t/s effective, wall 1.35 s) against the local front's
0.45–0.79 t/s under load and 1,232–1,778 s for the same class of
generation locally.

Fences (unchanged from the design):

- **Director work only** — agenda cycles, EVO 0007 curriculum
  proposals, opportunity-register synthesis. These organs are never
  measurement subjects, and their output is never disguised as local
  output: every director product records its brain-of-origin as
  ``groq/<model>`` or ``gemini/<model>`` (see :func:`brain_of_origin`).
- **Slate v2 is untouched** — this module adds registry records; it
  does not change routing, endpoints, or any measured organ.
- **Fail-closed** — a dead connector means director work falls back
  to the local organs or stops recorded; there is no silent identity
  substitution, and dismissal works through the registry exactly as
  for any other brain.
"""
from __future__ import annotations

from ace_operational.brain_registry import BrainRegistry

#: Capabilities of the director-strong organs — director work only.
#: Nothing on the measurement path may ever appear here.
DIRECTOR_CAPABILITIES = (
    "agenda_cycle",
    "curriculum_proposal",
    "opportunity_synthesis",
)

#: The two vault-connector transports, as registered brains.
DIRECTOR_ORGANS = (
    {
        "brain_id": "director-strong-groq",
        "kind": "external-director",
        "descriptor": (
            "groq — Secure Vault connector custom.groq, hub helper "
            "groq_call.py; free-tier API, director work only; "
            "brain-of-origin groq/<model>"
        ),
    },
    {
        "brain_id": "director-strong-gemini",
        "kind": "external-director",
        "descriptor": (
            "gemini — Secure Vault connector custom.gemini, hub helper "
            "gemini_call.py; free-tier API, director work only; "
            "brain-of-origin gemini/<model>"
        ),
    },
)

#: Hub-measured smoke for the Stage-1 gate (2026-11-18).
SMOKE_RECORD = {
    "brain_of_origin": "groq/openai/gpt-oss-120b",
    "completion_tokens": 309,
    "generation_s": 0.64,
    "effective_tps": 481,
    "wall_s": 1.35,
    "local_front_tps_under_load": "0.45-0.79",
    "local_same_class_wall_s": "1232-1778",
    "measured_by": "hub (ila), 2026-11-18",
}

_PROVIDERS = ("groq", "gemini")


def brain_of_origin(provider: str, model: str) -> str:
    """The recorded origin of one director call: ``<provider>/<model>``.

    Only the two registered vault-connector providers are valid
    origins for director-strong work; anything else is refused so a
    product can never be misattributed.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"unregistered director provider {provider!r}")
    if not model or not model.strip():
        raise ValueError("model must be a non-empty model id")
    return f"{provider}/{model}"


def register_director_strong(registry: BrainRegistry) -> list[dict]:
    """Register both director-strong organs in ``registry``.

    Idempotent at the record level: re-registering replaces the
    record (the registry's append-only event log keeps every
    registration act, as it does for every brain).
    """
    records = []
    for organ in DIRECTOR_ORGANS:
        records.append(registry.register(
            organ["brain_id"],
            kind=organ["kind"],
            descriptor=organ["descriptor"],
            status="active",
            capabilities=list(DIRECTOR_CAPABILITIES),
        ))
    return records
