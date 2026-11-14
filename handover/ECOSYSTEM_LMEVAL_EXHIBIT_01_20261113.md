# ECOSYSTEM WAVE 2 — lm-evaluation-harness SCREENING EXHIBIT #01 (2026-11-13)

> **LABEL: EXTERNAL EXHIBIT — comparability evidence, NOT sealed
> evidence.** Public benchmark tasks are contamination-exposed by
> construction. These numbers exist so ACE's two custodied brains can
> be compared against each other and against published model cards on
> a standard card. They are not gate evidence; ACE's custody stays in
> its own kernel. Source mandate: `ECOSYSTEM_INTAKE_01_20261113.md`
> (PR #176), candidate #3. Lane: intake ekosistem (parallel-lane
> structure, owner 2026-11-13 22:00–22:13). Draft PR only, no merge.

## Intake (custody, verified firsthand 2026-11-13)

| Item | Pin |
|---|---|
| lm-evaluation-harness | PyPI `lm_eval==0.4.13`; git tag `v0.4.13` → commit `ddd67220430a2470529f25fd5c05a576ca1057a0` (tag object `eb4678c395…`) |
| Wheel | `lm_eval-0.4.13-py3-none-any.whl`, sha256 `5daaa1973bf874005f64f28d3834b875f6886f0d6475878e6a6c821994a5286a` — `sha256sum -c` OK inside the sandbox, and independently on the lane VM |
| License | MIT |
| Installed | sandbox venv `/workspace/tools/lm-eval-intake/venv` (741 MB, no torch/GPU extras); `lm_eval 0.4.13`, `datasets 5.2.0`, `requests 2.34.2` (full freeze in `lm-eval-screening/`) |
| Datasets (HF, pinned by revision, pre-downloaded, then `HF_HUB_OFFLINE=1`) | `allenai/ai2_arc` @ `210d026faf…`, `Rowan/hellaswag` @ `218ec52e09…`, `allenai/winogrande` @ `01e74176c6…` |
| ~~Server path~~ | **FALSIFIED at intake (see below)** — the intake doc's survey claim that lm_eval can score via the llama.cpp server's OpenAI endpoint does not survive contact with the custodied build |
| Scoring engine (hub-approved deviation, 2026-11-13) | llama.cpp **b12316** `llama-perplexity --multiple-choice` (ARC/HellaSwag) and `--winogrande` (Winogrande), same custodied build; datafiles rendered from lm_eval 0.4.13's own task definitions over the same pinned datasets (`render_tasks.py`) |
| Door | Owner's Tailscale SSH (`ubuntu@100.93.61.37`, user.slice — no MCP 1-CPU quota), thread count measured at smoke time |

Models (both already in ACE custody in the sandbox home,
`/workspace/ace-omega/models/`):

| Model | File | Size |
|---|---|---|
| Qwen3-30B-A3B (Q4_K_M) | `Qwen3-30B-A3B-Q4_K_M.gguf` | 18,556,685,824 B, sha256 `0d003f6662…` |
| Llama-3.1-8B-Instruct (Q4_K_M) | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | 4,920,739,232 B, sha256 *(recorded in the run log)* |

Note the asymmetry, recorded plainly: the A3B file is the **base**
Qwen3-30B-A3B release; the Llama file is the **Instruct** release.
The card is plain-text loglikelihood (no chat template), which is
the standard published-card setting for both families.

## Sandbox facts that bound this measurement (verified 2026-11-13)

- The MCP-door process tree (`sandbox-mcp.service`) has
  **CPUQuota = 1.0 CPU total** and **MemoryMax = 20 GiB**
  (`systemctl show`, read firsthand by this lane). Every in-home
  number is a 1-effective-core number; thread sweeps in Wave 1
  already established `-t 1` as optimal under this quota.
- Disk `/workspace`: ~19 GiB free at intake start. Models stay in
  the sandbox; only notes/results (small) go to GitHub.
- Runs are executed one heavy load at a time, coordinated via the
  hub with the serving and proposer lanes sharing this home.

## Why the server path is dead (measured, 2026-11-13 evening)

Probes against `llama-server` b12316 (Llama-8B resident, prompts of
known length, `probe2/3/5` logs in the sandbox intake dir):

1. `POST /v1/completions` with `echo=true, logprobs=10` returns
   logprobs **only for generated tokens**: on a 26-token prompt the
   response's `logprobs.content` had length **1**. No prompt
   logprobs exist to parse — at any `--limit`.
2. The format is also the new OpenAI `content[]` shape, not the
   legacy `tokens/token_logprobs/text_offset` shape that lm_eval
   0.4.13's `gguf` and `local-completions` backends parse.
3. The native `POST /completion` endpoint is identical in this
   respect: `completion_probabilities` covers generated tokens only.

Conclusion: stock lm_eval × stock b12316 server **cannot** score
loglikelihood tasks. The hub approved the nearest faithful
replacement (same build, same pinned data, same card):
`llama-perplexity`'s multiple-choice scorer, which does batched
forward passes with the choices' common prefix evaluated once.
Its score is the argmax of the **mean per-token continuation
logprob** — the analogue of lm_eval's `acc_norm`, **not** raw
`acc` — and every number below is labeled that way. Winogrande
uses perplexity's native mode (score the suffix given
prefix+option), matching lm_eval's winogrande semantics.

## Frozen card

Loglikelihood / multiple-choice only, 0-shot:
`arc_easy`, `arc_challenge`, `hellaswag`, `winogrande`,
limit **250** per protocol (first 250 docs of each task's
evaluation split in dataset order — ARC: test; HellaSwag:
validation; Winogrande: validation). Metric: acc_norm-analogue
(see above). Chance levels: ARC 25%, HellaSwag 25%,
Winogrande 50%.

## Results

*(filled from the run logs — see `lm-eval-screening/results/`)*

| Task | Qwen3-30B-A3B Q4_K_M | Llama-3.1-8B-Instruct Q4_K_M |
|---|---|---|
| arc_easy (acc / acc_norm) | — | — |
| arc_challenge (acc / acc_norm) | — | — |
| hellaswag (acc / acc_norm) | — | — |
| winogrande (acc) | — | — |

## Method caveats (read before quoting)

1. Scoring is perplexity-MC's: each item's sequences are
   `question + " " + answer` tokenized jointly (with BOS), the
   common prefix across an item's choices is scored once, and the
   winner is the argmax of the **mean** continuation logprob
   (acc_norm analogue). lm_eval tokenizes context and continuation
   separately and reports both `acc` and `acc_norm`; boundary
   tokenization can differ in rare cases. Identical method for
   both models.
2. The rendered datafiles are byte-verified: the ARC-Easy binary
   was parsed back field-by-field (task count, offsets, strings,
   labels, exact EOF) before any model run.
3. Runs go through the SSH door in a hub-named exclusive RAM
   window: the sandbox's `earlyoom` (5% threshold) kills the
   largest-RSS process when the house is full, and two A3B-class
   residents cannot coexist with the desktop tenants in 24 GiB.

— Intake lane, 2026-11-13.
