# ECOSYSTEM INTAKE #01 — CANDIDATE LIST (2026-11-13)

Desk item from the owner via hub (2026-11-13 ~19:05 WIB):
survey open-source repos/components that STRENGTHEN ACE
instead of building everything in-house. Screened by the
hub's criteria: (a) fits local-first + the sandbox home
as-is; (b) license compatible for use/adaptation;
(c) intake-able with custody discipline (pinned version,
recorded hash, clear provenance); (d) benefit MEASURED
before full adoption (before/after numbers, not
impressions). Three research lanes (serving / eval /
memory+curriculum), consolidated by Ian. Claims marked
UNVERIFIED were single-source at survey time and must be
re-read at intake. Adoption of anything here happens
only via draft PR, after its measurement gate.

**Shared diagnostic (drives the serving ranking):** in
the sandbox home the A3B brain generates at tg 0.91 t/s
while reading only ~1.6–1.9 GB of weights per token —
an effective ~1.5–1.7 GB/s, far below DDR bandwidth.
Generation here is COMPUTE/SCHEDULING-bound under
contention (~1 effective core), not bandwidth-bound.
Kernel quality and thread fit are the levers; smaller
quants are not.

## Ranked trial list

### 1. Config tuning pack on pinned llama.cpp b12316 — SERVING, zero intake
- What: thread/batch/KV sweep on the build ACE already
  custodies: -t/-tb ∈ {1,2,3,4,6,8}, flash-attn on,
  ubatch/batch for pp, KV q8_0 → q4_0, mmap/mlock.
  The baseline was measured at -t 8 on a ~1-effective-
  core host — classic oversubscription territory.
- License/pin: N/A (same MIT build, already in home).
- Protocol: full llama-bench -p 512 -n 128 matrix.
  ADOPT the best cell if tg128 improves ≥ 15%
  (≥ 1.05 t/s); record pp and tg optima separately.
- Confidence: HIGH that this is the cheapest first
  experiment; gain size unknown (possibly ~0 if the
  contention is hypervisor-level).

### 2. ik_llama.cpp — SERVING, engine-swap candidate
- Repo: github.com/ikawrakow/ik_llama.cpp (MIT). Fork
  by the K-quants author: CPU flash attention, IQK
  kernels with AVX-512 paths (the sandbox Xeon loads
  the cascadelake/AVX-512 ggml backend today), runtime
  repacking (-rtr), dynamic MoE expert cache.
- Pin: no tagged releases — pin an exact commit SHA +
  sha256 of the GitHub source tarball; build in the
  sandbox. Same GGUF format; intake must smoke-test
  that ACE's exact qwen3moe file loads sanely (fork
  diverged from upstream since Aug 2024).
- Protocol: same GGUF, ik llama-bench -p 512 -n 128,
  -t swept {2,4,8} ± -rtr. ADOPT if tg128 ≥ 1.30×
  baseline (≥ 1.18 t/s) with pp512 not regressing.
- Confidence: HIGH it is the largest available lever;
  MEDIUM on win size under ~1 effective core.
  Single-maintainer risk noted.

### 3. lm-evaluation-harness (EleutherAI) — EVAL, brain screening standard
- Repo: github.com/EleutherAI/lm-evaluation-harness
  (MIT). The de-facto few-shot scoring standard
  (ARC/HellaSwag/MMLU/GSM8K/Winogrande, 300+ tasks).
- Pin: PyPI lm_eval==0.4.13 or git tag v0.4.13; each
  task's HF dataset pinned by revision commit SHA,
  pre-downloaded, run with HF_HUB_OFFLINE=1. Scores
  the local llama.cpp server via its OpenAI-compatible
  endpoint (no torch/GPU needed since v0.4.10 core).
- Protocol: frozen screening card of LOGLIKELIHOOD
  tasks only (ARC-Easy+Challenge, HellaSwag,
  Winogrande, --limit 250 each) for A3B vs Llama —
  BEFORE: no cross-model-comparable numbers exist in
  ACE; AFTER: numbers comparable to published model
  cards. Its results enter ACE's ledger as external
  exhibits — comparability evidence, never sealed
  evidence (public tasks are contamination-exposed);
  custody stays in ACE's kernel.
- Confidence: HIGH. Best first eval adoption.

### 4. sqlite-vec — MEMORY, first adoption candidate
- Repo: github.com/asg017/sqlite-vec (MIT OR
  Apache-2.0, dual). Pure-C SQLite extension: vec0
  virtual table, KNN inside ACE's existing .db files.
- Pin: PyPI sqlite-vec wheel with --require-hashes, or
  vendor the amalgamation tarball + sha256. COMPANION
  INTAKE REQUIRED: a local embedding GGUF (nomic-embed
  / bge-small class) via llama.cpp embedding mode,
  hash-pinned like every model.
- Fit: zero new storage model, CPU-trivial, offline.
  Limit: brute-force exact KNN (no ANN) — fine at
  ACE's 10³–10⁵ corpus scale.
- Protocol: frozen set of ~50 paraphrased queries over
  the real evidence/register corpus, hand-labeled.
  ADOPT if recall@10 improves ≥ +30 points over the
  substring/recency baseline with p95 latency
  < 50 ms/query at 10k entries.
- Confidence: HIGH on fit/license; MEDIUM on
  maintenance (pre-v1, single maintainer) — mitigated
  by the tiny vendoring surface.

### 5. Speculative decoding on current llama.cpp — SERVING
- 5a. ngram-mod / --spec-default: self-speculation
  from token history, no second model, ~16 MB state.
  Best on repetitive traffic (code edits, JSON —
  much of ACE's director-cycle load). Near-zero
  downside.
- 5b. draft-simple + Qwen3-0.6B draft GGUF
  (Apache-2.0, HF LFS oid == sha256 pinning; ~0.7 GB):
  same vocab family as the target. GENUINE COIN-FLIP
  in this home: draft and target timeshare the same
  starved core; llama.cpp's own field reports warn
  drafts can cost more than they earn on small-active-
  param MoEs. Sweep draft length {3,5,8}.
- NOT applicable: draft-mtp (A3B has no MTP head);
  draft-eagle3 speculator for 30B-A3B UNVERIFIED /
  likely unavailable — do not plan on it.
- Protocol: llama-bench CANNOT measure speculation —
  use llama-cli on a fixed prompt set (one director-
  style JSON task, one prose), -n 256, temp 0.
  Quality gate: outputs byte-identical to baseline.
  ADOPT an arm if generation t/s ≥ 1.25× with
  identical outputs. Confidence: MEDIUM (5a),
  LOW-MEDIUM (5b).

### 6. SWE-smith strategies — CURRICULUM (port, don't drop-in)
- Repo: github.com/SWE-bench/SWE-smith (MIT).
  Synthesis of bug-fix tasks from any Python codebase
  (LM rewrites, procedural AST mutations, PR-mirroring,
  bug combination), every instance validated by
  breaking real tests — its mutator set is a superset
  of ACE's hand-rolled defect classes and its
  fail-to-pass validation matches ACE's gate discipline.
- Blocker for the full toolkit: it requires Docker
  (absent on the VM; sandbox availability UNVERIFIED)
  and per-repo env storage is huge. ADOPT THE
  STRATEGIES into ACE's own generator Docker-free;
  run the toolkit itself only if a Docker host appears.
- Protocol: ACE repo as seed, fixed 2 h CPU budget:
  valid instances/hour + strategy coverage + operator-
  discovery yield per 100 valid tasks vs the hand-rolled
  generator. ADOPT if ≥ 2× instances/hour at equal-or-
  better coverage. Confidence: HIGH on strategy value.

### 7. distilabel — CURRICULUM, pipeline discipline
- Repo: github.com/argilla-io/distilabel (Apache-2.0).
  Pipeline framework for synthetic-data generation with
  a native LlamaCppLLM backend — the only candidate
  that speaks ACE's inference stack out of the box.
  Value: industrialize the LLM-driven curriculum steps
  (issue-text generation, difficulty labeling, AI-
  feedback filtering) with caching/resume instead of
  hand-rolled loops. It wraps ACE's generator; it does
  not replace the defect-class core.
- Protocol: one existing hand-rolled LLM-gen step,
  500-item run: validated outputs/hour, % passing the
  gate, wall-time lost to restarts. ADOPT if ≥ 1.5×
  validated outputs/hour OR ≥ 50% less lost work.
  Confidence: MEDIUM-HIGH fit; MEDIUM maintenance
  (community-maintained since the Argilla team moved
  on — UNVERIFIED against the live repo).

### 8. Inspect AI (UK AISI) — EVAL, substrate for new evals
- Repos: github.com/UKGovernmentBEIS/inspect_ai +
  inspect_evals (both MIT). Dataset × solver × scorer
  framework, 200+ ready evals, transcript logs.
- Pin: PyPI inspect_ai (0.3.x, pin exact) + git-commit
  pin of inspect_evals (moves fast); datasets by HF
  revision. Caveat: built-in sandboxes are Docker or
  `local` (= no isolation) — agentic evals need the
  Docker question answered first.
- Protocol: port ONE existing director-packet eval to
  an Inspect Task; adoption = identical-or-better
  discrimination at ~zero bespoke runner code, with
  log hashes entering ACE's chain. ACE's kernel stays
  the system of record — .eval logs never become a
  parallel truth. Confidence: HIGH.

### 9. SWE-bench, frozen Lite slice — EVAL, external repair anchor (GATED)
- Repo: github.com/SWE-bench/SWE-bench (code MIT;
  dataset cards MIT-listed, card-level UNVERIFIED).
  The reference real-issue repair benchmark.
- Gate: official evaluation is Docker-per-instance
  (several GB each, UNVERIFIED). Full Verified is
  infeasible on ACE's disks; a 10–25 instance Lite
  slice is the only realistic pilot, and only if
  Docker exists in the sandbox (UNVERIFIED — check
  first, cheap).
- Protocol: resolve-rate on a frozen 25-instance Lite
  subset — BEFORE: ACE's repair claim rests only on
  its own sealed tasks; AFTER: the first externally
  anchored, published-comparable repair number.
  Report as external benchmark (public issues are
  contamination-exposed), never as sealed evidence.
  Confidence: HIGH on facts, MEDIUM on fit.

## Second tier (recorded, not in the first trial wave)

- **bigcode-evaluation-harness** (Apache-2.0): HumanEval/
  MBPP+ pass@1 in score-only mode (ACE generates via
  llama.cpp; harness only scores). Cheap bonus
  screening; executor is NOT a sandbox — score inside
  ACE's isolation only.
- **R2E-Gym / SWE-GEN** (Apache-2.0 per secondary
  listing — CONFIRM the LICENSE file at intake):
  commit-back-translation task generation + hybrid
  verifiers, portable Docker-free as a METHOD; its
  pre-generated corpus is Docker-heavy.
- **DeepEval** (Apache-2.0): rubric/judge metrics as
  ADVISORY cross-checks only, after an agreement study
  on ~50 already-adjudicated ACE dossiers (local judge
  mandatory; telemetry opt-out to confirm). Never a
  verdict authority in ACE.
- **LanceDB** (Apache-2.0): the scale-out memory
  option — adopt only if sqlite-vec's brute force
  actually becomes the bottleneck (~100k entries).
- **mem0** (Apache-2.0): borrow the extract→dedup→
  update DESIGN into ACE's memory module; adopt code
  only if local-model extraction quality passes a
  100-entry labeled test (defaults are OpenAI-bound;
  telemetry must be off).
- **llama.cpp mainline upgrade b12316 → current**
  (MIT, signed tarballs): hygiene, expected delta
  negligible (~43 builds, no CPU-MoE work) — fold into
  another bench session, never a dedicated slot.

## Screened OUT for this home (assessed, do not adopt)

- **KTransformers** (Apache-2.0): every documented
  config needs a 24 GB-class GPU; the home has none.
- **vLLM / SGLang CPU modes** (Apache-2.0): GPU-centric,
  GGUF not first-class, heavy torch footprint.
- **llamafile** (Apache-2.0/MIT): packaging of an older
  llama.cpp line, no kernel advantage. **Ollama** (MIT):
  a daemon wrapper, no performance mechanism.
- **Re-quantization (IQ4_XS/Q3_K_M)**: the home is not
  bandwidth-bound (see diagnostic) — small expected
  gain, permanent quality cost. Deprioritized.
- **Chroma** (Apache-2.0): nothing over sqlite-vec for
  ACE at a heavier stack. **Letta** (Apache-2.0): an
  agent RUNTIME — adopting it means adopting its loop,
  which is ACE's research surface, not a commodity.
- **HELM** (maintenance mode since 2026-06), **OpenAI
  Evals** (steers to hosted dashboard), **promptfoo**
  (MIT but Node toolchain + weakest custody story;
  optional at most).

## Proposed sequence (each a measured mini-stage)

Wave 1 (serving, same bench sessions): #1 tuning pack
→ #2 ik_llama.cpp intake+bench → #5a ngram spec.
Wave 2 (numbers that travel): #3 lm-eval screening
card for A3B + Llama (this also feeds any future
bake-off with external exhibits).
Wave 3 (memory): embedding-model intake + #4
sqlite-vec recall trial.
Wave 4 (curriculum): #6 mutator port census vs the
hand-rolled generator; #7 distilabel trial on one
LLM-gen step.
Gated/parallel checks: Docker presence in the sandbox
(unlocks or kills #9 and parts of #6/#8) — one command,
do it in Wave 1.

— Ian, 2026-11-13. Sources: three parallel research
lanes over public repos/docs, 2026-11-13; every
version figure is a point-in-time read to be re-read
at intake.
