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
- ``custom.gonka`` — helper ``custom.gonka/bin/gonka_call.py``
  (added 2026-11-18 after the Stage-1 gate; third-party broker,
  second-opinion role — see ``GONKA_NOTES`` in this module)

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
    {
        "brain_id": "director-strong-gonka",
        "kind": "external-director",
        "descriptor": (
            "gonka — Secure Vault connector custom.gonka, hub helper "
            "gonka_call.py; third-party broker route, SECOND-OPINION "
            "organ (real balance 100,000 raw tokens/month, not the "
            "advertised 1M value-equivalent); NO private material "
            "through this route; brain-of-origin gonka/<model>"
        ),
    },
)

#: Standing notes for the Gonka broker route (hub-verified 2026-11-18).
#: (1) QUIRK: DeepSeek-V4-Flash through this route emits its JSON
#: object TWICE, concatenated — consumers must parse only the first
#: complete object. (2) BALANCE: the real dashboard balance is
#: 100,000 raw tokens/month (≈24 full director cycles or ≈440 judge
#: calls); the "1M tokens" on the vendor page is a value-equivalent
#: framing against its most expensive model, not a balance. Treat
#: Gonka as a second-opinion organ, never an unbounded pool.
#: (3) PRIVACY: third-party broker — no private material on this route.
GONKA_NOTES = (
    "quirk: DeepSeek-V4-Flash emits its JSON object twice, "
    "concatenated; parse only the first complete object",
    "balance: 100,000 raw tokens/month real (≈24 director cycles "
    "or ≈440 judge calls); advertised 1M is value-equivalent framing",
    "role: second-opinion organ, not an unbounded pool",
    "privacy: third-party broker route; no private material",
)

#: Hub-measured Gonka smoke (2026-11-18): judge call on
#: DeepSeek-V4-Flash returned valid JSON (score 85).
GONKA_SMOKE_RECORD = {
    "brain_of_origin": "gonka/deepseek-ai/DeepSeek-V4-Flash-0731",
    "total_tokens": 226,
    "wall_s": 2.68,
    "result": "valid JSON, score 85 (emitted twice — see GONKA_NOTES)",
    "models_verified": [
        "deepseek-ai/DeepSeek-V4-Flash-0731",
        "MiniMaxAI/MiniMax-M2.7",
        "zai-org/GLM-5.3-Flash",
        "BAAI/bge-m3",
    ],
    "measured_by": "hub (ila) via custom.gonka, 2026-11-18",
}

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

_PROVIDERS = ("groq", "gemini", "gonka")


def brain_of_origin(provider: str, model: str) -> str:
    """The recorded origin of one director call: ``<provider>/<model>``.

    Only the registered vault-connector providers are valid origins
    for director-strong work; anything else is refused so a product
    can never be misattributed.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"unregistered director provider {provider!r}")
    if not model or not model.strip():
        raise ValueError("model must be a non-empty model id")
    return f"{provider}/{model}"


def register_director_strong(registry: BrainRegistry) -> list[dict]:
    """Register the director-strong organs in ``registry``.

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
