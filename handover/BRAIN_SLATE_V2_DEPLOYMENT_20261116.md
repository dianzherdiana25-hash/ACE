# BRAIN SLATE v2 — DEPLOYMENT RECORD (2026-11-16)

Owner order (main chat, 2026-11-16 ~00:24 WIB): "udah, pake aja racikan kita
langsung" — the v2 slate was deployed directly as services, superseding the
bench-first gate. The small-organ bench series was stopped mid-run; its
interim MTP pair is recorded below.

## Services (systemd, sandbox home 2887726280f4)

| unit | organ | model | port | flags | MemoryMax |
|---|---|---|---|---|---|
| ace-front | front brain | Qwen3.5-4B-MTP-Q4_K_M.gguf | 8001 | `--spec-type draft-mtp -c 8192 -t 1` | 4G |
| ace-coder | coder | qwen2.5-coder-7b-instruct-q4_k_m.gguf | 8002 | `-c 8192 -t 1` | 6G |
| ace-embedding | embedding | bge-m3-Q8_0.gguf | 8003 | `--embedding -c 8192 -t 1` | 1536M |

- Binary: /workspace/tools/llama.cpp/llama-b12316/llama-server (build 12316)
- Bind: 127.0.0.1. Restart=on-failure, enabled at boot.
- Total caps 11.5 GiB ≤ the slate's 16 GiB always-on ceiling.
- Verified at deployment: all three `active`, /health OK on 8001/8002/8003,
  MemAvailable 12,001,600 kB with all three resident.

## Amendment — idle-off for coder + embedding (owner, 2026-11-16 00:43)

- ace-front stays always-on. ace-coder and ace-embedding now run with
  `--metrics` and are stopped by **ace-idle-watchdog** (systemd timer,
  every 5 min) after **20 minutes** with no served request (activity =
  `llamacpp:prompt_tokens_total` on each organ's /metrics).
- Wake-on-call lives in the client wrapper (`brain_endpoints.ensure_organ`):
  an unhealthy wakeable organ is started via a NOPASSWD sudoers entry
  scoped to exactly those two units, health is awaited up to 120 s, and
  the wake is recorded as a wake event for run evidence. Only a FAILED
  wake is organ-dead (BrainUnavailable). The front organ is never woken
  (always-on) and A3B stays explicit-start.
- Verified live 2026-11-16: with ace-embedding stopped, `embed()` woke
  the unit, recorded the wake event, returned a 1024-dim vector, and the
  organ's prompt-token counter moved (0 → 11), confirming the watchdog's
  activity signal for the embedding organ as well.

## Amendment — host keep-alive (owner, 2026-11-16 01:10)

The owner notes the sandbox HOST itself idles out at 20 minutes and dies
("batas idlenya 20 menit") — the same 20 minutes as the organ idle-off
window. The organs may sleep; the MACHINE must not. The existing
5-minute watchdog timer now also carries a host keep-alive, independent
of organ state: every run writes a heartbeat file
(/run/ace-idle/host-heartbeat), performs a small hash computation, and
logs a journal line — real host activity every 5 minutes, well under
the host's 20-minute idle limit, including while both wakeable organs
are stopped. Organ idle-off remains 20 minutes per the 00:43 decision.

Observation (not a conclusion): tonight's SSH-door falls (~23:00,
~23:28, ~00:50; TLS EOF, spontaneous recovery in ~3–19 min) are
consistent with a host/Funnel wake-up lag, but they were NOT all
preceded by ≥20 min of inactivity from this side (the 00:50 fall
followed sandbox work minutes earlier), so idle-sleep is at most a
partial explanation. The keep-alive removes the idle variable either
way; the falls' cause is not established.

## Interim bench (stopped mid-series by the owner's order)

Method: llama-server on 127.0.0.1:18099, one organ at a time, -c 8192 -t 1,
temperature 0, seed 42, max_tokens 128, 3 reps per prompt. Note: llama-server
prompt caching makes reps 2–3 prompt_tps non-comparable (only ~4 uncached
tokens); gen_tps is the clean metric.

- front_mtp_off, id_short gen t/s: 1.18 / 1.33 / 1.28 (median 1.28)
- front_mtp_off, id_long gen t/s: 1.44 / 1.55 / 1.39 (median 1.44)
- front_mtp_on, id_short rep 1 gen t/s: 1.58 (series stopped before completion)
- Observation: at max_tokens 128 the front model returned EMPTY message
  content in 6/6 calls (all tokens consumed) — consistent with a long
  reasoning channel; the live-service probe below measures this directly.

## Live-service probes (2026-11-16, production services)

- **Embedding (:8003) — PASS.** Indonesian sentence → 1024 dims (bge-m3 as
  specified), L2 norm 1.0, wall 0.8 s.
- **Coder (:8002) — PASS.** Indonesian instruction → correct, complete
  `gabung_rentang` implementation with an Indonesian docstring, 256 tokens,
  gen 0.82 t/s measured WHILE sharing CPU with the front organ's probe
  (concurrency figure, not solo).
- **Front (:8001) @ max_tokens 512, reasoning capture — SETTLED, and the
  finding is structural.** Unbounded (default template): the model sinks
  the whole budget into the reasoning channel. Attempt 1 died on a 420 s
  client timeout; attempt 2 (timeout 1200 s) was still generating after
  ~35 min — slot telemetry showed the context crawling 355 → 430 tokens
  (~0.08 t/s effective) with no answer delivered; the run was terminated
  by the operator at 453 context tokens to unblock the corrective
  measurement. Bounded variant (same prompt, seed, budget;
  `chat_template_kwargs: {"enable_thinking": false}`): **clean content
  channel, reasoning_len 0, finish=stop, 77 tokens, wall 215.9 s** — a
  correct three-sentence Indonesian Rayleigh-scattering answer.
  Consequence locked into `brain_endpoints.STRUCTURED_TEMPLATE_KWARGS =
  {"enable_thinking": False}`: structured consumers never run the front
  organ unbounded.

## A3B restoration

The A3B GGUF (Qwen/Qwen3-30B-A3B-GGUF, Qwen3-30B-A3B-Q4_K_M.gguf,
18,556,685,824 B, intake pin sha256
0d003f6662faee786ed5da3e31b29c978de5ae5d275c8794c606a7f3c01aa8f5) was found
MISSING from the sandbox on 2026-11-16 (full-disk GGUF inventory; pattern
consistent with a platform snapshot rollback). Restoration was approved by
the hub under the owner's automatic-restoration rule (same file, same pin,
same route, same destination /workspace/ace-omega/models/) and runs AFTER
the small-organ measurements so the 18.56 GB download cannot contaminate
them. Per the owner's no-rerun-without-a-named-delta rule, arrival is
verified by sha256 only — NO A3B re-bench; the PR #176 anchor
(pp 7.96 ± 0.35 / tg 2.46 ± 0.10 t/s, -t 1, same build b12316) stands.

**Result: RESTORE_ACCEPTED 2026-11-16T00:33:20+07:00** — downloaded
18,556,685,824 B, sha256 matched the intake pin, file promoted to
/workspace/ace-omega/models/Qwen3-30B-A3B-Q4_K_M.gguf. (Operational note:
the first launch attempt died at an unfed sudo prompt and never started;
the accepted run is the second launch, 00:30:42.)
